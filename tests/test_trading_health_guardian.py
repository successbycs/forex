import json
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import importlib.util


SOURCE = Path("t480/trading_health_guardian.py")


def module():
    spec = importlib.util.spec_from_file_location("trading_health_guardian_test", SOURCE)
    assert spec and spec.loader
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


NOW = datetime(2026, 9, 26, 0, 30, tzinfo=UTC)


def write(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")


def listener():
    return {
        "release_id": "e786bc9636f756ce", "state": "MAINTENANCE_HOLD",
        "heartbeat_at_utc": "2026-09-26T00:29:55Z", "assessment_completed_at_utc": None,
        "runtime_binding": {"state": "MAPPED", "terminal_connected": True,
                            "terminal_trade_allowed": True, "account_trade_allowed": True,
                            "account_trade_expert": True},
        "monitor": {"state": "IDLE", "last_checked_at_utc": "2026-09-26T00:29:54Z",
                    "result": {"recovered": []}},
    }


def runtime_config():
    return {"FOREX_M20_CONFIGURATION_FINGERPRINT": "sha256:" + "c" * 64,
            "FOREX_M20_APPLICATION_REVISION": "d" * 40,
            "terminal_path": "C:\\Program Files\\MetaTrader 5\\terminal64.exe"}


def test_missing_intent_fails_closed_and_writes_schema_valid_shape(tmp_path, monkeypatch):
    g = module()
    monkeypatch.setattr(g, "_boot_id", lambda: "test-boot")
    monkeypatch.setattr(g, "_managed_mt5_inventory", lambda _: (1, 0))
    write(tmp_path / "m20_demo_listener_status.local.json", listener())
    write(tmp_path / "m20_demo_maintenance_hold.local.json", {"enabled": True})
    status = g.run_once(tmp_path, NOW)
    assert status["state"] == "BLOCKED_POLICY"
    assert status["entry_eligible"] is False
    assert json.loads((tmp_path / "trading_health_status.local.json").read_text()) == status


def test_monitor_only_reports_hold_without_publishing_entry_authority(tmp_path, monkeypatch):
    g = module()
    monkeypatch.setattr(g, "_boot_id", lambda: "test-boot")
    monkeypatch.setattr(g, "_managed_mt5_inventory", lambda _: (1, 0))
    write(tmp_path / "m20_demo_listener_status.local.json", listener())
    write(tmp_path / "m20_demo_maintenance_hold.local.json", {"enabled": True})
    write(tmp_path / "trading_health_intent.local.json", {
        "schema_version": "forex.trading-health-intent.v1", "mode": "MONITOR_ONLY",
        "revision": 1, "set_at_utc": "2026-09-26T00:00:00Z",
        "account_scope_sha256": "sha256:" + "a" * 64, "profile_sha256": "sha256:" + "b" * 64,
    })
    status = g.run_once(tmp_path, NOW)
    assert status["state"] == "MONITOR_ONLY"
    assert status["execution_capable"] is True
    assert status["entry_eligible"] is False


def test_stale_or_missing_listener_is_visible_and_never_becomes_entry_eligible(tmp_path, monkeypatch):
    g = module()
    monkeypatch.setattr(g, "_boot_id", lambda: "test-boot")
    monkeypatch.setattr(g, "_managed_mt5_inventory", lambda _: (1, 0))
    stopped = listener()
    stopped["state"] = "STOPPED"
    write(tmp_path / "m20_demo_listener_status.local.json", stopped)
    write(tmp_path / "m20_demo_listener_service.local.json", runtime_config())
    write(tmp_path / "trading_health_intent.local.json", {
        "schema_version": "forex.trading-health-intent.v1", "mode": "RUN_DEMO",
        "revision": 1, "set_at_utc": "2026-09-26T00:00:00Z",
        "account_scope_sha256": "sha256:" + "a" * 64, "profile_sha256": "sha256:" + "b" * 64,
    })
    status = g.run_once(tmp_path, NOW)
    assert status["state"] == "RECOVERING_LISTENER"
    assert status["reasons"] == ["LISTENER_ABSENT"]
    assert status["entry_eligible"] is False
    request = json.loads((tmp_path / "trading_health_recovery_request.local.json").read_text())
    assert request["state"] == "PENDING" and request["action"] == "START_LISTENER"


def test_non_recovery_cycle_does_not_write_an_invalid_terminal_request(tmp_path, monkeypatch):
    g = module()
    monkeypatch.setattr(g, "_boot_id", lambda: "test-boot")
    monkeypatch.setattr(g, "_managed_mt5_inventory", lambda _: (1, 0))
    write(tmp_path / "m20_demo_listener_status.local.json", listener())
    write(tmp_path / "m20_demo_maintenance_hold.local.json", {"enabled": True})
    write(tmp_path / "trading_health_recovery_request.local.json", {"generation": 7})
    g.run_once(tmp_path, NOW)
    request = json.loads((tmp_path / "trading_health_recovery_request.local.json").read_text())
    # Requests have one actionable PENDING shape.  Terminal information belongs
    # in a receipt, so a benign guardian cycle cannot manufacture an invalid
    # v2 request record.
    assert request == {"generation": 7}


def test_guardian_retains_owned_pending_request_instead_of_overwriting_it(tmp_path, monkeypatch):
    g = module()
    monkeypatch.setattr(g, "_boot_id", lambda: "test-boot")
    monkeypatch.setattr(g, "_managed_mt5_inventory", lambda _: (1, 0))
    stopped = listener()
    stopped["state"] = "STOPPED"
    write(tmp_path / "m20_demo_listener_status.local.json", stopped)
    write(tmp_path / "m20_demo_listener_service.local.json", runtime_config())
    write(tmp_path / "trading_health_intent.local.json", {
        "schema_version": "forex.trading-health-intent.v1", "mode": "RUN_DEMO", "revision": 1,
        "set_at_utc": "2026-09-26T00:00:00Z", "account_scope_sha256": "sha256:" + "a" * 64,
        "profile_sha256": "sha256:" + "b" * 64,
    })
    g.run_once(tmp_path, NOW)
    first = json.loads((tmp_path / "trading_health_recovery_request.local.json").read_text())
    status = g.run_once(tmp_path, NOW.replace(second=31))
    second = json.loads((tmp_path / "trading_health_recovery_request.local.json").read_text())
    assert second == first
    assert status["recovery_request_id"] == first["request_id"]
    assert status["recovery_phase"] == "PENDING"


def test_corrupt_recovery_ledger_opens_circuit_and_requires_intervention(tmp_path, monkeypatch):
    g = module()
    monkeypatch.setattr(g, "_boot_id", lambda: "test-boot")
    monkeypatch.setattr(g, "_managed_mt5_inventory", lambda _: (1, 0))
    write(tmp_path / "m20_demo_listener_status.local.json", listener())
    write(tmp_path / "trading_health_intent.local.json", {
        "schema_version": "forex.trading-health-intent.v1", "mode": "RUN_DEMO", "revision": 1,
        "set_at_utc": "2026-09-26T00:00:00Z", "account_scope_sha256": "sha256:" + "a" * 64,
        "profile_sha256": "sha256:" + "b" * 64,
    })
    (tmp_path / "trading_health_recovery_ledger.local.json").write_text("not-json")
    status = g.run_once(tmp_path, NOW)
    assert status["state"] == "CIRCUIT_OPEN"
    assert status["recovery_phase"] == "INTERVENTION_REQUIRED"
    assert status["entry_eligible"] is False


def test_active_mt5_coordinator_blocks_listener_request(tmp_path, monkeypatch):
    g = module()
    monkeypatch.setattr(g, "_boot_id", lambda: "test-boot")
    monkeypatch.setattr(g, "_managed_mt5_inventory", lambda _: (1, 0))
    stopped = listener(); stopped["state"] = "STOPPED"
    write(tmp_path / "m20_demo_listener_status.local.json", stopped)
    write(tmp_path / "m20_demo_listener_service.local.json", runtime_config())
    write(tmp_path / "trading_health_intent.local.json", {"schema_version":"forex.trading-health-intent.v1","mode":"RUN_DEMO","revision":1,"set_at_utc":"2026-09-26T00:00:00Z","account_scope_sha256":"sha256:"+"a"*64,"profile_sha256":"sha256:"+"b"*64})
    write(tmp_path / "trading_health_mt5_recovery_coordinator.local.json", {"schema_version":"forex.trading-health-recovery-coordinator.v1","recovery_epoch":1,"protocol":"MT5_V1","request_id":"a"*32,"generation":1,"boot_id":"test-boot","configuration_fingerprint":runtime_config()["FOREX_M20_CONFIGURATION_FINGERPRINT"],"phase":"PENDING"})
    status = g.run_once(tmp_path, NOW)
    assert status["recovery_phase"] == "INTERVENTION_REQUIRED"
    assert "MT5_RECOVERY_PARTIAL_BUNDLE" in status["reasons"]

def test_partial_mt5_recovery_bundle_is_fenced(tmp_path, monkeypatch):
    g = module(); monkeypatch.setattr(g, "_boot_id", lambda: "test-boot"); monkeypatch.setattr(g, "_managed_mt5_inventory", lambda _: (1, 0))
    write(tmp_path / "m20_demo_listener_status.local.json", listener()); write(tmp_path / "m20_demo_listener_service.local.json", runtime_config())
    write(tmp_path / "trading_health_intent.local.json", {"schema_version":"forex.trading-health-intent.v1","mode":"RUN_DEMO","revision":1,"set_at_utc":"2026-09-26T00:00:00Z","account_scope_sha256":"sha256:"+"a"*64,"profile_sha256":"sha256:"+"b"*64})
    write(tmp_path / "trading_health_mt5_recovery_request.local.json", {"schema_version":"forex.trading-health-mt5-recovery-request.v1","request_id":"a"*32})
    status=g.run_once(tmp_path,NOW)
    assert status["recovery_phase"]=="INTERVENTION_REQUIRED" and "MT5_RECOVERY_PARTIAL_BUNDLE" in status["reasons"]


def test_absent_mt5_refuses_without_writing_listener_v2_request(tmp_path, monkeypatch):
    g = module()
    monkeypatch.setattr(g, "_boot_id", lambda: "test-boot")
    monkeypatch.setattr(g, "_managed_mt5_inventory", lambda _: (0, 0))
    write(tmp_path / "m20_demo_listener_status.local.json", listener())
    write(tmp_path / "m20_demo_listener_service.local.json", runtime_config())
    write(tmp_path / "m20_demo_maintenance_hold.local.json", {"enabled": True})
    write(tmp_path / "trading_health_intent.local.json", {"schema_version":"forex.trading-health-intent.v1","mode":"RUN_DEMO","revision":1,"set_at_utc":"2026-09-26T00:00:00Z","account_scope_sha256":"sha256:"+"a"*64,"profile_sha256":"sha256:"+"b"*64})
    status = g.run_once(tmp_path, NOW)
    assert status["state"] == "RECOVERING_MT5"
    assert status["recovery_phase"] == "REFUSED"
    assert "MT5_START_REQUIRES_INDEPENDENT_HELD_WITNESS" in status["reasons"]
    assert not (tmp_path / "trading_health_recovery_request.local.json").exists()
    assert not (tmp_path / "trading_health_mt5_recovery_request.local.json").exists()


def test_duplicate_mt5_publishes_only_bound_mt5_protocol_request(tmp_path, monkeypatch):
    g = module()
    monkeypatch.setattr(g, "_boot_id", lambda: "test-boot")
    monkeypatch.setattr(g, "_managed_mt5_inventory", lambda _: (2, 0))
    write(tmp_path / "m20_demo_listener_status.local.json", listener())
    write(tmp_path / "m20_demo_listener_service.local.json", runtime_config())
    write(tmp_path / "m20_demo_maintenance_hold.local.json", {"enabled": True})
    write(tmp_path / "trading_health_intent.local.json", {"schema_version":"forex.trading-health-intent.v1","mode":"RUN_DEMO","revision":1,"set_at_utc":"2026-09-26T00:00:00Z","account_scope_sha256":"sha256:"+"a"*64,"profile_sha256":"sha256:"+"b"*64})
    binding = {"schema_version":"forex.trading-health-mt5-task-binding.v1","task_name":"Forex-M20-Demo-Listener","task_xml_sha256":"sha256:"+"e"*64,"task_action_sha256":"sha256:"+"f"*64,"principal":"SYSTEM","terminal_path":"C:/MT5/terminal64.exe","terminal_config_sha256":"sha256:"+"1"*64,"session_id":0,"parent_path":"C:/Windows/System32/taskeng.exe","command_line_sha256":"sha256:"+"2"*64,"binding_sha256":None}
    binding["binding_sha256"] = g._digest_without(binding, "binding_sha256")
    inventory = {"schema_version":"forex.trading-health-mt5-inventory.v1","processes":[{"pid":1,"path":"C:/MT5/terminal64.exe","session_id":0,"command_line_sha256":"sha256:"+"2"*64,"parent_pid":0,"parent_path":"C:/Windows/System32/taskeng.exe","creation_id":"first","classification":"PRIMARY_MANAGED"},{"pid":2,"path":"C:/MT5/terminal64.exe","session_id":0,"command_line_sha256":"sha256:"+"2"*64,"parent_pid":0,"parent_path":"C:/Windows/System32/taskeng.exe","creation_id":"second","classification":"ADDITIONAL_MANAGED"}],"inventory_sha256":None}
    inventory["inventory_sha256"] = g._digest_without(inventory, "inventory_sha256")
    write(tmp_path / "trading_health_mt5_task_binding.local.json", binding)
    write(tmp_path / "trading_health_mt5_inventory.local.json", inventory)
    status = g.run_once(tmp_path, NOW)
    assert status["state"] == "RECOVERING_MT5", status
    assert status["recovery_phase"] == "PENDING", status
    request = json.loads((tmp_path / "trading_health_mt5_recovery_request.local.json").read_text())
    coordinator = json.loads((tmp_path / "trading_health_mt5_recovery_coordinator.local.json").read_text())
    assert request["action"] == "RECYCLE_MANAGED_SET_FLAT"
    assert request["entry_eligible"] is False
    assert coordinator["protocol"] == "MT5_V1" and coordinator["request_id"] == request["request_id"]
    assert not (tmp_path / "trading_health_recovery_request.local.json").exists()


def test_unattributable_terminal_process_is_an_ownership_incident(tmp_path, monkeypatch):
    g = module()
    monkeypatch.setattr(g, "_boot_id", lambda: "test-boot")
    monkeypatch.setattr(g, "_managed_mt5_inventory", lambda _: (1, 1))
    write(tmp_path / "m20_demo_listener_status.local.json", listener())
    write(tmp_path / "trading_health_intent.local.json", {
        "schema_version": "forex.trading-health-intent.v1", "mode": "MONITOR_ONLY",
        "revision": 1, "set_at_utc": "2026-09-26T00:00:00Z",
        "account_scope_sha256": "sha256:" + "a" * 64, "profile_sha256": "sha256:" + "b" * 64,
    })
    status = g.run_once(tmp_path, NOW)
    assert status["state"] == "BLOCKED_OWNERSHIP"
    assert status["entry_eligible"] is False


def test_immutable_guardian_release_loads_its_adjacent_policy_payload(tmp_path):
    release = tmp_path / "guardian-releases" / "dbe9c0058259b577"
    release.mkdir(parents=True)
    guardian = release / "trading_health_guardian.payload"
    shutil.copyfile(SOURCE, guardian)
    shutil.copyfile("src/forex/trading_health.py", release / "trading_health.payload")
    state = tmp_path / "state"
    state.mkdir()
    write(state / "m20_demo_listener_status.local.json", listener())
    write(state / "m20_demo_maintenance_hold.local.json", {"enabled": True})
    completed = subprocess.run(
        [sys.executable, str(guardian), "--state-root", str(state)],
        check=False, capture_output=True, text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert json.loads((state / "trading_health_status.local.json").read_text())["entry_eligible"] is False
