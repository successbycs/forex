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
import hashlib
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import sys
import time
import traceback
from types import SimpleNamespace
from typing import Any
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parent
# Immutable release code may live under ProgramData\ForexListener\releases\<id>.
# Keep mutable lease, status, and machine-local configuration in one shared
# sibling state directory so release switches cannot split the observer view.
STATE_ROOT = ROOT.parent.parent / "state" if ROOT.parent.name == "releases" else ROOT
STATUS_PATH = STATE_ROOT / "m20_demo_listener_status.local.json"
FAILURE_PATH = STATE_ROOT / "m20_demo_listener_failures.local.jsonl"
STOP_PATH = STATE_ROOT / "m20_demo_listener.stop"
LEASE_PATH = STATE_ROOT / "m20_demo_session.local.json"
CONFIG_PATH = STATE_ROOT / "m20_demo_listener_service.local.json"
ASSESSMENT_TOTAL_PATH = STATE_ROOT / "m20_demo_assessment_total.local.json"
ASSESSMENT_GATE_PATH = STATE_ROOT / "m20_demo_assessment_gate.local.json"
# A replace-only latest complete assessment is deliberately separate from the
# redacted heartbeat.  It gives a fixed read-only exporter one bound
# snapshot/proposal pair without turning the five-second listener loop into an
# unbounded local evidence archive.  Long-term retention belongs on the
# orchestrator once an exporter is deployed.
LATEST_ASSESSMENT_PATH = STATE_ROOT / "m20_demo_latest_assessment.local.json"
# Immutable source records remove replace-only loss at the listener boundary.
# Draining them is intentionally separate: downstream export failure must not
# delete source evidence or delay broker protection.
ASSESSMENT_SPOOL_PATH = STATE_ROOT / "m20_demo_assessment_spool" / ROOT.name
# This mutable record is set only by fixed adapter actions during coordinated
# maintenance. A malformed record fails closed: monitoring remains available
# for an existing position but entry processing stays disabled.
MAINTENANCE_HOLD_PATH = STATE_ROOT / "m20_demo_maintenance_hold.local.json"
# One bounded Wave 1 drill: the first naturally accepted protected Demo position
# restarts the listener through its Scheduled Task, then startup recovery must
# reclaim the same durable position. The terminal record prevents any repeat.
PROTECTED_RESTART_DRILL_PATH = STATE_ROOT / "m20_demo_protected_restart_drill.local.json"
CONTINUITY_PROTOCOL_PATH = STATE_ROOT / "m20_demo_continuity_protocol.local.json"
CONTINUITY_PROTOCOL_LOG_PATH = STATE_ROOT / "m20_demo_continuity_protocol.local.jsonl"
# Windows endpoint protection can block newly-created executable script
# extensions under ProgramData.  Python executes this immutable hash-checked
# payload explicitly, so the deployment artifact intentionally has no .py
# extension; source remains reviewed Python in the repository.
RUNNER_PATH = ROOT / "m20_demo_trading_session.payload"
POLL_SECONDS = 1
ASSESSMENT_INTERVAL_SECONDS = 5
MONITOR_RETRY_SECONDS = 10
RESTART_DRILL_OBSERVATION = "NOT_CHECKED"
CONTINUITY_WINDOW_SECONDS = 30 * 60
CONTINUITY_SAMPLE_SECONDS = 5
CONTINUITY_STATUS_READ_ATTEMPTS = 3
CONTINUITY_MAX_HEARTBEAT_AGE_SECONDS = 30
CONTINUITY_RECOVERY_DEADLINE_SECONDS = 5 * 60
CONTINUITY_TERMINAL_STATES = {"PASS", "FAIL", "INCONCLUSIVE"}


class ProtectedRestartDrillRequested(RuntimeError):
    """Intentional one-shot task exit after durable broker protection exists."""


