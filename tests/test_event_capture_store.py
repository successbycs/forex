import json
import multiprocessing
from pathlib import Path

import pytest

from forex import event_capture_store as store
from forex.event_capture_store import CaptureConflictError, CaptureRecoveryRequired, EventCaptureStoreError, read_capture_journal, retain_bls_capture


def raw_html(reference="November 2025", date="Dec. 18, 2025", time="08:30 AM"):
    return ("<html><body><p>All release times are Eastern Time.</p><table>"
            "<tr><th>Reference Month</th><th>Release Date</th><th>Release Time</th></tr>"
            f"<tr><td>{reference}</td><td>{date}</td><td>{time}</td></tr>"
            "</table></body></html>").encode()


def _worker(root: str, capture_id: str, completed: str, queue):
    try:
        result = retain_bls_capture(Path(root), capture_id=capture_id, raw=raw_html(), source_family="CPI", capture_completed_at_utc=completed)
        queue.put(("ok", len(result["journal"]["captures"])))
    except Exception as exc:  # pragma: no cover - assertion happens in parent
        queue.put(("error", str(exc)))


def test_immutable_raw_metadata_and_journal_are_published_with_integrity(tmp_path):
    result = retain_bls_capture(tmp_path, capture_id="capture-one", raw=raw_html(), source_family="CPI", capture_completed_at_utc="2026-01-01T00:00:00Z")
    assert result["capture_timestamp_provenance"] == "CALLER_DECLARED_NOT_AUTHENTICATED"
    assert result["parser_result"]["payload_sha256"] == result["raw_capture_sha256"]
    assert (tmp_path / "raw" / "capture-one.html").read_bytes() == raw_html()
    metadata = json.loads((tmp_path / "metadata" / "capture-one.json").read_text())
    assert metadata["raw_capture_sha256"] == result["raw_capture_sha256"]
    assert len(list((tmp_path / "journals").glob("*.json"))) == 1
    before = sorted(path.name for path in (tmp_path / "journals").glob("*.json"))
    assert read_capture_journal(tmp_path) == result["journal"]
    assert sorted(path.name for path in (tmp_path / "journals").glob("*.json")) == before
    with pytest.raises(CaptureConflictError):
        retain_bls_capture(tmp_path, capture_id="capture-one", raw=raw_html(), source_family="CPI", capture_completed_at_utc="2026-01-02T00:00:00Z")


def test_tamper_symlink_and_orphan_raw_fail_closed(tmp_path):
    retain_bls_capture(tmp_path, capture_id="one", raw=raw_html(), source_family="CPI", capture_completed_at_utc="2026-01-01T00:00:00Z")
    raw = tmp_path / "raw" / "one.html"
    raw.write_bytes(b"tampered")
    with pytest.raises(EventCaptureStoreError, match="hash mismatch"):
        retain_bls_capture(tmp_path, capture_id="two", raw=raw_html(), source_family="CPI", capture_completed_at_utc="2026-01-02T00:00:00Z")
    unsafe = tmp_path / "unsafe"
    unsafe.mkdir(); (unsafe / "raw").symlink_to(tmp_path / "raw", target_is_directory=True)
    with pytest.raises(EventCaptureStoreError, match="symlink"):
        retain_bls_capture(unsafe, capture_id="two", raw=raw_html(), source_family="CPI", capture_completed_at_utc="2026-01-02T00:00:00Z")
    orphan = tmp_path / "orphan"; (orphan / "raw").mkdir(parents=True); (orphan / "raw" / "stuck.html").write_bytes(raw_html())
    with pytest.raises(CaptureRecoveryRequired, match="without metadata"):
        retain_bls_capture(orphan, capture_id="two", raw=raw_html(), source_family="CPI", capture_completed_at_utc="2026-01-02T00:00:00Z")
    readonly = tmp_path / "readonly"; (readonly / "raw").mkdir(parents=True); (readonly / "metadata").mkdir(); (readonly / "journals").mkdir()
    (readonly / "raw" / "stuck.html").write_bytes(raw_html())
    assert not (readonly / ".event-capture-store.lock").exists()
    with pytest.raises(CaptureRecoveryRequired, match="without metadata"):
        read_capture_journal(readonly)
    assert not (readonly / ".event-capture-store.lock").exists()


def test_concurrent_different_captures_rebuild_one_lossless_journal(tmp_path):
    context = multiprocessing.get_context("fork")
    queue = context.Queue()
    one = context.Process(target=_worker, args=(str(tmp_path), "one", "2026-01-01T00:00:00Z", queue))
    two = context.Process(target=_worker, args=(str(tmp_path), "two", "2026-01-02T00:00:00Z", queue))
    one.start(); two.start(); one.join(); two.join()
    results = [queue.get(timeout=3), queue.get(timeout=3)]
    # Completion timestamps need not arrive in order. Every byte must survive;
    # a late writer is explicitly refused rather than rewriting a published prefix.
    assert all(result[0] == "ok" or "late capture" in result[1] for result in results), results
    assert (tmp_path / "raw" / "one.html").read_bytes() == raw_html()
    assert (tmp_path / "raw" / "two.html").read_bytes() == raw_html()
    generations = list((tmp_path / "journals").glob("*.json"))
    latest = max((json.loads(path.read_text()) for path in generations), key=lambda item: len(item["captures"]))
    if all(result[0] == "ok" for result in results):
        assert [item["capture_id"] for item in latest["captures"]] == ["one", "two"]
    else:
        with pytest.raises(CaptureRecoveryRequired, match="late capture"):
            read_capture_journal(tmp_path)
    assert len(latest["records"]) == 1


