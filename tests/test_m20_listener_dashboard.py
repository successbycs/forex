import subprocess
from unittest import mock

from scripts.m20_listener_dashboard import listener_status, render


def test_dashboard_status_timeout_remains_refreshable():
    with mock.patch("scripts.m20_listener_dashboard.subprocess.run", side_effect=subprocess.TimeoutExpired("listener-status", 8)):
        status = listener_status()
    assert status["state"] == "UNAVAILABLE"
    assert "exceeded eight seconds" in status["detail"]


def test_dashboard_renders_decision_and_candle_metrics():
    screen = render({
        "state": "RUNNING", "iteration": 7, "heartbeat_at_utc": "2026-09-03T09:33:00Z", "heartbeat_at_nzst": "03/09/26 21:33:00 NZST",
        "last_result": {
            "server": "GOMarketsMU-Demo", "symbol": "EURUSD",
            "proposal": {"action": "NO_TRADE", "selected_timeframe": "M1", "rationale": "No breakout."},
            "execution": {"status": "NOT_SUBMITTED"}, "reconciliation": {"status": "NO_TRADE_RECONCILED"},
            "strategy_assessments": [
                {"label": "Momentum breakout", "signal": "NO_TRADE", "eligible_for_execution": True, "reason": "No breakout."},
                {"label": "Compression breakout", "signal": "BUY", "eligible_for_execution": False, "reason": "Shadow comparison."},
                {"label": "Trend pullback", "signal": "NO_TRADE", "eligible_for_execution": False, "reason": "Shadow comparison."},
                {"label": "Range reversion", "signal": "SELL", "eligible_for_execution": False, "reason": "Shadow comparison."},
                {"label": "Session breakout", "signal": "NO_TRADE", "eligible_for_execution": False, "reason": "Shadow comparison."},
            ],
            "assessment_metrics": {"last_close": 1.16024, "previous_close": 1.16016, "prior_five_low": 1.16011, "prior_five_high": 1.16041, "two_candle_direction": "MIXED", "two_candle_aligned": False, "breakout_above_prior_high": False, "breakout_below_prior_low": False, "combined_move_points": 4, "spread_points": 8, "combined_move_exceeds_spread": False},
        },
    })
    assert "M20 Demo Listener" in screen
    assert "Decision: NO_TRADE" in screen
    assert "NZST 03/09/26 21:33:00 NZST" in screen
    assert "Direction: MIXED" in screen
    assert "Combined move: 4 pts" in screen
    assert "Strategy comparison — only Momentum Breakout may trade" in screen
    assert "Momentum breakout      NO_TRADE     ACTIVE" in screen
    assert "Compression breakout   BUY          SHADOW" in screen
