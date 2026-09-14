from copy import deepcopy

import pytest

from forex.event_revisions import EventRevisionError, append_parsed_capture, empty_journal, qualify_journal, validate_journal


def capture(*, completed="2026-01-01T00:00:00Z", payload="sha256:" + "a" * 64, time="08:30", status="SCHEDULED", source="bls-cpi-release-schedule"):
    record = {"event_id": "bls-cpi-2025-11", "event_name": "US Consumer Price Index release",
              "source_id": source, "source_url": "https://www.bls.gov/schedule/news_release/cpi.htm",
              "license": "BLS terms", "license_url": "https://www.bls.gov/opub/copyright-information.htm",
              "status": status, "time_precision": "EXACT_LOCAL_TIME", "timezone": "America/New_York",
              "scheduled_at_local": f"2025-12-18T{time}:00", "reference_month": "2025-11",
              "release_date": "2025-12-18", "declared_release_time_local": time,
              "available_at_utc": completed, "payload_sha256": payload}
    return {"capture_completed_at_utc": completed, "payload_sha256": payload,
            "source_family": "CPI", "source_url": record["source_url"], "parser_version": "test.v1",
            "records": [record], "quarantined": []}


def test_identical_semantic_event_keeps_first_availability_despite_new_payload_and_capture():
    first = append_parsed_capture(empty_journal(), capture_id="capture-1", parsed_capture=capture())
    second = append_parsed_capture(first, capture_id="capture-2", parsed_capture=capture(completed="2026-01-02T00:00:00Z", payload="sha256:" + "b" * 64))
    assert len(second["records"]) == 1
    assert second["records"][0]["available_at_utc"] == "2026-01-01T00:00:00Z"
    assert second["captures"][1]["payload_sha256"] == "sha256:" + "b" * 64


def test_semantic_schedule_status_or_source_change_creates_local_revision_and_keeps_old():
    journal = append_parsed_capture(empty_journal(), capture_id="one", parsed_capture=capture())
    revised = append_parsed_capture(journal, capture_id="two", parsed_capture=capture(completed="2026-01-02T00:00:00Z", time="09:15"))
    assert [(item["revision"], item["declared_release_time_local"]) for item in revised["records"]] == [(1, "08:30"), (2, "09:15")]
    assert revised["records"][1]["revision_semantics"] == "LOCAL_CAPTURE_SEMANTIC_CHANGE"
    status = append_parsed_capture(revised, capture_id="three", parsed_capture=capture(completed="2026-01-03T00:00:00Z", time="09:15", status="CANCELLED"))
    assert status["records"][-1]["revision"] == 3
    source = append_parsed_capture(status, capture_id="four", parsed_capture=capture(completed="2026-01-04T00:00:00Z", time="09:15", status="CANCELLED", source="other-source"))
    assert source["records"][-1]["revision"] == 4


def test_disappearance_is_recorded_as_absence_not_cancellation():
    journal = append_parsed_capture(empty_journal(), capture_id="one", parsed_capture=capture())
    missing = capture(completed="2026-01-02T00:00:00Z")
    missing["records"] = []
    result = append_parsed_capture(journal, capture_id="two", parsed_capture=missing)
    assert len(result["records"]) == 1
    assert result["records"][0]["status"] == "SCHEDULED"
    assert result["captures"][-1]["disappeared_event_ids"] == ["bls-cpi-2025-11"]


def test_tamper_conflict_clock_and_capture_record_binding_are_rejected_without_aliasing():
    journal = append_parsed_capture(empty_journal(), capture_id="one", parsed_capture=capture())
    tampered = deepcopy(journal); tampered["records"][0]["status"] = "CANCELLED"
    with pytest.raises(EventRevisionError, match="does not bind"):
        validate_journal(tampered)
    bad = capture(completed="2026-01-02T00:00:00Z"); bad["records"][0]["payload_sha256"] = "sha256:" + "z" * 64
    with pytest.raises(EventRevisionError, match="does not bind"):
        append_parsed_capture(journal, capture_id="two", parsed_capture=bad)
    with pytest.raises(EventRevisionError, match="capture_id"):
        append_parsed_capture(journal, capture_id="one", parsed_capture=capture(completed="2026-01-02T00:00:00Z"))
    with pytest.raises(EventRevisionError, match="later"):
        append_parsed_capture(journal, capture_id="two", parsed_capture=capture())
    returned = append_parsed_capture(journal, capture_id="two", parsed_capture=capture(completed="2026-01-02T00:00:00Z"))
    returned["records"][0]["status"] = "MUTATED"
    assert journal["records"][0]["status"] == "SCHEDULED"


