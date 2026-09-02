"""M17's offline, non-executing research-agent context boundary."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

FORBIDDEN_KEYS = {"account", "credentials", "mt5_control", "order", "execution", "future_bars"}


def _utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def build_context(*, bars: list[dict[str, Any]], cutoff_utc: str, features: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return only closed historical research data available by the cutoff.

    This pure function has no model, network, MT5, account, command, or order surface.
    """
    cutoff = _utc(cutoff_utc)
    selected: list[dict[str, Any]] = []
    previous: datetime | None = None
    for bar in bars:
        if FORBIDDEN_KEYS & set(bar):
            raise ValueError("input contains a forbidden agent-context field")
        timestamp = _utc(str(bar["time_utc"]))
        available = _utc(str(bar["available_at_utc"]))
        if timestamp > cutoff or available > cutoff:
            continue
        if previous is not None and timestamp <= previous:
            raise ValueError("bars must be strictly chronological")
        previous = timestamp
        selected.append({key: bar[key] for key in ("time_utc", "open", "high", "low", "close", "volume") if key in bar})
    safe_features = dict(features or {})
    if FORBIDDEN_KEYS & set(safe_features):
        raise ValueError("features contain a forbidden agent-context field")
    return {
        "schema_version": "forex.agent-context.v1",
        "mode": "OFFLINE_CONTEXT_ONLY",
        "cutoff_utc": cutoff.isoformat().replace("+00:00", "Z"),
        "price_bars": selected,
        "research_features": safe_features,
        "agent_authority": "NONE",
        "order_capability": False,
        "live_trading_capability": False,
    }
