from copy import deepcopy
import json

import pytest

from forex.primary_event_context import load_contract
from forex.primary_event_context_integration import (
    PrimaryEventContextIntegrationError,
    report_policy_timing_context,
)
from forex.first_party_policy_timing_store import retain_policy_timing_bundle


CONTRACT = load_contract(__import__("pathlib").Path(__file__).parents[1] / "config" / "primary_event_context.json")


def _retain(root, **changes):
    values = {"family_id": "FOMC_POLICY_DECISION", "target_date": "2026-01-28",
              "calendar_raw": b"#### 2026 FOMC Meetings January 27-28",
              "calendar_capture_completed_at_utc": "2026-01-01T01:00:00Z",
              "timing_raw": b"The Committee releases a policy statement at 2 p.m. Eastern Time.",
              "timing_capture_completed_at_utc": "2026-01-01T02:00:00Z"}
    values.update(changes)
    return retain_policy_timing_bundle(root, **values)


def _family(report, family_id):
    return next(row for row in report["primary_context"]["families"] if row["family_id"] == family_id)


def test_one_verified_bundle_is_retained_detail_but_unknown_coverage_stays_partial(tmp_path):
    _retain(tmp_path)
    report = report_policy_timing_context(store_root=tmp_path, contract=CONTRACT)
    fomc = _family(report, "FOMC_POLICY_DECISION")
    assert (fomc["state"], fomc["reason"]) == ("PARTIAL", "SOURCE_COVERAGE_NOT_COMPLETE")
    assert len(report["verified_policy_timing_bundles"]) == 1
    assert report["coverage_status"] == "UNKNOWN" and report["execution_authority"] is False


def test_multiple_real_bundles_are_not_silently_selected(tmp_path):
    _retain(tmp_path)
    _retain(tmp_path, target_date="2026-03-18", calendar_raw=b"#### 2026 FOMC Meetings January 27-28 March 17-18")
    report = report_policy_timing_context(store_root=tmp_path, contract=CONTRACT)
    fomc = _family(report, "FOMC_POLICY_DECISION")
    assert (fomc["state"], fomc["reason"]) == ("AMBIGUOUS", "MULTIPLE_SOURCE_OBSERVATIONS")
    assert [item["target_date"] for item in report["verified_policy_timing_bundles"]] == ["2026-01-28", "2026-03-18"]


def test_verifier_failure_and_contract_source_mismatch_are_explicit(tmp_path):
    _retain(tmp_path)
    target = tmp_path / "FOMC_POLICY_DECISION" / "2026-01-28"
    (target / "timing.html").write_bytes(b"tampered")
    with pytest.raises(PrimaryEventContextIntegrationError):
        report_policy_timing_context(store_root=tmp_path, contract=CONTRACT)
    clean = tmp_path / "clean"; _retain(clean)
    mismatch = deepcopy(CONTRACT)
    next(row for row in mismatch["required_families"] if row["family_id"] == "FOMC_POLICY_DECISION")["source_url"] = "https://wrong.example/calendar"
    report = report_policy_timing_context(store_root=clean, contract=mismatch)
    assert (_family(report, "FOMC_POLICY_DECISION")["state"], _family(report, "FOMC_POLICY_DECISION")["reason"]) == ("AMBIGUOUS", "SOURCE_URL_DOES_NOT_MATCH_CONTRACT")
