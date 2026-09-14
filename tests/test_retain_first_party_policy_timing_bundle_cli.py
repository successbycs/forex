import json
import subprocess
import sys
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "retain_first_party_policy_timing_bundle.py"


def test_cli_retains_local_inputs_and_refuses_invalid_bytes(tmp_path):
    calendar = tmp_path / "calendar.html"; timing = tmp_path / "timing.html"
    calendar.write_bytes(b"#### 2026 FOMC Meetings January 27-28")
    timing.write_bytes(b"The Committee releases a policy statement at 2 p.m. Eastern Time.")
    command = [sys.executable, str(SCRIPT), str(calendar), str(timing), "--store", str(tmp_path / "store"),
               "--family", "FOMC_POLICY_DECISION", "--target-date", "2026-01-28",
               "--calendar-capture-completed-at", "2026-01-01T01:00:00Z",
               "--timing-capture-completed-at", "2026-01-01T02:00:00Z"]
    first = subprocess.run(command, text=True, capture_output=True, check=False)
    assert first.returncode == 0 and json.loads(first.stdout)["status"] == "CREATED"
    second = subprocess.run(command, text=True, capture_output=True, check=False)
    assert second.returncode == 0 and json.loads(second.stdout)["status"] == "EXISTING"
    timing.write_bytes(b"no official declaration")
    refused = subprocess.run(command, text=True, capture_output=True, check=False)
    assert refused.returncode == 2 and "refused" in refused.stderr
