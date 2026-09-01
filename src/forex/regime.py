"""Deterministic, research-only M14 regime and event-window classification."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any


def session_contract(config: dict[str, Any]) -> dict[str, Any]:
    value = config["intraday_session"]
    if value["contract_version"] != "eurusd-intraday-session.v1":
        raise ValueError("unsupported session contract")
    if not value["decision_time_utc"] < value["flat_by_time_utc"]:
        raise ValueError("decision time must precede flat-by time")
    if value["daylight_saving_policy"] != "UTC_FIXED":
        raise ValueError("session contract must be UTC fixed")
    return dict(value)


def classify_regime(bars: list[dict[str, Any]]) -> str:
    """Classify a bounded historical window without a prediction or signal."""
    if len(bars) < 2:
        return "INSUFFICIENT_HISTORY"
    closes = [float(bar["close"]) for bar in bars]
    ranges = [float(bar["high"]) - float(bar["low"]) for bar in bars]
    move = abs(closes[-1] / closes[0] - 1.0)
    average_range = sum(ranges) / len(ranges)
    if average_range / closes[-1] >= 0.003:
        return "HIGH_VOLATILITY"
    if move >= 0.002:
        return "TRENDING"
    return "RANGE_BOUND"


def event_window(decision_at_utc: str, events: list[dict[str, Any]], blackout_minutes: int) -> str:
    decision = datetime.fromisoformat(decision_at_utc.replace("Z", "+00:00"))
    for event in events:
        scheduled = event.get("scheduled_at_utc")
        if not scheduled:
            continue
        instant = datetime.fromisoformat(scheduled.replace("Z", "+00:00"))
        if abs(instant - decision) <= timedelta(minutes=blackout_minutes):
            return "EVENT_BLACKOUT"
    return "NO_SCHEDULED_EVENT_BLACKOUT"


def classify_context(bars: list[dict[str, Any]], decision_at_utc: str, events: list[dict[str, Any]], config: dict[str, Any]) -> dict[str, str]:
    contract = session_contract(config)
    return {"regime": classify_regime(bars), "event_window": event_window(decision_at_utc, events, contract["scheduled_event_blackout_minutes"]), "session_contract_version": contract["contract_version"]}
