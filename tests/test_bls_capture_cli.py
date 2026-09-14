import hashlib
import json
from pathlib import Path
import subprocess
import sys

from tests.test_bls_events import table


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/bls_capture.py"


def invoke(tmp_path, capture_id="capture-1", completed="2026-07-01T00:00:00Z", *, resume=False):
    return subprocess.run([sys.executable, str(SCRIPT), str(tmp_path / "input.html"),
        "--store", str(tmp_path / "store"), "--capture-id", capture_id,
        "--family", "CPI", "--capture-completed-at", completed, *(["--resume"] if resume else [])],
        cwd=tmp_path, capture_output=True, text=True)


def test_cli_retains_original_bytes_and_preserves_first_revision(tmp_path):
    raw = b'\xef\xbb\xbf' + table(("June 2026", "Jul. 02, 2026", "08:30 AM")).encode()
    source = tmp_path / "input.html"
    source.write_bytes(raw)
    result = invoke(tmp_path)
    assert result.returncode == 0, result.stderr
    first = json.loads(result.stdout)
    assert first["raw_capture_sha256"] == "sha256:" + hashlib.sha256(raw).hexdigest()
    assert first["capture_provenance"] == "CALLER_SUPPLIED_NOT_AUTHENTICATED"
    assert first["capture_count"] == first["revision_count"] == 1
    assert first["parser_quarantined"]
    assert first["execution_authority"] is False
    later = invoke(tmp_path, "capture-2", "2026-07-01T01:00:00Z")
    assert later.returncode == 0, later.stderr
    second = json.loads(later.stdout)
    assert second["capture_count"] == 2
    assert second["revision_count"] == 1
    assert second["journal_sha256"] != first["journal_sha256"]
    assert source.read_bytes() == raw


def test_cli_conflict_refuses_without_replacing_capture(tmp_path):
    source = tmp_path / "input.html"
    source.write_text(table(("June 2026", "Jul. 02, 2026", "08:30 AM")))
    assert invoke(tmp_path).returncode == 0
    before = {str(path.relative_to(tmp_path / "store")): path.read_bytes()
              for path in (tmp_path / "store").rglob("*") if path.is_file()}
    source.write_text("<html>changed response</html>")
    conflict = invoke(tmp_path)
    assert conflict.returncode == 2
    assert conflict.stdout == ""
    assert "refused" in conflict.stderr
    for path, raw in before.items():
        assert (tmp_path / "store" / path).read_bytes() == raw


def test_cli_bad_capture_identifier_cannot_escape_store(tmp_path):
    (tmp_path / "input.html").write_text("<html>test</html>")
    result = invoke(tmp_path, "../escaped")
    assert result.returncode == 2
    assert result.stdout == ""
    assert not (tmp_path / "escaped").exists()


def test_cli_timestamp_overflow_is_a_clean_refusal(tmp_path):
    (tmp_path / "input.html").write_text("<html>test</html>")
    result = invoke(tmp_path, completed="0001-01-01T00:00:00+01:00")
    assert result.returncode == 2
    assert result.stdout == ""
    assert "Traceback" not in result.stderr
    assert not (tmp_path / "store").exists()


def test_resume_cli_is_idempotent_and_cannot_replace_original_bytes(tmp_path):
    source = tmp_path / "input.html"
    source.write_text(table(("June 2026", "Jul. 02, 2026", "08:30 AM")))
    first = invoke(tmp_path)
    assert first.returncode == 0, first.stderr
    resumed = invoke(tmp_path, resume=True)
    assert resumed.returncode == 0, resumed.stderr
    assert json.loads(resumed.stdout) == json.loads(first.stdout)
    original = (tmp_path / "store/raw/capture-1.html").read_bytes()
    source.write_text("<html>different bytes</html>")
    conflict = invoke(tmp_path, resume=True)
    assert conflict.returncode == 2
    assert not conflict.stdout
    assert (tmp_path / "store/raw/capture-1.html").read_bytes() == original


def test_resume_cli_finishes_raw_only_request(tmp_path):
    from forex import event_capture_store as store
    root = tmp_path / "store"
    layout = store._layout(root)
    raw = table(("June 2026", "Jul. 02, 2026", "08:30 AM")).encode()
    (tmp_path / "input.html").write_bytes(raw)
    # Simulate a completed raw publication followed by process loss before
    # metadata publication. The same retained request supplies its provenance.
    store._publish_exclusive(layout["raw"] / "capture-1.html", raw)
    resumed = invoke(tmp_path, resume=True)
    assert resumed.returncode == 0, resumed.stderr
    assert json.loads(resumed.stdout)["capture_count"] == 1
    assert (layout["raw"] / "capture-1.html").read_bytes() == raw


def test_store_to_context_respects_capture_availability_and_is_read_only(tmp_path):
    raw = ("<p>All times are Eastern Time.</p>" + table(
        ("June 2026", "Jul. 02, 2026", "08:30 AM"))).encode()
    (tmp_path / "input.html").write_bytes(raw)
    assert invoke(tmp_path).returncode == 0
    before = {str(path): path.read_bytes() for path in (tmp_path / "store").rglob("*") if path.is_file()}
    script = SCRIPT.with_name("event_context.py")
    for cutoff, count in [("2026-06-30T23:59:59Z", 0), ("2026-07-01T00:00:00Z", 1)]:
        result = subprocess.run([sys.executable, str(script), "--store", str(tmp_path / "store"),
            "--decision-at", cutoff, "--window-start", "2026-07-02T00:00:00Z",
            "--window-end", "2026-07-03T00:00:00Z"], capture_output=True, text=True, cwd=tmp_path)
        assert result.returncode == 0, result.stderr
        report = json.loads(result.stdout)
        assert len(report["qualification"]["accepted"]) == count
        assert report["annotation"]["coverage"]["status"] == "UNKNOWN"
        assert report["execution_authority"] is False
    for path, content in before.items():
        assert Path(path).read_bytes() == content


def test_later_parser_failure_is_not_reported_as_earlier_context(tmp_path):
    (tmp_path / "input.html").write_text("<p>All times are Eastern Time.</p>" + table(
        ("June 2026", "Jul. 02, 2026", "08:30 AM")))
    assert invoke(tmp_path).returncode == 0
    (tmp_path / "input.html").write_text("<html>unrecognized publisher response</html>")
    assert invoke(tmp_path, "capture-2", "2026-07-01T02:00:00Z").returncode == 0
    script = SCRIPT.with_name("event_context.py")
    for cutoff, count in [("2026-07-01T01:00:00Z", 0), ("2026-07-01T02:00:00Z", 1)]:
        result = subprocess.run([sys.executable, str(script), "--store", str(tmp_path / "store"),
            "--decision-at", cutoff, "--window-start", "2026-07-02T00:00:00Z",
            "--window-end", "2026-07-03T00:00:00Z"], capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
        report = json.loads(result.stdout)
        assert len(report["capture_quarantine"]) == count
        assert report["annotation"]["coverage"]["status"] == "UNKNOWN"
