import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/retain_first_party_policy_capture.py"

def sample():
    return b'<div data-forex-policy-event="FOMC_POLICY_DECISION" data-scheduled-at-local="2026-10-29T14:00" data-timezone="America/New_York"></div>'

def command(input_path, store, capture_id="one"):
    return [sys.executable, str(SCRIPT), str(input_path), "--store", str(store), "--capture-id", capture_id,
            "--family", "FOMC_POLICY_DECISION", "--capture-completed-at", "2026-09-13T00:00:00Z"]

def test_cli_retains_only_supplied_local_bytes_and_keeps_unknown_coverage(tmp_path):
    source = tmp_path / "input.html"; source.write_bytes(sample()); before = source.read_bytes()
    result = subprocess.run(command(source, tmp_path / "store"), cwd=ROOT, text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    assert source.read_bytes() == before
    payload = json.loads(result.stdout)
    assert payload["coverage_status"] == "UNKNOWN" and payload["execution_authority"] is False
    text = SCRIPT.read_text()
    assert "urllib" not in text and "requests" not in text and "t480_adapter" not in text and "subprocess" not in text

def test_cli_refuses_invalid_input_and_never_overwrites_capture(tmp_path):
    bad = tmp_path / "bad.html"; bad.write_bytes(b"<html></html>")
    store = tmp_path / "store"
    first = subprocess.run(command(bad, store), cwd=ROOT, text=True, capture_output=True)
    assert first.returncode == 0  # quarantined local evidence is still retained
    second = subprocess.run(command(bad, store), cwd=ROOT, text=True, capture_output=True)
    assert second.returncode == 2 and second.stdout == "" and "already exists" in second.stderr
    missing = subprocess.run(command(tmp_path / "missing.html", store, "two"), cwd=ROOT, text=True, capture_output=True)
    assert missing.returncode == 2 and missing.stdout == ""
