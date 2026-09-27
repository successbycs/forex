"""Fail-closed M33 MT5-v1 recovery executor.

This local payload deliberately has no fallback process action.  It atomically
claims only a fresh request whose held bindings still match, records every
refusal, and requires a future separately reviewed fixed adapter effect before
it can transition to DISPATCHED.  It cannot import MT5, release a hold, or
place an order.
"""
from __future__ import annotations

import argparse
import ctypes
import importlib.util
import json
import os
import subprocess
import sys
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
if HERE.parent.name in {"releases", "guardian-releases"}:
    loader = importlib.util.spec_from_file_location(
        "forex_m33_managed_mt5", HERE / "trading_health_managed_mt5_recovery.payload"
    )
    if loader is None or loader.loader is None:
        raise RuntimeError("M33 managed MT5 recovery payload is unavailable")
    module = importlib.util.module_from_spec(loader)
    sys.modules[loader.name] = module
    loader.loader.exec_module(module)
    validate_request, verify_duplicate_targets = module.validate_request, module.verify_duplicate_targets
else:
    if str(HERE) not in sys.path:
        sys.path.insert(0, str(HERE))
    from trading_health_managed_mt5_recovery import validate_request, verify_duplicate_targets  # noqa: E402


def _now() -> datetime:
    return datetime.now(UTC)


def _read(path: Path) -> dict[str, Any] | None:
    try:
        result = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return None
    return result if isinstance(result, dict) else None


def _write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    temporary.replace(path)


@contextmanager
def _recovery_mutex():
    """Use the same host-wide lease as the listener recovery protocol."""
    if os.name != "nt":
        # Local contract tests have no Windows kernel object.  The released
        # payload takes the real named mutex on T480.
        yield True
        return
    handle = ctypes.windll.kernel32.CreateMutexW(None, False, "Global\\Forex-M33-Trading-Health-Recovery")
    if not handle:
        yield False
        return
    acquired = ctypes.windll.kernel32.WaitForSingleObject(handle, 0) == 0
    try:
        yield acquired
    finally:
        if acquired:
            ctypes.windll.kernel32.ReleaseMutex(handle)
        ctypes.windll.kernel32.CloseHandle(handle)


def _receipt(request: dict[str, Any] | None, state: str, reason: str, now: datetime) -> dict[str, Any]:
    if isinstance(request, dict):
        result = {"schema_version": "forex.trading-health-mt5-recovery-receipt.v1",
                  "request_id": request.get("request_id", "0" * 32), "generation": request.get("generation", 1),
                  "recovery_epoch": request.get("recovery_epoch", 1), "boot_id": request.get("boot_id", "unreadable"),
                  "configuration_fingerprint": request.get("configuration_fingerprint", "sha256:" + "0" * 64)}
    else:
        result = {"schema_version": "forex.trading-health-mt5-recovery-receipt.v1", "request_id": "0" * 32,
                  "generation": 1, "recovery_epoch": 1, "boot_id": "unreadable",
                  "configuration_fingerprint": "sha256:" + "0" * 64}
    result.update({"observed_at_utc": now.astimezone(UTC).isoformat().replace("+00:00", "Z"), "state": state,
                   "reason": reason, "broker_mutation": "NONE", "entry_eligible": False})
    return result


def _parse_utc(value: object) -> datetime | None:
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(UTC)
    except (TypeError, ValueError):
        return None


def _dispatch_record(request: dict[str, Any], inventory: dict[str, Any], now: datetime) -> dict[str, Any]:
    """Immutable linkage between the one effect and later reconciliation."""
    return {
        "schema_version": "forex.trading-health-mt5-recovery-dispatch.v1",
        "request_id": request["request_id"], "generation": request["generation"],
        "recovery_epoch": request["recovery_epoch"], "boot_id": request["boot_id"],
        "configuration_fingerprint": request["configuration_fingerprint"],
        "pre_effect_inventory_sha256": inventory["inventory_sha256"],
        "dispatched_at_utc": now.astimezone(UTC).isoformat().replace("+00:00", "Z"),
        "broker_mutation": "NONE", "entry_eligible": False,
    }


