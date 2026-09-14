from __future__ import annotations

import json
from pathlib import Path

import pytest

from forex.bls_retained_calendar_facts import project_retained_bls_store
from forex.event_capture_store import CaptureRecoveryRequired, EventCaptureStoreError, isolate_late_capture, retain_bls_capture


def raw_html() -> bytes:
    return ("<html><p>All release times are Eastern Time.</p><table>"
            "<tr><th>Reference Month</th><th>Release Date</th><th>Release Time</th></tr>"
            "<tr><td>November 2025</td><td>Dec. 18, 2025</td><td>08:30 AM</td></tr>"
            "</table></html>").encode()


def retain(root: Path, capture_id="one", completed="2026-01-01T00:00:00Z"):
    return retain_bls_capture(root, capture_id=capture_id, raw=raw_html(), source_family="CPI",
                              capture_completed_at_utc=completed)


def test_reads_verified_metadata_receipt_hash_for_every_projected_fact(tmp_path):
    retain(tmp_path)
    metadata = json.loads((tmp_path / "metadata/one.json").read_text())
    result = project_retained_bls_store(tmp_path)
    assert result["facts"]
    assert {fact["receipt_sha256"] for fact in result["facts"]} == {metadata["metadata_sha256"]}
    assert result["execution_authority"] is False


def test_tampered_or_missing_metadata_refuses_before_projection(tmp_path):
    retain(tmp_path)
    metadata = tmp_path / "metadata/one.json"
    value = json.loads(metadata.read_text()); value["source_url"] = "https://example.invalid/"
    metadata.write_text(json.dumps(value))
    with pytest.raises(EventCaptureStoreError, match="hash mismatch"):
        project_retained_bls_store(tmp_path)
    metadata.unlink()
    with pytest.raises(CaptureRecoveryRequired, match="without metadata"):
        project_retained_bls_store(tmp_path)


def test_extra_isolated_capture_refuses_full_store_projection(tmp_path):
    retain(tmp_path, "published", "2026-01-02T00:00:00Z")
    with pytest.raises(CaptureRecoveryRequired, match="late capture"):
        retain(tmp_path, "late", "2026-01-01T00:00:00Z")
    isolate_late_capture(tmp_path, capture_id="late")
    with pytest.raises(CaptureRecoveryRequired, match="does not match"):
        project_retained_bls_store(tmp_path)
