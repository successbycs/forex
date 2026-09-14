from copy import deepcopy

import pytest

from forex.event_quality import qualify_events
from forex.first_party_policy_capture import SOURCES
from forex.first_party_policy_event_adapter import PolicyEventAdapterError, project_policy_timing_event
from forex.first_party_policy_timing import TIMING_URLS, derive_exact_policy_time


def _inputs(family="FOMC_POLICY_DECISION"):
    if family == "FOMC_POLICY_DECISION":
        date, calendar, timing = ("2026-01-28", b"#### 2026 FOMC Meetings January 27-28",
                                  b"The Committee releases a policy statement at 2 p.m. Eastern Time.")
    else:
        date, calendar, timing = ("2026-10-30", b"Day 2: 30 October 2026 Governing Council monetary policy meeting",
                                  b"The ECB's monetary policy decisions are published in a press release at 14:15 CET.")
    bundle = derive_exact_policy_time(family_id=family, target_date=date, calendar_raw=calendar,
                                      calendar_url=SOURCES[family][1], timing_raw=timing,
                                      timing_url=TIMING_URLS[family])
    def receipt(url, raw, stamp):
        import hashlib
        return {"source_url": url, "source_sha256": "sha256:" + hashlib.sha256(raw).hexdigest(),
                "capture_completed_at_utc": stamp}
    return bundle, calendar, receipt(SOURCES[family][1], calendar, "2026-01-01T01:00:00Z"), timing, receipt(TIMING_URLS[family], timing, "2026-01-01T02:00:00Z")


def test_projects_hash_bound_fomc_bundle_into_event_quality_record():
    bundle, calendar, calendar_receipt, timing, timing_receipt = _inputs()
    record = project_policy_timing_event(bundle=bundle, calendar_raw=calendar, calendar_receipt=calendar_receipt,
                                         timing_raw=timing, timing_receipt=timing_receipt)
    assert record["available_at_utc"] == "2026-01-01T02:00:00Z"
    assert set(record["document_provenance"]) == {"calendar", "timing", "timing_bundle_sha256"}
    result = qualify_events([record], "2026-02-01T00:00:00Z")
    assert result["accepted"][0]["scheduled_at_utc"] == bundle["scheduled_at_utc"]


def test_projects_ecb_bundle_with_later_calendar_receipt():
    bundle, calendar, calendar_receipt, timing, timing_receipt = _inputs("ECB_POLICY_DECISION")
    calendar_receipt["capture_completed_at_utc"] = "2026-01-01T03:00:00Z"
    record = project_policy_timing_event(bundle=bundle, calendar_raw=calendar, calendar_receipt=calendar_receipt,
                                         timing_raw=timing, timing_receipt=timing_receipt)
    assert record["available_at_utc"] == "2026-01-01T03:00:00Z"
    assert qualify_events([record], "2026-11-01T00:00:00Z")["accepted"]


@pytest.mark.parametrize("mutation", ["bundle_hash", "bundle_url", "raw_hash", "receipt_url", "future_schedule"])
def test_tampered_bundle_or_receipt_refuses(mutation):
    bundle, calendar, calendar_receipt, timing, timing_receipt = _inputs()
    if mutation == "bundle_hash": bundle["bundle_sha256"] = "sha256:" + "0" * 64
    elif mutation == "bundle_url": bundle["timing_url"] = "https://wrong.example/timing"
    elif mutation == "raw_hash": timing = b"different retained bytes"
    elif mutation == "receipt_url": calendar_receipt["source_url"] = "https://wrong.example/calendar"
    else:
        bundle["scheduled_at_utc"] = "2026-01-28T00:00:00Z"
        from forex.first_party_policy_timing import timing_bundle_sha256
        bundle["bundle_sha256"] = timing_bundle_sha256(bundle)
    with pytest.raises(PolicyEventAdapterError):
        project_policy_timing_event(bundle=bundle, calendar_raw=calendar, calendar_receipt=calendar_receipt,
                                    timing_raw=timing, timing_receipt=timing_receipt)


def test_malformed_receipt_and_unaccepted_event_quality_path_refuse():
    bundle, calendar, calendar_receipt, timing, timing_receipt = _inputs()
    calendar_receipt.pop("capture_completed_at_utc")
    with pytest.raises(PolicyEventAdapterError):
        project_policy_timing_event(bundle=bundle, calendar_raw=calendar, calendar_receipt=calendar_receipt,
                                    timing_raw=timing, timing_receipt=timing_receipt)