def _listener_recovery_active(root: Path, boot_id: str) -> bool:
    """Fail closed when the listener-v2 protocol owns a nonterminal action."""
    ledger = _read(root / "trading_health_recovery_ledger.local.json")
    request = _read(root / "trading_health_recovery_request.local.json")
    if ledger is None and request is None:
        return False
    if not isinstance(ledger, dict) or not isinstance(request, dict):
        return True
    return (ledger.get("schema_version") == "forex.trading-health-recovery-ledger.v1"
            and ledger.get("boot_id") == boot_id
            and ledger.get("phase") in {"PENDING", "CLAIMED", "DISPATCHED"}
            and ledger.get("active_request_id") == request.get("request_id")
            and request.get("schema_version") == "forex.trading-health-recovery-request.v2")


def _fixed_duplicate_stop(targets: list[dict[str, Any]]) -> str | None:
    """Stop only supplied, freshly revalidated identities on the Windows host.

    The PowerShell program is fixed. Target values arrive only from the
    already hash-bound inventory record through stdin; no adapter caller can
    provide a PID, command, path, or account. It re-enumerates each identity in
    the same process invocation immediately before Stop-Process.
    """
    if os.name != "nt":
        return "WINDOWS_FIXED_EFFECT_REQUIRED"
    command = (
        "$ErrorActionPreference='Stop';$raw=[Console]::In.ReadToEnd();$want=@($raw|ConvertFrom-Json);"
        "foreach($w in $want){$p=Get-CimInstance Win32_Process -Filter ('ProcessId='+[int]$w.pid);"
        "$q=Get-CimInstance Win32_Process -Filter ('ProcessId='+[int]$p.ParentProcessId);if(!$p -or !$q -or [string]$p.ExecutablePath -ne [string]$w.path -or [int]$p.SessionId -ne [int]$w.session_id -or [int]$p.ParentProcessId -ne [int]$w.parent_pid -or [string]$q.ExecutablePath -ne [string]$w.parent_path -or [string]$p.CreationDate.ToString() -ne [string]$w.creation_id){throw 'process identity changed'};"
        "$h='sha256:'+([BitConverter]::ToString([Security.Cryptography.SHA256]::Create().ComputeHash([Text.Encoding]::UTF8.GetBytes([string]$p.CommandLine))).Replace('-','').ToLower();"
        "if($h -ne [string]$w.command_line_sha256){throw 'command identity changed'};Stop-Process -Id ([int]$p.ProcessId) -ErrorAction Stop};"
        "[pscustomobject]@{stopped=@($want|ForEach-Object{[int]$_.pid})}|ConvertTo-Json -Compress"
    )
    done = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command], input=json.dumps(targets),
                          text=True, capture_output=True, timeout=15, check=False)
    return None if done.returncode == 0 else "FIXED_DUPLICATE_STOP_FAILED"


def _collect_fresh_inventory(root: Path) -> dict[str, Any]:
    """Run the fixed read-only collector while the recovery mutex is held."""
    if HERE.parent.name in {"releases", "guardian-releases"}:
        spec = importlib.util.spec_from_file_location(
            "forex_m33_managed_mt5_inventory", HERE / "trading_health_managed_mt5_inventory.payload"
        )
        if spec is None or spec.loader is None:
            raise RuntimeError("MANAGED_MT5_COLLECTOR_PAYLOAD_UNAVAILABLE")
        collected = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = collected
        spec.loader.exec_module(collected)
        collected.collect_once(root)
    else:
        from trading_health_managed_mt5_inventory import collect_once
        collect_once(root)
    inventory = _read(root / "trading_health_mt5_inventory.local.json")
    if not isinstance(inventory, dict):
        raise RuntimeError("FRESH_MANAGED_MT5_INVENTORY_UNREADABLE")
    return inventory


