import importlib.util
import json
from pathlib import Path


SOURCE = Path("t480/m20_demo_listener_service.py")


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
    module.MAINTENANCE_HOLD_PATH.write_text(json.dumps({
        "schema_version": "forex.m20.maintenance-hold.v1", "enabled": True, "reason": "test",
    }), encoding="utf-8")
    monkeypatch.setattr(module, "POLL_SECONDS", 0)
    monkeypatch.setattr(module, "_load_environment", lambda: {"python_path": "python", "terminal_path": "terminal"})
    calls = []
    def monitor(values, previous, retry_at):
        calls.append("monitor")
        module.STOP_PATH.write_text("stop", encoding="utf-8")
        return {"state": "IDLE"}, 0.0
    monkeypatch.setattr(module, "_monitor_update", monitor)
    monkeypatch.setattr(module, "_quote_identity", lambda values: calls.append("quote"))
    statuses = []
    monkeypatch.setattr(module, "_write_status", lambda payload: statuses.append(payload))
    module.run()
    assert calls == ["monitor"]
    assert any(status["state"] == "MAINTENANCE_HOLD" for status in statuses)


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
