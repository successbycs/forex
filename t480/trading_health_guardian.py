"""Local, observation-only T480 trading-health guardian (M33.2).

The guardian deliberately has no MT5 import, broker call, order function, or
Scheduled Task mutation.  It reads the listener's local receipts, classifies
them with the shared deterministic policy, and writes an atomic local status.
Recovery and permit publication are separate later waves; until then a missing
or malformed intent or observation can only fence new entries.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from importlib.machinery import SourceFileLoader
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
# Installed packages live under the separate immutable guardian-release root;
# local development uses the normal repository checkout instead.
_IMMUTABLE_RELEASE = HERE.parent.name in {"releases", "guardian-releases"}
if _IMMUTABLE_RELEASE:
    _policy_loader = SourceFileLoader("forex_m33_trading_health", str(HERE / "trading_health.payload"))
    _policy_spec = importlib.util.spec_from_loader(_policy_loader.name, _policy_loader)
    if _policy_spec is None or _policy_spec.loader is None:
        raise RuntimeError("M33 release trading-health policy payload is unavailable")
    _policy = importlib.util.module_from_spec(_policy_spec)
    sys.modules[_policy_spec.name] = _policy
    _policy_spec.loader.exec_module(_policy)
    Observation, classify, recovery_budget = _policy.Observation, _policy.classify, _policy.recovery_budget
else:
    if str(HERE.parent / "src") not in sys.path:
        sys.path.insert(0, str(HERE.parent / "src"))
    from forex.trading_health import Observation, classify, recovery_budget  # noqa: E402


def _default_state_root() -> Path:
    return HERE.parent.parent / "state" if _IMMUTABLE_RELEASE else HERE


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    temporary.replace(path)


def _age_seconds(value: Any, now: datetime) -> float | None:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return None
        age = (now - parsed.astimezone(UTC)).total_seconds()
        return age if age >= 0 else None
    except (TypeError, ValueError):
        return None


def _intent_mode(intent: dict[str, Any] | None) -> str | None:
    if not isinstance(intent, dict) or intent.get("schema_version") != "forex.trading-health-intent.v1":
        return None
    mode = intent.get("mode")
    return mode if mode in {"STOPPED", "MONITOR_ONLY", "RUN_DEMO"} else None


def _boot_id() -> str:
    """Return a local boot identity without treating an unavailable source as current."""
    if os.name == "nt":
        # The Windows boot-time FILETIME is stable for the current boot and is
        # available without an MT5 or broker surface.
        try:
            import subprocess
            done = subprocess.run(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
                 "(Get-CimInstance Win32_OperatingSystem).LastBootUpTime.ToUniversalTime().ToString('o')"],
                capture_output=True, text=True, timeout=5, check=False,
            )
            text = done.stdout.strip()
            if done.returncode == 0 and text:
                return "windows-boot:" + text
        except (OSError, subprocess.SubprocessError):
            pass
    return "boot-unavailable"


def _managed_mt5_inventory(root: Path) -> tuple[int | None, int]:
    """Return ``(managed_count, unattributable_count)`` from the local host.

    A process is managed only when it is the configured MT5 executable in
    Session 0.  A same-named process in another session or at another path is
    deliberately unattributable and blocks recovery; this observer never
    terminates anything.  ``None`` means inventory was unavailable.
    """
    config = _read_json(root / "m20_demo_listener_service.local.json")
    expected = config.get("terminal_path") if isinstance(config, dict) else None
    if os.name != "nt" or not isinstance(expected, str) or not expected:
        return None, 0
    # The configured local path is data, not a command argument.  Encode it as
    # a PowerShell literal so metacharacters cannot alter the fixed inventory.
    literal = expected.replace("'", "''")
    command = (
        "$ErrorActionPreference='Stop';$expected='" + literal + "';"
        "$p=@(Get-CimInstance Win32_Process|Where-Object {$_.Name -in @('terminal.exe','terminal64.exe')}|"
        "ForEach-Object{[pscustomobject]@{path=[string]$_.ExecutablePath;session=[int]$_.SessionId}});"
        "$p|ConvertTo-Json -Compress"
    )
    try:
        done = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command],
                              capture_output=True, text=True, timeout=5, check=False)
        value = json.loads(done.stdout) if done.returncode == 0 and done.stdout.strip() else []
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
        return None, 0
    rows = value if isinstance(value, list) else [value]
    if not all(isinstance(row, dict) and isinstance(row.get("path"), str) and isinstance(row.get("session"), int)
               for row in rows):
        return None, 0
    managed = sum(row["path"].casefold() == expected.casefold() and row["session"] == 0 for row in rows)
    return managed, len(rows) - managed


def _observation(root: Path, now: datetime) -> tuple[Observation, str, int, list[datetime]]:
    listener = _read_json(root / "m20_demo_listener_status.local.json")
    hold = _read_json(root / "m20_demo_maintenance_hold.local.json")
    intent = _read_json(root / "trading_health_intent.local.json")
    guardian = _read_json(root / "trading_health_guardian_state.local.json") or {}
    heartbeat_age = _age_seconds(listener.get("heartbeat_at_utc") if listener else None, now)
    binding = listener.get("runtime_binding") if isinstance(listener, dict) else None
    binding = binding if isinstance(binding, dict) else {}
    monitor = listener.get("monitor") if isinstance(listener, dict) else None
    monitor = monitor if isinstance(monitor, dict) else {}
    monitor_result = monitor.get("result") if isinstance(monitor.get("result"), dict) else {}
    attempts: list[datetime] = []
    for raw in guardian.get("recovery_attempts_utc", []) if isinstance(guardian.get("recovery_attempts_utc"), list) else []:
        try:
            stamp = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
            if stamp.tzinfo is not None:
                attempts.append(stamp.astimezone(UTC))
        except ValueError:
            continue
    circuit_open, next_retry = recovery_budget(attempts, now, True)
    state = str(listener.get("state")) if listener else ""
    managed_count, unattributable_count = _managed_mt5_inventory(root)
    observation = Observation(
        boot_seconds=None,
        # Keep a verified intended Session 0 context distinct from an extra
        # unattributable process: the policy reports the latter explicitly as
        # an ownership incident rather than obscuring it as a session failure.
        session_ok=binding.get("state") == "MAPPED" and managed_count == 1,
        managed_mt5_count=managed_count,
        unattributable_mt5_count=unattributable_count,
        mt5_identity_ok=binding.get("state") == "MAPPED",
        mt5_responding=binding.get("terminal_connected") is True,
        permissions_ok=(binding.get("terminal_trade_allowed") is True
                        and binding.get("account_trade_allowed") is True
                        and binding.get("account_trade_expert") is True),
        broker_connected=binding.get("terminal_connected"),
        data_fresh=heartbeat_age is not None and heartbeat_age < 30,
        db_available=monitor.get("state") in {"IDLE", "RUNNING"},
        listener_present=listener is not None and state not in {"STOPPED", "STARTUP_FAILED"},
        listener_heartbeat_age_s=heartbeat_age,
        assessment_age_s=_age_seconds(listener.get("assessment_completed_at_utc") if listener else None, now),
        source_input_advancing=None,
        monitoring_fresh=monitor.get("state") in {"IDLE", "RUNNING"},
        exposure_flat=True if monitor.get("state") == "IDLE" and monitor_result.get("recovered") in ([], None) else None,
        inflight_unresolved=False if monitor.get("state") == "IDLE" else None,
        risk_or_maintenance_hold=bool(hold and hold.get("enabled") is True),
        lease_valid=None,
        market_open=None,
    )
    return observation, _intent_mode(intent), int(max(0, next_retry)), attempts if circuit_open else attempts


def run_once(root: Path, now: datetime | None = None) -> dict[str, Any]:
    now = now or _utc_now()
    observation, mode, next_retry, attempts = _observation(root, now)
    circuit_open, _ = recovery_budget(attempts, now, True)
    decision = classify(observation, mode, budget_open=circuit_open)
    release_id = "unknown"
    listener = _read_json(root / "m20_demo_listener_status.local.json")
    if isinstance(listener, dict) and isinstance(listener.get("release_id"), str):
        release_id = listener["release_id"]
    status = {
        "schema_version": "forex.trading-health-status.v1",
        "observed_at_utc": now.isoformat().replace("+00:00", "Z"),
        "boot_id": _boot_id(),
        "release_id": release_id if len(release_id) == 16 else "0" * 16,
        "state": decision.state,
        "reasons": list(decision.reasons),
        "execution_capable": decision.execution_capable,
        "entry_eligible": False,  # Wave 2 never publishes entry authority.
        "recommended_action": decision.recommended_action,
        "desired_mode": mode,
        "managed_mt5_count": observation.managed_mt5_count,
        "attempts_in_window": len(attempts),
        "next_retry_after_s": next_retry,
        "last_assessment_completed_at_utc": listener.get("assessment_completed_at_utc") if isinstance(listener, dict) else None,
        "last_monitor_at_utc": (listener.get("monitor") or {}).get("last_checked_at_utc") if isinstance(listener, dict) and isinstance(listener.get("monitor"), dict) else None,
    }
    _atomic_json(root / "trading_health_status.local.json", status)
    return status


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one no-order local trading-health observation cycle.")
    parser.add_argument("--state-root", type=Path, default=_default_state_root())
    args = parser.parse_args()
    print(json.dumps(run_once(args.state_root), separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