def _collect_held_account_witness(root: Path, request: dict[str, Any], now: datetime) -> dict[str, Any]:
    """Collect an independent, fixed no-order Demo witness from the listener release.

    This deliberately calls the immutable listener's held-readiness mode, not
    the managed-MT5 recovery payload. It cannot start a task, submit an order,
    or use a caller-supplied terminal path. If MT5 is absent the operation
    fails, which keeps the missing-terminal START branch refused.
    """
    runtime = _read(root / "trading_health_runtime_binding.local.json")
    config = _read(root / "m20_demo_listener_service.local.json")
    if not isinstance(runtime, dict) or not isinstance(config, dict):
        raise RuntimeError("HELD_WITNESS_RUNTIME_BINDING_UNREADABLE")
    release, python_path = runtime.get("listener_release_id"), config.get("python_path")
    if not (isinstance(release, str) and len(release) == 16 and isinstance(python_path, str) and python_path
            and runtime.get("boot_id") == request.get("boot_id")
            and runtime.get("configuration_fingerprint") == request.get("configuration_fingerprint")
            and runtime.get("account_scope_sha256") == request.get("account_scope_sha256")
            and runtime.get("profile_sha256") == request.get("profile_sha256")
            and config.get("FOREX_M20_CONFIGURATION_FINGERPRINT") == request.get("configuration_fingerprint")):
        raise RuntimeError("HELD_WITNESS_RUNTIME_BINDING_INVALID")
    service = Path(r"C:\ProgramData\ForexListener\releases") / release / "m20_demo_listener_service.payload"
    completed = subprocess.run([python_path, str(service), "--held-readiness-assessment"], text=True,
                               capture_output=True, timeout=30, check=False)
    if completed.returncode != 0:
        raise RuntimeError("HELD_WITNESS_ASSESSMENT_FAILED")
    try:
        payload, assessment = json.loads(completed.stdout), None
        assessment = payload["assessment"]
    except (TypeError, KeyError, json.JSONDecodeError) as error:
        raise RuntimeError("HELD_WITNESS_ASSESSMENT_INVALID") from error
    if not (payload.get("maintenance_hold") is True and payload.get("listener_release_id") == release
            and assessment.get("marker") == "FOREX_M20_DEMO_HELD_READINESS_ASSESSMENT_OK"
            and assessment.get("server") == "GOMarketsMU-Demo" and assessment.get("currency") == "AUD"
            and assessment.get("symbol") == "EURUSD" and assessment.get("open_positions") == 0
            and assessment.get("pending_orders") == 0 and assessment.get("broker_mutation") == "NONE"
            and assessment.get("order_submission") == "STRUCTURALLY_UNAVAILABLE"):
        raise RuntimeError("HELD_WITNESS_ASSESSMENT_UNSAFE")
    witness = {"schema_version": "forex.trading-health-mt5-held-account-witness.v1",
               "observed_at_utc": now.astimezone(UTC).isoformat().replace("+00:00", "Z"),
               "account_scope_sha256": request["account_scope_sha256"], "profile_sha256": request["profile_sha256"],
               "server": "GOMarketsMU-Demo", "currency": "AUD", "symbol": "EURUSD",
               "open_positions": 0, "pending_orders": 0, "unresolved_submission": False,
               "unresolved_monitoring": False, "broker_mutation": "NONE", "entry_eligible": False}
    _write(root / "trading_health_mt5_held_account_witness.local.json", witness)
    return witness


