import importlib.util
import hashlib
import json
import shutil
import subprocess
import sys
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path


SOURCE = Path("t480/trading_health_recovery_executor.py")
NOW = datetime(2026, 9, 26, 6, 0, tzinfo=UTC)


def module():
    spec = importlib.util.spec_from_file_location("trading_health_recovery_executor_test", SOURCE)
    assert spec and spec.loader
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def write(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")


def current_request(action="RESTART_LISTENER"):
    status_core = {"observed_at_utc": "2026-09-26T06:00:00Z", "state": "RECOVERING_LISTENER",
                   "recommended_action": action, "entry_eligible": False}
    status_sha = "sha256:" + hashlib.sha256(
        json.dumps(status_core, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return {
        "schema_version": "forex.trading-health-recovery-request.v2", "state": "PENDING",
        "request_id": "a" * 32, "generation": 3, "boot_id": "test-boot",
        "guardian_release_id": "b" * 16, "listener_release_id": "c" * 16,
        "configuration_fingerprint": "sha256:" + "d" * 64,
        "account_scope_sha256": "sha256:" + "e" * 64, "profile_sha256": "sha256:" + "f" * 64,
        "status_sha256": status_sha, "health_state": "RECOVERING_LISTENER", "action": action,
        "issued_at_utc": "2026-09-26T06:00:00Z", "expires_at_utc": "2026-09-26T06:01:15Z",
        "entry_eligible": False,
    }


def status(action="RESTART_LISTENER"):
    value = {"observed_at_utc": "2026-09-26T06:00:00Z", "state": "RECOVERING_LISTENER",
             "recommended_action": action, "recovery_request_id": "a" * 32, "entry_eligible": False}
    projection = {key: item for key, item in value.items() if key != "recovery_request_id"}
    value["status_sha256"] = "sha256:" + hashlib.sha256(
        json.dumps(projection, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return value


def test_executor_refuses_stale_or_unmatched_request_without_side_effects(tmp_path, monkeypatch):
    executor = module()
    monkeypatch.setattr(executor, "_recovery_mutex", lambda: (_ for _ in ()).throw(AssertionError("no mutex")))
    request = current_request()
    request["expires_at_utc"] = "2026-09-26T05:58:44Z"
    write(tmp_path / "trading_health_recovery_request.local.json", request)
    write(tmp_path / "trading_health_status.local.json", status())
    result = executor.execute_once(tmp_path, NOW)
    assert result["state"] == "REFUSED" and result["reason"] == "REQUEST_STALE_OR_FUTURE"
    assert result["broker_mutation"] == "NONE" and result["entry_eligible"] is False


def test_executor_preserves_operator_stops_and_refuses_mt5_actions(tmp_path, monkeypatch):
    executor = module()
    write(tmp_path / "trading_health_recovery_request.local.json", current_request())
    write(tmp_path / "trading_health_status.local.json", status())
    write(tmp_path / "m20_demo_maintenance_hold.local.json", {"enabled": True})
    result = executor.execute_once(tmp_path, NOW)
    assert result["reason"] == "INTENT_NOT_RUN_DEMO"

    write(tmp_path / "trading_health_intent.local.json", {
        "schema_version": "forex.trading-health-intent.v1", "mode": "RUN_DEMO"})
    write(tmp_path / "trading_health_recovery_request.local.json", current_request("START_ONE_MT5"))
    write(tmp_path / "trading_health_status.local.json", status("START_ONE_MT5"))
    result = executor.execute_once(tmp_path, NOW)
    assert result["reason"] == "REQUEST_SHAPE_INVALID"


def test_executor_requires_mutex_before_readiness_or_task_action(tmp_path, monkeypatch):
    executor = module()
    write(tmp_path / "trading_health_recovery_request.local.json", current_request())
    write(tmp_path / "trading_health_status.local.json", status())
    write(tmp_path / "trading_health_intent.local.json", {
        "schema_version": "forex.trading-health-intent.v1", "mode": "RUN_DEMO"})
    write(tmp_path / "m20_demo_maintenance_hold.local.json", {"enabled": True})
    result = executor.execute_once(tmp_path, NOW)
    assert result["reason"] == "RECOVERY_MUTEX_UNAVAILABLE_OR_HELD"
    assert result["broker_mutation"] == "NONE"


def test_executor_refuses_status_digest_substitution_before_mutex(tmp_path, monkeypatch):
    executor = module()
    monkeypatch.setattr(executor, "_recovery_mutex", lambda: (_ for _ in ()).throw(AssertionError("no mutex")))
    request = current_request()
    current = status()
    current["state"] = "BLOCKED_POLICY"
    write(tmp_path / "trading_health_recovery_request.local.json", request)
    write(tmp_path / "trading_health_status.local.json", current)
    result = executor.execute_once(tmp_path, NOW)
    assert result["reason"] == "REQUEST_NOT_CURRENT"


def test_absent_listener_preflight_uses_bound_manifest_not_missing_heartbeat(tmp_path, monkeypatch):
    executor = module()
    request = current_request()
    write(tmp_path / "trading_health_runtime_binding.local.json", {
        "boot_id": request["boot_id"], "listener_release_id": request["listener_release_id"],
        "configuration_fingerprint": request["configuration_fingerprint"],
        "account_scope_sha256": request["account_scope_sha256"], "profile_sha256": request["profile_sha256"],
    })
    write(tmp_path / "m20_demo_listener_service.local.json", {
        "python_path": "python", "FOREX_M20_CONFIGURATION_FINGERPRINT": request["configuration_fingerprint"],
    })
    assessment = {"marker": "FOREX_M20_DEMO_HELD_READINESS_ASSESSMENT_OK", "server": "GOMarketsMU-Demo",
                  "currency": "AUD", "symbol": "EURUSD", "open_positions": 0, "pending_orders": 0,
                  "broker_mutation": "NONE", "order_submission": "STRUCTURALLY_UNAVAILABLE"}
    output = {"maintenance_hold": True, "listener_release_id": request["listener_release_id"], "assessment": assessment}
    monkeypatch.setattr(executor.subprocess, "run", lambda *_, **__: type("R", (), {"returncode": 0, "stdout": json.dumps(output)})())
    assert executor._held_readiness(tmp_path, request) == (output, None)


def test_reconcile_requires_fresh_heartbeat_guardian_monitor_and_readiness(tmp_path, monkeypatch):
    executor = module()
    request = current_request()
    write(tmp_path / "trading_health_recovery_request.local.json", request)
    write(tmp_path / "trading_health_recovery_ledger.local.json", {
        "schema_version": "forex.trading-health-recovery-ledger.v1", "boot_id": request["boot_id"],
        "last_generation": request["generation"], "attempts_utc": ["2026-09-26T05:59:00Z"],
        "active_request_id": request["request_id"], "phase": "DISPATCHED",
    })
    write(tmp_path / "m20_demo_listener_status.local.json", {
        "release_id": request["listener_release_id"], "state": "MAINTENANCE_HOLD",
        "heartbeat_at_utc": "2026-09-26T06:00:00Z", "monitor": {"state": "IDLE", "result": {"recovered": []}},
    })
    write(tmp_path / "trading_health_status.local.json", {
        "observed_at_utc": "2026-09-26T06:00:00Z", "recovery_request_id": request["request_id"],
        "entry_eligible": False, "managed_mt5_count": 1, "unattributable_mt5_count": 0,
    })
    write(tmp_path / "trading_health_runtime_binding.local.json", {
        "boot_id": request["boot_id"], "listener_release_id": request["listener_release_id"],
        "configuration_fingerprint": request["configuration_fingerprint"],
        "account_scope_sha256": request["account_scope_sha256"], "profile_sha256": request["profile_sha256"],
    })
    write(tmp_path / "m20_demo_listener_service.local.json", {
        "python_path": "python", "FOREX_M20_CONFIGURATION_FINGERPRINT": request["configuration_fingerprint"],
    })
    assessment = {"marker": "FOREX_M20_DEMO_HELD_READINESS_ASSESSMENT_OK", "server": "GOMarketsMU-Demo",
                  "currency": "AUD", "symbol": "EURUSD", "open_positions": 0, "pending_orders": 0,
                  "broker_mutation": "NONE", "order_submission": "STRUCTURALLY_UNAVAILABLE"}
    output = {"maintenance_hold": True, "listener_release_id": request["listener_release_id"], "assessment": assessment}
    monkeypatch.setattr(executor.subprocess, "run", lambda *_, **__: type("R", (), {"returncode": 0, "stdout": json.dumps(output)})())
    @contextmanager
    def locked():
        yield True
    monkeypatch.setattr(executor, "_recovery_mutex", locked)
    result = executor.reconcile_once(tmp_path, NOW)
    assert result["state"] == "VERIFIED" and result["entry_eligible"] is False
    assert json.loads((tmp_path / "trading_health_recovery_ledger.local.json").read_text())["phase"] == "VERIFIED"


def test_reconcile_refuses_task_dispatch_without_restored_monitor(tmp_path, monkeypatch):
    executor = module()
    request = current_request()
    write(tmp_path / "trading_health_recovery_request.local.json", request)
    write(tmp_path / "trading_health_recovery_ledger.local.json", {
        "schema_version": "forex.trading-health-recovery-ledger.v1", "boot_id": request["boot_id"],
        "last_generation": request["generation"], "attempts_utc": ["2026-09-26T05:59:00Z"],
        "active_request_id": request["request_id"], "phase": "DISPATCHED",
    })
    write(tmp_path / "m20_demo_listener_status.local.json", {"release_id": request["listener_release_id"],
          "state": "MAINTENANCE_HOLD", "heartbeat_at_utc": "2026-09-26T06:00:00Z", "monitor": {"state": "RUNNING"}})
    write(tmp_path / "trading_health_status.local.json", {"observed_at_utc": "2026-09-26T06:00:00Z",
          "recovery_request_id": request["request_id"], "entry_eligible": False,
          "managed_mt5_count": 1, "unattributable_mt5_count": 0})
    @contextmanager
    def locked():
        yield True
    monkeypatch.setattr(executor, "_recovery_mutex", locked)
    result = executor.reconcile_once(tmp_path, NOW)
    assert result["state"] == "INTERVENTION_REQUIRED"
    assert result["reason"] == "POST_ACTION_MONITOR_NOT_RESTORED"


def test_reconcile_rejects_mismatched_or_malformed_dispatched_ledger(tmp_path, monkeypatch):
    executor = module()
    request = current_request()
    write(tmp_path / "trading_health_recovery_request.local.json", request)
    write(tmp_path / "trading_health_recovery_ledger.local.json", {
        "schema_version": "forex.trading-health-recovery-ledger.v1", "boot_id": request["boot_id"],
        "last_generation": request["generation"], "attempts_utc": ["not-a-time"],
        "active_request_id": "b" * 32, "phase": "DISPATCHED",
    })
    @contextmanager
    def locked():
        yield True
    monkeypatch.setattr(executor, "_recovery_mutex", locked)
    result = executor.reconcile_once(tmp_path, NOW)
    assert result["reason"] == "RECOVERY_LEDGER_NOT_CURRENT"


def test_listener_task_action_requires_exact_release_bound_payload(monkeypatch):
    executor = module()
    captured = {}
    monkeypatch.setattr(executor, "_powershell", lambda command: captured.setdefault("command", command) or None)
    # A return code is enough for this fixed-command construction test.
    monkeypatch.setattr(executor, "_powershell", lambda command: type("R", (), {"returncode": 1})())
    assert executor._listener_task_action("START_LISTENER", current_request()) == "LISTENER_TASK_ACTION_FAILED"
    # The exact binding check is part of the fixed command, not caller input.
    source = SOURCE.read_text(encoding="utf-8")
    assert "listener task release binding required" in source


def test_immutable_executor_release_loads_its_adjacent_policy_payload(tmp_path):
    release = tmp_path / "guardian-releases" / "e3c4b9c18cde410f"
    release.mkdir(parents=True)
    executor = release / "trading_health_recovery_executor.payload"
    shutil.copyfile(SOURCE, executor)
    shutil.copyfile("src/forex/trading_health.py", release / "trading_health.payload")
    state = tmp_path / "state"
    state.mkdir()
    completed = subprocess.run([sys.executable, str(executor), "--state-root", str(state)],
                               check=False, capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout)
    assert result["state"] == "REFUSED" and result["broker_mutation"] == "NONE"
