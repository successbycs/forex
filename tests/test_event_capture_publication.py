from pathlib import Path

import pytest

from forex import event_capture_store as store


def test_fsync_failure_never_exposes_partial_final_artifact(tmp_path, monkeypatch):
    final = tmp_path / "capture.html"
    def fail_fsync(fd):
        raise OSError("simulated storage failure")
    monkeypatch.setattr(store.os, "fsync", fail_fsync)
    with pytest.raises(OSError, match="storage failure"):
        store._publish_exclusive(final, b"original bytes")
    assert not final.exists()
    staged = list(tmp_path.glob(".pending-*"))
    assert len(staged) == 1
    assert staged[0].read_bytes() == b"original bytes"
    monkeypatch.undo()
    store._publish_exclusive(final, b"original bytes")
    assert final.read_bytes() == b"original bytes"
    assert staged[0].read_bytes() == b"original bytes"


def test_exclusive_publication_does_not_replace_racing_file(tmp_path, monkeypatch):
    final = tmp_path / "capture.html"
    real_link = store.os.link
    def racing_link(source, destination, **kwargs):
        Path(destination).write_bytes(b"prior writer")
        return real_link(source, destination, **kwargs)
    monkeypatch.setattr(store.os, "link", racing_link)
    with pytest.raises(store.CaptureConflictError):
        store._publish_exclusive(final, b"new bytes")
    assert final.read_bytes() == b"prior writer"


def test_directory_sync_failure_is_reported_with_complete_final_retained(tmp_path, monkeypatch):
    final = tmp_path / "capture.html"
    real_sync = store.os.fsync
    calls = 0
    def fail_directory_sync(fd):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("directory sync failure")
        return real_sync(fd)
    monkeypatch.setattr(store.os, "fsync", fail_directory_sync)
    with pytest.raises(OSError, match="directory sync"):
        store._publish_exclusive(final, b"complete bytes")
    assert final.read_bytes() == b"complete bytes"
