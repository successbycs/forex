import pytest

from forex.agent_context import build_context


def test_m17_context_is_time_bounded_and_non_executing():
    bars = [
        {"time_utc": "2026-08-01T00:00:00Z", "available_at_utc": "2026-08-01T01:00:00Z", "open": 1.1, "high": 1.2, "low": 1.0, "close": 1.15, "volume": 1},
        {"time_utc": "2026-08-01T01:00:00Z", "available_at_utc": "2026-08-01T03:00:00Z", "open": 1.15, "high": 1.2, "low": 1.1, "close": 1.16, "volume": 2},
    ]
    result = build_context(bars=bars, cutoff_utc="2026-08-01T02:00:00Z", features={"return_2": 0.01})
    assert len(result["price_bars"]) == 1
    assert result["agent_authority"] == "NONE"
    assert result["order_capability"] is False and result["live_trading_capability"] is False


def test_m17_rejects_forbidden_input():
    with pytest.raises(ValueError, match="forbidden"):
        build_context(bars=[{"time_utc":"2026-08-01T00:00:00Z","available_at_utc":"2026-08-01T00:00:00Z","close":1.1,"order":"BUY"}], cutoff_utc="2026-08-01T01:00:00Z")


def test_m17_excludes_a_bar_after_the_cutoff_even_if_marked_available():
    result = build_context(bars=[{"time_utc":"2026-08-01T02:00:00Z","available_at_utc":"2026-08-01T01:00:00Z","close":1.1}], cutoff_utc="2026-08-01T01:00:00Z")
    assert result["price_bars"] == []
