import json
import subprocess
import sys
from pathlib import Path

from forex.first_party_policy_timing_store import retain_policy_timing_bundle


SCRIPT = Path(__file__).parents[1] / "scripts" / "report_primary_event_policy_timing_context.py"
CONTRACT = Path(__file__).parents[1] / "config" / "primary_event_context.json"


def test_cli_reports_current_pending_state_without_mutating_store(tmp_path):
    retain_policy_timing_bundle(tmp_path, family_id="FOMC_POLICY_DECISION", target_date="2026-01-28",
        calendar_raw=b"#### 2026 FOMC Meetings January 27-28", calendar_capture_completed_at_utc="2026-01-01T01:00:00Z",
        timing_raw=b"The Committee releases a policy statement at 2 p.m. Eastern Time.", timing_capture_completed_at_utc="2026-01-01T02:00:00Z")
    before = sorted(str(path.relative_to(tmp_path)) for path in tmp_path.rglob("*"))
    result = subprocess.run([sys.executable, str(SCRIPT), "--store", str(tmp_path), "--contract", str(CONTRACT)], text=True, capture_output=True, check=False)
    assert result.returncode == 0
    report = json.loads(result.stdout)
    assert report["primary_context"]["context_state"] == "UNAVAILABLE"
    assert sorted(str(path.relative_to(tmp_path)) for path in tmp_path.rglob("*")) == before
