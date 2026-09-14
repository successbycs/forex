import json

import pytest

from forex.first_party_policy_source_verifier import PolicySourceVerificationError, verify_policy_timing_store
from forex.first_party_policy_timing_store import retain_policy_timing_bundle


def _retain(root, **changes):
    values = {"family_id": "FOMC_POLICY_DECISION", "target_date": "2026-01-28",
              "calendar_raw": b"#### 2026 FOMC Meetings January 27-28",
              "calendar_capture_completed_at_utc": "2026-01-01T01:00:00Z",
              "timing_raw": b"The Committee releases a policy statement at 2 p.m. Eastern Time.",
              "timing_capture_completed_at_utc": "2026-01-01T02:00:00Z"}
    values.update(changes)
    return retain_policy_timing_bundle(root, **values)


def test_verifies_complete_bundle_and_emits_primary_context_shape(tmp_path):
    retained = _retain(tmp_path)
    report = verify_policy_timing_store(tmp_path)
    assert report["coverage_status"] == "UNKNOWN"
    assert report["qualification_state"] == "PENDING_RETAINED_CAPTURE"
    assert report["execution_authority"] is False
    assert report["bundles"][0]["manifest_sha256"] == retained["manifest_sha256"]
    observation = report["context_observations"][0]
    assert set(observation) == {"source_id", "source_url", "capture_state", "coverage_status", "captured_at_utc", "source_sha256"}
    assert observation["coverage_status"] == "UNKNOWN"
    target = tmp_path / "FOMC_POLICY_DECISION" / "2026-01-28"
    calendar_receipt = json.loads((target / "calendar.receipt.json").read_text())
    assert observation["source_url"] == calendar_receipt["source_url"]
    assert observation["source_sha256"] == calendar_receipt["source_sha256"]
    assert observation["captured_at_utc"] == calendar_receipt["capture_completed_at_utc"]


def test_ecb_projection_uses_the_canonical_primary_event_source_identifier(tmp_path):
    _retain(
        tmp_path,
        family_id="ECB_POLICY_DECISION",
        target_date="2026-10-29",
        calendar_raw=b"29/10/2026 Governing Council monetary policy meeting (Day 2)",
        timing_raw=b"The ECB monetary policy decisions are published in a press release at 14:15 CET.",
    )
    report = verify_policy_timing_store(tmp_path)
    event = report["bundles"][0]["event_record"]
    observation = report["context_observations"][0]
    # This identifier is the one declared in primary_event_context and used
    # by the M1/H_SLOW policy consumers.  A local alias would cause retained
    # event records to fail semantic reconstruction despite valid hashes.
    assert event["source_id"] == "ecb-monetary-policy-calendar"
    assert observation["source_id"] == "ecb-monetary-policy-calendar"


def test_tamper_or_partial_or_unsafe_date_path_refuses(tmp_path):
    _retain(tmp_path)
    target = tmp_path / "FOMC_POLICY_DECISION" / "2026-01-28"
    (target / "event.record.json").write_text("{}")
    with pytest.raises(PolicySourceVerificationError, match="hash mismatch"):
        verify_policy_timing_store(tmp_path)
    clean = tmp_path / "clean"; _retain(clean)
    (clean / "FOMC_POLICY_DECISION" / "duplicate").mkdir()
    with pytest.raises(PolicySourceVerificationError, match="target-date"):
        verify_policy_timing_store(clean)
    actual = tmp_path / "actual"; actual.mkdir()
    link = tmp_path / "link"; link.symlink_to(actual, target_is_directory=True)
    with pytest.raises(PolicySourceVerificationError, match="symlink"):
        verify_policy_timing_store(link)
    locked = tmp_path / "locked"; _retain(locked)
    (locked / ".policy-timing-store.lock").unlink()
    (locked / ".policy-timing-store.lock").symlink_to(target / "calendar.html")
    with pytest.raises(PolicySourceVerificationError, match="lock is unsafe"):
        verify_policy_timing_store(locked)


def test_multiple_captures_stay_separate_and_never_claim_complete(tmp_path):
    _retain(tmp_path)
    _retain(tmp_path, target_date="2026-03-18",
            calendar_raw=b"#### 2026 FOMC Meetings January 27-28 March 17-18")
    report = verify_policy_timing_store(tmp_path)
    assert [row["target_date"] for row in report["bundles"]] == ["2026-01-28", "2026-03-18"]
    assert len(report["context_observations"]) == 2
    assert report["coverage_status"] != "COMPLETE"
