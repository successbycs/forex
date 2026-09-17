import importlib.util
import importlib.machinery
import json
from pathlib import Path

import pytest


SOURCE = Path("t480/m20_demo_listener_service.py")


@pytest.fixture(autouse=True)
def isolate_protected_restart_drill(tmp_path, monkeypatch):
    """Keep every dynamically loaded listener module off the repository tree."""
    original = importlib.machinery.SourceFileLoader.exec_module

    def load(loader, module):
        original(loader, module)
        if Path(getattr(module, "__file__", "")).resolve() == SOURCE.resolve():
            monkeypatch.setattr(module, "PROTECTED_RESTART_DRILL_PATH", tmp_path / "restart-drill.json")

    monkeypatch.setattr(importlib.machinery.SourceFileLoader, "exec_module", load)


def test_permanent_listener_is_a_bounded_m1_supervisor_with_status_and_stop():
    source = SOURCE.read_text(encoding="utf-8")
    assert "ASSESSMENT_INTERVAL_SECONDS = 5" in source
    assert "WAITING_FOR_ACTIVE_DEMO_LEASE" in source
    assert "m20_demo_listener_status.local.json" in source
    assert "m20_demo_listener.stop" in source
    assert "M20 listener service accepts no arguments" in source
    assert "M20 monitor recovery exceeded its eight-second bound" in source
    assert "timeout=8" in source
    assert "M20 assessment exceeded its twelve-second bound" in source
    assert "timeout=12" in source
    assert "m20_demo_assessment_total.local.json" in source
    assert '"m20_demo_assessment_spool" / ROOT.name' in source
    assert "assessment_total" in source and "process_iteration" in source
    assert "WAITING_FOR_FRESH_MT5_QUOTE" in source
    assert "--quote-identity" in source
    assert "m20_demo_assessment_gate.local.json" in source
    assert "last_assessed_tick_time_msc" in source
    assert "last_quote: dict[str, Any] | None = None" in source
    assert '"monitor": monitor_state, "quote": last_quote' in source
    assert "FOREX_M20_POSTGRES_DSN\"" not in source.split("required =", 1)[1].split("if not", 1)[0]
    assert '"FOREX_M20_MINIMUM_NET_PROFIT_AUD"' in source
    assert '"FOREX_M20_DISCORD_WEBHOOK_URL"' in source
    assert "order_send" not in source


def test_runner_preserves_unresolved_history_for_operator_reconciliation():
    source = Path("t480/m20_demo_trading_session.py").read_text(encoding="utf-8")
    bridge = Path("t480/m20_postgres_audit_bridge.py").read_text(encoding="utf-8")
    assert '"archive-history-unavailable-positions"' not in source
    assert "Missing or incomplete history is unresolved exposure/accounting" in source
    assert "archive_history_unavailable_positions" not in bridge
    assert "M20 closed outcome has no durable open position" in bridge


def test_runner_uses_the_mt5_position_history_overload_for_reconciliation():
    source = Path("t480/m20_demo_trading_session.py").read_text(encoding="utf-8")
    assert "history_deals_get(position=position_identifier)" in source
    assert "datetime.now(timezone.utc) + timedelta(seconds=5), position=ticket" not in source


def test_runner_persists_complete_non_secret_mt5_rejection_context():
    source = Path("t480/m20_demo_trading_session.py").read_text(encoding="utf-8")
    bridge = Path("t480/m20_postgres_audit_bridge.py").read_text(encoding="utf-8")
    for required in (
        "forex.m20.mt5-result-context.v1", "broker_comment", "requested_price", "observed_bid",
        "trade_tick_size", "stops_level_points", "reservation_slot_number", "position_ticket",
    ):
        assert required in source
    assert "M20 rejected broker result lacks fixed diagnostic context" in bridge


def test_runner_has_a_fixed_demo_only_quote_identity_without_order_submission():
    source = Path("t480/m20_demo_trading_session.py").read_text(encoding="utf-8")
    quote = source[source.index("def quote_identity("):source.index("def _wait_for_position(")]
    assert "FOREX_M20_DEMO_QUOTE_IDENTITY_OK" in quote
    assert "GOMarketsMU-Demo" in quote
    assert "EURUSD" in quote
    assert "order_send" not in quote


def test_runner_validates_the_quote_trigger_before_assessment():
    source = Path("t480/m20_demo_trading_session.py").read_text(encoding="utf-8")
    assert "--assessment-trigger-tick-ms" in source
    assert "M20 assessment tick predates its fresh-quote trigger" in source


