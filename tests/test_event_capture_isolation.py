from __future__ import annotations

import json

import pytest

from forex import event_capture_store as store
from forex.event_capture_store import CaptureRecoveryRequired, EventCaptureStoreError, isolate_late_capture, read_capture_journal, read_capture_store, retain_bls_capture


def raw_html() -> bytes:
    return ("<html><body><p>All release times are Eastern Time.</p><table>"
            "<tr><th>Reference Month</th><th>Release Date</th><th>Release Time</th></tr>"
            "<tr><td>November 2025</td><td>Dec. 18, 2025</td><td>08:30 AM</td></tr>"
            "</table></body></html>").encode()


def retain_late(root):
    retain_bls_capture(root, capture_id="published", raw=raw_html(), source_family="CPI",
                       capture_completed_at_utc="2026-01-02T00:00:00Z")
    with pytest.raises(CaptureRecoveryRequired, match="late capture"):
        retain_bls_capture(root, capture_id="late", raw=raw_html(), source_family="CPI",
                           capture_completed_at_utc="2026-01-01T00:00:00Z")


def test_isolation_is_append_only_idempotent_and_allows_future_capture(tmp_path):
    retain_late(tmp_path)
    before = {path.name: path.read_bytes() for path in (tmp_path / "journals").glob("*.json")}
    marker = isolate_late_capture(tmp_path, capture_id="late")
    assert marker["reason"] == "LATE_CAPTURE_NOT_APPLIED"
    assert marker == isolate_late_capture(tmp_path, capture_id="late")
    assert {path.name: path.read_bytes() for path in (tmp_path / "journals").glob("*.json")} == before
    state = read_capture_store(tmp_path)
    assert [item["capture_id"] for item in state["journal"]["captures"]] == ["published"]
    assert state["isolated_captures"] == [marker]
    later = retain_bls_capture(tmp_path, capture_id="future", raw=raw_html(), source_family="CPI",
                               capture_completed_at_utc="2026-01-03T00:00:00Z")
    assert [item["capture_id"] for item in later["journal"]["captures"]] == ["published", "future"]
    assert (tmp_path / "raw" / "late.html").is_file()
    assert (tmp_path / "metadata" / "late.json").is_file()


def test_unmarked_late_still_fails_and_legacy_store_has_no_isolations_directory(tmp_path):
    retain_late(tmp_path)
    with pytest.raises(CaptureRecoveryRequired, match="late capture"):
        read_capture_journal(tmp_path)
    legacy = tmp_path / "legacy"
    retain_bls_capture(legacy, capture_id="one", raw=raw_html(), source_family="CPI",
                       capture_completed_at_utc="2026-01-01T00:00:00Z")
    assert not (legacy / "isolations").exists()
    assert read_capture_store(legacy)["isolated_captures"] == []


def test_tampered_orphan_early_or_ineligible_marker_fails_closed(tmp_path):
    retain_late(tmp_path)
    marker = isolate_late_capture(tmp_path, capture_id="late")
    marker_path = tmp_path / "isolations" / "late.json"
    damaged = dict(marker); damaged["reason"] = "OTHER"
    marker_path.write_bytes(store._canonical(damaged))
    with pytest.raises(EventCaptureStoreError, match="reason"):
        read_capture_store(tmp_path)

    marker_path.write_bytes(store._canonical(marker))
    orphan = dict(marker); orphan["capture_id"] = "missing"; orphan["marker_sha256"] = store._sha(store._canonical(store._isolation_payload(orphan)))
    (tmp_path / "isolations" / "missing.json").write_bytes(store._canonical(orphan))
    with pytest.raises(EventCaptureStoreError, match="retained metadata"):
        read_capture_store(tmp_path)
    (tmp_path / "isolations" / "missing.json").unlink()

    with pytest.raises(EventCaptureStoreError, match="published capture"):
        isolate_late_capture(tmp_path, capture_id="published")
    (tmp_path / "isolations" / "late.json").unlink()
    with pytest.raises(CaptureRecoveryRequired, match="late capture"):
        read_capture_journal(tmp_path)


def test_marker_requires_intact_historical_generation_and_original_lateness(tmp_path):
    retain_late(tmp_path)
    isolate_late_capture(tmp_path, capture_id="late")
    marker_path = tmp_path / "isolations" / "late.json"
    marker = json.loads(marker_path.read_bytes())
    marker["published_journal_sha256"] = "sha256:" + "0" * 64
    marker["marker_sha256"] = store._sha(store._canonical(store._isolation_payload(marker)))
    marker_path.write_bytes(store._canonical(marker))
    with pytest.raises(EventCaptureStoreError, match="missing or invalid"):
        read_capture_store(tmp_path)


def test_layout_taken_before_first_isolation_cannot_hide_marker(tmp_path, monkeypatch):
    retain_late(tmp_path)
    before_lock = store._existing_layout(tmp_path)
    assert "isolations" not in before_lock
    marker = isolate_late_capture(tmp_path, capture_id="late")
    monkeypatch.setattr(store, "_existing_layout", lambda root: before_lock)
    state = read_capture_store(tmp_path)
    assert state["isolated_captures"] == [marker]
    assert [row["capture_id"] for row in state["journal"]["captures"]] == ["published"]


def test_parent_directory_sync_failure_refuses_before_marker_publication(tmp_path, monkeypatch):
    import os
    retain_late(tmp_path)
    original = os.fsync
    root_stat = tmp_path.stat()
    def fail_parent(fd):
        observed = os.fstat(fd)
        if (observed.st_dev, observed.st_ino) == (root_stat.st_dev, root_stat.st_ino):
            raise OSError("injected isolation parent sync failure")
        return original(fd)
    monkeypatch.setattr(store.os, "fsync", fail_parent)
    with pytest.raises(OSError, match="parent sync"):
        isolate_late_capture(tmp_path, capture_id="late")
    assert not (tmp_path / "isolations/late.json").exists()
    monkeypatch.setattr(store.os, "fsync", original)
    assert isolate_late_capture(tmp_path, capture_id="late")["capture_id"] == "late"
