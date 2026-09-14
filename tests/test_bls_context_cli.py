import hashlib
import json
from pathlib import Path
import subprocess
import sys

from tests.test_bls_events import table


def test_retained_capture_pipeline_binds_original_bytes_and_quarantines_imprecise_time(tmp_path):
    raw = b'\xef\xbb\xbf' + table(("June 2026", "Jul. 02, 2026", "08:30 AM")).encode()
    path = tmp_path / "bls.html"
    path.write_bytes(raw)
    script = Path(__file__).resolve().parents[1] / "scripts/bls_event_context.py"
    result = subprocess.run([sys.executable, str(script), str(path), "--family", "CPI",
        "--capture-completed-at", "2026-07-01T00:00:00Z", "--decision-at", "2026-07-01T01:00:00Z",
        "--window-start", "2026-07-01T00:00:00Z", "--window-end", "2026-07-03T00:00:00Z"],
        capture_output=True, text=True, cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["raw_capture_sha256"] == "sha256:" + hashlib.sha256(raw).hexdigest()
    assert report["raw_capture_sha256"] != report["parser_result"]["payload_sha256"]
    assert report["annotation"]["events"] == []
    assert report["annotation"]["quarantined"][0]["reason"] == "TIME_PRECISION_INSUFFICIENT"
    assert report["execution_authority"] is False
    assert path.read_bytes() == raw
