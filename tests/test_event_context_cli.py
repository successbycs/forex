import hashlib
import json
from pathlib import Path
import subprocess
import sys
import pytest

from forex.event_quality import fixture_records

ROOT = Path(__file__).resolve().parents[1]


def run_context(path):
    return subprocess.run([
        sys.executable, str(ROOT / "scripts/event_context.py"), "--input", str(path),
        "--decision-at", "2026-10-15T00:00:00Z",
        "--window-start", "2026-10-24T00:00:00Z",
        "--window-end", "2026-10-26T00:00:00Z",
    ], capture_output=True, text=True, cwd=path.parent)


def test_retained_metadata_through_cli_preserves_input_and_quarantine(tmp_path):
    path = tmp_path / "events.json"
    raw = json.dumps(fixture_records()).encode()
    path.write_bytes(raw)
    result = run_context(path)
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["input_sha256"] == "sha256:" + hashlib.sha256(raw).hexdigest()
    assert report["annotation"]["events"][0]["event"]["revision"] == 2
    assert report["annotation"]["coverage"]["status"] == "UNKNOWN"
    assert report["qualification"]["quarantined"]
    assert report["execution_authority"] is False
    assert path.read_bytes() == raw


def test_malformed_input_produces_no_report(tmp_path):
    path = tmp_path / "events.json"
    path.write_text('[null]')
    result = run_context(path)
    assert result.returncode == 2
    assert not result.stdout
    assert "JSON array" in result.stderr


@pytest.mark.parametrize("raw", ['[{"revision":1,"revision":2}]', '[{"revision":NaN}]'])
def test_ambiguous_json_is_refused(tmp_path, raw):
    path = tmp_path / "events.json"
    path.write_text(raw)
    result = run_context(path)
    assert result.returncode == 2
    assert result.stdout == ""
