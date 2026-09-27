"""Bounded, held-only M33.3 listener recovery executor.

This is deliberately a *narrow* lifecycle owner.  It consumes one current
guardian request and can start or restart only ``Forex-M20-Demo-Listener``.
It never starts, stops or terminates MT5, cannot release the maintenance hold,
and refuses every managed-client/duplicate action until the shared T480
process primitives are available as a separately reviewed fixed operation.
"""
from __future__ import annotations

import argparse
import ctypes
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
from contextlib import contextmanager
from datetime import UTC, datetime
from importlib.machinery import SourceFileLoader
from pathlib import Path
from typing import Any, Iterator


HERE = Path(__file__).resolve().parent
_IMMUTABLE_RELEASE = HERE.parent.name in {"releases", "guardian-releases"}
if _IMMUTABLE_RELEASE:
    _policy_loader = SourceFileLoader("forex_m33_recovery_policy", str(HERE / "trading_health.payload"))
    _policy_spec = importlib.util.spec_from_loader(_policy_loader.name, _policy_loader)
    if _policy_spec is None or _policy_spec.loader is None:
        raise RuntimeError("M33 recovery policy payload is unavailable")
    _policy = importlib.util.module_from_spec(_policy_spec)
    sys.modules[_policy_spec.name] = _policy
    _policy_spec.loader.exec_module(_policy)
    RecoveryRequest, recovery_budget, validate_recovery_request = (
        _policy.RecoveryRequest, _policy.recovery_budget, _policy.validate_recovery_request)
else:
    sys.path.insert(0, str(HERE.parent / "src"))
    from forex.trading_health import RecoveryRequest, recovery_budget, validate_recovery_request


LISTENER_TASK = "Forex-M20-Demo-Listener"
RECOVERY_MUTEX = "Global\\Forex-M33-Trading-Health-Recovery"
MAX_REQUEST_AGE_SECONDS = 75
_REQUEST_ID = re.compile(r"^[a-f0-9]{32}$")
_RELEASE_ID = re.compile(r"^[a-f0-9]{16}$")
_FINGERPRINT = re.compile(r"^sha256:[a-f0-9]{64}$")


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _default_state_root() -> Path:
    return HERE.parent.parent / "state" if _IMMUTABLE_RELEASE else HERE


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


def _parse_utc(value: Any) -> datetime | None:
    try:
        result = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return result.astimezone(UTC) if result.tzinfo else None


