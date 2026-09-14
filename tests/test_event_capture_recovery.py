import json

import pytest

from forex import event_capture_store as store
from forex.event_capture_recovery import resume_bls_capture
from forex.event_capture_store import CaptureConflictError, CaptureRecoveryRequired, EventCaptureStoreError, retain_bls_capture


def raw_html():
    return ("<html><body><p>All release times are Eastern Time.</p><table>"
            "<tr><th>Reference Month</th><th>Release Date</th><th>Release Time</th></tr>"
            "<tr><td>November 2025</td><td>Dec. 18, 2025</td><td>08:30 AM</td></tr>"
            "</table></body></html>").encode()


def test_raw_only_capture_is_completed_without_republishing_raw(tmp_path):
    layout = store._layout(tmp_path)
    raw = raw_html()
    store._publish_exclusive(layout["raw"] / "one.html", raw)
    result = resume_bls_capture(tmp_path, capture_id="one", raw=raw, source_family="CPI", capture_completed_at_utc="2026-01-01T00:00:00Z")
    assert result["recovery"] == "EXACT_EXISTING_RAW_ONLY"
    assert (tmp_path / "raw" / "one.html").read_bytes() == raw
    assert (tmp_path / "metadata" / "one.json").is_file()
    assert len(result["journal"]["captures"]) == 1


def test_exact_retry_recovers_missing_generation_and_is_idempotent(tmp_path, monkeypatch):
    raw = raw_html()
    monkeypatch.setattr(store, "_publish_journal", lambda *args: (_ for _ in ()).throw(OSError("generation failure")))
    with pytest.raises(OSError, match="generation failure"):
        retain_bls_capture(tmp_path, capture_id="one", raw=raw, source_family="CPI", capture_completed_at_utc="2026-01-01T00:00:00Z")
    monkeypatch.undo()
    first = resume_bls_capture(tmp_path, capture_id="one", raw=raw, source_family="CPI", capture_completed_at_utc="2026-01-01T00:00:00Z")
    second = resume_bls_capture(tmp_path, capture_id="one", raw=raw, source_family="CPI", capture_completed_at_utc="2026-01-01T00:00:00Z")
    assert first["journal"] == second["journal"]
    assert len(list((tmp_path / "journals").glob("*.json"))) == 1


def test_resume_rejects_missing_raw_and_conflicting_bytes_or_declared_time(tmp_path):
    raw = raw_html()
    with pytest.raises(CaptureRecoveryRequired, match="missing"):
        resume_bls_capture(tmp_path, capture_id="new", raw=raw, source_family="CPI", capture_completed_at_utc="2026-01-01T00:00:00Z")
    assert list(tmp_path.iterdir()) == []
    retain_bls_capture(tmp_path, capture_id="one", raw=raw, source_family="CPI", capture_completed_at_utc="2026-01-01T00:00:00Z")
    with pytest.raises(CaptureConflictError, match="bytes"):
        resume_bls_capture(tmp_path, capture_id="one", raw=raw + b" ", source_family="CPI", capture_completed_at_utc="2026-01-01T00:00:00Z")
    with pytest.raises(CaptureConflictError, match="metadata"):
        resume_bls_capture(tmp_path, capture_id="one", raw=raw, source_family="CPI", capture_completed_at_utc="2026-01-02T00:00:00Z")


def test_resume_refuses_tamper_and_unrelated_orphan_state(tmp_path):
    raw = raw_html()
    retain_bls_capture(tmp_path, capture_id="one", raw=raw, source_family="CPI", capture_completed_at_utc="2026-01-01T00:00:00Z")
    (tmp_path / "raw" / "one.html").write_bytes(b"tampered")
    with pytest.raises(CaptureConflictError):
        resume_bls_capture(tmp_path, capture_id="one", raw=raw, source_family="CPI", capture_completed_at_utc="2026-01-01T00:00:00Z")
    clean = tmp_path / "clean"
    retain_bls_capture(clean, capture_id="one", raw=raw, source_family="CPI", capture_completed_at_utc="2026-01-01T00:00:00Z")
    (clean / "raw" / "other.html").write_bytes(raw)
    with pytest.raises(CaptureRecoveryRequired, match="without metadata"):
        resume_bls_capture(clean, capture_id="one", raw=raw, source_family="CPI", capture_completed_at_utc="2026-01-01T00:00:00Z")
