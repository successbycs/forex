from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from forex.h_slow_policy import HSlowInputError, MINIMUM_DAILY_BAR_WARMUP, monthly_target


DECISION = "2026-09-01T12:00:00Z"


def stamp(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def qualified_bars(*, start_close: float = 1.0, end_close: float = 1.1) -> list[dict]:
    start = datetime(2025, 8, 1, tzinfo=timezone.utc)
    end = datetime(2026, 8, 31, tzinfo=timezone.utc)
    dates: list[datetime] = []
    current = start
    while current <= end:
        if current.weekday() < 5:
            dates.append(current)
        current += timedelta(days=1)
    assert len(dates) >= MINIMUM_DAILY_BAR_WARMUP
    rows = []
    for index, opened in enumerate(dates):
        ratio = index / (len(dates) - 1)
        rows.append({
            "opened_at_utc": stamp(opened),
            "closed_at_utc": stamp(opened + timedelta(days=1)),
            "available_at_utc": DECISION,
            "close": start_close + (end_close - start_close) * ratio,
        })
    return rows


def test_monthly_target_returns_buy_from_positive_completed_12_month_return():
    result = monthly_target(decision_at_utc=DECISION, daily_bars=qualified_bars())
    assert result["action"] == "BUY"
    assert result["signal_month"] == "2026-08"
    assert result["reference_month"] == "2025-08"
    assert result["research_only"] is True
    assert result["execution_authority"] is False


def test_monthly_target_returns_sell_from_negative_completed_12_month_return():
    assert monthly_target(decision_at_utc=DECISION, daily_bars=qualified_bars(start_close=1.1, end_close=1.0))["action"] == "SELL"


def test_monthly_target_returns_no_trade_for_zero_return():
    assert monthly_target(decision_at_utc=DECISION, daily_bars=qualified_bars(start_close=1.1, end_close=1.1))["action"] == "NO_TRADE"


def test_rejects_insufficient_daily_warmup():
    with pytest.raises(HSlowInputError, match="240 completed daily bars"):
        monthly_target(decision_at_utc=DECISION, daily_bars=qualified_bars()[:239])


def test_rejects_nonchronological_daily_bars():
    rows = qualified_bars()
    rows[1], rows[2] = rows[2], rows[1]
    with pytest.raises(HSlowInputError, match="strictly chronological"):
        monthly_target(decision_at_utc=DECISION, daily_bars=rows)


def test_rejects_future_and_unclosed_daily_data():
    rows = qualified_bars()
    rows.append({"opened_at_utc": "2026-09-01T00:00:00Z", "closed_at_utc": "2026-09-02T00:00:00Z", "available_at_utc": "2026-09-02T00:00:00Z", "close": 1.2})
    with pytest.raises(HSlowInputError, match="not closed at decision time"):
        monthly_target(decision_at_utc=DECISION, daily_bars=rows)


def test_rejects_closed_bar_not_yet_available_at_decision():
    rows = qualified_bars()
    rows[-1]["available_at_utc"] = "2026-09-02T00:00:00Z"
    with pytest.raises(HSlowInputError, match="unavailable at decision time"):
        monthly_target(decision_at_utc=DECISION, daily_bars=rows)


def test_rejects_missing_final_trading_day_of_an_otherwise_present_month():
    rows = qualified_bars()
    rows.pop()  # 2026-08-31: the final weekday of the signal month.
    with pytest.raises(HSlowInputError, match="final session missing for 2026-08"):
        monthly_target(decision_at_utc=DECISION, daily_bars=rows)


def test_rejects_non_monthly_decision_clock():
    with pytest.raises(HSlowInputError, match="monthly decision clock"):
        monthly_target(decision_at_utc="2026-08-31T23:59:59Z", daily_bars=qualified_bars())
