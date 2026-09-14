from __future__ import annotations

from copy import deepcopy

import pytest

from forex.bls_journal_calendar_projection import BLSJournalProjectionError, project_bls_journal
from forex.calendar_fact_persistence import canonical_fact
from forex.event_revisions import append_parsed_capture, empty_journal


def capture(*, completed="2026-01-01T00:00:00Z"):
    payload = "sha256:" + "a" * 64
    base = {"source_id": "bls-cpi-release-schedule", "source_url": "https://www.bls.gov/schedule/news_release/cpi.htm", "license": "BLS terms", "status": "SCHEDULED", "payload_sha256": payload, "available_at_utc": completed}
    return {"capture_completed_at_utc": completed, "payload_sha256": payload, "source_family": "CPI", "source_url": base["source_url"], "parser_version": "test.v1", "quarantined": [], "records": [
        {**base, "event_id": "cpi-exact", "event_name": "CPI exact", "time_precision": "EXACT_LOCAL_TIME", "timezone": "America/New_York", "scheduled_at_local": "2026-02-01T08:30:00"},
        {**base, "event_id": "cpi-date-only", "event_name": "CPI date only", "time_precision": "DATE_ONLY"},
    ]}


def journal():
    return append_parsed_capture(empty_journal(), capture_id="capture-1", parsed_capture=capture())


def receipts(value=None):
    return {"capture-1": value or "sha256:" + "b" * 64}


def test_projects_every_retained_revision_with_capture_bound_provenance():
    result = project_bls_journal(journal(), capture_receipt_sha256_by_id=receipts())
    assert result["execution_authority"] is False
    assert result["projection_sha256"].startswith("sha256:")
    assert [fact["event_identifier"] for fact in result["facts"]] == ["cpi-date-only", "cpi-exact"]
    exact, date_only = result["facts"][1], result["facts"][0]
    assert exact["scheduled_at_utc"] == "2026-02-01T13:30:00Z"
    assert exact["qualification_state"] == "QUALIFIED"
    assert date_only["qualification_state"] == "QUARANTINED"
    assert date_only["qualification_reason"] == "TIME_PRECISION_INSUFFICIENT"
    assert date_only["scheduled_at_utc"] is None
    for fact in result["facts"]:
        assert fact["raw_sha256"] == "sha256:" + "a" * 64
        assert fact["receipt_sha256"] == receipts()["capture-1"]
        assert canonical_fact(fact)["execution_authority"] is False
    assert result["facts"][0]["event_payload"]["event_revision"]["origin_capture_id"] == "capture-1"


def test_tampered_journal_or_capture_lineage_is_refused_before_projection():
    bad = deepcopy(journal())
    bad["records"][0]["event_name"] = "tampered"
    with pytest.raises(BLSJournalProjectionError, match="journal validation"):
        project_bls_journal(bad, capture_receipt_sha256_by_id=receipts())
    bad = deepcopy(journal())
    bad["records"][0]["origin_capture_id"] = "missing"
    # Rehashing does not repair the journal's rebuilt lineage.
    import hashlib, json
    payload = {key: bad[key] for key in ("schema_version", "captures", "records")}
    bad["journal_sha256"] = "sha256:" + hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    with pytest.raises(BLSJournalProjectionError, match="journal validation"):
        project_bls_journal(bad, capture_receipt_sha256_by_id=receipts())


def test_projection_is_pure_and_does_not_alias_caller_journal():
    source = journal()
    projected = project_bls_journal(source, capture_receipt_sha256_by_id=receipts())
    projected["facts"][0]["event_payload"]["event_revision"]["event_name"] = "mutated"
    assert source["records"][0]["event_name"] != "mutated"


def test_prefix_only_raw_digest_in_an_otherwise_valid_journal_is_refused():
    parsed = capture()
    parsed["payload_sha256"] = "sha256:bad"
    for record in parsed["records"]:
        record["payload_sha256"] = "sha256:bad"
    weak_journal = append_parsed_capture(empty_journal(), capture_id="capture-1", parsed_capture=parsed)
    with pytest.raises(BLSJournalProjectionError, match="canonical persistence"):
        project_bls_journal(weak_journal, capture_receipt_sha256_by_id=receipts())


@pytest.mark.parametrize("bindings", [{}, {"capture-1": "sha256:" + "b" * 64, "extra": "sha256:" + "c" * 64}, {"capture-1": "bad"}])
def test_receipt_bindings_are_closed_and_digest_valid(bindings):
    with pytest.raises(BLSJournalProjectionError, match="receipt binding"):
        project_bls_journal(journal(), capture_receipt_sha256_by_id=bindings)
