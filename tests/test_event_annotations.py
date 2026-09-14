from __future__ import annotations

import copy

import pytest

from forex.event_annotations import EventAnnotationInputError, event_annotation
from forex.event_quality import fixture_records, qualify_events


DECISION = "2026-10-15T00:00:00Z"


def qualified() -> dict:
    return qualify_events(fixture_records(), DECISION)


def test_annotation_is_context_only_and_preserves_qualified_provenance():
    result = event_annotation(
        qualified(),
        decision_at_utc=DECISION,
        window_start_utc="2026-10-24T00:00:00Z",
        window_end_utc="2026-10-26T00:00:00Z",
    )
    assert result["annotation_type"] == "EVENT_CONTEXT_ONLY"
    assert not ({"allow", "block", "trade", "action"} & set(result))
    assert result["coverage"] == {
        "status": "UNKNOWN",
        "reason": "QUALIFIED_EVENTS_DO_NOT_ASSERT_COMPLETE_CALENDAR_COVERAGE",
        "source_ids_with_accepted_records": ["ecb-statistical-calendar"],
    }
    assert len(result["events"]) == 1
    event = result["events"][0]
    assert event["scheduled_at_utc"] == "2026-10-25T02:30:00Z"
    assert event["seconds_from_decision"] == 873000
    assert event["event"]["source_id"] == "ecb-statistical-calendar"
    assert event["event"]["revision"] == 2
    assert event["event"]["available_at_utc"] == "2026-10-02T00:00:00Z"
    assert result["annotation_sha256"].startswith("sha256:")


def test_window_exclusion_does_not_erase_quarantine_or_claim_clear_coverage():
    source = qualified()
    result = event_annotation(
        source,
        decision_at_utc=DECISION,
        window_start_utc="2026-10-20T00:00:00Z",
        window_end_utc="2026-10-21T00:00:00Z",
    )
    assert result["events"] == []
    assert result["quarantined"] == source["quarantined"]
    assert result["quarantine_window_membership"] == "UNKNOWN_WITHOUT_RELIABLE_SCHEDULE"
    assert result["coverage"]["status"] == "UNKNOWN"


def test_annotation_rejects_a_mismatched_or_tampered_qualified_result():
    with pytest.raises(EventAnnotationInputError, match="cutoff"):
        event_annotation(
            qualified(),
            decision_at_utc="2026-10-14T00:00:00Z",
            window_start_utc="2026-10-24T00:00:00Z",
            window_end_utc="2026-10-26T00:00:00Z",
        )
    tampered = copy.deepcopy(qualified())
    tampered["accepted"][0]["revision"] = 999
    with pytest.raises(EventAnnotationInputError, match="digest"):
        event_annotation(
            tampered,
            decision_at_utc=DECISION,
            window_start_utc="2026-10-24T00:00:00Z",
            window_end_utc="2026-10-26T00:00:00Z",
        )


def test_annotation_rejects_future_available_event_and_inverted_window():
    source = qualified()
    source["accepted"][0]["available_at_utc"] = "2026-10-16T00:00:00Z"
    # Bind the deliberately malformed fixture so the annotation's as-of check,
    # rather than the digest check, is exercised.
    import hashlib
    import json

    payload = {key: source[key] for key in ("decision_cutoff_utc", "accepted", "quarantined")}
    source["result_sha256"] = "sha256:" + hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    with pytest.raises(EventAnnotationInputError, match="unavailable"):
        event_annotation(
            source,
            decision_at_utc=DECISION,
            window_start_utc="2026-10-24T00:00:00Z",
            window_end_utc="2026-10-26T00:00:00Z",
        )
    with pytest.raises(EventAnnotationInputError, match="precede"):
        event_annotation(
            qualified(),
            decision_at_utc=DECISION,
            window_start_utc="2026-10-26T00:00:00Z",
            window_end_utc="2026-10-24T00:00:00Z",
        )
