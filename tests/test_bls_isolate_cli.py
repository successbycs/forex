import json
from pathlib import Path
import subprocess
import sys

import pytest

from forex.event_capture_store import CaptureRecoveryRequired, retain_bls_capture
from tests.test_bls_events import table

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def capture(root, identity, timestamp):
    return retain_bls_capture(root, capture_id=identity, raw=(
        "<p>All times are Eastern Time.</p>" + table(("June 2026", "Jul. 02, 2026", "08:30 AM"))
    ).encode(), source_family="CPI", capture_completed_at_utc=timestamp)


def isolate(root, identity):
    return subprocess.run([sys.executable, str(SCRIPTS / "bls_isolate_capture.py"),
        "--store", str(root), "--capture-id", identity], capture_output=True, text=True)


def test_explicit_isolation_unblocks_capture_and_reports_current_health(tmp_path):
    root = tmp_path / "store"
    capture(root, "published", "2026-07-01T02:00:00Z")
    with pytest.raises(CaptureRecoveryRequired):
        capture(root, "late", "2026-07-01T01:00:00Z")
    before = {path: path.read_bytes() for path in root.rglob("*") if path.is_file()}
    result = isolate(root, "late")
    assert result.returncode == 0, result.stderr
    output = json.loads(result.stdout)
    assert output["isolation"]["capture_id"] == "late"
    assert output["execution_authority"] is False
    assert isolate(root, "late").stdout == result.stdout
    later = capture(root, "later", "2026-07-01T03:00:00Z")
    assert [row["capture_id"] for row in later["journal"]["captures"]] == ["published", "later"]
    for path, raw in before.items():
        assert path.read_bytes() == raw
    result = subprocess.run([sys.executable, str(SCRIPTS / "event_context.py"),
        "--store", str(root), "--decision-at", "2026-07-01T02:30:00Z",
        "--window-start", "2026-07-02T00:00:00Z", "--window-end", "2026-07-03T00:00:00Z"],
        capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["store_health_scope"] == "CURRENT_RETAINED_STATE_NOT_DECISION_TIME"
    assert report["store_isolated_captures"][0]["capture_id"] == "late"
    assert report["annotation"]["coverage"]["status"] == "UNKNOWN"
    assert report["execution_authority"] is False


@pytest.mark.parametrize("identity", ["published", "missing", "../escape"])
def test_ineligible_capture_cannot_be_removed_from_history(tmp_path, identity):
    root = tmp_path / "store"
    capture(root, "published", "2026-07-01T02:00:00Z")
    before = {path: path.read_bytes() for path in root.rglob("*") if path.is_file()}
    result = isolate(root, identity)
    assert result.returncode == 2
    assert not result.stdout
    assert "Traceback" not in result.stderr
    for path, raw in before.items():
        assert path.read_bytes() == raw