def _status_digest(status: dict[str, Any]) -> str:
    projection = {key: value for key, value in status.items()
                  if key not in {"status_sha256", "recovery_request_id", "recovery_phase"}}
    return "sha256:" + hashlib.sha256(
        json.dumps(projection, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _request_is_well_formed(request: dict[str, Any]) -> bool:
    required = {"schema_version", "state", "request_id", "generation", "boot_id", "guardian_release_id",
                "listener_release_id", "configuration_fingerprint", "account_scope_sha256", "profile_sha256",
                "status_sha256", "health_state", "action", "issued_at_utc", "expires_at_utc", "entry_eligible"}
    return (set(request) == required and request.get("schema_version") == "forex.trading-health-recovery-request.v2"
            and request.get("state") == "PENDING" and isinstance(request.get("request_id"), str)
            and bool(_REQUEST_ID.fullmatch(request["request_id"])) and type(request.get("generation")) is int
            and request["generation"] >= 1 and isinstance(request.get("boot_id"), str) and request["boot_id"]
            and all(isinstance(request.get(name), str) and _RELEASE_ID.fullmatch(request[name])
                    for name in ("guardian_release_id", "listener_release_id"))
            and all(isinstance(request.get(name), str) and _FINGERPRINT.fullmatch(request[name])
                    for name in ("configuration_fingerprint", "account_scope_sha256", "profile_sha256", "status_sha256"))
            and request.get("health_state") == "RECOVERING_LISTENER"
            and request.get("action") in {"START_LISTENER", "RESTART_LISTENER"}
            and request.get("entry_eligible") is False)


def _load_ledger(root: Path, request: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    ledger = _read_json(root / "trading_health_recovery_ledger.local.json")
    if not isinstance(ledger, dict):
        return None, "RECOVERY_LEDGER_UNREADABLE_OR_CORRUPT"
    if (ledger.get("schema_version") != "forex.trading-health-recovery-ledger.v1"
            or ledger.get("boot_id") != request["boot_id"]
            or ledger.get("active_request_id") != request["request_id"]
            or ledger.get("last_generation") != request["generation"]
            or ledger.get("phase") != "PENDING" or not isinstance(ledger.get("attempts_utc"), list)):
        return None, "RECOVERY_LEDGER_NOT_CURRENT"
    return ledger, None


def _dispatched_ledger(root: Path, request: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    ledger = _read_json(root / "trading_health_recovery_ledger.local.json")
    if not isinstance(ledger, dict):
        return None, "RECOVERY_LEDGER_UNREADABLE_OR_CORRUPT"
    if (ledger.get("schema_version") != "forex.trading-health-recovery-ledger.v1"
            or ledger.get("boot_id") != request["boot_id"]
            or ledger.get("active_request_id") != request["request_id"]
            or ledger.get("last_generation") != request["generation"]
            or ledger.get("phase") != "DISPATCHED"
            or not isinstance(ledger.get("attempts_utc"), list)):
        return None, "RECOVERY_LEDGER_NOT_CURRENT"
    if any(_parse_utc(stamp) is None for stamp in ledger["attempts_utc"]):
        return None, "RECOVERY_LEDGER_ATTEMPT_HISTORY_INVALID"
    return ledger, None


def _failure(root: Path, reason: str, *, request: dict[str, Any] | None = None,
             now: datetime | None = None) -> dict[str, Any]:
    if isinstance(request, dict) and _request_is_well_formed(request):
        result = {"schema_version": "forex.trading-health-recovery-receipt.v2", "request_id": request["request_id"],
                  "generation": request["generation"], "boot_id": request["boot_id"],
                  "listener_release_id": request["listener_release_id"],
                  "configuration_fingerprint": request["configuration_fingerprint"],
                  "observed_at_utc": (now or _utc_now()).isoformat().replace("+00:00", "Z"),
                  "state": "REFUSED", "reason": reason, "broker_mutation": "NONE", "entry_eligible": False}
    else:
        result = {"schema_version": "forex.trading-health-recovery-receipt.v1",
                  "observed_at_utc": (now or _utc_now()).isoformat().replace("+00:00", "Z"),
                  "state": "REFUSED", "reason": reason, "broker_mutation": "NONE", "entry_eligible": False}
    _atomic_json(root / "trading_health_recovery_receipt.local.json", result)
    return result


def _refuse_claim(root: Path, ledger: dict[str, Any], request: dict[str, Any], reason: str,
                  now: datetime) -> dict[str, Any]:
    """Close a claimed request before returning a refusal; never leave it reusable."""
    ledger["phase"] = "REFUSED"
    _atomic_json(root / "trading_health_recovery_ledger.local.json", ledger)
    return _failure(root, reason, request=request, now=now)


@contextmanager
def _recovery_mutex() -> Iterator[bool]:
    """Acquire only the machine-wide recovery mutex; non-Windows fails closed."""
    if os.name != "nt":
        yield False
        return
    handle = ctypes.windll.kernel32.CreateMutexW(None, False, RECOVERY_MUTEX)
    if not handle:
        yield False
        return
    waited = ctypes.windll.kernel32.WaitForSingleObject(handle, 0)
    acquired = waited == 0
    try:
        yield acquired
    finally:
        if acquired:
            ctypes.windll.kernel32.ReleaseMutex(handle)
        ctypes.windll.kernel32.CloseHandle(handle)


def _powershell(command: str, *, timeout: int = 30) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command],
                          text=True, capture_output=True, timeout=timeout, check=False)


def _intent_is_run_demo(root: Path) -> bool:
    intent = _read_json(root / "trading_health_intent.local.json")
    return bool(isinstance(intent, dict)
                and intent.get("schema_version") == "forex.trading-health-intent.v1"
                and intent.get("mode") == "RUN_DEMO")


def _fresh_request(root: Path, now: datetime) -> tuple[dict[str, Any] | None, str | None]:
    request = _read_json(root / "trading_health_recovery_request.local.json")
    status = _read_json(root / "trading_health_status.local.json")
    if not isinstance(request, dict) or not isinstance(status, dict):
        return request, "REQUEST_OR_STATUS_UNREADABLE"
    if not _request_is_well_formed(request):
        return request, "REQUEST_SHAPE_INVALID"
    issued, expires = _parse_utc(request.get("issued_at_utc")), _parse_utc(request.get("expires_at_utc"))
    if (issued is None or expires is None or expires <= issued
            or (expires - issued).total_seconds() > MAX_REQUEST_AGE_SECONDS
            or not issued <= now < expires):
        return request, "REQUEST_STALE_OR_FUTURE"
    if (status.get("recovery_request_id") != request["request_id"]
            or status.get("state") != request["health_state"]
            or status.get("recommended_action") != request["action"]
            or status.get("entry_eligible") is not False):
        return request, "REQUEST_NOT_CURRENT"
    if status.get("status_sha256") != request["status_sha256"] or _status_digest(status) != request["status_sha256"]:
        return request, "REQUEST_STATUS_DIGEST_MISMATCH"
    return request, None


def _held_readiness(root: Path, request: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    """Preflight from the immutable prior binding, even when listener status is absent."""
    manifest = _read_json(root / "trading_health_runtime_binding.local.json")
    config = _read_json(root / "m20_demo_listener_service.local.json")
    if not isinstance(manifest, dict) or not isinstance(config, dict):
        return None, "RUNTIME_BINDING_UNREADABLE"
    release = manifest.get("listener_release_id")
    python_path = config.get("python_path")
    if (not isinstance(release, str) or release != request["listener_release_id"]
            or manifest.get("boot_id") != request["boot_id"]
            or manifest.get("configuration_fingerprint") != request["configuration_fingerprint"]
            or manifest.get("account_scope_sha256") != request["account_scope_sha256"]
            or manifest.get("profile_sha256") != request["profile_sha256"]
            or config.get("FOREX_M20_CONFIGURATION_FINGERPRINT") != request["configuration_fingerprint"]
            or not isinstance(python_path, str) or not python_path):
        return None, "RUNTIME_BINDING_INVALID"
    service = Path(r"C:\ProgramData\ForexListener\releases") / release / "m20_demo_listener_service.payload"
    # The path is derived solely from the current local binding; no caller can
    # supply a command, release, account, or terminal argument.
    completed = subprocess.run([python_path, str(service), "--held-readiness-assessment"],
                               text=True, capture_output=True, timeout=30, check=False)
    if completed.returncode != 0:
        return None, "HELD_READINESS_FAILED"
    try:
        payload = json.loads(completed.stdout)
        assessment = payload["assessment"]
    except (TypeError, KeyError, json.JSONDecodeError):
        return None, "HELD_READINESS_INVALID"
    if not (payload.get("maintenance_hold") is True and payload.get("listener_release_id") == release
            and assessment.get("marker") == "FOREX_M20_DEMO_HELD_READINESS_ASSESSMENT_OK"
            and assessment.get("server") == "GOMarketsMU-Demo" and assessment.get("currency") == "AUD"
            and assessment.get("symbol") == "EURUSD" and assessment.get("open_positions") == 0
            and assessment.get("pending_orders") == 0
            and assessment.get("broker_mutation") == "NONE"
            and assessment.get("order_submission") == "STRUCTURALLY_UNAVAILABLE"):
        return None, "HELD_READINESS_UNSAFE"
    return payload, None


def _listener_task_action(action: str, request: dict[str, Any]) -> str | None:
    expected = ("C:\\ProgramData\\ForexListener\\releases\\" + request["listener_release_id"]
                + "\\m20_demo_listener_service.payload")
    # This is an internal request field with a strict hexadecimal release ID;
    # it is still escaped as a PowerShell literal before fixed task inspection.
    expected_literal = expected.replace("'", "''")
    ownership = ("$a=@($t.Actions)[0];$want='" + expected_literal
                 + "';if($a.Execute -notmatch 'python' -or $a.Arguments -notlike ('*'+$want+'*'))"
                 + "{throw 'listener task release binding required'};")
    if action == "START_LISTENER":
        command = "$ErrorActionPreference='Stop';$t=Get-ScheduledTask -TaskName 'Forex-M20-Demo-Listener';if($t.Principal.LogonType.ToString() -ne 'S4U'){throw 'listener S4U required'};" + ownership + "Start-ScheduledTask -TaskName 'Forex-M20-Demo-Listener';[pscustomobject]@{task_state=(Get-ScheduledTask -TaskName 'Forex-M20-Demo-Listener').State.ToString()}|ConvertTo-Json -Compress"
    elif action == "RESTART_LISTENER":
        command = "$ErrorActionPreference='Stop';$t=Get-ScheduledTask -TaskName 'Forex-M20-Demo-Listener';if($t.Principal.LogonType.ToString() -ne 'S4U'){throw 'listener S4U required'};" + ownership + "if($t.State.ToString() -eq 'Running'){Stop-ScheduledTask -TaskName 'Forex-M20-Demo-Listener';Start-Sleep -Milliseconds 500};Start-ScheduledTask -TaskName 'Forex-M20-Demo-Listener';[pscustomobject]@{task_state=(Get-ScheduledTask -TaskName 'Forex-M20-Demo-Listener').State.ToString()}|ConvertTo-Json -Compress"
    else:
        return None
    completed = _powershell(command)
    return None if completed.returncode == 0 else "LISTENER_TASK_ACTION_FAILED"


def _post_action_evidence(root: Path, request: dict[str, Any], dispatched_at: datetime) -> tuple[dict[str, Any] | None, str | None]:
    """Require new local evidence; a task-launch acknowledgement is insufficient."""
    listener = _read_json(root / "m20_demo_listener_status.local.json")
    guardian = _read_json(root / "trading_health_status.local.json")
    if not isinstance(listener, dict) or not isinstance(guardian, dict):
        return None, "POST_ACTION_LISTENER_OR_GUARDIAN_UNREADABLE"
    heartbeat, observed = _parse_utc(listener.get("heartbeat_at_utc")), _parse_utc(guardian.get("observed_at_utc"))
    if (heartbeat is None or observed is None or heartbeat < dispatched_at or observed < dispatched_at
            or listener.get("release_id") != request["listener_release_id"]
            or listener.get("state") != "MAINTENANCE_HOLD"
            or guardian.get("recovery_request_id") != request["request_id"]
            or guardian.get("entry_eligible") is not False
            or guardian.get("managed_mt5_count") != 1
            or guardian.get("unattributable_mt5_count") != 0):
        return None, "POST_ACTION_FRESH_BINDING_OR_FENCE_MISSING"
    monitor = listener.get("monitor")
    monitor_result = monitor.get("result") if isinstance(monitor, dict) else None
    if not (isinstance(monitor, dict) and monitor.get("state") == "IDLE"
            and isinstance(monitor_result, dict) and monitor_result.get("recovered") in ([], None)):
        return None, "POST_ACTION_MONITOR_NOT_RESTORED"
    readiness, reason = _held_readiness(root, request)
    if reason:
        return None, "POST_ACTION_" + reason
    return {"listener_heartbeat_at_utc": listener["heartbeat_at_utc"],
            "guardian_observed_at_utc": guardian["observed_at_utc"], "monitor_state": monitor["state"],
            "held_readiness": readiness}, None


def reconcile_once(root: Path, now: datetime | None = None) -> dict[str, Any]:
    """Finish one dispatched recovery only with fresh identity-bound evidence."""
    now = now or _utc_now()
    request = _read_json(root / "trading_health_recovery_request.local.json")
    if not isinstance(request, dict) or not _request_is_well_formed(request):
        return _failure(root, "REQUEST_SHAPE_INVALID", request=request, now=now)
    with _recovery_mutex() as acquired:
        if not acquired:
            return _failure(root, "RECOVERY_MUTEX_UNAVAILABLE_OR_HELD", request=request, now=now)
        ledger, ledger_reason = _dispatched_ledger(root, request)
        if ledger_reason:
            return _failure(root, ledger_reason, request=request, now=now)
        assert ledger is not None
        attempts = ledger.get("attempts_utc")
        dispatched_at = _parse_utc(attempts[-1]) if isinstance(attempts, list) and attempts else None
        if dispatched_at is None:
            return _failure(root, "RECOVERY_DISPATCH_TIME_UNREADABLE", request=request, now=now)
        evidence, reason = _post_action_evidence(root, request, dispatched_at)
        if reason:
            ledger["phase"] = "INTERVENTION_REQUIRED"
            _atomic_json(root / "trading_health_recovery_ledger.local.json", ledger)
            result = _failure(root, reason, request=request, now=now)
            result["state"] = "INTERVENTION_REQUIRED"
            _atomic_json(root / "trading_health_recovery_receipt.local.json", result)
            return result
        ledger["phase"] = "VERIFIED"
        _atomic_json(root / "trading_health_recovery_ledger.local.json", ledger)
        result = {"schema_version": "forex.trading-health-recovery-receipt.v2", "request_id": request["request_id"],
                  "generation": request["generation"], "boot_id": request["boot_id"],
                  "listener_release_id": request["listener_release_id"],
                  "configuration_fingerprint": request["configuration_fingerprint"],
                  "observed_at_utc": now.isoformat().replace("+00:00", "Z"), "state": "VERIFIED",
                  "post_action_evidence": evidence, "broker_mutation": "NONE", "entry_eligible": False}
        _atomic_json(root / "trading_health_recovery_receipt.local.json", result)
        return result


def execute_once(root: Path, now: datetime | None = None) -> dict[str, Any]:
    now = now or _utc_now()
    request, reason = _fresh_request(root, now)
    if reason:
        return _failure(root, reason, request=request, now=now)
    if not _intent_is_run_demo(root):
        return _failure(root, "INTENT_NOT_RUN_DEMO", request=request, now=now)
    hold = _read_json(root / "m20_demo_maintenance_hold.local.json")
    if not isinstance(hold, dict) or hold.get("enabled") is not True:
        return _failure(root, "MAINTENANCE_HOLD_REQUIRED", request=request, now=now)
    assert request is not None
    with _recovery_mutex() as acquired:
        if not acquired:
            return _failure(root, "RECOVERY_MUTEX_UNAVAILABLE_OR_HELD", request=request, now=now)
        # Re-read after locking so a guardian's later generation cannot be acted on.
        request, reason = _fresh_request(root, now)
        if reason:
            return _failure(root, reason, request=request, now=now)
        assert request is not None
        ledger, reason = _load_ledger(root, request)
        if reason:
            return _failure(root, reason, request=request, now=now)
        # Persist ownership before any readiness work.  A crash after this
        # point is intervention-required, never a silent retry by a later run.
        ledger["phase"] = "CLAIMED"
        _atomic_json(root / "trading_health_recovery_ledger.local.json", ledger)
        # Recheck mutable operator controls under the same lifecycle lock,
        # immediately before the only task mutation.
        if not _intent_is_run_demo(root):
            return _refuse_claim(root, ledger, request, "INTENT_NOT_RUN_DEMO_AFTER_LOCK", now)
        hold = _read_json(root / "m20_demo_maintenance_hold.local.json")
        if not isinstance(hold, dict) or hold.get("enabled") is not True:
            return _refuse_claim(root, ledger, request, "MAINTENANCE_HOLD_REQUIRED_AFTER_LOCK", now)
        attempts = [_parse_utc(raw) for raw in ledger["attempts_utc"]]
        if any(stamp is None for stamp in attempts):
            return _refuse_claim(root, ledger, request, "RECOVERY_LEDGER_ATTEMPT_HISTORY_INVALID", now)
        attempts = [stamp for stamp in attempts if stamp is not None]
        circuit_open, wait_s = recovery_budget(attempts, now, True)
        if circuit_open or wait_s > 0:
            return _refuse_claim(root, ledger, request, "RECOVERY_BUDGET_OR_SPACING_BLOCKED", now)
        readiness, reason = _held_readiness(root, request)
        if reason:
            return _refuse_claim(root, ledger, request, reason, now)
        ledger["attempts_utc"] = [stamp.isoformat().replace("+00:00", "Z") for stamp in attempts] + [now.isoformat().replace("+00:00", "Z")]
        ledger["phase"] = "DISPATCHED"
        _atomic_json(root / "trading_health_recovery_ledger.local.json", ledger)
        reason = _listener_task_action(request["action"], request)
        if reason:
            ledger["phase"] = "INTERVENTION_REQUIRED"
            _atomic_json(root / "trading_health_recovery_ledger.local.json", ledger)
            result = _failure(root, reason, request=request, now=now)
            result["state"] = "INTERVENTION_REQUIRED"
            _atomic_json(root / "trading_health_recovery_receipt.local.json", result)
            return result
        result = {"schema_version": "forex.trading-health-recovery-receipt.v2",
                  "request_id": request["request_id"], "generation": request["generation"],
                  "boot_id": request["boot_id"], "listener_release_id": request["listener_release_id"],
                  "configuration_fingerprint": request["configuration_fingerprint"],
                  "observed_at_utc": now.isoformat().replace("+00:00", "Z"), "state": "INTERVENTION_REQUIRED",
                  "reason": "ACTION_DISPATCHED_AWAITING_FRESH_POST_ACTION_RECONCILIATION", "action": request["action"],
                  "readiness": readiness, "broker_mutation": "NONE", "entry_eligible": False}
        _atomic_json(root / "trading_health_recovery_receipt.local.json", result)
        return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one fixed held-only M33 listener recovery attempt.")
    parser.add_argument("--state-root", type=Path, default=_default_state_root())
    parser.add_argument("--reconcile", action="store_true", help="Verify one already-dispatched recovery without mutating runtime.")
    args = parser.parse_args()
    result = reconcile_once(args.state_root) if args.reconcile else execute_once(args.state_root)
    print(json.dumps(result, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
