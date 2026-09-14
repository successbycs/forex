"""Deterministic, fail-closed quality controls for historical event context.

This module deliberately qualifies *event metadata*, not market direction or a
trading signal.  An event is usable only when its source/provenance, exact
availability, revision lineage, cancellation state, and local-time conversion
are all known as of the supplied decision cutoff.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


REQUIRED = {
    "event_id", "event_name", "source_id", "source_url", "license", "status",
    "revision", "available_at_utc", "time_precision",
}
EXACT = "EXACT_LOCAL_TIME"
DATE_ONLY = "DATE_ONLY"


def _utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include an offset")
    return parsed.astimezone(UTC)


def _identity(record: dict[str, Any]) -> str:
    return f"{record.get('event_id', 'unknown')}@{record.get('revision', 'unknown')}"


def _local_to_utc(record: dict[str, Any]) -> str:
    """Convert an exact local schedule, rejecting DST gaps/ambiguity by default."""
    try:
        local = datetime.fromisoformat(str(record["scheduled_at_local"]))
        if local.tzinfo is not None:
            raise ValueError("scheduled_at_local must not embed an offset")
        zone = ZoneInfo(str(record["timezone"]))
    except (KeyError, TypeError, ValueError, ZoneInfoNotFoundError) as exc:
        raise ValueError("INVALID_LOCAL_TIME") from exc
    candidates: list[tuple[int, datetime]] = []
    for fold in (0, 1):
        aware = local.replace(tzinfo=zone, fold=fold)
        round_trip = aware.astimezone(UTC).astimezone(zone).replace(tzinfo=None)
        if round_trip == local:
            candidates.append((fold, aware.astimezone(UTC)))
    unique = {candidate.isoformat() for _, candidate in candidates}
    if not unique:
        raise ValueError("DST_NONEXISTENT_LOCAL_TIME")
    if len(unique) > 1:
        fold = record.get("local_fold")
        if fold not in (0, 1):
            raise ValueError("DST_AMBIGUOUS_LOCAL_TIME")
        selected = [candidate for candidate_fold, candidate in candidates if candidate_fold == fold]
        if not selected:
            raise ValueError("INVALID_LOCAL_TIME")
        return selected[0].isoformat().replace("+00:00", "Z")
    return candidates[0][1].isoformat().replace("+00:00", "Z")


def qualify_events(records: list[dict[str, Any]], decision_cutoff_utc: str) -> dict[str, Any]:
    """Return latest usable revisions and explicit quarantine outcomes.

    Records are never silently repaired.  DATE_ONLY schedules are retained as
    quarantine because they cannot safely support intraday historical context.
    """
    cutoff = _utc(decision_cutoff_utc)
    if not isinstance(records, list) or not all(isinstance(row, dict) for row in records):
        raise ValueError("records must be a list of event objects")
    candidates: list[dict[str, Any]] = []
    quarantined: list[dict[str, str]] = []
    # Every duplicate version is ambiguous. Quarantine the entire version so
    # input order cannot decide whether a cancellation suppresses a schedule.
    def known_by_cutoff(row: dict[str, Any]) -> bool:
        try:
            return _utc(str(row.get("available_at_utc"))) <= cutoff
        except ValueError:
            return False

    version_counts = Counter(
        (row["event_id"], row["revision"]) for row in records
        if isinstance(row.get("event_id"), str)
        and type(row.get("revision")) is int and row["revision"] >= 1
        and known_by_cutoff(row)
    )
    for record in records:
        identity = _identity(record)
        missing = REQUIRED - record.keys()
        if missing:
            quarantined.append({"event": identity, "reason": "MISSING_REQUIRED_FIELD"})
            continue
        if type(record["revision"]) is not int or record["revision"] < 1:
            quarantined.append({"event": identity, "reason": "INVALID_REVISION"})
            continue
        revision = record["revision"]
        if not all(isinstance(record[field], str) and record[field].strip()
                   for field in ("event_id", "event_name", "source_id", "source_url", "license")):
            quarantined.append({"event": identity, "reason": "MISSING_PROVENANCE"})
            continue
        key = (record["event_id"], revision)
        if known_by_cutoff(record) and version_counts[key] > 1:
            quarantined.append({"event": identity, "reason": "DUPLICATE_REVISION"})
            continue
        if not str(record["source_url"]).startswith("https://") or not str(record["license"]).strip():
            quarantined.append({"event": identity, "reason": "MISSING_PROVENANCE"})
            continue
        try:
            available = _utc(str(record["available_at_utc"]))
        except ValueError:
            quarantined.append({"event": identity, "reason": "MALFORMED_AVAILABILITY"})
            continue
        if available > cutoff:
            quarantined.append({"event": identity, "reason": "LOOKAHEAD"})
            continue
        # Status is deliberately resolved *after* revision selection.  A later
        # cancellation or unknown state must suppress an earlier schedule.
        candidates.append({**record, "revision": revision, "available_at_utc": available.isoformat().replace("+00:00", "Z")})

    accepted: list[dict[str, Any]] = []
    for event_id in sorted({str(item["event_id"]) for item in candidates}):
        versions = [item for item in candidates if str(item["event_id"]) == event_id]
        current = max(versions, key=lambda item: item["revision"])
        # An ambiguous newer version cannot resurrect an older schedule.
        ambiguous_newer = any(identity == event_id and
                              (revision > current["revision"] or
                               (revision == current["revision"] and count > 1))
                              for (identity, revision), count in version_counts.items())
        if ambiguous_newer:
            for version in versions:
                quarantined.append({"event": _identity(version), "reason": "AMBIGUOUS_REVISION_LINEAGE"})
            continue
        for old in versions:
            if old is not current:
                quarantined.append({"event": _identity(old), "reason": "SUPERSEDED_REVISION"})
        if current["status"] == "CANCELLED":
            quarantined.append({"event": _identity(current), "reason": "CANCELLED"})
            continue
        if current["status"] != "SCHEDULED":
            quarantined.append({"event": _identity(current), "reason": "UNKNOWN_STATUS"})
            continue
        if current["time_precision"] != EXACT:
            quarantined.append({"event": _identity(current), "reason": "TIME_PRECISION_INSUFFICIENT"})
            continue
        try:
            scheduled_at_utc = _local_to_utc(current)
        except ValueError as exc:
            quarantined.append({"event": _identity(current), "reason": str(exc)})
            continue
        accepted.append({**current, "scheduled_at_utc": scheduled_at_utc})
    accepted.sort(key=lambda item: (item["scheduled_at_utc"], item["event_id"]))
    quarantined.sort(key=lambda item: (item["event"], item["reason"]))
    payload = {"decision_cutoff_utc": cutoff.isoformat().replace("+00:00", "Z"), "accepted": accepted, "quarantined": quarantined}
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return {**payload, "result_sha256": f"sha256:{digest}"}


def fixture_records() -> list[dict[str, Any]]:
    """A source-labelled drill fixture exercising each mandatory M21 control."""
    fred = "https://fred.stlouisfed.org/docs/api/fred/release_dates.html"
    ecb = "https://www.ecb.europa.eu/press/calendars/statscal/html/index.en.html"
    base = {"source_id": "ecb-statistical-calendar", "source_url": ecb, "license": "ECB public statistical-calendar terms", "status": "SCHEDULED", "time_precision": EXACT, "timezone": "Europe/Berlin"}
    return [
        {**base, "event_id": "ecb-hicp-2026-10", "event_name": "HICP", "revision": 1, "scheduled_at_local": "2026-10-25T02:30:00", "local_fold": 1, "available_at_utc": "2026-10-01T00:00:00Z"},
        {**base, "event_id": "ecb-hicp-2026-10", "event_name": "HICP revised", "revision": 2, "scheduled_at_local": "2026-10-25T03:30:00", "available_at_utc": "2026-10-02T00:00:00Z"},
        {**base, "event_id": "ecb-cancelled", "event_name": "Cancelled release", "revision": 1, "status": "CANCELLED", "scheduled_at_local": "2026-10-20T10:00:00", "available_at_utc": "2026-10-01T00:00:00Z"},
        {"event_id": "fred-cpi-date", "event_name": "CPI release date", "source_id": "fred-release-dates", "source_url": fred, "license": "FRED API terms", "status": "SCHEDULED", "revision": 1, "available_at_utc": "2026-10-01T00:00:00Z", "time_precision": DATE_ONLY},
        {**base, "event_id": "ecb-future-revision", "event_name": "Future revision", "revision": 1, "scheduled_at_local": "2026-10-20T10:00:00", "available_at_utc": "2026-11-01T00:00:00Z"},
        {**base, "event_id": "ecb-dst-gap", "event_name": "DST gap", "revision": 1, "scheduled_at_local": "2026-03-29T02:30:00", "available_at_utc": "2026-01-01T00:00:00Z"},
    ]