def test_listener_module_loads_without_mt5_dependency():
    spec = importlib.util.spec_from_file_location("m20_listener_service", SOURCE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.ASSESSMENT_INTERVAL_SECONDS == 5
    assert module._nzst("2026-09-03T09:30:00Z") == "03/09/26 21:30:00 NZST"


def test_latest_assessment_retention_is_replace_only_and_never_listener_critical(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("m20_listener_service", SOURCE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    target = tmp_path / "latest.json"
    monkeypatch.setattr(module, "LATEST_ASSESSMENT_PATH", target)
    output = {
        "marker": "FOREX_M20_DEMO_TRADING_OPERATION_OK", "schema_version": "forex.m20.demo-trading-operation.v1",
        "operation": "m20_demo_trading_session", "server": "GOMarketsMU-Demo", "symbol": "EURUSD",
        "captured_at_utc": "2026-09-12T00:00:01Z", "configuration_fingerprint": "sha256:" + "a" * 64,
        "tick_timestamp_offset_seconds": 0, "decision_snapshot": {"snapshot_id": "s"},
        "proposal": {"proposal_id": "p"}, "postgres_audit": {"not_retained": True},
    }
    assert module._write_latest_assessment(output, assessment_started_at_utc="2026-09-12T00:00:00Z",
                                            assessment_completed_at_utc="2026-09-12T00:00:02Z",
                                            assessment_sequence=1) == "RETAINED_LATEST"
    retained = json.loads(target.read_text())
    assert retained["assessment_sequence"] == 1
    assert retained["assessment"]["decision_snapshot"] == {"snapshot_id": "s"}
    assert "postgres_audit" not in retained["assessment"]
    assert module._write_latest_assessment({}, assessment_started_at_utc="a", assessment_completed_at_utc="b", assessment_sequence=2) == "NOT_WRITTEN_UNSUPPORTED_RUNNER_OUTPUT"
    assert module._write_latest_assessment(output, assessment_started_at_utc="a", assessment_completed_at_utc="b", assessment_sequence=0) == "NOT_WRITTEN_UNSUPPORTED_RUNNER_OUTPUT"
    assert json.loads(target.read_text()) == retained


def test_immutable_assessment_spool_is_idempotent_and_never_overwrites(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("m20_listener_service", SOURCE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "ASSESSMENT_SPOOL_PATH", tmp_path / "spool")
    output = {
        "marker": "FOREX_M20_DEMO_TRADING_OPERATION_OK", "schema_version": "forex.m20.demo-trading-operation.v1",
        "operation": "m20_demo_trading_session", "server": "GOMarketsMU-Demo", "symbol": "EURUSD",
        "captured_at_utc": "2026-09-12T00:00:01Z", "configuration_fingerprint": "sha256:" + "a" * 64,
        "tick_timestamp_offset_seconds": 0, "decision_snapshot": {"snapshot_id": "s"}, "proposal": {"proposal_id": "p"},
    }
    assert module._write_assessment_spool(output, assessment_started_at_utc="2026-09-12T00:00:00Z",
                                          assessment_completed_at_utc="2026-09-12T00:00:02Z",
                                          assessment_sequence=7) == "SPOOLED_IMMUTABLE"
    target = tmp_path / "spool" / "00000000000000000007.json"
    before = target.read_bytes()
    assert module._write_assessment_spool(output, assessment_started_at_utc="2026-09-12T00:00:00Z",
                                          assessment_completed_at_utc="2026-09-12T00:00:02Z",
                                          assessment_sequence=7) == "SPOOL_ALREADY_RETAINED"
    changed = {**output, "proposal": {"proposal_id": "changed"}}
    assert module._write_assessment_spool(changed, assessment_started_at_utc="2026-09-12T00:00:00Z",
                                          assessment_completed_at_utc="2026-09-12T00:00:02Z",
                                          assessment_sequence=7) == "NOT_SPOOLED_CONFLICT"
    assert target.read_bytes() == before
    assert not list((tmp_path / "spool").glob("*.pending"))


def test_immutable_assessment_spool_skips_only_windows_unsupported_directory_fsync(tmp_path, monkeypatch):
    """A flushed receipt remains publishable on NTFS without a directory fsync."""
    spec = importlib.util.spec_from_file_location("m20_listener_service", SOURCE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "ASSESSMENT_SPOOL_PATH", tmp_path / "spool")
    monkeypatch.setattr(module, "ROOT", Path("a" * 16))
    monkeypatch.setattr(module.os, "name", "nt")
    output = {
        "marker": "FOREX_M20_DEMO_TRADING_OPERATION_OK", "schema_version": "forex.m20.demo-trading-operation.v1",
        "operation": "m20_demo_trading_session", "server": "GOMarketsMU-Demo", "symbol": "EURUSD",
        "captured_at_utc": "2026-09-12T00:00:01Z", "configuration_fingerprint": "sha256:" + "a" * 64,
        "tick_timestamp_offset_seconds": 0, "decision_snapshot": {"snapshot_id": "s"}, "proposal": {"proposal_id": "p"},
    }
    assert module._write_assessment_spool(output, assessment_started_at_utc="2026-09-12T00:00:00Z",
                                          assessment_completed_at_utc="2026-09-12T00:00:02Z",
                                          assessment_sequence=8) == "SPOOLED_IMMUTABLE"
    assert (tmp_path / "spool" / "00000000000000000008.json").is_file()


def test_listener_never_sleeps_a_negative_interval_after_monitoring():
    spec = importlib.util.spec_from_file_location("m20_listener_service", SOURCE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module._idle_wait_seconds(105.0, 100.0) == module.POLL_SECONDS
    assert round(module._idle_wait_seconds(100.4, 100.0), 6) == 0.4
    assert module._idle_wait_seconds(100.0, 100.0) == 0.0
    assert module._idle_wait_seconds(100.0, 100.1) == 0.0


def test_maintenance_hold_is_fixed_and_fails_closed_when_unreadable(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("m20_listener_service", SOURCE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "MAINTENANCE_HOLD_PATH", tmp_path / "hold.json")
    assert module._maintenance_hold() == {"active": False, "reason": "NONE"}
    module.MAINTENANCE_HOLD_PATH.write_text("not-json", encoding="utf-8")
    assert module._maintenance_hold() == {"active": True, "reason": "MAINTENANCE_HOLD_UNREADABLE"}
    module.MAINTENANCE_HOLD_PATH.write_text(json.dumps({
        "schema_version": "forex.m20.maintenance-hold.v1",
        "enabled": True,
        "reason": "W1R_COORDINATED_MAINTENANCE",
    }), encoding="utf-8")
    assert module._maintenance_hold() == {"active": True, "reason": "W1R_COORDINATED_MAINTENANCE"}


def test_listener_blocks_assessment_but_keeps_monitoring_during_maintenance(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("m20_listener_service", SOURCE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "STOP_PATH", tmp_path / "listener.stop")
    monkeypatch.setattr(module, "STATUS_PATH", tmp_path / "listener-status.json")
    monkeypatch.setattr(module, "ASSESSMENT_TOTAL_PATH", tmp_path / "assessment-total.json")
    monkeypatch.setattr(module, "MAINTENANCE_HOLD_PATH", tmp_path / "hold.json")
    monkeypatch.setattr(module, "PROTECTED_RESTART_DRILL_PATH", tmp_path / "restart-drill.json")
    module._write_restart_drill_state({"schema_version": "forex.m20.protected-restart-drill.v1", "state": "RESTART_REQUESTED", "attempt_id": "attempt", "position_ticket": 42, "requested_at_utc": "2026-09-10T00:00:00Z"})
    module.MAINTENANCE_HOLD_PATH.write_text(json.dumps({
        "schema_version": "forex.m20.maintenance-hold.v1", "enabled": True, "reason": "test",
    }), encoding="utf-8")
    monkeypatch.setattr(module, "POLL_SECONDS", 0)
    monkeypatch.setattr(module, "_load_environment", lambda: {"python_path": "python", "terminal_path": "terminal"})
    calls = []
    def monitor(values, previous, retry_at):
        calls.append("monitor")
        module.STOP_PATH.write_text("stop", encoding="utf-8")
        return {"state": "IDLE", "result": {"recovered": [{"attempt_id": "attempt", "position_ticket": 42, "reconciliation": {"status": "OPEN_MONITORING"}}]}}, 0.0
    monkeypatch.setattr(module, "_monitor_update", monitor)
    monkeypatch.setattr(module, "_quote_identity", lambda values: calls.append("quote"))
    statuses = []
    monkeypatch.setattr(module, "_write_status", lambda payload: statuses.append(payload))
    module.run()
    assert calls == ["monitor"]
    assert any(status["state"] == "MAINTENANCE_HOLD" for status in statuses)
    assert module._restart_drill_state()["state"] == "RECOVERED"


def test_listener_continues_to_the_next_fresh_quote_after_a_normal_no_trade(tmp_path, monkeypatch):
    """A normal terminal refusal is evidence, not a service-wide entry pause."""
    spec = importlib.util.spec_from_file_location("m20_listener_service", SOURCE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "STOP_PATH", tmp_path / "listener.stop")
    monkeypatch.setattr(module, "STATUS_PATH", tmp_path / "listener-status.json")
    monkeypatch.setattr(module, "ASSESSMENT_TOTAL_PATH", tmp_path / "assessment-total.json")
    monkeypatch.setattr(module, "ASSESSMENT_GATE_PATH", tmp_path / "assessment-gate.json")
    monkeypatch.setattr(module, "LATEST_ASSESSMENT_PATH", tmp_path / "latest.json")
    monkeypatch.setattr(module, "ASSESSMENT_SPOOL_PATH", tmp_path / "spool")
    monkeypatch.setattr(module, "PROTECTED_RESTART_DRILL_PATH", tmp_path / "restart-drill.json")
    monkeypatch.setattr(module, "MAINTENANCE_HOLD_PATH", tmp_path / "maintenance-hold.json")
    monkeypatch.setattr(module, "POLL_SECONDS", 0)
    monkeypatch.setattr(module, "ASSESSMENT_INTERVAL_SECONDS", 0)
    monkeypatch.setattr(module, "_load_environment", lambda: {"python_path": "python", "terminal_path": "terminal"})
    monkeypatch.setattr(module, "_active_lease", lambda: True)
    monkeypatch.setattr(module, "_maintenance_hold", lambda: {"active": False, "reason": "NONE"})
    monkeypatch.setattr(module, "_monitor_update", lambda values, previous, retry_at: ({"state": "IDLE"}, retry_at))

    quote_count = 0
    def quote(values):
        nonlocal quote_count
        quote_count += 1
        if quote_count > 2:
            module.STOP_PATH.write_text("stop", encoding="utf-8")
            return {"error": "test complete"}
        return {"marker": "FOREX_M20_DEMO_QUOTE_IDENTITY_OK", "server": "GOMarketsMU-Demo",
                "symbol": "EURUSD", "tick_time_msc": quote_count, "bid": 1.1, "ask": 1.1001}
    monkeypatch.setattr(module, "_quote_identity", quote)

    runner_calls = []
    output = {
        "marker": "FOREX_M20_DEMO_TRADING_OPERATION_OK", "schema_version": "forex.m20.demo-trading-operation.v1",
        "operation": "m20_demo_trading_session", "server": "GOMarketsMU-Demo", "symbol": "EURUSD",
        "captured_at_utc": "2026-09-17T00:00:01Z", "configuration_fingerprint": "sha256:" + "a" * 64,
        "tick_timestamp_offset_seconds": 0,
        "decision_snapshot": {"m1_closed_bars": [], "bid": 1.1, "ask": 1.1001, "spread_points": 10},
        "proposal": {"proposal_id": "proposal", "action": "NO_TRADE"},
    }
    def runner(argv, **kwargs):
        runner_calls.append(argv)
        return type("Completed", (), {"returncode": 0, "stdout": json.dumps(output), "stderr": ""})()
    monkeypatch.setattr(module.subprocess, "run", runner)

    module.run()

    assert [call[-1] for call in runner_calls] == ["1", "2"]
    assert not module.MAINTENANCE_HOLD_PATH.exists()
    assert json.loads(module.LATEST_ASSESSMENT_PATH.read_text())["assessment"]["proposal"]["action"] == "NO_TRADE"


def test_listener_reconciles_durable_positions_before_its_first_assessment(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("m20_listener_service", SOURCE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "STOP_PATH", tmp_path / "listener.stop")
    monkeypatch.setattr(module, "STATUS_PATH", tmp_path / "listener-status.json")
    monkeypatch.setattr(module, "ASSESSMENT_TOTAL_PATH", tmp_path / "assessment-total.json")
    monkeypatch.setattr(module, "POLL_SECONDS", 0)
    monkeypatch.setattr(module, "_load_environment", lambda: {"python_path": "python", "terminal_path": "terminal"})
    monkeypatch.setattr(module, "_active_lease", lambda: True)
    calls = []

    def monitor(values, previous, retry_at):
        calls.append("monitor")
        return {"state": "IDLE"}, 10_000.0

    def quote(values):
        calls.append("quote")
        module.STOP_PATH.write_text("stop", encoding="utf-8")
        return {"error": "test quote unavailable"}

    monkeypatch.setattr(module, "_monitor_update", monitor)
    monkeypatch.setattr(module, "_quote_identity", quote)
    module.run()
    assert calls[:2] == ["monitor", "quote"]


def test_listener_blocks_assessment_when_startup_reconciliation_fails(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("m20_listener_service", SOURCE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "STOP_PATH", tmp_path / "listener.stop")
    monkeypatch.setattr(module, "STATUS_PATH", tmp_path / "listener-status.json")
    monkeypatch.setattr(module, "ASSESSMENT_TOTAL_PATH", tmp_path / "assessment-total.json")
    monkeypatch.setattr(module, "POLL_SECONDS", 0)
    monkeypatch.setattr(module, "_load_environment", lambda: {"python_path": "python", "terminal_path": "terminal"})
    monkeypatch.setattr(module, "_active_lease", lambda: True)
    calls = []

    def monitor(values, previous, retry_at):
        calls.append("monitor")
        module.STOP_PATH.write_text("stop", encoding="utf-8")
        return {"state": "FAILED", "result": {"error": "test failure"}}, 10_000.0

    monkeypatch.setattr(module, "_monitor_update", monitor)
    monkeypatch.setattr(module, "_quote_identity", lambda values: calls.append("quote"))
    statuses = []
    monkeypatch.setattr(module, "_write_status", lambda payload: statuses.append(payload))
    module.run()
    assert calls == ["monitor"]
    assert any(status["state"] == "MONITORING_UNAVAILABLE" for status in statuses)


def test_listener_blocks_assessment_when_a_retained_position_recovery_fails(monkeypatch):
    spec = importlib.util.spec_from_file_location("m20_listener_service", SOURCE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    class Completed:
        returncode = 0
        stdout = '{"marker":"FOREX_M20_DEMO_MONITOR_OPERATION_OK","recovered":[{"attempt_id":"retained","status":"RECOVERY_FAILED","error":"history unavailable"}]}'
        stderr = ""

    monkeypatch.setattr(module.subprocess, "run", lambda *args, **kwargs: Completed())
    monkeypatch.setattr(module.time, "monotonic", lambda: 100.0)
    state, _ = module._monitor_update({"python_path": "python", "terminal_path": "terminal"}, {}, 0.0)
    assert state["state"] == "FAILED"
    assert "retained position" in state["error"]


def test_listener_accepts_empty_or_reconciled_recovery_only_when_the_marker_is_valid(monkeypatch):
    spec = importlib.util.spec_from_file_location("m20_listener_service", SOURCE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    class Completed:
        returncode = 0
        stdout = '{"marker":"FOREX_M20_DEMO_MONITOR_OPERATION_OK","recovered":[{"attempt_id":"closed","reconciliation":{"status":"MATCHED"}}]}'
        stderr = ""

    monkeypatch.setattr(module.subprocess, "run", lambda *args, **kwargs: Completed())
    monkeypatch.setattr(module.time, "monotonic", lambda: 100.0)
    state, _ = module._monitor_update({"python_path": "python", "terminal_path": "terminal"}, {}, 0.0)
    assert state["state"] == "IDLE"


def test_listener_metrics_explain_a_no_trade_breakout_rejection():
    spec = importlib.util.spec_from_file_location("m20_listener_service", SOURCE)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    bars = [
        {"open": 1.1000 + index * .00001, "close": 1.1001 + index * .00001, "high": 1.1002 + index * .00001, "low": 1.0999, "closed_at_utc": f"2026-09-03T00:0{index}:00Z"}
        for index in range(6)
    ]
    bars[-1]["close"] = 1.1000  # mixed direction means no valid momentum setup.
    metrics = module._assessment_metrics({"m1_closed_bars": bars, "bid": 1.1000, "ask": 1.1002, "spread_points": 20}, {"action": "NO_TRADE"})
    assert metrics["decision"] == "NO_TRADE"
    assert metrics["two_candle_direction"] == "MIXED"
    assert metrics["prior_five_high"] > metrics["prior_five_low"]


def _crash_test_service():
    spec = importlib.util.spec_from_file_location('listener_crash_test', SOURCE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_listener_crash_record_preserves_failure_without_sensitive_message(tmp_path, monkeypatch):
    import pytest
    service = _crash_test_service()
    failure_path = tmp_path / 'failure.jsonl'
    status_path = tmp_path / 'status.json'
    monkeypatch.setattr(service, 'FAILURE_PATH', failure_path)
    monkeypatch.setattr(service, 'STATUS_PATH', status_path)
    def fail():
        raise PermissionError(13, 'sensitive-test-message-must-not-appear')
    monkeypatch.setattr(service, 'run', fail)
    for _ in range(2):
        with pytest.raises(PermissionError):
            service.run_guarded()
    records = [json.loads(line) for line in failure_path.read_text().splitlines()]
    assert len(records) == 2
    assert all(r['exception_type'] == 'PermissionError' and r['errno'] == 13 and r['frames'] for r in records)
    assert 'sensitive-test-message' not in failure_path.read_text() + status_path.read_text()
    assert json.loads(status_path.read_text())['state'] == 'STARTUP_FAILED'


def test_listener_retries_transient_status_replacement_but_bounds_persistent_failure(tmp_path, monkeypatch):
    import pytest
    service = _crash_test_service()
    monkeypatch.setattr(service, 'STATUS_PATH', tmp_path / 'status.json')
    monkeypatch.setattr(service.time, 'sleep', lambda delay: None)
    original = Path.replace
    attempts = []
    def temporary_collision(path, target):
        attempts.append(1)
        if len(attempts) < 3:
            raise PermissionError('reader has file open')
        return original(path, target)
    monkeypatch.setattr(Path, 'replace', temporary_collision)
    service._write_status({'state': 'MAINTENANCE_HOLD'})
    assert len(attempts) == 3
    assert json.loads(service.STATUS_PATH.read_text())['state'] == 'MAINTENANCE_HOLD'
    attempts.clear()
    def permanent_failure(path, target):
        attempts.append(1)
        raise PermissionError('persistent')
    monkeypatch.setattr(Path, 'replace', permanent_failure)
    with pytest.raises(PermissionError):
        service._write_status({'state': 'MAINTENANCE_HOLD'})
    assert len(attempts) == 3

def test_one_shot_protected_restart_drill_requests_only_after_durable_accepted_open(tmp_path, monkeypatch):
    import pytest
    service = _crash_test_service()
    monkeypatch.setattr(service, "PROTECTED_RESTART_DRILL_PATH", tmp_path / "restart-drill.json")
    assert service._restart_drill_state()["state"] == "ARMED"
    with pytest.raises(service.ProtectedRestartDrillRequested):
        service._request_protected_restart({
            "execution": {"status": "ACCEPTED", "monitor_job_scheduled": True, "attempt_id": "attempt"},
            "reconciliation": {"status": "OPEN_MONITORING", "position_ticket": 42},
        })
    state = service._restart_drill_state()
    assert state["state"] == "RESTART_REQUESTED" and state["position_ticket"] == 42
    service._request_protected_restart({
        "execution": {"status": "ACCEPTED", "monitor_job_scheduled": True, "attempt_id": "attempt"},
        "reconciliation": {"status": "OPEN_MONITORING", "position_ticket": 42},
    })
    assert service._restart_drill_state()["state"] == "RESTART_REQUESTED"


def test_one_shot_protected_restart_drill_records_recovery_or_prior_close(tmp_path, monkeypatch):
    service = _crash_test_service()
    monkeypatch.setattr(service, "PROTECTED_RESTART_DRILL_PATH", tmp_path / "restart-drill.json")
    service._write_restart_drill_state({"schema_version": "forex.m20.protected-restart-drill.v1", "state": "RESTART_REQUESTED", "attempt_id": "attempt", "position_ticket": 42, "requested_at_utc": "2026-09-10T00:00:00Z"})
    service._record_protected_restart_recovery({"result": {"recovered": [{"attempt_id": "other", "position_ticket": 42, "reconciliation": {"status": "OPEN_MONITORING"}}]}})
    assert service._restart_drill_state()["state"] == "RESTART_REQUESTED"
    service._record_protected_restart_recovery({"result": {"recovered": [{"attempt_id": "attempt", "position_ticket": 42, "reconciliation": {"status": "OPEN_MONITORING"}}]}})
    assert service._restart_drill_state()["state"] == "RECOVERED"


def test_protected_restart_drill_corruption_or_write_failure_does_not_interrupt_protection(tmp_path, monkeypatch):
    service = _crash_test_service()
    marker = tmp_path / "restart-drill.json"
    monkeypatch.setattr(service, "PROTECTED_RESTART_DRILL_PATH", marker)
    marker.write_text("not-json", encoding="utf-8")
    assert service._restart_drill_state() is None
    assert service._restart_drill_status() == {"observation": "UNREADABLE", "state": None}
    service._request_protected_restart({
        "execution": {"status": "ACCEPTED", "monitor_job_scheduled": True, "attempt_id": "attempt"},
        "reconciliation": {"status": "OPEN_MONITORING", "position_ticket": 42},
    })
    service._record_protected_restart_recovery({"result": {"recovered": []}})
    assert marker.read_text(encoding="utf-8") == "not-json"

    marker.unlink()
    monkeypatch.setattr(service, "_write_restart_drill_state", lambda state: False)
    service._request_protected_restart({
        "execution": {"status": "ACCEPTED", "monitor_job_scheduled": True, "attempt_id": "attempt"},
        "reconciliation": {"status": "OPEN_MONITORING", "position_ticket": 42},
    })
    assert service._restart_drill_state()["state"] == "ARMED"


def test_protected_restart_drill_rejects_boolean_ticket_and_keeps_marker_for_review(tmp_path, monkeypatch):
    service = _crash_test_service()
    marker = tmp_path / "restart-drill.json"
    monkeypatch.setattr(service, "PROTECTED_RESTART_DRILL_PATH", marker)
    marker.write_text(json.dumps({
        "schema_version": "forex.m20.protected-restart-drill.v1", "state": "RESTART_REQUESTED",
        "attempt_id": "attempt", "position_ticket": True,
    }), encoding="utf-8")
    assert service._restart_drill_state() is None
    assert service._restart_drill_status() == {"observation": "INVALID", "state": None}


def test_protected_restart_child_uses_fixed_absolute_payload_and_retains_parent(tmp_path, monkeypatch):
    service = _crash_test_service()
    monkeypatch.setattr(service, "PROTECTED_RESTART_DRILL_PATH", tmp_path / "restart-drill.json")
    service._write_restart_drill_state({"schema_version": "forex.m20.protected-restart-drill.v1", "state": "RESTART_REQUESTED", "attempt_id": "attempt", "position_ticket": 42, "requested_at_utc": "2026-09-10T00:00:00Z"})
    calls = []

    class Child:
        def wait(self, timeout=None):
            calls.append(("wait", timeout))
            return 0

    def launch(argv, **kwargs):
        calls.append(("launch", argv, kwargs))
        return Child()

    monkeypatch.setattr(service.subprocess, "Popen", launch)
    assert service._run_protected_restart_child() is True
    launch_call = calls[0]
    assert Path(launch_call[1][0]).is_absolute() and Path(launch_call[1][1]).is_absolute()
    assert launch_call[1][0] == str(Path(service.sys.executable).resolve())
    assert launch_call[1][1] == str(Path(service.__file__).resolve())
    assert launch_call[2] == {"close_fds": True}
    state = service._restart_drill_state()
    assert state["state"] == "RESTARTING" and state["restart_parent_pid"] == service.os.getpid()


@pytest.mark.parametrize("mode", ["spawn", "nonzero"])
def test_restart_child_failure_latches_fault_then_parent_resumes_monitoring(tmp_path, monkeypatch, mode):
    service = _crash_test_service()
    monkeypatch.setattr(service, "PROTECTED_RESTART_DRILL_PATH", tmp_path / "restart-drill.json")
    service._write_restart_drill_state({"schema_version": "forex.m20.protected-restart-drill.v1", "state": "RESTART_REQUESTED", "attempt_id": "attempt", "position_ticket": 42, "requested_at_utc": "2026-09-10T00:00:00Z"})
    calls = []

    def run():
        calls.append("run")
        if len(calls) == 1:
            raise service.ProtectedRestartDrillRequested("test")

    monkeypatch.setattr(service, "run", run)
    if mode == "spawn":
        monkeypatch.setattr(service.subprocess, "Popen", lambda *args, **kwargs: (_ for _ in ()).throw(OSError("blocked")))
    else:
        monkeypatch.setattr(service.subprocess, "Popen", lambda *args, **kwargs: type("Child", (), {"wait": lambda self, timeout=None: 7})())
    service.run_guarded()
    assert calls == ["run", "run"]
    state = service._restart_drill_state()
    assert state["state"] == "RESTART_FAILED"
    assert state["failure_reason"] == ("CHILD_SPAWN_FAILED" if mode == "spawn" else "CHILD_EXIT_NONZERO")
    assert service._restart_drill_status()["observation"] == "FAULTED"


def test_restart_wait_error_keeps_parent_inert_until_child_exit_is_known(tmp_path, monkeypatch):
    service = _crash_test_service()
    monkeypatch.setattr(service, "PROTECTED_RESTART_DRILL_PATH", tmp_path / "restart-drill.json")
    service._write_restart_drill_state({"schema_version": "forex.m20.protected-restart-drill.v1", "state": "RESTART_REQUESTED", "attempt_id": "attempt", "position_ticket": 42, "requested_at_utc": "2026-09-10T00:00:00Z"})
    attempts = []

    class Child:
        def wait(self, timeout=None):
            attempts.append(timeout)
            if len(attempts) == 1:
                raise OSError("wait failed")
            return 9

    monkeypatch.setattr(service.subprocess, "Popen", lambda *args, **kwargs: Child())
    monkeypatch.setattr(service.time, "sleep", lambda delay: None)
    assert service._run_protected_restart_child() is False
    assert attempts == [1, 1]
    assert service._restart_drill_state()["failure_reason"] == "CHILD_EXIT_NONZERO"


def test_autonomous_continuity_protocol_fails_closed_when_handoff_is_not_reached(tmp_path, monkeypatch):
    service = _crash_test_service()
    monkeypatch.setattr(service, "CONTINUITY_PROTOCOL_PATH", tmp_path / "continuity.json")
    monkeypatch.setattr(service, "CONTINUITY_PROTOCOL_LOG_PATH", tmp_path / "continuity.jsonl")
    monkeypatch.setattr(service, "CONTINUITY_WINDOW_SECONDS", 0)
    monkeypatch.setattr(service, "_load_environment", lambda: {"python_path": "python"})
    monkeypatch.setattr(service, "_continuity_sample", lambda release: {
        "captured_at_utc": "2026-09-10T00:00:00Z", "heartbeat_at_utc": "2026-09-10T00:00:00Z",
        "heartbeat_age_seconds": 0, "state": "MAINTENANCE_HOLD", "release_id": release, "valid": True,
    })
    monkeypatch.setattr(service, "_continuity_observation", lambda values, release: {
        "valid": True,
        "heartbeat": {"captured_at_utc": "2026-09-10T00:00:00Z", "heartbeat_at_utc": "2026-09-10T00:00:00Z",
                      "heartbeat_age_seconds": 0, "state": "MAINTENANCE_HOLD", "release_id": release, "valid": True},
        "account": {}, "deployment": {},
    })
    handoffs = []
    monkeypatch.setattr(service, "_continuity_worker_handoff", lambda: handoffs.append(True) or True)
    monkeypatch.setattr(service, "_notify_continuity", lambda run_id, event: {"state": "SENT", "event": event})
    service.CONTINUITY_PROTOCOL_PATH.write_text(json.dumps({
        "schema_version": "forex.m20.continuity-protocol.v1", "run_id": "run", "release_id": "release",
        "started_at_utc": "2026-09-10T00:00:00Z", "state": "ARMED", "baseline": {}, "samples": [],
        "incident_delivery": {"state": "PENDING"},
    }), encoding="utf-8")
    assert service.run_continuity_protocol() == 2  # zero window cannot exercise the mandatory handoff
    result = json.loads(service.CONTINUITY_PROTOCOL_PATH.read_text())
    assert result["state"] == "FAIL" and result["failure_reason"] == "WORKER_HANDOFF_NOT_REACHED"
    assert handoffs == []


def test_completed_continuity_protocol_is_archived_without_overwrite(tmp_path, monkeypatch):
    service = _crash_test_service()
    active = tmp_path / "continuity.json"
    monkeypatch.setattr(service, "CONTINUITY_PROTOCOL_PATH", active)
    run_id = "a" * 24
    active.write_text(json.dumps({"schema_version": "forex.m20.continuity-protocol.v1", "run_id": run_id,
                                  "state": "INCONCLUSIVE"}), encoding="utf-8")
    original = active.read_bytes()
    service._archive_completed_continuity_protocol()
    archived = list(tmp_path.glob(f"m20_demo_continuity_protocol.{run_id}.*.json"))
    assert not active.exists() and len(archived) == 1 and archived[0].read_bytes() == original


def test_unavailable_incident_alert_finishes_without_worker_handoff(tmp_path, monkeypatch):
    service = _crash_test_service()
    marker = tmp_path / "continuity.json"
    monkeypatch.setattr(service, "CONTINUITY_PROTOCOL_PATH", marker)
    monkeypatch.setattr(service, "CONTINUITY_PROTOCOL_LOG_PATH", tmp_path / "continuity.jsonl")
    monkeypatch.setattr(service, "_load_environment", lambda: {"python_path": "python"})
    monkeypatch.setattr(service, "_notify_continuity", lambda run_id, event: {"state": "FAILED", "reason": "HTTP_401"})
    monkeypatch.setattr(service, "_continuity_worker_handoff", lambda: (_ for _ in ()).throw(AssertionError("handoff")))
    marker.write_text(json.dumps({"schema_version": "forex.m20.continuity-protocol.v1", "run_id": "run", "release_id": "release",
                                  "started_at_utc": "2026-09-10T00:00:00Z", "state": "ARMED", "baseline": {}, "samples": [],
                                  "incident_delivery": {"state": "PENDING"}}), encoding="utf-8")
    assert service.run_continuity_protocol() == 0
    record = json.loads(marker.read_text())
    assert record["state"] == "INCONCLUSIVE" and record["failure_reason"] == "INCIDENT_ALERT_UNAVAILABLE"
    assert record["recovery_delivery"] == {"state": "NOT_ATTEMPTED"}


def test_corrupt_restart_drill_marker_blocks_assessment_but_not_monitoring(tmp_path, monkeypatch):
    service = _crash_test_service()
    marker = tmp_path / "restart-drill.json"
    marker.write_text("not-json", encoding="utf-8")
    monkeypatch.setattr(service, "PROTECTED_RESTART_DRILL_PATH", marker)
    monkeypatch.setattr(service, "STOP_PATH", tmp_path / "listener.stop")
    monkeypatch.setattr(service, "STATUS_PATH", tmp_path / "listener-status.json")
    monkeypatch.setattr(service, "ASSESSMENT_TOTAL_PATH", tmp_path / "assessment-total.json")
    monkeypatch.setattr(service, "POLL_SECONDS", 0)
    monkeypatch.setattr(service, "_load_environment", lambda: {"python_path": "python", "terminal_path": "terminal"})
    monkeypatch.setattr(service, "_active_lease", lambda: True)
    calls = []

    def monitor(values, previous, retry_at):
        calls.append("monitor")
        if len(calls) == 2:
            service.STOP_PATH.write_text("stop", encoding="utf-8")
        return {"state": "IDLE", "result": {"recovered": []}}, 10_000.0

    monkeypatch.setattr(service, "_monitor_update", monitor)
    monkeypatch.setattr(service, "_quote_identity", lambda values: calls.append("quote"))
    statuses = []
    monkeypatch.setattr(service, "_write_status", lambda payload: statuses.append(payload))
    service.run()
    assert calls == ["monitor", "monitor"]
    blocked = next(status for status in statuses if status["state"] == "DRILL_UNAVAILABLE")
    assert blocked["protected_restart_drill"] == {"observation": "UNREADABLE", "state": None}
