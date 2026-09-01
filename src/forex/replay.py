"""M13 UTC point-in-time alignment for historical replay only."""
from __future__ import annotations
from datetime import datetime
from typing import Any


def align_at_cutoff(price_bars: list[dict[str, Any]], contexts: list[dict[str, Any]], cutoff_utc: str) -> dict[str, Any]:
    cutoff = datetime.fromisoformat(cutoff_utc.replace("Z", "+00:00"))
    visible_context = [item for item in contexts if datetime.fromisoformat(item["available_at_utc"].replace("Z", "+00:00")) <= cutoff]
    visible_bars = [item for item in price_bars if datetime.fromisoformat(item["available_at_utc"].replace("Z", "+00:00")) <= cutoff]
    if not visible_bars:
        raise ValueError("No price bar is available at the requested cutoff")
    return {"cutoff_utc": cutoff_utc, "bar_count": len(visible_bars), "context_count": len(visible_context), "latest_bar_utc": max(item["time_utc"] for item in visible_bars), "no_lookahead": all(datetime.fromisoformat(item["available_at_utc"].replace("Z", "+00:00")) <= cutoff for item in visible_bars + visible_context)}
