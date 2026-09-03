import importlib.util
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
    assert "FOREX_M20_POSTGRES_DSN\"" not in source.split("required =", 1)[1].split("if not", 1)[0]
    assert "order_send" not in source


def test_runner_has_a_narrow_history_unavailable_mvp_recovery_path():
    source = Path("t480/m20_demo_trading_session.py").read_text(encoding="utf-8")
    bridge = Path("t480/m20_postgres_audit_bridge.py").read_text(encoding="utf-8")
    assert '"archive-history-unavailable-positions"' in source
    assert '"BROKER_HISTORY_UNAVAILABLE"' in source
    assert "not owned_positions" in source
    assert "archive_history_unavailable_positions" in bridge
    assert "M20 close deal history has no priced market deal" in bridge


def test_listener_module_loads_without_mt5_dependency():
    spec = importlib.util.spec_from_file_location("m20_listener_service", SOURCE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.ASSESSMENT_INTERVAL_SECONDS == 5
    assert module._nzst("2026-09-03T09:30:00Z") == "03/09/26 21:30:00 NZST"


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
