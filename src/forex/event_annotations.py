"""Decision-time economic-event context with no trading authority.

This module deliberately turns an already-qualified event result into a small,
replayable *annotation*.  It does not choose a direction, assess entry
eligibility, or return an allow/block signal.  In particular, records that
passed :func:`forex.event_quality.qualify_events` are not evidence that a
calendar is complete, healthy, or quiet; coverage therefore remains explicit
and unknown until a separately qualified coverage snapshot exists.
"""
from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any


class EventAnnotationInputError(ValueError):
    """Raised when an alleged qualified result cannot be used as-of a decision."""


def _utc(value: object, *, field: str) -> datetime:
    if not isinstance(value, str):
        raise EventAnnotationInputError(f"{field} must be an ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise EventAnnotationInputError(f"{field} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise EventAnnotationInputError(f"{field} must include an offset")
    return parsed.astimezone(UTC)


def _stamp(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _verified_qualified_result(result: dict[str, Any], decision: datetime) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Validate the deterministic result shape produced by ``qualify_events``."""
    if not isinstance(result, dict):
        raise EventAnnotationInputError("qualified_result must be a mapping")
    cutoff = _utc(result.get("decision_cutoff_utc"), field="decision_cutoff_utc")
    if cutoff != decision:
        raise EventAnnotationInputError("qualified result cutoff must equal decision_at_utc")
    accepted = result.get("accepted")
    quarantined = result.get("quarantined")
    if not isinstance(accepted, list) or not all(isinstance(item, dict) for item in accepted):
        raise EventAnnotationInputError("qualified result accepted must be a list of mappings")
    if not isinstance(quarantined, list) or not all(isinstance(item, dict) for item in quarantined):
        raise EventAnnotationInputError("qualified result quarantined must be a list of mappings")
    payload = {
        "decision_cutoff_utc": _stamp(cutoff),
        "accepted": accepted,
        "quarantined": quarantined,
    }
    payload_digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    expected = f"sha256:{payload_digest}"
    if result.get("result_sha256") != expected:
        raise EventAnnotationInputError("qualified result digest does not match its contents")
    return accepted, quarantined


def event_annotation(
    qualified_result: dict[str, Any],
    *,
    decision_at_utc: str,
    window_start_utc: str,
    window_end_utc: str,
) -> dict[str, Any]:
    """Return qualified event context for an inclusive UTC time window.

    ``qualified_result`` must be the unchanged output of
    :func:`forex.event_quality.qualify_events` for exactly
    ``decision_at_utc``.  This prevents a later qualification run from being
    relabelled as information available at an earlier decision.  Quarantined
    records are retained verbatim because they have no reliable schedule by
    which to decide window membership.
    """
    decision = _utc(decision_at_utc, field="decision_at_utc")
    start = _utc(window_start_utc, field="window_start_utc")
    end = _utc(window_end_utc, field="window_end_utc")
    if end < start:
        raise EventAnnotationInputError("window_end_utc must not precede window_start_utc")
    accepted, quarantined = _verified_qualified_result(qualified_result, decision)

    events: list[dict[str, Any]] = []
    source_ids: set[str] = set()
    for record in accepted:
        required = {"event_id", "revision", "source_id", "source_url", "available_at_utc", "scheduled_at_utc"}
        missing = required - record.keys()
        if missing:
            raise EventAnnotationInputError("accepted event is missing required provenance or timing")
        available = _utc(record["available_at_utc"], field="accepted.available_at_utc")
        if available > decision:
            raise EventAnnotationInputError("accepted event is unavailable at decision time")
        scheduled = _utc(record["scheduled_at_utc"], field="accepted.scheduled_at_utc")
        source_ids.add(str(record["source_id"]))
        if start <= scheduled <= end:
            # Keep the complete qualified record nested, including source URL,
            # revision and availability.  The extra fields are descriptive
            # timing only, never a trade instruction.
            events.append({
                "event": dict(record),
                "scheduled_at_utc": _stamp(scheduled),
                "seconds_from_decision": int((scheduled - decision).total_seconds()),
            })
    events.sort(key=lambda item: (item["scheduled_at_utc"], str(item["event"]["event_id"])))

    payload = {
        "annotation_type": "EVENT_CONTEXT_ONLY",
        "decision_at_utc": _stamp(decision),
        "window": {"start_utc": _stamp(start), "end_utc": _stamp(end)},
        "qualified_result_sha256": qualified_result["result_sha256"],
        "coverage": {
            "status": "UNKNOWN",
            "reason": "QUALIFIED_EVENTS_DO_NOT_ASSERT_COMPLETE_CALENDAR_COVERAGE",
            "source_ids_with_accepted_records": sorted(source_ids),
        },
        "events": events,
        "quarantined": [dict(item) for item in quarantined],
        "quarantine_window_membership": "UNKNOWN_WITHOUT_RELIABLE_SCHEDULE",
    }
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return {**payload, "annotation_sha256": f"sha256:{digest}"}
