from copy import deepcopy

import pytest

from forex.event_quality import fixture_records, qualify_events

CUTOFF = "2026-10-15T00:00:00Z"


@pytest.mark.parametrize("field,value", [("revision", 2.9), ("revision", True),
    ("revision", "2"), ("license", None), ("event_id", None), ("source_id", ""), ("event_name", None)])
def test_malformed_identity_is_quarantined(field, value):
    row = deepcopy(fixture_records()[0])
    row[field] = value
    result = qualify_events([row], CUTOFF)
    assert result["accepted"] == []
    assert result["quarantined"]


def test_conflicting_revisions_are_order_independent_and_suppress_older_schedule():
    old = deepcopy(fixture_records()[0])
    new = {**old, "revision": 2}
    cancelled = {**new, "status": "CANCELLED"}
    forward = qualify_events([old, new, cancelled], CUTOFF)
    backward = qualify_events([cancelled, new, old], CUTOFF)
    assert forward == backward
    assert not forward["accepted"]


def test_future_conflicting_revisions_do_not_change_past_context():
    old = deepcopy(fixture_records()[0])
    future = {**old, "revision": 2, "available_at_utc": "2026-11-01T00:00:00Z"}
    result = qualify_events([old, future, {**future, "status": "CANCELLED"}], CUTOFF)
    assert len(result["accepted"]) == 1
    assert result["accepted"][0]["revision"] == 1


def test_known_newer_invalid_cancellation_does_not_restore_old_schedule():
    old = deepcopy(fixture_records()[0])
    new = {**old, "revision": 2, "status": "CANCELLED", "license": None}
    result = qualify_events([old, new], CUTOFF)
    assert result["accepted"] == []
    assert {row["reason"] for row in result["quarantined"]} == {
        "MISSING_PROVENANCE", "AMBIGUOUS_REVISION_LINEAGE"}