def _restart_drill_state() -> dict[str, Any] | None:
    """Load or atomically arm the optional one-shot protected restart drill.

    The drill can never displace the normal protection/recovery path.  Its
    corrupt or unwritable local marker therefore disables only the drill; the
    marker is preserved for operator diagnosis and is never reset or rearmed.
    """
    global RESTART_DRILL_OBSERVATION
    if not PROTECTED_RESTART_DRILL_PATH.exists():
        state = {"schema_version": "forex.m20.protected-restart-drill.v1", "state": "ARMED"}
        temporary = PROTECTED_RESTART_DRILL_PATH.with_suffix(".tmp")
        try:
            temporary.write_text(json.dumps(state, sort_keys=True, separators=(",", ":")), encoding="utf-8")
            temporary.replace(PROTECTED_RESTART_DRILL_PATH)
        except OSError:
            RESTART_DRILL_OBSERVATION = "UNWRITABLE"
            return None
        RESTART_DRILL_OBSERVATION = "VALID"
        return state
    try:
        state = json.loads(PROTECTED_RESTART_DRILL_PATH.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        RESTART_DRILL_OBSERVATION = "UNREADABLE"
        return None
    if (not isinstance(state, dict)
            or state.get("schema_version") != "forex.m20.protected-restart-drill.v1"
            or state.get("state") not in {"ARMED", "RESTART_REQUESTED", "RESTARTING", "RECOVERED", "CLOSED_BEFORE_RECOVERY", "RESTART_FAILED"}):
        RESTART_DRILL_OBSERVATION = "INVALID"
        return None
    if state["state"] != "ARMED" and (not isinstance(state.get("attempt_id"), str) or not state["attempt_id"]
                                        or not isinstance(state.get("position_ticket"), int) or isinstance(state["position_ticket"], bool) or state["position_ticket"] <= 0):
        RESTART_DRILL_OBSERVATION = "INVALID"
        return None
    RESTART_DRILL_OBSERVATION = "VALID"
    return state


def _write_restart_drill_state(state: dict[str, Any]) -> bool:
    global RESTART_DRILL_OBSERVATION
    temporary = PROTECTED_RESTART_DRILL_PATH.with_suffix(".tmp")
    try:
        temporary.write_text(json.dumps(state, sort_keys=True, separators=(",", ":")), encoding="utf-8")
        temporary.replace(PROTECTED_RESTART_DRILL_PATH)
    except OSError:
        RESTART_DRILL_OBSERVATION = "UNWRITABLE"
        return False
    RESTART_DRILL_OBSERVATION = "VALID"
    return True


def _restart_drill_status() -> dict[str, Any]:
    """Return a redacted drill incident suitable for the public heartbeat."""
    state = _restart_drill_state()
    if state is None:
        return {"observation": RESTART_DRILL_OBSERVATION, "state": None}
    state_name = state["state"]
    observation = "VALID" if state_name in {"ARMED", "RECOVERED", "CLOSED_BEFORE_RECOVERY"} else (
        "LEGACY_UNVERIFIED" if state_name == "RESTART_REQUESTED" and not state.get("restart_parent_pid") else
        ("PENDING" if state_name in {"RESTART_REQUESTED", "RESTARTING"} else "FAULTED")
    )
    return {
        "observation": observation, "state": state_name,
        "attempt_id": state.get("attempt_id"), "position_ticket": state.get("position_ticket"),
        "requested_at_utc": state.get("requested_at_utc"),
        "restart_parent_pid": state.get("restart_parent_pid"),
        "restart_started_at_utc": state.get("restart_started_at_utc"),
        "recovery_worker_pid": state.get("recovery_worker_pid"),
        "failure_reason": state.get("failure_reason"),
        "completed_at_utc": state.get("recovered_at_utc", state.get("observed_at_utc")),
    }


def _request_protected_restart(output: dict[str, Any]) -> None:
    """Request exactly one restart after a durable broker-protected acceptance."""
    state = _restart_drill_state()
    execution = output.get("execution")
    reconciliation = output.get("reconciliation")
    if not isinstance(state, dict) or state.get("state") != "ARMED" or not isinstance(execution, dict) or not isinstance(reconciliation, dict):
        return
    if execution.get("status") != "ACCEPTED" or execution.get("monitor_job_scheduled") is not True or reconciliation.get("status") != "OPEN_MONITORING":
        return
    ticket = reconciliation.get("position_ticket")
    attempt_id = execution.get("attempt_id")
    if not isinstance(ticket, int) or ticket <= 0 or not isinstance(attempt_id, str):
        return
    if not _write_restart_drill_state({"schema_version": "forex.m20.protected-restart-drill.v1", "state": "RESTART_REQUESTED", "attempt_id": attempt_id, "position_ticket": ticket, "requested_at_utc": _utc_now()}):
        return
    raise ProtectedRestartDrillRequested("M20 protected restart drill requested")


def _record_protected_restart_recovery(monitor: dict[str, Any]) -> None:
    """Close the one-shot drill only after startup sees the bound durable state."""
    state = _restart_drill_state()
    if not isinstance(state, dict) or state.get("state") not in {"RESTART_REQUESTED", "RESTARTING"}:
        return
    recovered = monitor.get("result", {}).get("recovered") if isinstance(monitor.get("result"), dict) else None
    if not isinstance(recovered, list):
        return
    ticket = state["position_ticket"]
    attempt_id = state["attempt_id"]
    for item in recovered:
        if not isinstance(item, dict) or item.get("position_ticket") != ticket or item.get("attempt_id") != attempt_id:
            continue
        reconciliation = item.get("reconciliation")
        status = reconciliation.get("status") if isinstance(reconciliation, dict) else None
        if status == "OPEN_MONITORING":
            _write_restart_drill_state({**state, "state": "RECOVERED", "recovery_worker_pid": os.getpid(), "recovered_at_utc": _utc_now()})
        elif status == "MATCHED":
            _write_restart_drill_state({**state, "state": "CLOSED_BEFORE_RECOVERY", "recovery_worker_pid": os.getpid(), "observed_at_utc": _utc_now()})
        return


def _latch_protected_restart_failure(reason: str, exit_code: int | None = None) -> None:
    """Retain a redacted drill fault and leave normal monitoring available."""
    state = _restart_drill_state()
    if not isinstance(state, dict) or state.get("state") == "ARMED":
        return
    failed = {**state, "state": "RESTART_FAILED", "failure_reason": reason,
              "failure_at_utc": _utc_now(), "restart_parent_pid": os.getpid()}
    if exit_code is not None:
        failed["restart_child_exit_code"] = exit_code
    _write_restart_drill_state(failed)


def _run_protected_restart_child() -> bool:
    """Run one fixed child worker while this task-owned parent waits inertly."""
    state = _restart_drill_state()
    if not isinstance(state, dict) or state.get("state") != "RESTART_REQUESTED":
        return False
    restarting = {**state, "state": "RESTARTING", "restart_parent_pid": os.getpid(),
                  "restart_started_at_utc": _utc_now()}
    if not _write_restart_drill_state(restarting):
        return False
    try:
        child = subprocess.Popen(
            [str(Path(sys.executable).resolve()), str(Path(__file__).resolve())], close_fds=True,
        )
    except OSError:
        _latch_protected_restart_failure("CHILD_SPAWN_FAILED")
        return False
    while True:
        try:
            exit_code = child.wait(timeout=1)
            break
        except subprocess.TimeoutExpired:
            # Parent remains inert and task-owned while the child is alive.
            continue
        except OSError:
            # Do not resume a second monitor loop until a later wait proves
            # that this child is gone. ScheduledTask stop kills this process
            # tree if an operator needs to interrupt the retained parent.
            _latch_protected_restart_failure("CHILD_WAIT_FAILED")
            time.sleep(POLL_SECONDS)
    if exit_code != 0:
        _latch_protected_restart_failure("CHILD_EXIT_NONZERO", exit_code)
        return False
    return True


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
    for attempt in range(3):
        try:
            temporary.replace(STATUS_PATH)
            break
        except PermissionError:
            # Windows readers may briefly deny replacement. Bound the retry;
            # a persistent storage failure still terminates with a crash record.
            if attempt == 2:
                raise
            time.sleep(.05)


def _retained_assessment(output: dict[str, Any], *, assessment_started_at_utc: str,
                         assessment_completed_at_utc: str, assessment_sequence: int) -> dict[str, Any] | None:
    """Build the one non-secret record shared by latest and immutable views."""
    required = {"marker", "schema_version", "server", "symbol", "captured_at_utc",
                "configuration_fingerprint", "decision_snapshot", "proposal"}
    if (not isinstance(output, dict) or not required <= set(output)
            or isinstance(assessment_sequence, bool) or not isinstance(assessment_sequence, int)
            or assessment_sequence <= 0):
        return None
    if not isinstance(output["decision_snapshot"], dict) or not isinstance(output["proposal"], dict):
        return None
    return {
        "schema_version": "forex.m20.latest-assessment.v1",
        "listener_release_id": ROOT.name,
        "assessment_sequence": assessment_sequence,
        "assessment_started_at_utc": assessment_started_at_utc,
        "assessment_completed_at_utc": assessment_completed_at_utc,
        "assessment": {key: output.get(key) for key in (
            "marker", "schema_version", "operation", "server", "symbol", "captured_at_utc",
            "configuration_fingerprint", "tick_timestamp_offset_seconds", "decision_snapshot", "proposal",
        )},
    }


def _write_latest_assessment(output: dict[str, Any], *, assessment_started_at_utc: str,
                             assessment_completed_at_utc: str, assessment_sequence: int) -> str:
    """Atomically retain one full non-secret assessment for fixed export.

    Failure is diagnostic only: the existing listener and protection path must
    continue.  This is replacement state, not a historical evidence archive.
    """
    retained = _retained_assessment(output, assessment_started_at_utc=assessment_started_at_utc,
                                    assessment_completed_at_utc=assessment_completed_at_utc,
                                    assessment_sequence=assessment_sequence)
    if retained is None:
        return "NOT_WRITTEN_UNSUPPORTED_RUNNER_OUTPUT"
    try:
        temporary = LATEST_ASSESSMENT_PATH.with_suffix(".tmp")
        temporary.write_text(json.dumps(retained, sort_keys=True, separators=(",", ":")), encoding="utf-8")
        temporary.replace(LATEST_ASSESSMENT_PATH)
    except (OSError, TypeError, ValueError):
        return "NOT_WRITTEN_STORAGE_FAILURE"
    return "RETAINED_LATEST"


def _write_assessment_spool(output: dict[str, Any], *, assessment_started_at_utc: str,
                            assessment_completed_at_utc: str, assessment_sequence: int) -> str:
    """Publish one immutable source assessment after runner completion.

    Storage trouble is only a diagnostic: runner execution, broker protection
    and reconciliation have already completed before this postflight write.
    """
    retained = _retained_assessment(output, assessment_started_at_utc=assessment_started_at_utc,
                                    assessment_completed_at_utc=assessment_completed_at_utc,
                                    assessment_sequence=assessment_sequence)
    if retained is None:
        return "NOT_SPOOLED_UNSUPPORTED_RUNNER_OUTPUT"
    try:
        ASSESSMENT_SPOOL_PATH.mkdir(mode=0o700, parents=True, exist_ok=True)
        if not ASSESSMENT_SPOOL_PATH.is_dir() or ASSESSMENT_SPOOL_PATH.is_symlink():
            return "NOT_SPOOLED_STORAGE_FAILURE"
        target = ASSESSMENT_SPOOL_PATH / f"{assessment_sequence:020d}.json"
        raw = json.dumps(retained, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
        if target.exists() or target.is_symlink():
            if target.is_symlink() or not target.is_file() or target.read_bytes() != raw:
                return "NOT_SPOOLED_CONFLICT"
            return "SPOOL_ALREADY_RETAINED"
        staging = target.with_suffix(".pending")
        if staging.exists() or staging.is_symlink():
            return "NOT_SPOOLED_STORAGE_FAILURE"
        with staging.open("xb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(staging, target)
        except FileExistsError:
            if target.is_symlink() or not target.is_file() or target.read_bytes() != raw:
                return "NOT_SPOOLED_CONFLICT"
        finally:
            if staging.exists() and not staging.is_symlink():
                staging.unlink()
        # ``fsync`` on a directory is a useful durability barrier on POSIX.
        # Windows does not expose a directory handle that ``fsync`` accepts;
        # attempting it there turned a successfully published immutable NTFS
        # receipt into ``NOT_SPOOLED_STORAGE_FAILURE`` on every assessment.
        # The file itself is flushed before its no-overwrite link publication,
        # so skip only the unsupported directory barrier on Windows.
        if os.name != "nt":
            directory = os.open(ASSESSMENT_SPOOL_PATH, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
    except (OSError, TypeError, ValueError):
        return "NOT_SPOOLED_STORAGE_FAILURE"
    return "SPOOLED_IMMUTABLE"


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


def _maintenance_hold() -> dict[str, str | bool]:
    """Return a redacted, fail-closed maintenance hold observation."""
    if not MAINTENANCE_HOLD_PATH.exists():
        return {"active": False, "reason": "NONE"}
    try:
        hold = json.loads(MAINTENANCE_HOLD_PATH.read_text(encoding="utf-8-sig"))
        if hold.get("schema_version") != "forex.m20.maintenance-hold.v1" or hold.get("enabled") is not True:
            raise ValueError("invalid maintenance hold")
        reason = hold.get("reason")
        if not isinstance(reason, str) or not reason:
            raise ValueError("maintenance hold reason is absent")
        return {"active": True, "reason": reason}
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        return {"active": True, "reason": "MAINTENANCE_HOLD_UNREADABLE"}


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
        "FOREX_M20_PERSISTENT_RISK_POLICY",
        "FOREX_M20_FINANCING_POLICY",
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


def _idle_wait_seconds(next_assessment_at: float, now: float | None = None) -> float:
    """Return a safe bounded wait after a monitor pass may have used the interval."""
    remaining = next_assessment_at - (time.monotonic() if now is None else now)
    return max(0.0, min(POLL_SECONDS, remaining))


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
        valid_terminal_statuses = {"OPEN_MONITORING", "MATCHED"}
        recovery_error: str | None = None
        running = False
        if completed.returncode != 0:
            recovery_error = "M20 durable-position recovery process failed"
        elif not isinstance(result, dict) or result.get("marker") != "FOREX_M20_DEMO_MONITOR_OPERATION_OK":
            recovery_error = "M20 durable-position recovery returned an invalid marker"
        elif not isinstance(recovered, list):
            recovery_error = "M20 durable-position recovery returned an invalid result list"
        else:
            for item in recovered:
                if not isinstance(item, dict):
                    recovery_error = "M20 durable-position recovery returned a malformed item"
                    break
                if item.get("status") == "RECOVERY_FAILED":
                    recovery_error = "M20 durable-position recovery failed for a retained position"
                    break
                reconciliation = item.get("reconciliation")
                if not isinstance(reconciliation, dict) or reconciliation.get("status") not in valid_terminal_statuses:
                    recovery_error = "M20 durable-position recovery returned an unresolved position"
                    break
                running = running or reconciliation["status"] == "OPEN_MONITORING"
        state = {
            "state": "FAILED" if recovery_error else ("RUNNING" if running else "IDLE"),
            "exit_code": completed.returncode,
            "last_checked_at_utc": _utc_now(),
            "result": result,
        }
        if recovery_error:
            state["error"] = recovery_error
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
    monitor_initialized = False
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
        maintenance_hold = _maintenance_hold()
        if maintenance_hold["active"]:
            monitor_state, monitor_retry_at = _monitor_update(values, monitor_state, monitor_retry_at)
            _record_protected_restart_recovery(monitor_state)
            _write_status({"state": "MAINTENANCE_HOLD", "iteration": iteration,
                           "last_result": last_result, "next_assessment_at_utc": None,
                           "assessment_completed_at_utc": last_assessment_completed_at_utc,
                           "assessment_duration_ms": last_assessment_duration_ms,
                           "monitor": monitor_state, "quote": last_quote,
                           "maintenance_hold": maintenance_hold,
                           "detail": "Coordinated maintenance hold is active; open-position monitoring continues but no assessment or Demo order is permitted."})
            time.sleep(POLL_SECONDS)
            continue
        if not _active_lease():
            monitor_state, monitor_retry_at = _monitor_update(values, monitor_state, monitor_retry_at)
            _record_protected_restart_recovery(monitor_state)
            _write_status({"state": "WAITING_FOR_ACTIVE_DEMO_LEASE", "iteration": iteration,
                           "last_result": last_result, "next_assessment_at_utc": None,
                           "assessment_completed_at_utc": last_assessment_completed_at_utc,
                           "assessment_duration_ms": last_assessment_duration_ms,
                           "monitor": monitor_state, "quote": last_quote,
                           "detail": "Service is alive; no tick capture or Demo order is permitted without an active Demo lease."})
            time.sleep(POLL_SECONDS)
            continue
        # On startup a broker-side close can already be reflected in account
        # balance while its durable open-position record still awaits
        # reconciliation.  Reconcile first so that the risk guard does not
        # misclassify that realised trade P&L as an external cash flow.
        if not monitor_initialized or monitor_state.get("state") == "FAILED":
            monitor_state, monitor_retry_at = _monitor_update(values, monitor_state, monitor_retry_at)
            if monitor_state.get("state") == "FAILED":
                _write_status({"state": "MONITORING_UNAVAILABLE", "iteration": iteration,
                               "last_result": last_result, "next_assessment_at_utc": None,
                               "assessment_completed_at_utc": last_assessment_completed_at_utc,
                               "assessment_duration_ms": last_assessment_duration_ms,
                               "monitor": monitor_state, "quote": last_quote,
                               "detail": "Durable open-position reconciliation is unavailable; no assessment or order is submitted."})
                time.sleep(POLL_SECONDS)
                continue
            monitor_initialized = True
            _record_protected_restart_recovery(monitor_state)
        restart_drill = _restart_drill_status()
        if restart_drill["observation"] not in {"VALID", "LEGACY_UNVERIFIED"}:
            monitor_state, monitor_retry_at = _monitor_update(values, monitor_state, monitor_retry_at)
            _write_status({"state": "DRILL_UNAVAILABLE", "iteration": iteration,
                           "last_result": last_result, "next_assessment_at_utc": None,
                           "assessment_completed_at_utc": last_assessment_completed_at_utc,
                           "assessment_duration_ms": last_assessment_duration_ms,
                           "monitor": monitor_state, "quote": last_quote,
                           "protected_restart_drill": restart_drill,
                           "detail": "Protected-restart drill marker is unavailable; monitoring continues but no assessment or Demo order is permitted."})
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
                           "monitor": monitor_state, "protected_restart_drill": restart_drill,
                           "detail": "Waiting for the five-second minimum before accepting the next MT5 quote update."})
            # Monitoring is bounded but can still consume the remaining
            # assessment interval.  A negative sleep would terminate this
            # permanent supervisor and leave a stale heartbeat.
            time.sleep(_idle_wait_seconds(next_assessment_at, now))
            continue
        quote = _quote_identity(values)
        if quote.get("error"):
            monitor_state, monitor_retry_at = _monitor_update(values, monitor_state, monitor_retry_at)
            _write_status({"state": "WAITING_FOR_FRESH_MT5_QUOTE", "iteration": iteration,
                           "last_result": last_result, "next_assessment_at_utc": None,
                           "assessment_completed_at_utc": last_assessment_completed_at_utc,
                           "assessment_duration_ms": last_assessment_duration_ms,
                           "monitor": monitor_state, "quote": quote, "protected_restart_drill": restart_drill,
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
                           "monitor": monitor_state, "quote": quote, "protected_restart_drill": restart_drill,
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
        assessment_sequence = _increment_assessment_total()
        next_assessment_at = started + ASSESSMENT_INTERVAL_SECONDS
        try:
            output = json.loads(completed.stdout)
            proposal = output.get("proposal", {})
            last_result = {key: output.get(key) for key in ("marker", "server", "symbol", "captured_at_utc", "proposal", "strategy_selection", "strategy_assessments", "multi_timeframe_context", "execution", "reconciliation")}
            last_result["assessment_metrics"] = _assessment_metrics(output.get("decision_snapshot", {}), proposal)
            last_result["latest_assessment_retention"] = _write_latest_assessment(
                output, assessment_started_at_utc=assessment_started_at_utc,
                assessment_completed_at_utc=assessment_completed_at_utc,
                assessment_sequence=assessment_sequence,
            )
            last_result["assessment_spool_retention"] = _write_assessment_spool(
                output, assessment_started_at_utc=assessment_started_at_utc,
                assessment_completed_at_utc=assessment_completed_at_utc,
                assessment_sequence=assessment_sequence,
            )
            _request_protected_restart(output)
        except json.JSONDecodeError:
            last_result = {"error": completed.stderr.strip() or completed.stdout.strip(), "exit_code": completed.returncode}
        _write_status({"state": "RUNNING" if completed.returncode == 0 else "LAST_ASSESSMENT_FAILED",
                       "iteration": iteration, "last_result": last_result,
                       "assessment_started_at_utc": assessment_started_at_utc,
                       "assessment_completed_at_utc": assessment_completed_at_utc,
                       "assessment_duration_ms": assessment_duration_ms,
                       "next_assessment_at_utc": datetime.fromtimestamp(time.time() + max(0, next_assessment_at - time.monotonic()), timezone.utc).isoformat().replace("+00:00", "Z"),
                       "monitor": monitor_state, "quote": quote, "protected_restart_drill": restart_drill,
                       "detail": "This assessment started from a fresh MT5 quote. The next needs a later quote update and the five-second minimum; decisions use completed M1 candles."})
    _write_status({"state": "STOPPED", "iteration": iteration, "last_result": last_result,
                   "next_assessment_at_utc": None, "monitor": monitor_state, "detail": "Stop sentinel observed."})


def run_guarded() -> None:
    while True:
        try:
            run()
            return
        except ProtectedRestartDrillRequested:
            # ScheduledTask retry did not restart a deliberate normal exit.
            # This parent remains task-owned and inert while one fixed child
            # worker runs; a failure falls back to parent monitoring only.
            if _run_protected_restart_child():
                return
            continue
        except (Exception, SystemExit) as error:
            if isinstance(error, SystemExit) and error.code in (None, 0):
                raise
            # Never retain exception messages, source lines, locals or environment:
            # database/notification exceptions can contain credentials.
            failure = {"captured_at_utc": _utc_now(), "release_id": ROOT.name,
                       "exception_type": type(error).__name__,
                       "errno": getattr(error, "errno", None),
                       "winerror": getattr(error, "winerror", None),
                       "frames": [{"file": Path(frame.filename).name, "line": frame.lineno,
                                   "function": frame.name}
                                  for frame in traceback.extract_tb(error.__traceback__)[-6:]]}
            try:
                with FAILURE_PATH.open("a", encoding="utf-8") as stream:
                    stream.write(json.dumps(failure, sort_keys=True) + "\n")
            except OSError:
                pass  # Storage failure must not replace the original exception.
            try:
                _write_status({"state": "STARTUP_FAILED", "iteration": 0, "last_result": {},
                               "next_assessment_at_utc": None,
                               "detail": "Listener exited: " + type(error).__name__ + "; inspect retained failure frames."})
            except OSError:
                pass
            raise


def _load_continuity_protocol() -> dict[str, Any]:
    """Load the fixed T480-local protocol record without repairing it."""
    try:
        value = json.loads(CONTINUITY_PROTOCOL_PATH.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as error:
        raise SystemExit("M20 continuity protocol record is unavailable") from error
    required = {"schema_version", "run_id", "release_id", "started_at_utc", "state",
                "baseline", "samples", "incident_delivery"}
    if (not isinstance(value, dict) or set(value) != required
            or value.get("schema_version") != "forex.m20.continuity-protocol.v1"
            or value.get("state") != "ARMED" or not isinstance(value.get("run_id"), str)
            or not isinstance(value.get("baseline"), dict) or not isinstance(value.get("samples"), list)
            or not isinstance(value.get("incident_delivery"), dict)):
        raise SystemExit("M20 continuity protocol record is invalid")
    return value


def _archive_completed_continuity_protocol() -> None:
    """Retain a terminal protocol record before a distinct later run is armed.

    A flat held account may be tested more than once.  Replacing a record would
    destroy evidence, while refusing forever would make the fixed protocol
    unusable after one inconclusive run.  Only a complete terminal record is
    moved to a run-id-addressed immutable filename; an armed record blocks a
    second handoff.
    """
    if not CONTINUITY_PROTOCOL_PATH.exists():
        return
    try:
        record = json.loads(CONTINUITY_PROTOCOL_PATH.read_text(encoding="utf-8-sig"))
        run_id = record.get("run_id")
        state = record.get("state")
        if (not isinstance(run_id, str) or len(run_id) != 24 or
                any(char not in "0123456789abcdef" for char in run_id) or
                state not in CONTINUITY_TERMINAL_STATES):
            raise ValueError("record is not terminal")
        digest = hashlib.sha256(CONTINUITY_PROTOCOL_PATH.read_bytes()).hexdigest()[:16]
        archived = CONTINUITY_PROTOCOL_PATH.with_name(
            f"m20_demo_continuity_protocol.{run_id}.{digest}.json"
        )
        if archived.exists():
            raise ValueError("terminal record archive already exists")
        CONTINUITY_PROTOCOL_PATH.replace(archived)
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise SystemExit("M20 continuity protocol has an unfinished or invalid retained record") from error


def _write_continuity_protocol(value: dict[str, Any]) -> None:
    temporary = CONTINUITY_PROTOCOL_PATH.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    temporary.replace(CONTINUITY_PROTOCOL_PATH)


def _append_continuity_event(value: dict[str, Any]) -> None:
    """Append redacted local evidence; failure never changes listener safety."""
    try:
        with CONTINUITY_PROTOCOL_LOG_PATH.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n")
    except OSError:
        pass


def _continuity_sample(release_id: str) -> dict[str, Any]:
    # The listener publishes its heartbeat with an atomic replace.  On NTFS a
    # concurrent reader can momentarily see neither name during that replace;
    # this is not a listener outage.  Retry only this bounded local read, then
    # retain a real unavailable observation if all attempts fail.
    for attempt in range(CONTINUITY_STATUS_READ_ATTEMPTS):
        try:
            status = json.loads(STATUS_PATH.read_text(encoding="utf-8-sig"))
            heartbeat = str(status["heartbeat_at_utc"])
            parsed = datetime.fromisoformat(heartbeat.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                raise ValueError("heartbeat lacks timezone")
            age = (datetime.now(timezone.utc) - parsed.astimezone(timezone.utc)).total_seconds()
            valid = (status.get("release_id") == release_id and status.get("state") == "MAINTENANCE_HOLD"
                     and 0 <= age < CONTINUITY_MAX_HEARTBEAT_AGE_SECONDS)
            return {"captured_at_utc": _utc_now(), "heartbeat_at_utc": heartbeat,
                    "heartbeat_age_seconds": round(age, 3), "state": status.get("state"),
                    "release_id": status.get("release_id"), "valid": valid}
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
            if attempt + 1 < CONTINUITY_STATUS_READ_ATTEMPTS:
                time.sleep(0.1)
                continue
            return {"captured_at_utc": _utc_now(), "valid": False, "reason": "STATUS_UNAVAILABLE"}


def _continuity_observation(values: dict[str, Any], release_id: str) -> dict[str, Any]:
    """Take one bounded non-trading baseline or postflight observation.

    The listener's most recent monitor result is the durable unresolved-
    execution view.  MT5 supplies the separate account/exposure observation.
    Both must be available and consistent; unknown state never becomes a pass.
    """
    sample = _continuity_sample(release_id)
    try:
        status = json.loads(STATUS_PATH.read_text(encoding="utf-8-sig"))
        monitor = status.get("monitor")
        recovered = monitor.get("result", {}).get("recovered") if isinstance(monitor, dict) else None
        unresolved_clear = isinstance(monitor, dict) and monitor.get("state") == "IDLE" and recovered == []
        lease = json.loads(LEASE_PATH.read_text(encoding="utf-8-sig"))
        config = json.loads(CONFIG_PATH.read_text(encoding="utf-8-sig"))
        payload_hashes = {}
        for name in ("m20_demo_listener_service.payload", "m20_demo_trading_session.payload",
                     "m20_postgres_audit_bridge.payload", "m20_discord_trade_notification.payload"):
            path = ROOT / name
            if not path.is_file():
                raise ValueError("payload absent")
            payload_hashes[name] = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
        initialized = False
        try:
            import MetaTrader5 as mt5
            initialized = mt5.initialize(path=str(values["terminal_path"]))
            account = mt5.account_info() if initialized else None
            positions = mt5.positions_get() if account is not None else None
        finally:
            if initialized:
                mt5.shutdown()
        account_observation = {
            "server": getattr(account, "server", None), "currency": getattr(account, "currency", None),
            "balance": getattr(account, "balance", None), "equity": getattr(account, "equity", None),
            "position_observation": "AVAILABLE" if positions is not None else "UNAVAILABLE",
            "open_positions": len(positions) if positions is not None else None,
        }
        return {
            "valid": bool(sample.get("valid")) and unresolved_clear and
                     account_observation == {**account_observation, "server": "GOMarketsMU-Demo", "currency": "AUD", "position_observation": "AVAILABLE", "open_positions": 0},
            "heartbeat": sample, "account": account_observation,
            "unresolved_execution": {"state": "CLEAR" if unresolved_clear else "UNKNOWN_OR_OPEN", "monitor": monitor},
            "deployment": {"release_id": release_id,
                           "application_revision": config.get("FOREX_M20_APPLICATION_REVISION"),
                           "configuration_fingerprint": config.get("FOREX_M20_CONFIGURATION_FINGERPRINT"),
                           "payload_sha256": payload_hashes,
                           "lease": lease,
                           "persistent_risk_policy": config.get("FOREX_M20_PERSISTENT_RISK_POLICY"),
                           "financing_policy": config.get("FOREX_M20_FINANCING_POLICY")},
        }
    except (OSError, TypeError, ValueError, KeyError, json.JSONDecodeError):
        return {"valid": False, "reason": "PREFLIGHT_OR_POSTFLIGHT_UNAVAILABLE", "heartbeat": sample}


def _continuity_worker_handoff() -> bool:
    """Request exactly one local listener task restart; it cannot trade."""
    command = (
        "$ErrorActionPreference='Stop';$n='Forex-M20-Demo-Listener';"
        "$t=Get-ScheduledTask -TaskName $n -ErrorAction Stop;"
        "if($t.Principal.LogonType.ToString() -ne 'S4U'){throw 'listener task is not S4U'};"
        "if($t.State -eq 'Running'){Stop-ScheduledTask -TaskName $n -ErrorAction Stop};"
        "Start-ScheduledTask -TaskName $n -ErrorAction Stop"
    )
    completed = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command],
                               text=True, capture_output=True, check=False, timeout=30)
    return completed.returncode == 0


def _notify_continuity(run_id: str, event: str) -> dict[str, Any]:
    """Deliver a redacted best-effort drill marker without affecting recovery."""
    notifier = ROOT / "m20_discord_trade_notification.payload"
    values = _load_environment()
    if not notifier.is_file():
        return {"state": "FAILED", "reason": "NOTIFIER_PAYLOAD_ABSENT"}
    try:
        completed = subprocess.run(
            [str(values["python_path"]), str(notifier)],
            input=json.dumps({"run_id": run_id, "event": event, "captured_at_utc": _utc_now()}),
            text=True, capture_output=True, check=False, env=os.environ.copy(), timeout=5,
        )
        response = json.loads(completed.stdout)
        if completed.returncode == 0 and isinstance(response, dict) and response.get("delivery") in {"SENT", "DISABLED"}:
            return {"state": response["delivery"]}
        if isinstance(response, dict) and response.get("delivery") in {"FAILED", "INVALID"}:
            detail = str(response.get("detail", "DELIVERY_FAILED"))
            return {"state": "FAILED", "reason": detail[:160]}
        return {"state": "FAILED", "reason": f"NOTIFIER_EXIT_{completed.returncode}"}
    except subprocess.TimeoutExpired:
        return {"state": "FAILED", "reason": "NOTIFIER_TIMEOUT"}
    except (OSError, json.JSONDecodeError, KeyError, TypeError):
        return {"state": "FAILED", "reason": "NOTIFIER_UNAVAILABLE"}


def arm_continuity_protocol() -> int:
    """Preflight and schedule the non-trading protocol entirely on T480."""
    _archive_completed_continuity_protocol()
    if not _maintenance_hold()["active"]:
        raise SystemExit("M20 continuity protocol requires maintenance hold")
    values = _load_environment()
    baseline = _continuity_observation(values, ROOT.name)
    if not baseline.get("valid"):
        raise SystemExit("M20 continuity protocol requires a fresh held, flat, reconciled Demo baseline")
    task_check = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
         "$t=Get-ScheduledTask -TaskName 'Forex-M20-Demo-Listener' -ErrorAction Stop;"
         "if($t.Principal.LogonType.ToString() -ne 'S4U'){exit 2};exit 0"],
        text=True, capture_output=True, check=False, timeout=15,
    )
    if task_check.returncode != 0:
        raise SystemExit("M20 continuity protocol requires listener S4U task identity")
    run_id = hashlib.sha256((ROOT.name + _utc_now()).encode("utf-8")).hexdigest()[:24]
    baseline["listener_logon_type"] = "S4U"
    record = {"schema_version": "forex.m20.continuity-protocol.v1", "run_id": run_id,
              "release_id": ROOT.name, "started_at_utc": _utc_now(), "state": "ARMED",
              "baseline": baseline, "samples": [], "incident_delivery": {"state": "PENDING"}}
    _write_continuity_protocol(record)
    protocol_task = "Forex-M20-Continuity-Protocol"
    command = (
        "$ErrorActionPreference='Stop';$n='Forex-M20-Continuity-Protocol';"
        "$a=New-ScheduledTaskAction -Execute '" + str(values["python_path"]).replace("'", "''")
        + "' -Argument '\"" + str(Path(__file__).resolve()).replace("'", "''") + "\" --continuity-protocol';"
        "$p=New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType S4U -RunLevel Highest;"
        "$s=New-ScheduledTaskSettingsSet -ExecutionTimeLimit ([TimeSpan]::Zero);"
        "Register-ScheduledTask -TaskName $n -Action $a -Principal $p -Settings $s -Force|Out-Null;Start-ScheduledTask -TaskName $n"
    )
    scheduled = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command],
                                text=True, capture_output=True, check=False, timeout=30)
    if scheduled.returncode != 0:
        CONTINUITY_PROTOCOL_PATH.unlink(missing_ok=True)
        raise SystemExit("M20 continuity protocol task registration failed")
    print(json.dumps({"armed": True, "run_id": run_id, "task": protocol_task,
                      "maintenance_hold": True, "broker_mutation": "NONE"}, separators=(",", ":")))
    return 0


