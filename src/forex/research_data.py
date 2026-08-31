"""Read-only application boundary for point-in-time historical research."""
from __future__ import annotations

from .data_contracts import bars_available_before, validate_dataset_snapshot


def historical_bars(snapshot: dict, cutoff_utc: str) -> list[dict]:
    """Return validated EUR/USD historical bars available at ``cutoff_utc``.

    This is deliberately an in-process application boundary: callers provide a
    governed snapshot; this module has no database, MT5, network, account, or
    order capability.
    """
    validate_dataset_snapshot(snapshot)
    return bars_available_before(snapshot, cutoff_utc)
