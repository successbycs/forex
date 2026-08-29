"""Development-only historical market-data fixtures.

These helpers deliberately do not claim live connectivity or backtest proof.
They support M1 weekend readiness by enforcing an explicit historical-fixture
label and point-in-time replay boundary.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


FIXTURE_KIND = "HISTORICAL_FIXTURE"


def validate_fixture(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Validate a small, JSON-friendly development fixture and return its bars."""
    if payload.get("kind") != FIXTURE_KIND:
        raise ValueError("fixture must be explicitly labelled HISTORICAL_FIXTURE")
    if payload.get("symbol") != "EURUSD":
        raise ValueError("fixture symbol must be EURUSD")
    bars = payload.get("bars")
    if not isinstance(bars, list) or not bars:
        raise ValueError("fixture must contain one or more bars")
    previous: datetime | None = None
    for bar in bars:
        if set(bar) != {"time_utc", "open", "high", "low", "close", "volume"}:
            raise ValueError("fixture bar fields are invalid")
        observed = datetime.fromisoformat(str(bar["time_utc"]).replace("Z", "+00:00"))
        if observed.tzinfo is None:
            raise ValueError("fixture times must be UTC")
        if previous is not None and observed <= previous:
            raise ValueError("fixture bars must be strictly chronological")
        previous = observed.astimezone(timezone.utc)
    return bars


def replay_before(payload: dict[str, Any], decision_time_utc: str) -> list[dict[str, Any]]:
    """Return only bars known strictly before a decision time; reject lookahead."""
    decision = datetime.fromisoformat(decision_time_utc.replace("Z", "+00:00"))
    if decision.tzinfo is None:
        raise ValueError("decision time must be UTC")
    return [
        bar
        for bar in validate_fixture(payload)
        if datetime.fromisoformat(bar["time_utc"].replace("Z", "+00:00")) < decision
    ]
