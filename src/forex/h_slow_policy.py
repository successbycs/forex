"""Disabled, deterministic H_SLOW EUR/USD research decision component.

This module has no broker, filesystem, configuration, database, environment,
or network dependency.  It only qualifies point-in-time daily-bar input and
returns a monthly research target; it cannot place, amend, or close an order.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import math
from typing import Any


POLICY_VERSION = "forex.h-slow.eurusd-tsmom-12m.v1"
INSTRUMENT = "EUR/USD"
MINIMUM_DAILY_BAR_WARMUP = 240
LOOKBACK_MONTHS = 12


class HSlowInputError(ValueError):
    """Input cannot support a point-in-time H_SLOW research conclusion."""


def _utc(value: Any, label: str) -> datetime:
    if not isinstance(value, str):
        raise HSlowInputError(f"{label} must be an ISO-8601 UTC timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise HSlowInputError(f"{label} is invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise HSlowInputError(f"{label} must be UTC")
    return parsed.astimezone(timezone.utc)


def _positive_finite(value: Any, label: str) -> float:
    if isinstance(value, bool):
        raise HSlowInputError(f"{label} must be a positive finite number")
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise HSlowInputError(f"{label} must be a positive finite number") from exc
    if not math.isfinite(result) or result <= 0:
        raise HSlowInputError(f"{label} must be a positive finite number")
    return result


def _month_before(year: int, month: int, count: int = 1) -> tuple[int, int]:
    ordinal = year * 12 + (month - 1) - count
    return ordinal // 12, ordinal % 12 + 1


def _month_span(start: tuple[int, int], end: tuple[int, int]) -> list[tuple[int, int]]:
    months: list[tuple[int, int]] = []
    year, month = start
    while (year, month) <= end:
        months.append((year, month))
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return months


def _last_weekday_in_month(year: int, month: int) -> datetime:
    """Return the final Monday--Friday UTC session date in a calendar month.

    This intentionally makes a source gap at month-end fail closed.  A future
    production data adapter may add an explicit, versioned FX-holiday calendar;
    until then the research component must not silently treat an older close as
    the month's final close.
    """
    next_year, next_month = (year + 1, 1) if month == 12 else (year, month + 1)
    candidate = datetime(next_year, next_month, 1, tzinfo=timezone.utc) - timedelta(days=1)
    while candidate.weekday() >= 5:
        candidate -= timedelta(days=1)
    return candidate


def monthly_target(*, decision_at_utc: str, daily_bars: list[dict[str, Any]]) -> dict[str, Any]:
    """Return the frozen monthly H_SLOW target from qualified daily closes.

    A decision is allowed only on the first UTC calendar day, after the prior
    UTC month has completed.  Every supplied bar must already be closed and
    available at that decision timestamp; accepting a future or unavailable
    row would make the conclusion look ahead.
    """
    decision_at = _utc(decision_at_utc, "decision_at_utc")
    if decision_at.day != 1:
        raise HSlowInputError("decision_at_utc is not in the monthly decision clock")
    if not isinstance(daily_bars, list) or len(daily_bars) < MINIMUM_DAILY_BAR_WARMUP:
        raise HSlowInputError(
            f"at least {MINIMUM_DAILY_BAR_WARMUP} completed daily bars are required"
        )

    validated: list[tuple[datetime, datetime, float]] = []
    previous_open: datetime | None = None
    for index, row in enumerate(daily_bars):
        if not isinstance(row, dict):
            raise HSlowInputError(f"daily bar {index} is invalid")
        opened = _utc(row.get("opened_at_utc"), f"daily bar {index} opened_at_utc")
        closed = _utc(row.get("closed_at_utc"), f"daily bar {index} closed_at_utc")
        available = _utc(row.get("available_at_utc"), f"daily bar {index} available_at_utc")
        if closed - opened != timedelta(days=1):
            raise HSlowInputError(f"daily bar {index} is not a one-day bar")
        if previous_open is not None and opened <= previous_open:
            raise HSlowInputError(f"daily bars are not strictly chronological at index {index}")
        if closed > decision_at:
            raise HSlowInputError(f"daily bar {index} is not closed at decision time")
        if available < closed or available > decision_at:
            raise HSlowInputError(f"daily bar {index} is unavailable at decision time")
        validated.append((opened, closed, _positive_finite(row.get("close"), f"daily bar {index} close")))
        previous_open = opened

    target_month = _month_before(decision_at.year, decision_at.month)
    reference_month = _month_before(*target_month, LOOKBACK_MONTHS)
    closes_by_month: dict[tuple[int, int], tuple[datetime, float]] = {}
    for opened, closed, close in validated:
        key = (opened.year, opened.month)
        # Input order was validated, so this deliberately retains each month's
        # final completed daily close.
        closes_by_month[key] = (closed, close)
    missing = [month for month in _month_span(reference_month, target_month) if month not in closes_by_month]
    if missing:
        formatted = ", ".join(f"{year:04d}-{month:02d}" for year, month in missing)
        raise HSlowInputError(f"daily-bar monthly coverage is incomplete: {formatted}")
    for month in _month_span(reference_month, target_month):
        final_opened = closes_by_month[month][0] - timedelta(days=1)
        if final_opened.date() != _last_weekday_in_month(*month).date():
            raise HSlowInputError(
                "daily-bar monthly coverage is incomplete: "
                f"final session missing for {month[0]:04d}-{month[1]:02d}"
            )

    reference_closed, reference_close = closes_by_month[reference_month]
    signal_closed, signal_close = closes_by_month[target_month]
    return_12m = signal_close / reference_close - 1.0
    action = "BUY" if return_12m > 0 else "SELL" if return_12m < 0 else "NO_TRADE"
    return {
        "policy_version": POLICY_VERSION,
        "instrument": INSTRUMENT,
        "decision_at_utc": decision_at.isoformat().replace("+00:00", "Z"),
        "signal_month": f"{target_month[0]:04d}-{target_month[1]:02d}",
        "reference_month": f"{reference_month[0]:04d}-{reference_month[1]:02d}",
        "signal_closed_at_utc": signal_closed.isoformat().replace("+00:00", "Z"),
        "reference_closed_at_utc": reference_closed.isoformat().replace("+00:00", "Z"),
        "return_12m": return_12m,
        "action": action,
        "reason": "positive 12-month completed-daily-close return" if action == "BUY" else
                  "negative 12-month completed-daily-close return" if action == "SELL" else
                  "zero 12-month completed-daily-close return",
        "research_only": True,
        "execution_authority": False,
    }
