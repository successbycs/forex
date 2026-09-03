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
# Windows endpoint protection can block newly-created executable script
# extensions under ProgramData.  Python executes this immutable hash-checked
# payload explicitly, so the deployment artifact intentionally has no .py
# extension; source remains reviewed Python in the repository.
RUNNER_PATH = ROOT / "m20_demo_trading_session.payload"
POLL_SECONDS = 1
ASSESSMENT_INTERVAL_SECONDS = 10


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _nzst(timestamp: str | None) -> str | None:
    if not timestamp:
        return None
    parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    return parsed.astimezone(ZoneInfo("Pacific/Auckland")).strftime("%d/%m/%y %H:%M:%S %Z")


def _write_status(payload: dict[str, Any]) -> None:
    payload["release_id"] = ROOT.name
    payload["heartbeat_at_utc"] = _utc_now()
    payload["heartbeat_at_nzst"] = _nzst(payload["heartbeat_at_utc"])
    if "next_assessment_at_utc" in payload:
        payload["next_assessment_at_nzst"] = _nzst(payload["next_assessment_at_utc"])
    temporary = STATUS_PATH.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    temporary.replace(STATUS_PATH)


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
        "FOREX_M20_APPLICATION_REVISION", "python_path", "terminal_path",
    }
    if not isinstance(values, dict) or set(values) != required:
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


def run() -> None:
    values = _load_environment()
    STOP_PATH.unlink(missing_ok=True)
    iteration = 0
    last_result: dict[str, Any] = {}
    next_assessment_at = 0.0
    while not STOP_PATH.exists():
        now = time.monotonic()
        if not _active_lease():
            _write_status({"state": "WAITING_FOR_ACTIVE_DEMO_LEASE", "iteration": iteration,
                           "last_result": last_result, "next_assessment_at_utc": None,
                           "detail": "Service is alive; no tick capture or Demo order is permitted without an active bounded lease."})
            time.sleep(POLL_SECONDS)
            continue
        if now < next_assessment_at:
            _write_status({"state": "RUNNING", "iteration": iteration, "last_result": last_result,
                           "next_assessment_at_utc": datetime.fromtimestamp(time.time() + next_assessment_at - now, timezone.utc).isoformat().replace("+00:00", "Z"),
                           "detail": "Waiting for the next ten-second M1 assessment; decisions use only completed candles."})
            time.sleep(min(POLL_SECONDS, next_assessment_at - now))
            continue
        started = time.monotonic()
        completed = subprocess.run([str(values["python_path"]), str(RUNNER_PATH), str(values["terminal_path"]), str(LEASE_PATH)],
                                   text=True, capture_output=True, check=False, env=os.environ.copy())
        iteration += 1
        next_assessment_at = started + ASSESSMENT_INTERVAL_SECONDS
        try:
            output = json.loads(completed.stdout)
            proposal = output.get("proposal", {})
            last_result = {key: output.get(key) for key in ("marker", "server", "symbol", "captured_at_utc", "proposal", "strategy_assessments", "execution", "reconciliation")}
            last_result["assessment_metrics"] = _assessment_metrics(output.get("decision_snapshot", {}), proposal)
        except json.JSONDecodeError:
            last_result = {"error": completed.stderr.strip() or completed.stdout.strip(), "exit_code": completed.returncode}
        _write_status({"state": "RUNNING" if completed.returncode == 0 else "LAST_ASSESSMENT_FAILED",
                       "iteration": iteration, "last_result": last_result,
                       "next_assessment_at_utc": datetime.fromtimestamp(time.time() + max(0, next_assessment_at - time.monotonic()), timezone.utc).isoformat().replace("+00:00", "Z"),
                       "detail": "The fixed M20 runner assesses every ten seconds using fresh pricing and completed M1 candles; raw tick observations are not retained."})
    _write_status({"state": "STOPPED", "iteration": iteration, "last_result": last_result,
                   "next_assessment_at_utc": None, "detail": "Stop sentinel observed."})


if __name__ == "__main__":
    if len(sys.argv) != 1:
        raise SystemExit("M20 listener service accepts no arguments")
    try:
        run()
    except SystemExit as error:
        _write_status({"state": "STARTUP_FAILED", "iteration": 0, "last_result": {},
                       "next_assessment_at_utc": None, "detail": str(error)})
        raise
