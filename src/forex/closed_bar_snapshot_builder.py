"""Pure builder for point-in-time EUR/USD H1 or D1 research snapshots.

The raw digest binds supplied retained bytes.  The fixed upstream
parser/collector, not this builder, establishes parsed-bar correspondence and
EUR/USD identity. Capture/observation/retrieval and decision timestamps are
caller-declared normalized provenance: this builder checks their consistency
and bounds, but does not independently attest to observation time.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
import hashlib
import math
import re
from typing import Any, Mapping

from forex.data_contracts import (CONTRACT_VERSION, ContractError, build_dataset_snapshot,
                                  validate_dataset_snapshot, validate_source_registry_entry)


class ClosedBarSnapshotError(ValueError):
    pass


_INPUT_BAR_FIELDS = {"time_utc", "open", "high", "low", "close", "volume", "available_at_utc"}
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}\Z")


def _utc(value: Any, field: str) -> datetime:
    if not isinstance(value, str):
        raise ClosedBarSnapshotError(f"{field} must be a UTC timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ClosedBarSnapshotError(f"{field} must be a UTC timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != UTC.utcoffset(parsed):
        raise ClosedBarSnapshotError(f"{field} must use UTC")
    return parsed.astimezone(UTC)


def _stamp(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def build_closed_eurusd_snapshot(*, snapshot_id: str, timeframe: str, decision_cutoff_utc: str,
                                 capture_available_at_utc: str, source_registry_entry: Mapping[str, Any],
                                 source_revision: str, raw_payload: bytes, payload_sha256: str,
                                 parsed_bars: list[Mapping[str, Any]]) -> dict[str, Any]:
    """Build a validated snapshot from already-observed raw bytes and closed bars.

    The payload path is a deterministic content address only, never an I/O
    request.  The caller remains responsible for immutable raw retention.
    """
    if timeframe not in {"H1", "D1"}:
        raise ClosedBarSnapshotError("timeframe must be H1 or D1")
    if not isinstance(raw_payload, bytes) or not raw_payload:
        raise ClosedBarSnapshotError("raw_payload must be non-empty bytes")
    actual_digest = "sha256:" + hashlib.sha256(raw_payload).hexdigest()
    if payload_sha256 != actual_digest or not _DIGEST.fullmatch(payload_sha256):
        raise ClosedBarSnapshotError("payload_sha256 does not bind supplied raw bytes")
    if not isinstance(source_revision, str) or not source_revision.strip():
        raise ClosedBarSnapshotError("source_revision must be non-empty text")
    try:
        source = validate_source_registry_entry(dict(source_registry_entry))
    except ContractError as exc:
        raise ClosedBarSnapshotError("source registry entry is invalid") from exc
    if source["timezone_policy"] != "UTC-normalised":
        raise ClosedBarSnapshotError("source registry timezone_policy must be UTC-normalised")
    cutoff = _utc(decision_cutoff_utc, "decision_cutoff_utc")
    capture = _utc(capture_available_at_utc, "capture_available_at_utc")
    if capture > cutoff:
        raise ClosedBarSnapshotError("capture availability exceeds decision cutoff")
    if not isinstance(parsed_bars, list) or not parsed_bars:
        raise ClosedBarSnapshotError("parsed_bars must be a non-empty list")
    duration = timedelta(hours=1) if timeframe == "H1" else timedelta(days=1)
    raw_id = "raw-" + actual_digest.removeprefix("sha256:")
    bars: list[dict[str, Any]] = []
    previous: datetime | None = None
    for candidate in parsed_bars:
        if not isinstance(candidate, Mapping) or set(candidate) != _INPUT_BAR_FIELDS:
            raise ClosedBarSnapshotError("parsed bar fields are invalid")
        opened = _utc(candidate["time_utc"], "bar time_utc")
        available = _utc(candidate["available_at_utc"], "bar available_at_utc")
        if (opened.minute or opened.second or opened.microsecond or (timeframe == "D1" and opened.hour)):
            raise ClosedBarSnapshotError("bar open is not aligned to timeframe")
        closed = opened + duration
        if closed > cutoff:
            raise ClosedBarSnapshotError("bar is incomplete or future at decision cutoff")
        if closed > capture:
            raise ClosedBarSnapshotError("bar close exceeds raw capture availability")
        if available < closed:
            raise ClosedBarSnapshotError("bar availability predates its close")
        if available < capture:
            raise ClosedBarSnapshotError("bar availability predates raw capture availability")
        if available > cutoff:
            raise ClosedBarSnapshotError("bar availability exceeds decision cutoff")
        if previous is not None and opened <= previous:
            raise ClosedBarSnapshotError("parsed bars must be strictly chronological without duplicates")
        previous = opened
        for field in ("open", "high", "low", "close"):
            value = candidate[field]
            if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value) or value <= 0:
                raise ClosedBarSnapshotError(f"bar {field} is invalid")
        if candidate["high"] < max(candidate["open"], candidate["close"]) or candidate["low"] > min(candidate["open"], candidate["close"]):
            raise ClosedBarSnapshotError("bar OHLC values are inconsistent")
        if not isinstance(candidate["volume"], int) or isinstance(candidate["volume"], bool) or candidate["volume"] < 0:
            raise ClosedBarSnapshotError("bar volume is invalid")
        bars.append({**dict(candidate), "time_utc": _stamp(opened), "available_at_utc": _stamp(available),
                     "raw_observation_id": raw_id})
    raw_observation = {
        "contract_version": CONTRACT_VERSION, "observation_id": raw_id, "source_id": source["source_id"],
        "source_revision": source_revision.strip(), "observed_at_utc": _stamp(capture),
        "available_at_utc": _stamp(capture), "retrieved_at_utc": _stamp(capture), "timezone": "UTC",
        "payload_sha256": actual_digest, "payload_path": "retained://raw/" + actual_digest.removeprefix("sha256:"),
        "redacted": False,
    }
    snapshot = build_dataset_snapshot(snapshot_id=snapshot_id, instrument="EUR/USD", timeframe=timeframe,
                                      decision_cutoff_utc=_stamp(cutoff), created_at_utc=_stamp(cutoff),
                                      source_registry=[source], raw_observations=[raw_observation], price_bars=bars)
    try:
        return validate_dataset_snapshot(snapshot)
    except ContractError as exc:
        raise ClosedBarSnapshotError("constructed snapshot violates data contract") from exc
