"""Point-in-time D1 input adapter for the disabled H_SLOW policy.

This is a research-data boundary only.  It turns an already validated
historical snapshot into the explicit bar shape consumed by ``h_slow_policy``;
it cannot fetch data, select an account, or submit an order.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
import hashlib
import json
from typing import Any

from .data_contracts import ContractError, validate_dataset_snapshot


ADAPTER_VERSION = "forex.h-slow.d1-input.v1"


class HSlowDataInputError(ValueError):
    """A dataset snapshot cannot support a monthly point-in-time decision."""


def _utc(value: Any, field: str) -> datetime:
    if not isinstance(value, str):
        raise HSlowDataInputError(f"{field} must be an RFC3339 timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise HSlowDataInputError(f"{field} is invalid") from exc
    if parsed.tzinfo is None:
        raise HSlowDataInputError(f"{field} must include an offset")
    return parsed.astimezone(UTC)


def _stamp(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _digest(value: dict[str, Any]) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def h_slow_daily_input(snapshot: dict[str, Any], *, decision_at_utc: str) -> dict[str, Any]:
    """Adapt a validated EUR/USD D1 snapshot for a frozen H_SLOW decision.

    The snapshot boundary and requested decision must be identical: using an
    older snapshot at a newer decision would make absent data look known, while
    relabelling a newer snapshot would look ahead.  A D1 input is one UTC day
    beginning at midnight and must be available only after that day has closed.
    """
    try:
        checked = validate_dataset_snapshot(snapshot)
    except ContractError as exc:
        raise HSlowDataInputError(f"invalid dataset snapshot: {exc}") from exc
    if checked["instrument"] != "EUR/USD" or checked["timeframe"] != "D1":
        raise HSlowDataInputError("H_SLOW requires an EUR/USD D1 dataset snapshot")

    decision = _utc(decision_at_utc, "decision_at_utc")
    snapshot_cutoff = _utc(checked["decision_cutoff_utc"], "snapshot decision_cutoff_utc")
    if decision != snapshot_cutoff:
        raise HSlowDataInputError("decision_at_utc must equal the dataset snapshot cutoff")

    daily_bars: list[dict[str, Any]] = []
    previous_open: datetime | None = None
    for index, source in enumerate(checked["price_bars"]):
        opened = _utc(source["time_utc"], f"price bar {index} time_utc")
        available = _utc(source["available_at_utc"], f"price bar {index} available_at_utc")
        if opened.hour or opened.minute or opened.second or opened.microsecond:
            raise HSlowDataInputError(f"price bar {index} must open at UTC midnight")
        closed = opened + timedelta(days=1)
        if closed > decision:
            raise HSlowDataInputError(f"price bar {index} is not closed at decision time")
        if available < closed or available > decision:
            raise HSlowDataInputError(f"price bar {index} is unavailable as a completed D1 bar")
        if previous_open is not None and opened <= previous_open:
            raise HSlowDataInputError(f"price bars are not strictly chronological at index {index}")
        daily_bars.append({
            "opened_at_utc": _stamp(opened),
            "closed_at_utc": _stamp(closed),
            "available_at_utc": _stamp(available),
            "close": source["close"],
        })
        previous_open = opened

    content = {
        "adapter_version": ADAPTER_VERSION,
        "snapshot_id": checked["snapshot_id"],
        "snapshot_artifact_sha256": checked["artifact_sha256"],
        "decision_at_utc": _stamp(decision),
        "daily_bars": daily_bars,
    }
    return {
        **content,
        "input_sha256": _digest(content),
        "research_only": True,
        "execution_authority": False,
    }
