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
    monkeypatch.setattr(g, "_managed_mt5_inventory", lambda _: (None, 0))
    write(tmp_path / "trading_health_intent.local.json", {
        "schema_version": "forex.trading-health-intent.v1", "mode": "RUN_DEMO",
        "revision": 1, "set_at_utc": "2026-09-26T00:00:00Z",
        "account_scope_sha256": "sha256:" + "a" * 64, "profile_sha256": "sha256:" + "b" * 64,
    })
    status = g.run_once(tmp_path, NOW)
    assert status["state"] in {"BLOCKED_SESSION", "BLOCKED_DEPENDENCY"}
    assert status["entry_eligible"] is False


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