def test_journal_feeds_existing_quality_gate_with_latest_local_revision():
    journal = append_parsed_capture(empty_journal(), capture_id="one", parsed_capture=capture())
    journal = append_parsed_capture(journal, capture_id="two", parsed_capture=capture(completed="2026-01-02T00:00:00Z", time="09:15"))
    result = qualify_journal(journal, decision_cutoff_utc="2026-01-03T00:00:00Z")
    assert len(result["accepted"]) == 1
    assert result["accepted"][0]["revision"] == 2
    assert result["accepted"][0]["scheduled_at_utc"] == "2025-12-18T14:15:00Z"


def test_fold_is_preserved_and_fold_change_creates_revision():
    parsed = capture()
    parsed["records"][0].update(timezone="Europe/Berlin", scheduled_at_local="2026-10-25T02:30:00", local_fold=1)
    journal = append_parsed_capture(empty_journal(), capture_id="one", parsed_capture=parsed)
    result = qualify_journal(journal, decision_cutoff_utc="2026-01-03T00:00:00Z")
    assert result["accepted"][0]["scheduled_at_utc"] == "2026-10-25T01:30:00Z"
    revised = deepcopy(parsed)
    revised["capture_completed_at_utc"] = "2026-01-02T00:00:00Z"
    revised["records"][0].update(available_at_utc=revised["capture_completed_at_utc"], local_fold=0)
    journal = append_parsed_capture(journal, capture_id="two", parsed_capture=revised)
    result = qualify_journal(journal, decision_cutoff_utc="2026-01-03T00:00:00Z")
    assert result["accepted"][0]["revision"] == 2
    assert result["accepted"][0]["scheduled_at_utc"] == "2026-10-25T00:30:00Z"


def test_disappearance_does_not_mix_source_calendars():
    journal = append_parsed_capture(empty_journal(), capture_id="cpi", parsed_capture=capture())
    employment = capture(completed="2026-01-02T00:00:00Z")
    employment["source_family"] = "EMPLOYMENT_SITUATION"
    employment["source_url"] = "https://www.bls.gov/schedule/news_release/empsit.htm"
    employment["records"][0].update(event_id="employment-2025-11", source_url=employment["source_url"])
    journal = append_parsed_capture(journal, capture_id="employment", parsed_capture=employment)
    assert journal["captures"][-1]["disappeared_event_ids"] == []


@pytest.mark.parametrize("field,value", [
    ("available_at_utc", "2020-01-01T00:00:00Z"),
    ("revision", 2), ("origin_capture_id", "missing"), ("status", "CANCELLED"),
])
def test_rehashed_but_inconsistent_revision_lineage_is_refused(field, value):
    import hashlib
    import json
    journal = append_parsed_capture(empty_journal(), capture_id="one", parsed_capture=capture())
    journal["records"][0][field] = value
    payload = {key: journal[key] for key in ("schema_version", "captures", "records")}
    journal["journal_sha256"] = "sha256:" + hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    with pytest.raises(EventRevisionError, match="lineage"):
        qualify_journal(journal, decision_cutoff_utc="2026-01-03T00:00:00Z")


def test_retained_capture_preserves_quarantine_and_has_reconstructable_digest():
    import hashlib
    import json
    parsed = capture()
    parsed["quarantined"] = [{"reason": "UNKNOWN_ROW", "row": ["unparsed"]}]
    journal = append_parsed_capture(empty_journal(), capture_id="one", parsed_capture=parsed)
    retained = journal["captures"][0]
    assert retained["content"]["quarantined"] == parsed["quarantined"]
    assert retained["content_sha256"] == "sha256:" + hashlib.sha256(json.dumps(retained["content"], sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    assert validate_journal(journal) == journal
