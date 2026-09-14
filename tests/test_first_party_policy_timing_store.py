import json

import pytest

from forex.first_party_policy_timing_store import PolicyTimingStoreError, retain_policy_timing_bundle


def _retain(root, **changes):
    args = {"family_id": "FOMC_POLICY_DECISION", "target_date": "2026-01-28",
            "calendar_raw": b"#### 2026 FOMC Meetings January 27-28",
            "calendar_capture_completed_at_utc": "2026-01-01T01:00:00Z",
            "timing_raw": b"The Committee releases a policy statement at 2 p.m. Eastern Time.",
            "timing_capture_completed_at_utc": "2026-01-01T02:00:00Z"}
    args.update(changes)
    return retain_policy_timing_bundle(root, **args)


def test_immutable_complete_publication_is_idempotent_and_event_quality_ready(tmp_path):
    first = _retain(tmp_path)
    second = _retain(tmp_path)
    assert first["status"] == "CREATED" and second["status"] == "EXISTING"
    assert first["manifest_sha256"] == second["manifest_sha256"]
    target = tmp_path / "FOMC_POLICY_DECISION" / "2026-01-28"
    assert {item.name for item in target.iterdir()} == {"calendar.html", "timing.html", "calendar.receipt.json", "timing.receipt.json", "timing.bundle.json", "event.record.json", "manifest.json"}
    event = json.loads((target / "event.record.json").read_text())
    assert event["available_at_utc"] == "2026-01-01T02:00:00Z"
    assert first["coverage_status"] == "UNKNOWN" and first["qualification_state"] == "PENDING_RETAINED_CAPTURE"


def test_conflict_partial_and_tamper_all_refuse(tmp_path):
    _retain(tmp_path)
    with pytest.raises(PolicyTimingStoreError, match="conflicts"):
        _retain(tmp_path, timing_raw=b"The Committee releases a policy statement at 2:00 p.m. Eastern Time.")
    target = tmp_path / "FOMC_POLICY_DECISION" / "2026-01-28"
    (target / "timing.html").write_bytes(b"tampered")
    with pytest.raises(PolicyTimingStoreError, match="hash mismatch"):
        _retain(tmp_path)
    partial = tmp_path / "partial" / "FOMC_POLICY_DECISION" / "2026-01-28"
    partial.mkdir(parents=True); (partial / "calendar.html").write_bytes(b"partial")
    with pytest.raises(PolicyTimingStoreError, match="partial"):
        _retain(tmp_path / "partial")


def test_unsafe_root_and_invalid_declared_receipt_time_refuse(tmp_path):
    actual = tmp_path / "actual"; actual.mkdir()
    link = tmp_path / "link"; link.symlink_to(actual, target_is_directory=True)
    with pytest.raises(PolicyTimingStoreError, match="symlink"):
        _retain(link / "nested")
    with pytest.raises(PolicyTimingStoreError, match="input is invalid"):
        _retain(tmp_path / "bad", timing_capture_completed_at_utc="not-a-time")
