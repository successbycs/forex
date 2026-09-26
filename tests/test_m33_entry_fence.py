import importlib.util
import json
import sys
import types
from datetime import UTC, datetime, timedelta
from pathlib import Path


NOW = datetime(2026, 9, 26, 1, 0, tzinfo=UTC)


def runner(monkeypatch):
    monkeypatch.setitem(sys.modules, "MetaTrader5", types.SimpleNamespace(TIMEFRAME_M1=1, TIMEFRAME_M5=5, TIMEFRAME_H1=60))
    spec = importlib.util.spec_from_file_location("m33_fence_runner", Path("t480/m20_demo_trading_session.py"))
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write(root, name, value):
    (root / name).write_text(json.dumps(value), encoding="utf-8")


def eligible_status():
    return {"schema_version": "forex.trading-health-status.v1", "boot_id": "boot", "generation": 4,
            "desired_mode": "RUN_DEMO", "entry_eligible": True, "state": "READY_FOR_ASSESSMENT"}


def permit(**changes):
    value = {"schema_version": "forex.trading-health-permit.v1", "boot_id": "boot", "generation": 4,
             "issued_at_utc": (NOW - timedelta(seconds=5)).isoformat(),
             "expires_at_utc": (NOW + timedelta(seconds=110)).isoformat(), "guardian_id": "guardian"}
    value.update(changes)
    return value


def test_fence_is_inert_for_existing_held_release(monkeypatch, tmp_path):
    r = runner(monkeypatch)
    monkeypatch.setattr(r, "_m33_state_root", lambda: tmp_path)
    monkeypatch.delenv(r.M33_ENTRY_FENCE_ENV, raising=False)
    assert r._m33_entry_fence_refusal(NOW) is None


def test_fence_refuses_missing_expired_and_mismatched_permits(monkeypatch, tmp_path):
    r = runner(monkeypatch)
    monkeypatch.setattr(r, "_m33_state_root", lambda: tmp_path)
    monkeypatch.setenv(r.M33_ENTRY_FENCE_ENV, "true")
    assert r._m33_entry_fence_refusal(NOW) == "M33_ENTRY_FENCE_PERMIT_MISSING_OR_UNREADABLE"
    write(tmp_path, "trading_health_status.local.json", eligible_status())
    write(tmp_path, "trading_health_permit.local.json", permit(expires_at_utc=(NOW - timedelta(seconds=1)).isoformat()))
    assert r._m33_entry_fence_refusal(NOW) == "M33_ENTRY_FENCE_PERMIT_EXPIRED"
    write(tmp_path, "trading_health_permit.local.json", permit(generation=5))
    assert r._m33_entry_fence_refusal(NOW) == "M33_ENTRY_FENCE_PERMIT_BINDING_MISMATCH"


def test_fence_accepts_only_current_matching_permit(monkeypatch, tmp_path):
    r = runner(monkeypatch)
    monkeypatch.setattr(r, "_m33_state_root", lambda: tmp_path)
    monkeypatch.setenv(r.M33_ENTRY_FENCE_ENV, "true")
    write(tmp_path, "trading_health_status.local.json", eligible_status())
    write(tmp_path, "trading_health_permit.local.json", permit())
    assert r._m33_entry_fence_refusal(NOW) is None