def test_failure_after_immutable_metadata_is_recoverable_without_skipping_capture(tmp_path, monkeypatch):
    def fail_generation(*args, **kwargs):
        raise OSError("simulated journal media failure")

    monkeypatch.setattr(store, "_publish_journal", fail_generation)
    with pytest.raises(OSError, match="media failure"):
        retain_bls_capture(tmp_path, capture_id="one", raw=raw_html(), source_family="CPI", capture_completed_at_utc="2026-01-01T00:00:00Z")
    assert (tmp_path / "raw" / "one.html").is_file()
    assert (tmp_path / "metadata" / "one.json").is_file()
    assert list((tmp_path / "journals").glob("*.json")) == []
    recovered = read_capture_journal(tmp_path)
    assert [capture["capture_id"] for capture in recovered["captures"]] == ["one"]
    monkeypatch.undo()
    result = retain_bls_capture(tmp_path, capture_id="two", raw=raw_html(), source_family="CPI", capture_completed_at_utc="2026-01-02T00:00:00Z")
    assert [capture["capture_id"] for capture in result["journal"]["captures"]] == ["one", "two"]


def test_late_arriving_capture_is_retained_but_cannot_rewrite_published_prefix(tmp_path):
    retain_bls_capture(tmp_path, capture_id="one", raw=raw_html(), source_family="CPI", capture_completed_at_utc="2026-01-02T00:00:00Z")
    before = max((json.loads(path.read_text()) for path in (tmp_path / "journals").glob("*.json")), key=lambda item: len(item["captures"]))
    with pytest.raises(CaptureRecoveryRequired, match="late capture"):
        retain_bls_capture(tmp_path, capture_id="late", raw=raw_html(), source_family="CPI", capture_completed_at_utc="2026-01-01T00:00:00Z")
    assert (tmp_path / "raw" / "late.html").is_file()
    assert (tmp_path / "metadata" / "late.json").is_file()
    after = max((json.loads(path.read_text()) for path in (tmp_path / "journals").glob("*.json")), key=lambda item: len(item["captures"]))
    assert after == before
    with pytest.raises(CaptureRecoveryRequired, match="late capture"):
        read_capture_journal(tmp_path)


def test_unsafe_identifier_and_malformed_raw_are_rejected_before_publication(tmp_path):
    with pytest.raises(EventCaptureStoreError, match="capture_id"):
        retain_bls_capture(tmp_path, capture_id="../escape", raw=raw_html(), source_family="CPI", capture_completed_at_utc="2026-01-01T00:00:00Z")
    with pytest.raises(EventCaptureStoreError, match="UTF-8"):
        retain_bls_capture(tmp_path, capture_id="bad", raw=b"\xff", source_family="CPI", capture_completed_at_utc="2026-01-01T00:00:00Z")


def test_rehashed_parser_tampering_cannot_disagree_with_raw_bytes(tmp_path):
    retain_bls_capture(tmp_path, capture_id="one", raw=raw_html(), source_family="CPI", capture_completed_at_utc="2026-01-01T00:00:00Z")
    path = tmp_path / "metadata/one.json"
    metadata = json.loads(path.read_bytes())
    metadata["parser_result"]["records"][0]["scheduled_at_local"] = "2020-01-01T08:30:00"
    metadata["metadata_sha256"] = store._sha(store._canonical(store._metadata_payload(metadata)))
    path.write_bytes(store._canonical(metadata))
    with pytest.raises(EventCaptureStoreError, match="parser result"):
        read_capture_journal(tmp_path)


def test_missing_published_capture_cannot_be_hidden_by_journal(tmp_path):
    retain_bls_capture(tmp_path, capture_id="one", raw=raw_html(), source_family="CPI", capture_completed_at_utc="2026-01-01T00:00:00Z")
    (tmp_path / "metadata/one.json").unlink()
    (tmp_path / "raw/one.html").unlink()
    with pytest.raises(CaptureRecoveryRequired, match="metadata is missing"):
        read_capture_journal(tmp_path)


def test_ancestor_symlink_refused_before_creating_nested_store(tmp_path):
    actual = tmp_path / "actual"
    actual.mkdir()
    link = tmp_path / "link"
    link.symlink_to(actual, target_is_directory=True)
    with pytest.raises(EventCaptureStoreError, match="symlink"):
        retain_bls_capture(link / "nested", capture_id="one", raw=raw_html(), source_family="CPI", capture_completed_at_utc="2026-01-01T00:00:00Z")
    assert not (actual / "nested").exists()


def test_duplicate_metadata_json_keys_are_refused(tmp_path):
    retain_bls_capture(tmp_path, capture_id="one", raw=raw_html(), source_family="CPI", capture_completed_at_utc="2026-01-01T00:00:00Z")
    path = tmp_path / "metadata/one.json"
    path.write_text('{"capture_id":"bad",' + path.read_text()[1:])
    with pytest.raises(EventCaptureStoreError, match="duplicate"):
        read_capture_journal(tmp_path)


def test_fractional_second_after_whole_second_is_not_treated_as_late(tmp_path):
    retain_bls_capture(tmp_path, capture_id="one", raw=raw_html(), source_family="CPI", capture_completed_at_utc="2026-01-01T00:00:00Z")
    result = retain_bls_capture(tmp_path, capture_id="two", raw=raw_html(), source_family="CPI", capture_completed_at_utc="2026-01-01T00:00:00.100000Z")
    assert [item["capture_id"] for item in result["journal"]["captures"]] == ["one", "two"]