def _independent_observer_witness(root: Path, request: dict[str, Any], now: datetime) -> bool:
    """Accept only a fresh, separately bound investor-observer witness.

    The observer task/credential is deliberately not created by this payload.
    Its binding must be release/ACL-provisioned on T480 in a later held step.
    """
    binding = _read(root / "trading_health_mt5_observer_binding.local.json")
    witness = _read(root / "trading_health_mt5_observer_witness.local.json")
    if not isinstance(binding, dict) or not isinstance(witness, dict):
        return False
    expected = {"schema_version", "task_name", "task_xml_sha256", "task_action_sha256", "principal", "terminal_path", "data_directory_sha256", "credential_target_sha256", "session_id", "binding_sha256"}
    if (set(binding) != expected or binding.get("schema_version") != "forex.trading-health-mt5-observer-binding.v1"
            or binding.get("task_name") != "CS AI Lab MT5 Observer" or binding.get("session_id") != 0):
        return False
    digest_input = {key: value for key, value in binding.items() if key != "binding_sha256"}
    import hashlib
    calculated = "sha256:" + hashlib.sha256(json.dumps(digest_input, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    if binding.get("binding_sha256") != calculated:
        return False
    observed = _parse_utc(witness.get("observed_at_utc"))
    if observed is None or (now - observed).total_seconds() < 0 or (now - observed).total_seconds() > 30:
        return False
    return (witness.get("schema_version") == "forex.trading-health-mt5-observer-witness.v1"
            and witness.get("observer_binding_sha256") == binding["binding_sha256"]
            and witness.get("boot_id") == request.get("boot_id")
            and witness.get("configuration_fingerprint") == request.get("configuration_fingerprint")
            and witness.get("account_scope_sha256") == request.get("account_scope_sha256")
            and witness.get("profile_sha256") == request.get("profile_sha256")
            and witness.get("server") == "GOMarketsMU-Demo" and witness.get("currency") == "AUD"
            and witness.get("symbol") == "EURUSD" and witness.get("open_positions") == 0
            and witness.get("pending_orders") == 0 and witness.get("unresolved_submission") is False
            and witness.get("unresolved_monitoring") is False and witness.get("broker_mutation") == "NONE"
            and witness.get("entry_eligible") is False and witness.get("order_submission") == "STRUCTURALLY_UNAVAILABLE")


def _execute_locked(root: Path, now: datetime) -> dict[str, Any]:
    request = _read(root / "trading_health_mt5_recovery_request.local.json")
    ledger = _read(root / "trading_health_mt5_recovery_ledger.local.json")
    coordinator = _read(root / "trading_health_mt5_recovery_coordinator.local.json")
    binding = _read(root / "trading_health_mt5_task_binding.local.json")
    inventory = _read(root / "trading_health_mt5_inventory.local.json")
    if not all(isinstance(item, dict) for item in (request, ledger, coordinator, binding, inventory)):
        result = _receipt(request, "REFUSED", "MT5_RECOVERY_RECORD_UNREADABLE", now)
    else:
        intent, hold = _read(root / "trading_health_intent.local.json"), _read(root / "m20_demo_maintenance_hold.local.json")
        # The coordinator is checked below as this request's own durable lease;
        # the shared validator treats any supplied nonterminal coordinator as a
        # competing protocol by design.
        reason = validate_request(request, None, now=now, binding_sha256=str(binding.get("binding_sha256")),
                                  inventory_sha256=str(inventory.get("inventory_sha256")), boot_id=str(ledger.get("boot_id")),
                                  fingerprint=str(request.get("configuration_fingerprint")))
        if reason is None and not (isinstance(intent, dict) and intent.get("mode") == "RUN_DEMO"
                                   and isinstance(hold, dict) and hold.get("enabled") is True):
            reason = "HELD_RUN_DEMO_INTENT_REQUIRED"
        if reason is None and _listener_recovery_active(root, str(request.get("boot_id"))):
            reason = "CROSS_PROTOCOL_LISTENER_RECOVERY_ACTIVE_OR_INVALID"
        authorization = _read(root / "trading_health_mt5_drill_authorization.local.json")
        if reason is None and not (isinstance(authorization, dict)
                                   and authorization.get("schema_version") == "forex.trading-health-mt5-drill-authorization.v1"
                                   and authorization.get("scope") == "M33_HELD_MT5_RECOVERY_DRILL"
                                   and authorization.get("request_id") == request.get("request_id")
                                   and authorization.get("boot_id") == request.get("boot_id")
                                   and authorization.get("configuration_fingerprint") == request.get("configuration_fingerprint")
                                   and authorization.get("maintenance_hold") is True
                                   and authorization.get("entry_eligible") is False
                                   and authorization.get("order_authority") is False):
            reason = "HELD_MT5_DRILL_AUTHORIZATION_REQUIRED"
        if reason is None and (ledger.get("phase") != "PENDING" or ledger.get("active_request_id") != request.get("request_id")
                               or coordinator.get("protocol") != "MT5_V1" or coordinator.get("phase") != "PENDING"
                               or coordinator.get("request_id") != request.get("request_id")
                               or coordinator.get("generation") != request.get("generation")
                               or coordinator.get("recovery_epoch") != request.get("recovery_epoch")
                               or coordinator.get("boot_id") != request.get("boot_id")
                               or coordinator.get("configuration_fingerprint") != request.get("configuration_fingerprint")):
            reason = "MT5_RECOVERY_OWNERSHIP_INVALID"
        if reason is not None:
            result = _receipt(request, "REFUSED", reason, now)
        elif request.get("action") == "START_ONE_MT5":
            if not _independent_observer_witness(root, request, now):
                result = _receipt(request, "REFUSED", "MT5_START_REQUIRES_INDEPENDENT_HELD_WITNESS", now)
            else:
                # Task start is intentionally a later separately reviewed,
                # fixed effect. This branch proves the witness contract only.
                result = _receipt(request, "REFUSED", "MT5_START_FIXED_EFFECT_NOT_INSTALLED", now)
        elif request.get("action") != "RECYCLE_MANAGED_SET_FLAT":
            result = _receipt(request, "REFUSED", "MT5_RECOVERY_ACTION_NOT_IMPLEMENTED", now)
        else:
            ledger["phase"] = "CLAIMED"; coordinator["phase"] = "CLAIMED"
            _write(root / "trading_health_mt5_recovery_ledger.local.json", ledger)
            _write(root / "trading_health_mt5_recovery_coordinator.local.json", coordinator)
            # Persist the claimed attempt before the single fixed effect.  The
            # stop helper independently re-enumerates every supplied identity
            # immediately before stopping it.
            _write(root / "trading_health_mt5_recovery_receipt.local.json",
                   _receipt(request, "INTERVENTION_REQUIRED", "DUPLICATE_STOP_PREPARED", now))
            try:
                fresh_inventory = _collect_fresh_inventory(root)
                targets = verify_duplicate_targets(inventory, fresh_inventory)
                reason = _fixed_duplicate_stop(targets)
            except (RuntimeError, ValueError):
                reason = "FRESH_DUPLICATE_IDENTITY_OR_INVENTORY_INVALID"
            if reason is not None:
                ledger["phase"] = "INTERVENTION_REQUIRED"; coordinator["phase"] = "INTERVENTION_REQUIRED"
                _write(root / "trading_health_mt5_recovery_ledger.local.json", ledger)
                _write(root / "trading_health_mt5_recovery_coordinator.local.json", coordinator)
                result = _receipt(request, "INTERVENTION_REQUIRED", reason, now)
            else:
                ledger["phase"] = "DISPATCHED"; coordinator["phase"] = "DISPATCHED"
                _write(root / "trading_health_mt5_recovery_ledger.local.json", ledger)
                _write(root / "trading_health_mt5_recovery_coordinator.local.json", coordinator)
                _write(root / "trading_health_mt5_recovery_dispatch.local.json",
                       _dispatch_record(request, fresh_inventory, now))
                result = _receipt(request, "INTERVENTION_REQUIRED", "DUPLICATE_STOP_DISPATCHED", now)
    _write(root / "trading_health_mt5_recovery_receipt.local.json", result)
    return result


def execute_once(root: Path, now: datetime | None = None) -> dict[str, Any]:
    now = now or _now()
    with _recovery_mutex() as acquired:
        if not acquired:
            result = _receipt(_read(root / "trading_health_mt5_recovery_request.local.json"), "REFUSED",
                              "RECOVERY_MUTEX_UNAVAILABLE_OR_HELD", now)
            _write(root / "trading_health_mt5_recovery_receipt.local.json", result)
            return result
        return _execute_locked(root, now)


def _reconcile_locked(root: Path, now: datetime) -> dict[str, Any]:
    """Verify a claimed MT5 request from fresh, held, no-order local records."""
    request = _read(root / "trading_health_mt5_recovery_request.local.json")
    ledger = _read(root / "trading_health_mt5_recovery_ledger.local.json")
    coordinator = _read(root / "trading_health_mt5_recovery_coordinator.local.json")
    binding = _read(root / "trading_health_mt5_task_binding.local.json")
    inventory = _read(root / "trading_health_mt5_inventory.local.json")
    dispatch = _read(root / "trading_health_mt5_recovery_dispatch.local.json")
    listener = _read(root / "m20_demo_listener_status.local.json")
    status = _read(root / "trading_health_status.local.json")
    hold = _read(root / "m20_demo_maintenance_hold.local.json")
    witness = None
    reason = None
    if not all(isinstance(item, dict) for item in (request, ledger, coordinator, binding, inventory, dispatch, listener, status, hold)):
        reason = "RECONCILIATION_RECORD_UNREADABLE"
    elif validate_request(request, None, now=now, binding_sha256=str(binding.get("binding_sha256")),
                           inventory_sha256=str(inventory.get("inventory_sha256")), boot_id=str(ledger.get("boot_id")),
                           fingerprint=str(request.get("configuration_fingerprint"))) is not None:
        reason = "RECONCILIATION_REQUEST_OR_BINDING_INVALID"
    elif _listener_recovery_active(root, str(request.get("boot_id"))):
        reason = "CROSS_PROTOCOL_LISTENER_RECOVERY_ACTIVE_OR_INVALID"
    elif not (ledger.get("phase") == "DISPATCHED" and coordinator.get("phase") == "DISPATCHED"
              and ledger.get("active_request_id") == request.get("request_id")
              and coordinator.get("request_id") == request.get("request_id")
              and ledger.get("last_generation") == request.get("generation")
              and ledger.get("last_recovery_epoch") == request.get("recovery_epoch")
              and coordinator.get("generation") == request.get("generation")
              and coordinator.get("recovery_epoch") == request.get("recovery_epoch")
              and coordinator.get("boot_id") == request.get("boot_id")
              and coordinator.get("configuration_fingerprint") == request.get("configuration_fingerprint")):
        reason = "RECONCILIATION_OWNERSHIP_INVALID"
    elif not (dispatch.get("schema_version") == "forex.trading-health-mt5-recovery-dispatch.v1"
              and all(dispatch.get(key) == request.get(key) for key in ("request_id", "generation", "recovery_epoch", "boot_id", "configuration_fingerprint"))
              and dispatch.get("broker_mutation") == "NONE" and dispatch.get("entry_eligible") is False
              and isinstance(_parse_utc(dispatch.get("dispatched_at_utc")), datetime)):
        reason = "RECONCILIATION_DISPATCH_LINKAGE_INVALID"
    elif not (hold.get("enabled") is True and listener.get("state") == "MAINTENANCE_HOLD"
              and status.get("entry_eligible") is False):
        reason = "RECONCILIATION_HOLD_OR_ENTRY_FENCE_INVALID"
    else:
        try:
            witness = _collect_held_account_witness(root, request, now)
        except RuntimeError:
            reason = "RECONCILIATION_HELD_ACCOUNT_WITNESS_UNAVAILABLE"
        dispatched_at = _parse_utc(dispatch.get("dispatched_at_utc"))
        heartbeat, observed, witnessed = (_parse_utc(listener.get("heartbeat_at_utc")),
                                          _parse_utc(status.get("observed_at_utc")),
                                          _parse_utc(witness.get("observed_at_utc")) if isinstance(witness, dict) else None)
        if reason is None and (dispatched_at is None or heartbeat is None or observed is None or witnessed is None
                or min(heartbeat, observed, witnessed) < dispatched_at):
            reason = "RECONCILIATION_POST_EFFECT_FRESHNESS_INVALID"
        elif reason is None and not (isinstance(listener.get("monitor"), dict) and listener["monitor"].get("state") == "IDLE"
                  and status.get("managed_mt5_count") == 1 and status.get("unattributable_mt5_count") == 0):
            reason = "RECONCILIATION_LISTENER_OR_GUARDIAN_INVALID"
        elif reason is None and not (witness.get("schema_version") == "forex.trading-health-mt5-held-account-witness.v1"
                  and witness.get("account_scope_sha256") == request.get("account_scope_sha256")
                  and witness.get("profile_sha256") == request.get("profile_sha256")
                  and witness.get("server") == "GOMarketsMU-Demo" and witness.get("currency") == "AUD"
                  and witness.get("symbol") == "EURUSD" and witness.get("open_positions") == 0
                  and witness.get("pending_orders") == 0 and witness.get("unresolved_submission") is False
                  and witness.get("unresolved_monitoring") is False and witness.get("broker_mutation") == "NONE"
                  and witness.get("entry_eligible") is False):
            reason = "RECONCILIATION_HELD_ACCOUNT_WITNESS_INVALID"
        else:
            # Never treat the pre-effect record as proof: obtain a new fixed
            # process inventory under this same mutex after the dispatch.
            try:
                inventory = _collect_fresh_inventory(root)
            except (RuntimeError, ValueError):
                inventory = None
                reason = "RECONCILIATION_FRESH_INVENTORY_UNAVAILABLE"
        processes = inventory.get("processes") if isinstance(inventory, dict) else None
        if reason is None and (not isinstance(processes, list) or any(item.get("classification") == "UNATTRIBUTABLE" for item in processes if isinstance(item, dict))):
            reason = "RECONCILIATION_INVENTORY_UNSAFE"
        elif reason is None and sum(isinstance(item, dict) and item.get("classification") == "PRIMARY_MANAGED" for item in processes) != 1:
            reason = "RECONCILIATION_ONE_MANAGED_TERMINAL_REQUIRED"
        elif reason is None and any(isinstance(item, dict) and item.get("classification") == "ADDITIONAL_MANAGED" for item in processes):
            reason = "RECONCILIATION_DUPLICATE_REMAINS"
    if reason is None:
        ledger["phase"] = "VERIFIED"; coordinator["phase"] = "VERIFIED"
        _write(root / "trading_health_mt5_recovery_ledger.local.json", ledger)
        _write(root / "trading_health_mt5_recovery_coordinator.local.json", coordinator)
        result = _receipt(request, "VERIFIED", "FRESH_HELD_INVENTORY_RECONCILED", now)
    else:
        if isinstance(ledger, dict): ledger["phase"] = "INTERVENTION_REQUIRED"; _write(root / "trading_health_mt5_recovery_ledger.local.json", ledger)
        if isinstance(coordinator, dict): coordinator["phase"] = "INTERVENTION_REQUIRED"; _write(root / "trading_health_mt5_recovery_coordinator.local.json", coordinator)
        result = _receipt(request, "INTERVENTION_REQUIRED", reason, now)
    _write(root / "trading_health_mt5_recovery_receipt.local.json", result)
    return result


def reconcile_once(root: Path, now: datetime | None = None) -> dict[str, Any]:
    now = now or _now()
    with _recovery_mutex() as acquired:
        if not acquired:
            result = _receipt(_read(root / "trading_health_mt5_recovery_request.local.json"), "INTERVENTION_REQUIRED",
                              "RECOVERY_MUTEX_UNAVAILABLE_OR_HELD", now)
            _write(root / "trading_health_mt5_recovery_receipt.local.json", result)
            return result
        return _reconcile_locked(root, now)


def main() -> int:
    parser = argparse.ArgumentParser(description="Execute no-order managed-MT5 recovery only through a fixed adapter.")
    parser.add_argument("--state-root", type=Path, required=True)
    parser.add_argument("--reconcile", action="store_true")
    args = parser.parse_args()
    print(json.dumps(reconcile_once(args.state_root) if args.reconcile else execute_once(args.state_root), separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
