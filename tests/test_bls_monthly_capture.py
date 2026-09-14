import json
from pathlib import Path
import subprocess
import sys

import pytest

from forex.event_capture_store import read_capture_journal, retain_bls_capture
from forex.event_capture_recovery import resume_bls_capture
from forex.event_revisions import qualify_journal


URL = "https://www.bls.gov/schedule/2026/09_sched_list.htm"
RAW = b'''<p>NOTE: All times on calendar are Eastern Time.</p><table>
<tr><th>Date</th><th>Time</th><th>Release</th></tr>
<tr><td>Friday, September 4, 2026</td><td>08:30 AM</td><td>Employment Situation for August 2026</td></tr>
<tr><td>Friday, September 11, 2026</td><td>08:30 AM</td><td>Consumer Price Index for August 2026</td></tr>
</table>'''


def test_monthly_capture_retention_resume_and_asof_qualification(tmp_path):
    args = dict(capture_id="monthly-1", raw=RAW, source_family="BLS_MONTHLY",
                source_url=URL, capture_completed_at_utc="2026-09-01T00:00:00Z")
    retained = retain_bls_capture(tmp_path, **args)
    assert len(retained["journal"]["records"]) == 2
    assert read_capture_journal(tmp_path) == retained["journal"]
    assert resume_bls_capture(tmp_path, **args)["journal"] == retained["journal"]
    assert qualify_journal(retained["journal"], decision_cutoff_utc="2026-08-31T23:59:59Z")["accepted"] == []
    accepted = qualify_journal(retained["journal"], decision_cutoff_utc="2026-09-01T00:00:00Z")["accepted"]
    assert [row["scheduled_at_utc"] for row in accepted] == ["2026-09-04T12:30:00Z", "2026-09-11T12:30:00Z"]
    assert all(row["source_url"] == URL for row in accepted)


def test_monthly_capture_command_uses_existing_durable_store(tmp_path):
    source = tmp_path / "monthly.html"
    source.write_bytes(RAW)
    script = Path(__file__).resolve().parents[1] / "scripts/bls_capture.py"
    result = subprocess.run([sys.executable, str(script), str(source),
        "--store", str(tmp_path / "store"), "--capture-id", "monthly-1",
        "--monthly-url", URL, "--capture-completed-at", "2026-09-01T00:00:00Z"],
        cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["revision_count"] == 2
    assert report["parser_quarantined"] == []
    assert report["coverage_status"] == "UNKNOWN"
    assert report["execution_authority"] is False
    assert source.read_bytes() == RAW


def test_monthly_wrong_source_refuses_before_publication(tmp_path):
    with pytest.raises(ValueError):
        retain_bls_capture(tmp_path, capture_id="bad", raw=RAW, source_family="BLS_MONTHLY",
            source_url="https://example.com/schedule/2026/09_sched_list.htm",
            capture_completed_at_utc="2026-09-01T00:00:00Z")
    assert list(tmp_path.iterdir()) == []


def test_new_unknown_release_time_does_not_fall_back_to_old_exact_schedule(tmp_path):
    args = dict(raw=RAW, source_family="BLS_MONTHLY", source_url=URL)
    retain_bls_capture(tmp_path, capture_id="one", capture_completed_at_utc="2026-09-01T00:00:00Z", **args)
    args["raw"] = RAW.replace(b"08:30 AM", b"TBD")
    later = retain_bls_capture(tmp_path, capture_id="two", capture_completed_at_utc="2026-09-02T00:00:00Z", **args)
    qualified = qualify_journal(later["journal"], decision_cutoff_utc="2026-09-02T00:00:00Z")
    assert qualified["accepted"] == []
    assert len(later["journal"]["records"]) == 4
    earlier = qualify_journal(later["journal"], decision_cutoff_utc="2026-09-01T00:00:00Z")
    assert len(earlier["accepted"]) == 2


def test_inconsistent_weekday_is_quarantined():
    from forex.bls_monthly_events import parse_bls_monthly_html
    parsed = parse_bls_monthly_html(RAW.decode().replace("Friday, September", "Monday, September"),
        source_url=URL, capture_completed_at_utc="2026-09-01T00:00:00Z")
    assert len(parsed["records"]) == 2
    assert all(row["time_precision"] == "DATE_ONLY" for row in parsed["records"])
    assert all(row["reason"] == "MALFORMED_BLS_MONTHLY_DATE" for row in parsed["quarantined"])


@pytest.mark.parametrize("raw", [RAW.replace(b"Friday, September", b"Monday, September"),
                                 RAW.replace(b"Friday, September 4", b"Sunday, October 4").replace(b"Friday, September 11", b"Sunday, October 11")])
def test_known_event_with_new_invalid_date_cannot_keep_old_exact_schedule(tmp_path, raw):
    common = dict(source_family="BLS_MONTHLY", source_url=URL)
    retain_bls_capture(tmp_path, capture_id="one", raw=RAW, capture_completed_at_utc="2026-09-01T00:00:00Z", **common)
    later = retain_bls_capture(tmp_path, capture_id="two", raw=raw, capture_completed_at_utc="2026-09-02T00:00:00Z", **common)
    assert qualify_journal(later["journal"], decision_cutoff_utc="2026-09-02T00:00:00Z")["accepted"] == []
    assert len(later["journal"]["records"]) == 4
