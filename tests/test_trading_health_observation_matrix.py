import importlib.util
from datetime import UTC, datetime


SOURCE = "t480/trading_health_observation_matrix.py"
NOW = datetime(2026, 9, 26, 5, 0, tzinfo=UTC)


def module():
    spec = importlib.util.spec_from_file_location("trading_health_matrix_test", SOURCE)
    assert spec and spec.loader
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def test_matrix_is_fail_closed_and_marks_in_memory_variants(tmp_path, monkeypatch):
    matrix = module()
    guardian = matrix._load_guardian()
    listener = {
        "release_id": "29f366fc34d08917", "state": "MAINTENANCE_HOLD",
        "runtime_binding": {"server": "GOMarketsMU-Demo", "currency": "AUD", "state": "MAPPED"},
    }
    monkeypatch.setattr(guardian, "_read_json", lambda path: {"enabled": True} if "hold" in path.name else listener)
    from forex.trading_health import Observation
    observation = Observation(session_ok=True, managed_mt5_count=1, mt5_identity_ok=True,
                              mt5_responding=True, permissions_ok=True, broker_connected=True,
                              data_fresh=True, db_available=True, listener_present=True,
                              listener_heartbeat_age_s=1, monitoring_fresh=True)
    output = tmp_path / "matrix.json"
    record = matrix.run_matrix(tmp_path, output, NOW, observation_loader=lambda *_: (observation, None, 0, []))
    assert output.exists() and record["broker_mutation"] == "NONE"
    assert {x["case_id"] for x in record["cases"]} == {
        "healthy_monitor_only", "operator_stopped", "listener_absent", "listener_stalled",
        "managed_duplicate_flat", "audit_dependency_blocked",
    }
    assert all(x["entry_eligible"] is False for x in record["cases"])
    assert next(x for x in record["cases"] if x["case_id"] == "managed_duplicate_flat")["simulated_fields"] == [
        "exposure_flat", "inflight_unresolved", "managed_mt5_count",
    ]