def run_continuity_protocol() -> int:
    """Run the self-contained held-only continuity proof on T480.

    It intentionally observes the local listener rather than market activity;
    neither this process nor its recovery handoff calls MT5 order APIs.
    """
    _load_environment()
    record = _load_continuity_protocol()
    _append_continuity_event({"run_id": record["run_id"], "event": "STARTED", "captured_at_utc": _utc_now()})
    record["incident_delivery"] = _notify_continuity(record["run_id"], "INCIDENT")
    if record["incident_delivery"].get("state") == "FAILED":
        # Do not consume a full continuity window or restart a healthy worker
        # when the mandatory first alert cannot leave T480.  This is a genuine
        # inconclusive alert-path outcome, retained separately from any proof.
        record.update({"state": "INCONCLUSIVE", "completed_at_utc": _utc_now(),
                       "failure_reason": "INCIDENT_ALERT_UNAVAILABLE",
                       "recovery_delivery": {"state": "NOT_ATTEMPTED"}})
        _write_continuity_protocol(record)
        _append_continuity_event({"run_id": record["run_id"], "event": "INCONCLUSIVE",
                                  "captured_at_utc": record["completed_at_utc"],
                                  "reason": record["failure_reason"]})
        return 0
    deadline = time.monotonic() + CONTINUITY_WINDOW_SECONDS
    handoff_at = time.monotonic() + min(30, max(5, CONTINUITY_WINDOW_SECONDS / 2))
    handoff_done = False
    failed_reason: str | None = None
    while time.monotonic() < deadline:
        sample = _continuity_sample(record["release_id"])
        record["samples"].append(sample)
        if not sample.get("valid"):
            failed_reason = str(sample.get("reason", "HEARTBEAT_OR_HOLD_INVALID"))
            break
        if not handoff_done and time.monotonic() >= handoff_at:
            record["handoff"] = {"requested_at_utc": _utc_now(), "state": "REQUESTED"}
            if not _continuity_worker_handoff():
                record["handoff"]["state"] = "FAILED"
                failed_reason = "WORKER_HANDOFF_REQUEST_FAILED"
                break
            handoff_done = True
            recovery_deadline = time.monotonic() + CONTINUITY_RECOVERY_DEADLINE_SECONDS
            while time.monotonic() < recovery_deadline:
                recovered = _continuity_sample(record["release_id"])
                record["samples"].append(recovered)
                if recovered.get("valid"):
                    record["handoff"] = {"requested_at_utc": record["handoff"]["requested_at_utc"],
                                         "recovered_at_utc": _utc_now(), "state": "RECOVERED"}
                    break
                time.sleep(CONTINUITY_SAMPLE_SECONDS)
            else:
                failed_reason = "WORKER_HANDOFF_RECOVERY_TIMEOUT"
                break
        _write_continuity_protocol(record)
        time.sleep(CONTINUITY_SAMPLE_SECONDS)
    postflight = _continuity_observation(_load_environment(), record["release_id"])
    final = postflight.get("heartbeat", _continuity_sample(record["release_id"]))
    record["samples"].append(final)
    if not postflight.get("valid") and failed_reason is None:
        failed_reason = str(postflight.get("reason", "POSTFLIGHT_INVALID"))
    if not handoff_done and failed_reason is None:
        failed_reason = "WORKER_HANDOFF_NOT_REACHED"
    if postflight.get("valid") and postflight.get("deployment") != record["baseline"].get("deployment") and failed_reason is None:
        failed_reason = "DEPLOYMENT_OR_RISK_BINDING_CHANGED"
    if postflight.get("valid") and postflight.get("account") != record["baseline"].get("account") and failed_reason is None:
        failed_reason = "ACCOUNT_OR_EXPOSURE_CHANGED"
    delivery_failed = (record.get("incident_delivery", {}).get("state") == "FAILED")
    if handoff_done and failed_reason is None and delivery_failed:
        record["state"] = "INCONCLUSIVE"
        failed_reason = "INCIDENT_ALERT_UNAVAILABLE"
    else:
        record["state"] = "PASS" if handoff_done and failed_reason is None else "FAIL"
    record["completed_at_utc"] = _utc_now()
    record["failure_reason"] = failed_reason
    record["postflight"] = postflight
    record["recovery_delivery"] = _notify_continuity(record["run_id"], "RECOVERED")
    if record["state"] == "PASS" and record["recovery_delivery"].get("state") == "FAILED":
        record["state"] = "INCONCLUSIVE"
        record["failure_reason"] = "RECOVERY_ALERT_UNAVAILABLE"
    _write_continuity_protocol(record)
    _append_continuity_event({"run_id": record["run_id"], "event": record["state"],
                              "captured_at_utc": record["completed_at_utc"], "reason": failed_reason})
    return 0 if record["state"] == "PASS" else 2


if __name__ == "__main__":
    if len(sys.argv) == 1:
        run_guarded()
    elif len(sys.argv) == 2 and sys.argv[1] == "--continuity-protocol":
        raise SystemExit(run_continuity_protocol())
    elif len(sys.argv) == 2 and sys.argv[1] == "--arm-continuity-protocol":
        raise SystemExit(arm_continuity_protocol())
    else:
        raise SystemExit("M20 listener service accepts no arguments or --continuity-protocol")
