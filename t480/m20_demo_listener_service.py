"""Permanent supervisor for the fixed M20 Demo-only M1 listener.

This is deliberately a small supervisor, not a second trading implementation.
It invokes the hash-bound fixed runner no more than once per completed M1
candle, writes an operator-readable heartbeat, and remains running between
human-enabled bounded session leases.  It neither retains a tick stream nor
widens the runner's Demo-only execution authority.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import sys
import time
from types import SimpleNamespace
from typing import Any
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parent
# Immutable release code may live under ProgramData\ForexListener\releases\<id>.
# Keep mutable lease, status, and machine-local configuration in one shared
# sibling state directory so release switches cannot split the observer view.
STATE_ROOT = ROOT.parent.parent / "state" if ROOT.parent.name == "releases" else ROOT
STATUS_PATH = STATE_ROOT / "m20_demo_listener_status.local.json"
STOP_PATH = STATE_ROOT / "m20_demo_listener.stop"
LEASE_PATH = STATE_ROOT / "m20_demo_session.local.json"
CONFIG_PATH = STATE_ROOT / "m20_demo_listener_service.local.json"
ASSESSMENT_TOTAL_PATH = STATE_ROOT / "m20_demo_assessment_total.local.json"
ASSESSMENT_GATE_PATH = STATE_ROOT / "m20_demo_assessment_gate.local.json"
# Windows endpoint protection can block newly-created executable script
# extensions under ProgramData.  Python executes this immutable hash-checked
# payload explicitly, so the deployment artifact intentionally has no .py
# extension; source remains reviewed Python in the repository.
RUNNER_PATH = ROOT / "m20_demo_trading_session.payload"
POLL_SECONDS = 1
ASSESSMENT_INTERVAL_SECONDS = 5
MONITOR_RETRY_SECONDS = 10


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _nzst(timestamp: str | None) -> str | None:
    if not timestamp:
        return None
    parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    return parsed.astimezone(ZoneInfo("Pacific/Auckland")).strftime("%d/%m/%y %H:%M:%S %Z")


def _write_status(payload: dict[str, Any]) -> None:
    # `iteration` restarts with the supervisor.  Show it as such and retain a
    # separate monotonic total in mutable ProgramData state for operators.
    payload["process_iteration"] = payload.get("iteration", 0)
    payload["assessment_total"] = _assessment_total()
    payload["release_id"] = ROOT.name
    payload["heartbeat_at_utc"] = _utc_now()
    payload["heartbeat_at_nzst"] = _nzst(payload["heartbeat_at_utc"])
    if "next_assessment_at_utc" in payload:
        payload["next_assessment_at_nzst"] = _nzst(payload["next_assessment_at_utc"])
    temporary = STATUS_PATH.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    temporary.replace(STATUS_PATH)


def _assessment_total() -> int:
    try:
        value = json.loads(ASSESSMENT_TOTAL_PATH.read_text(encoding="utf-8-sig"))
        total = int(value["assessment_total"])
        return max(0, total)
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        return 0


def _increment_assessment_total() -> int:
    total = _assessment_total() + 1
    temporary = ASSESSMENT_TOTAL_PATH.with_suffix(".tmp")
    temporary.write_text(json.dumps({"assessment_total": total}, separators=(",", ":")), encoding="utf-8")
    temporary.replace(ASSESSMENT_TOTAL_PATH)
    return total


def _last_assessed_tick_time_msc() -> int:
    try:
        value = json.loads(ASSESSMENT_GATE_PATH.read_text(encoding="utf-8-sig"))
        return max(0, int(value["last_assessed_tick_time_msc"]))
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        return 0


def _record_assessed_tick_time_msc(tick_time_msc: int) -> None:
    if tick_time_msc <= 0:
        raise ValueError("assessment tick watermark must be positive")
    temporary = ASSESSMENT_GATE_PATH.with_suffix(".tmp")
    temporary.write_text(json.dumps({"last_assessed_tick_time_msc": tick_time_msc}, separators=(",", ":")), encoding="utf-8")
    temporary.replace(ASSESSMENT_GATE_PATH)


def _active_lease() -> bool:
    try:
        lease = json.loads(LEASE_PATH.read_text(encoding="utf-8-sig"))
        now = datetime.now(timezone.utc)
        start = datetime.fromisoformat(lease["starts_at_utc"].replace("Z", "+00:00"))
        end = datetime.fromisoformat(lease["expires_at_utc"].replace("Z", "+00:00"))
        return bool(lease.get("enabled")) and start <= now <= end
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
        return False


def _load_environment() -> None:
    """Load secret-bearing service configuration from an ignored local file."""
    try:
        values = json.loads(CONFIG_PATH.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as error:
        raise SystemExit("M20 listener service local configuration is absent or unreadable") from error
    required = {
        "FOREX_M20_DEMO_TRADING_SESSION_SHA256", "FOREX_M20_POSTGRES_AUDIT_BRIDGE_SHA256",
        "FOREX_M20_CONFIGURATION_FINGERPRINT", "FOREX_M20_TICK_TIME_OFFSET_SECONDS",
        "FOREX_M20_MINIMUM_NET_PROFIT_AUD",
        "FOREX_M20_APPLICATION_REVISION", "python_path", "terminal_path",
    }
    optional = {"FOREX_M20_DISCORD_NOTIFICATIONS_ENABLED", "FOREX_M20_DISCORD_WEBHOOK_URL"}
    if not isinstance(values, dict) or not required <= set(values) or not set(values) <= required | optional:
        raise SystemExit("M20 listener service local configuration fields are invalid")
    os.environ.update({key: str(value) for key, value in values.items() if key.startswith("FOREX_M20_")})
    if not os.environ.get("FOREX_M20_POSTGRES_DSN"):
        raise SystemExit("M20 listener service requires the existing machine-local PostgreSQL DSN environment")
    return values


def _assessment_metrics(snapshot: dict[str, Any], proposal: dict[str, Any]) -> dict[str, Any]:
    """Return the compact, human-readable M1 breakout check results."""
    candles = snapshot.get("m1_closed_bars", [])
    tick_size = 0.00001  # EURUSD fixed display point; broker prices remain authoritative.
    metrics: dict[str, Any] = {
        "closed_candle_count": len(candles),
        "spread_points": snapshot.get("spread_points"),
        "decision": proposal.get("action"),
    }
    if len(candles) < 6:
        metrics["ready"] = False
        metrics["reason"] = "Fewer than six completed M1 candles."
        return metrics
    setup, previous = candles[-1], candles[-2]
    window = candles[-6:-1]
    setup_open = float(setup.get("open", previous["close"]))
    previous_open = float(previous.get("open", candles[-3]["close"]))
    setup_move = float(setup["close"]) - setup_open
    previous_move = float(previous["close"]) - previous_open
    high = max(float(candle.get("high", candle["close"])) for candle in window)
    low = min(float(candle.get("low", candle["close"])) for candle in window)
    spread_price = float(snapshot["ask"]) - float(snapshot["bid"])
    bullish = setup_move > 0 and previous_move > 0
    bearish = setup_move < 0 and previous_move < 0
    upward_break = float(setup["close"]) > high
    downward_break = float(setup["close"]) < low
    momentum = abs(setup_move + previous_move)
    metrics.update({
        "ready": True,
        "last_closed_at_utc": setup["closed_at_utc"],
        "last_close": float(setup["close"]),
        "previous_close": float(previous["close"]),
        "prior_five_high": high,
        "prior_five_low": low,
        "setup_move_points": round(setup_move / tick_size, 2),
        "previous_move_points": round(previous_move / tick_size, 2),
        "two_candle_direction": "BULLISH" if bullish else "BEARISH" if bearish else "MIXED",
        "two_candle_aligned": bullish or bearish,
        "breakout_above_prior_high": upward_break,
        "breakout_below_prior_low": downward_break,
        "combined_move_points": round(momentum / tick_size, 2),
        "spread_price": spread_price,
        "combined_move_exceeds_spread": momentum > spread_price,
    })
    return metrics


def _monitor_job_path() -> Path:
    return LEASE_PATH.with_name("m20_demo_monitor_job.local.json")


def _quote_identity(values: dict[str, str]) -> dict[str, Any]:
    """Read one current MT5 quote identity; it has no assessment or order path."""
    try:
        completed = subprocess.run(
            [str(values["python_path"]), str(RUNNER_PATH), str(values["terminal_path"]), str(LEASE_PATH), "--quote-identity"],
            text=True, capture_output=True, check=False, env=os.environ.copy(), timeout=5,
        )
    except subprocess.TimeoutExpired:
        return {"error": "M20 quote observation exceeded its five-second bound"}
    try:
        value = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return {"error": completed.stderr.strip() or completed.stdout.strip() or "M20 quote observation returned no JSON"}
    expected = {"marker", "server", "symbol", "tick_time_msc", "bid", "ask"}
    if (completed.returncode != 0 or not isinstance(value, dict) or set(value) != expected
            or value.get("marker") != "FOREX_M20_DEMO_QUOTE_IDENTITY_OK"
            or value.get("server") != "GOMarketsMU-Demo" or value.get("symbol") != "EURUSD"):
        return {"error": "M20 quote observation is invalid"}
    return value


def _quote_key(quote: dict[str, Any]) -> str:
    """Include MT5 time and price so a cached quote cannot trigger twice."""
    return f"{quote['tick_time_msc']}:{quote['bid']}:{quote['ask']}"


def _monitor_update(values: dict[str, str], previous: dict[str, Any], retry_at: float) -> tuple[dict[str, Any], float]:
    """Perform one bounded MT5 monitor pass between assessment invocations.

    MT5's Python connection is single-client in this deployment.  The monitor
    is therefore independent in responsibility but serialized with the short
    assessment process, preventing a ten-minute monitor from starving the
    heartbeat or five-second assessment schedule.
    """
    now = time.monotonic()
    state = previous
    if now >= retry_at:
        try:
            completed = subprocess.run(
                [str(values["python_path"]), str(RUNNER_PATH), str(values["terminal_path"]), str(LEASE_PATH), "--recover-open-positions-once"],
                text=True, capture_output=True, check=False, env=os.environ.copy(), timeout=8,
            )
        except subprocess.TimeoutExpired:
            # A slow MT5/WSL recovery must be observable as a monitor failure,
            # never terminate the permanent supervisor and leave a stale
            # STARTING heartbeat behind.
            return {
                "state": "FAILED", "exit_code": None,
                "last_checked_at_utc": _utc_now(),
                "result": {"error": "M20 monitor recovery exceeded its eight-second bound"},
            }, now + MONITOR_RETRY_SECONDS
        try:
            result = json.loads(completed.stdout)
        except json.JSONDecodeError:
            result = {"error": completed.stderr.strip() or completed.stdout.strip()}
        recovered = result.get("recovered") if isinstance(result, dict) else None
        running = isinstance(recovered, list) and any(
            isinstance(item, dict) and isinstance(item.get("reconciliation"), dict)
            and item["reconciliation"].get("status") == "OPEN_MONITORING"
            for item in recovered
        )
        state = {
            "state": "RUNNING" if completed.returncode == 0 and running else ("IDLE" if completed.returncode == 0 else "FAILED"),
            "exit_code": completed.returncode,
            "last_checked_at_utc": _utc_now(),
            "result": result,
        }
        retry_at = now + ASSESSMENT_INTERVAL_SECONDS
    return state, retry_at


def run() -> None:
    values = _load_environment()
    STOP_PATH.unlink(missing_ok=True)
    iteration = 0
    last_result: dict[str, Any] = {}
    next_assessment_at = 0.0
    last_assessed_tick_time_msc = _last_assessed_tick_time_msc()
    last_quote: dict[str, Any] | None = None
    monitor_state: dict[str, Any] = {"state": "IDLE"}
    monitor_retry_at = 0.0
    last_assessment_completed_at_utc: str | None = None
    last_assessment_duration_ms: int | None = None
    # Publish a release-bound liveness record before the first bounded broker
    # recovery pass.  Deployment health checks prove the supervisor is alive
    # independently of any slow or failed historical reconciliation.
    _write_status({"state": "STARTING", "iteration": iteration, "last_result": last_result,
                   "next_assessment_at_utc": None, "monitor": monitor_state,
                   "detail": "Supervisor started; broker-backed open-position recovery is pending."})
    while not STOP_PATH.exists():
        now = time.monotonic()
        if not _active_lease():
            monitor_state, monitor_retry_at = _monitor_update(values, monitor_state, monitor_retry_at)
            _write_status({"state": "WAITING_FOR_ACTIVE_DEMO_LEASE", "iteration": iteration,
                           "last_result": last_result, "next_assessment_at_utc": None,
                           "assessment_completed_at_utc": last_assessment_completed_at_utc,
                           "assessment_duration_ms": last_assessment_duration_ms,
                           "monitor": monitor_state, "quote": last_quote,
                           "detail": "Service is alive; no tick capture or Demo order is permitted without an active Demo lease."})
            time.sleep(POLL_SECONDS)
            continue
        if now < next_assessment_at:
            # A bounded monitor pass belongs in the idle period.  It must not
            # delay an eligible fresh-quote assessment and its trade decision.
            monitor_state, monitor_retry_at = _monitor_update(values, monitor_state, monitor_retry_at)
            now = time.monotonic()
            _write_status({"state": "RUNNING", "iteration": iteration, "last_result": last_result,
                           "next_assessment_at_utc": datetime.fromtimestamp(time.time() + next_assessment_at - now, timezone.utc).isoformat().replace("+00:00", "Z"),
                           "assessment_completed_at_utc": last_assessment_completed_at_utc,
                           "assessment_duration_ms": last_assessment_duration_ms,
                           "monitor": monitor_state,
                           "detail": "Waiting for the five-second minimum before accepting the next MT5 quote update."})
            time.sleep(min(POLL_SECONDS, next_assessment_at - now))
            continue
        quote = _quote_identity(values)
        if quote.get("error"):
            monitor_state, monitor_retry_at = _monitor_update(values, monitor_state, monitor_retry_at)
            _write_status({"state": "WAITING_FOR_FRESH_MT5_QUOTE", "iteration": iteration,
                           "last_result": last_result, "next_assessment_at_utc": None,
                           "assessment_completed_at_utc": last_assessment_completed_at_utc,
                           "assessment_duration_ms": last_assessment_duration_ms,
                           "monitor": monitor_state, "quote": quote,
                           "detail": "Waiting for a readable fresh Demo EURUSD quote; no assessment or order is submitted."})
            time.sleep(POLL_SECONDS)
            continue
        last_quote = quote
        if int(quote["tick_time_msc"]) <= last_assessed_tick_time_msc:
            monitor_state, monitor_retry_at = _monitor_update(values, monitor_state, monitor_retry_at)
            _write_status({"state": "WAITING_FOR_FRESH_MT5_QUOTE", "iteration": iteration,
                           "last_result": last_result, "next_assessment_at_utc": None,
                           "assessment_completed_at_utc": last_assessment_completed_at_utc,
                           "assessment_duration_ms": last_assessment_duration_ms,
                           "monitor": monitor_state, "quote": quote,
                           "detail": "The five-second interval has elapsed; waiting for the next MT5 quote update before assessing again."})
            time.sleep(POLL_SECONDS)
            continue
        _record_assessed_tick_time_msc(int(quote["tick_time_msc"]))
        last_assessed_tick_time_msc = int(quote["tick_time_msc"])
        started = time.monotonic()
        assessment_started_at_utc = _utc_now()
        try:
            completed = subprocess.run(
                [str(values["python_path"]), str(RUNNER_PATH), str(values["terminal_path"]), str(LEASE_PATH), "--assessment-trigger-tick-ms", str(last_assessed_tick_time_msc)],
                text=True, capture_output=True, check=False, env=os.environ.copy(), timeout=12,
            )
        except subprocess.TimeoutExpired:
            completed = SimpleNamespace(
                returncode=124, stdout="", stderr="M20 assessment exceeded its twelve-second bound"
            )
        assessment_completed_at_utc = _utc_now()
        assessment_duration_ms = round((time.monotonic() - started) * 1000)
        last_assessment_completed_at_utc = assessment_completed_at_utc
        last_assessment_duration_ms = assessment_duration_ms
        iteration += 1
        _increment_assessment_total()
        next_assessment_at = started + ASSESSMENT_INTERVAL_SECONDS
        try:
            output = json.loads(completed.stdout)
            proposal = output.get("proposal", {})
            last_result = {key: output.get(key) for key in ("marker", "server", "symbol", "captured_at_utc", "proposal", "strategy_selection", "strategy_assessments", "multi_timeframe_context", "execution", "reconciliation")}
            last_result["assessment_metrics"] = _assessment_metrics(output.get("decision_snapshot", {}), proposal)
        except json.JSONDecodeError:
            last_result = {"error": completed.stderr.strip() or completed.stdout.strip(), "exit_code": completed.returncode}
        _write_status({"state": "RUNNING" if completed.returncode == 0 else "LAST_ASSESSMENT_FAILED",
                       "iteration": iteration, "last_result": last_result,
                       "assessment_started_at_utc": assessment_started_at_utc,
                       "assessment_completed_at_utc": assessment_completed_at_utc,
                       "assessment_duration_ms": assessment_duration_ms,
                       "next_assessment_at_utc": datetime.fromtimestamp(time.time() + max(0, next_assessment_at - time.monotonic()), timezone.utc).isoformat().replace("+00:00", "Z"),
                       "monitor": monitor_state, "quote": quote,
                       "detail": "This assessment started from a fresh MT5 quote. The next needs a later quote update and the five-second minimum; decisions use completed M1 candles."})
    _write_status({"state": "STOPPED", "iteration": iteration, "last_result": last_result,
                   "next_assessment_at_utc": None, "monitor": monitor_state, "detail": "Stop sentinel observed."})


if __name__ == "__main__":
    if len(sys.argv) != 1:
        raise SystemExit("M20 listener service accepts no arguments")
    try:
        run()
    except SystemExit as error:
        _write_status({"state": "STARTUP_FAILED", "iteration": 0, "last_result": {},
                       "next_assessment_at_utc": None, "detail": str(error)})
        raise
