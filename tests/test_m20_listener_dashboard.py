import subprocess
from unittest import mock

from scripts.m20_listener_dashboard import listener_status, render


def test_dashboard_status_timeout_remains_refreshable():
    with mock.patch("scripts.m20_listener_dashboard.subprocess.run", side_effect=subprocess.TimeoutExpired("listener-status", 8)):
        status = listener_status()
    assert status["state"] == "UNAVAILABLE"
    assert "exceeded eight seconds" in status["detail"]


def test_dashboard_renders_a_clear_unavailable_state_instead_of_blank_fields():
    screen = render({"state": "UNAVAILABLE", "detail": "T480 listener-status check exceeded eight seconds; dashboard will retry."})
    assert "Listener status is temporarily unavailable." in screen
    assert "exceeded eight seconds" in screen
    assert "M1 decision:" not in screen


def test_dashboard_renders_decision_and_candle_metrics():
    screen = render({
        "state": "RUNNING", "iteration": 7, "heartbeat_at_utc": "2026-09-03T09:33:00Z", "heartbeat_at_nzst": "03/09/26 21:33:00 NZST",
        "quote": {"tick_time_msc": 123456, "bid": 1.161, "ask": 1.16108},
        "last_result": {
            "server": "GOMarketsMU-Demo", "symbol": "EURUSD",
            "proposal": {"action": "NO_TRADE", "selected_timeframe": "M1", "rationale": "No breakout."},
            "execution": {"status": "NOT_SUBMITTED"}, "reconciliation": {"status": "NO_TRADE_RECONCILED"},
            "strategy_selection": {"selected_strategy_id": "range_reversion", "selection_status": "SELECTED_EXECUTABLE"},
            "strategy_assessments": [
                {"id": "momentum_breakout", "label": "Momentum breakout", "signal": "NO_TRADE", "eligible_for_execution": True, "reason": "No breakout."},
                {"id": "compression_breakout", "label": "Compression breakout", "signal": "BUY", "eligible_for_execution": True, "reason": "Signal comparison."},
                {"id": "trend_pullback", "label": "Trend pullback", "signal": "NO_TRADE", "eligible_for_execution": True, "reason": "No signal."},
                {"id": "range_reversion", "label": "Range reversion", "signal": "SELL", "eligible_for_execution": True, "reason": "Signal comparison."},
                {"id": "session_breakout", "label": "Session breakout", "signal": "NO_TRADE", "eligible_for_execution": True, "reason": "No signal."},
            ],
            "assessment_metrics": {"last_close": 1.16024, "previous_close": 1.16016, "prior_five_low": 1.16011, "prior_five_high": 1.16041, "two_candle_direction": "MIXED", "two_candle_aligned": False, "breakout_above_prior_high": False, "breakout_below_prior_low": False, "combined_move_points": 4, "spread_points": 8, "combined_move_exceeds_spread": False},
        },
    })
    assert "M20 Demo Listener" in screen
    assert "Quote gate: MT5 tick 123456 | bid/ask 1.161/1.16108" in screen
    assert "M1 decision: NO_TRADE" in screen
    assert "NZST 03/09/26 21:33:00 NZST" in screen
    assert "Direction: MIXED" in screen
    assert "Combined move: 4 pts" in screen
    assert "Strategy comparison — regime precedence may select one executable owner" in screen
    assert "Momentum breakout      NO_TRADE     NO SIGNAL" in screen
    assert "Compression breakout   BUY          SIGNAL ONLY" in screen
    assert "Range reversion        SELL         BLOCKED" in screen
    assert "M1 strategy owner: range_reversion [SELECTED_EXECUTABLE]" in screen
    assert "Shadow context only — does not change this trade." in screen
    assert "M5: NOT RECORDED | close UTC — | age —" in screen
    assert "H1: NOT RECORDED | close UTC — | age —" in screen


def test_dashboard_renders_read_only_m5_h1_context_with_native_closes_and_ages():
    screen = render({
        "state": "RUNNING",
        "last_result": {
            "proposal": {"action": "BUY", "selected_timeframe": "M1", "rationale": "M1 breakout."},
            "execution": {"status": "NOT_SUBMITTED"},
            "reconciliation": {"status": "NO_TRADE_RECONCILED"},
            "strategy_selection": {"selected_strategy_id": "momentum_breakout", "selection_status": "SELECTED_EXECUTABLE", "market_regime": "TREND"},
            "multi_timeframe_context": {
                "overall_alignment": "ALIGNED", "context_disposition": "OBSERVE_ONLY",
                "rule_version": "forex.m20.12.mtf-context.v1", "reason": "Both closed contexts support BUY.",
                "contexts": [
                    {"timeframe": "M5", "closed_at_utc": "2026-09-04T01:35:00Z", "data_age_seconds": 41,
                     "integrity_status": "VALID", "market_state": "BULLISH", "volatility_state": "NORMAL",
                     "liquidity_state": "LIQUID", "alignment": "ALIGNED"},
                    {"timeframe": "H1", "closed_at_utc": "2026-09-04T01:00:00Z", "data_age_seconds": 2141,
                     "integrity_status": "VALID", "market_state": "BULLISH", "volatility_state": "NORMAL",
                     "liquidity_state": "LIQUID", "alignment": "ALIGNED"},
                ],
            },
        },
    })
    assert "Shadow context only — does not change this trade." in screen
    assert "M5: VALID | BULLISH | ALIGNED | close UTC 2026-09-04T01:35:00Z | age 41s" in screen
    assert "H1: VALID | BULLISH | ALIGNED | close UTC 2026-09-04T01:00:00Z | age 2141s" in screen
    assert "Context: alignment ALIGNED | disposition OBSERVE_ONLY | rule forex.m20.12.mtf-context.v1" in screen
    assert "M1 decision: BUY" in screen
    assert "M1 strategy owner: momentum_breakout [SELECTED_EXECUTABLE]" in screen


def test_dashboard_keeps_unavailable_higher_timeframe_context_visible_and_non_blocking():
    screen = render({
        "state": "RUNNING",
        "last_result": {
            "proposal": {"action": "SELL", "selected_timeframe": "M1"},
            "strategy_selection": {"selected_strategy_id": "range_reversion", "selection_status": "SELECTED_EXECUTABLE"},
            "multi_timeframe_context": {
                "overall_alignment": "UNAVAILABLE", "context_disposition": "NEUTRAL", "rule_version": "forex.m20.12.mtf-context.v1",
                "contexts": [{"timeframe": "M5", "integrity_status": "UNAVAILABLE", "alignment": "UNAVAILABLE"}],
            },
        },
    })
    assert "M1 decision: SELL" in screen
    assert "Context: alignment UNAVAILABLE | disposition NEUTRAL" in screen
    assert "M5: UNAVAILABLE | UNKNOWN | UNAVAILABLE | close UTC — | age —" in screen
    assert "H1: NOT RECORDED | close UTC — | age —" in screen
    assert "does not change this trade" in screen
