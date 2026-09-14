import hashlib
import json
from pathlib import Path

from forex.m1_event_risk_gate import evaluate_new_entry


ROOT = Path(__file__).resolve().parents[1]


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def primary(state="QUALIFIED_CONTEXT_ONLY"):
    sources = {
        "US_CPI": ("bls-monthly-release-calendar", "https://www.bls.gov/schedule/{year}/{month:02d}_sched_list.htm"),
        "US_EMPLOYMENT_SITUATION": ("bls-monthly-release-calendar", "https://www.bls.gov/schedule/{year}/{month:02d}_sched_list.htm"),
        "FOMC_POLICY_DECISION": ("federal-reserve-fomc-calendar", "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm"),
        "ECB_POLICY_DECISION": ("ecb-monetary-policy-calendar", "https://www.ecb.europa.eu/press/calendars/mgcgc/html/index.en.html"),
    }
    families = [{"family_id": family_id, "source_id": source_id, "state": "QUALIFIED_CONTEXT_ONLY",
                 "reason": "RETAINED_COMPLETE_SOURCE_COVERAGE", "qualification_state": "FUTURE_AMENDED_CONTRACT",
                 "limitation": "context only", "receipt": {"source_url": url, "captured_at_utc": "2026-09-12T00:00:00Z",
                 "source_sha256": "sha256:" + str(index) * 64, "coverage_status": "COMPLETE"}}
                for index, (family_id, (source_id, url)) in enumerate(sources.items(), start=1)]
    body = {"schema_version": "forex.primary-event-context.v1", "context_state": state, "families": families,
            "execution_authority": False, "limitations": ["context only"]}
    return {**body, "context_sha256": "sha256:" + hashlib.sha256(canonical(body)).hexdigest()}


def sidecar(seconds=3600):
    annotation_body = {"annotation_type": "EVENT_CONTEXT_ONLY", "decision_at_utc": "2026-09-13T00:00:00Z",
                       "window": {"start_utc": "2026-09-12T00:00:00Z", "end_utc": "2026-09-14T00:00:00Z"},
                       "qualified_result_sha256": "sha256:" + "2" * 64,
                       "coverage": {"status": "UNKNOWN"},
                       "events": [] if seconds is None else [{"seconds_from_decision": seconds}], "quarantined": [],
                       "quarantine_window_membership": "UNKNOWN"}
    annotation = {**annotation_body, "annotation_sha256": "sha256:" + hashlib.sha256(canonical(annotation_body)).hexdigest()}
    body = {"schema_version": "forex.m1.event-context-sidecar.v1", "annotation_type": "EVENT_CONTEXT_ONLY",
            "execution_authority": False, "source_raw_sha256": "sha256:" + "3" * 64,
            "event_context_journal_sha256": "sha256:" + "4" * 64,
            "event_qualification_sha256": "sha256:" + "2" * 64,
            "event_annotation_sha256": annotation["annotation_sha256"], "decision_at_utc": "2026-09-13T00:00:00Z",
            "event_annotation": annotation}
    return {**body, "sidecar_sha256": "sha256:" + hashlib.sha256(canonical(body)).hexdigest()}


def enabled_policy():
    policy = json.loads((ROOT / "config/m1_event_risk_gate.json").read_text())
    return {**policy, "enabled": True}


def test_shipped_disabled_policy_does_not_require_context_or_change_execution_behavior():
    policy = json.loads((ROOT / "config/m1_event_risk_gate.json").read_text())
    result = evaluate_new_entry(policy=policy, sidecar={"bad": True}, primary_context={"bad": True})
    assert result == {"schema_version": "forex.m1-event-risk-gate.v1", "execution_authority": False,
                      "scope": "NEW_ENTRY_ONLY", "state": "ANNOTATION_ONLY_DISABLED", "new_entry_permitted": None,
                      "reason": "SHIPPED_POLICY_DISABLED_NO_EXECUTION_BEHAVIOR_CHANGE"}


def test_enabled_gate_refuses_unavailable_partial_or_tampered_context():
    partial = evaluate_new_entry(policy=enabled_policy(), sidecar=sidecar(), primary_context=primary("PARTIAL"))
    assert partial["state"] == "FAIL_SAFE_CONTEXT_PARTIAL" and partial["new_entry_permitted"] is False
    broken = sidecar(); broken["event_annotation"]["events"].append({"seconds_from_decision": 0})
    tampered = evaluate_new_entry(policy=enabled_policy(), sidecar=broken, primary_context=primary())
    assert tampered["state"] == "FAIL_SAFE_CONTEXT_UNAVAILABLE" and tampered["new_entry_permitted"] is False


def test_enabled_gate_refuses_empty_or_future_primary_receipt_context():
    compact = primary(); compact["families"] = []
    compact_body = {key: value for key, value in compact.items() if key != "context_sha256"}
    compact["context_sha256"] = "sha256:" + hashlib.sha256(canonical(compact_body)).hexdigest()
    empty = evaluate_new_entry(policy=enabled_policy(), sidecar=sidecar(), primary_context=compact)
    assert empty["state"] == "FAIL_SAFE_CONTEXT_UNAVAILABLE" and empty["new_entry_permitted"] is False
    future = primary(); future["families"][0]["receipt"]["captured_at_utc"] = "2026-09-14T00:00:00Z"
    future_body = {key: value for key, value in future.items() if key != "context_sha256"}
    future["context_sha256"] = "sha256:" + hashlib.sha256(canonical(future_body)).hexdigest()
    result = evaluate_new_entry(policy=enabled_policy(), sidecar=sidecar(), primary_context=future)
    assert result["state"] == "FAIL_SAFE_CONTEXT_UNAVAILABLE" and "unavailable at decision" in result["reason"]


def test_enabled_gate_refuses_qualified_event_window_and_allows_only_qualified_clear_context():
    refused = evaluate_new_entry(policy=enabled_policy(), sidecar=sidecar(300), primary_context=primary())
    assert refused["state"] == "NEW_ENTRY_REFUSED_EVENT_WINDOW" and refused["new_entry_permitted"] is False
    allowed = evaluate_new_entry(policy=enabled_policy(), sidecar=sidecar(3601), primary_context=primary())
    assert allowed["state"] == "NEW_ENTRY_PERMITTED" and allowed["new_entry_permitted"] is True


def test_prepared_gate_is_wired_only_at_the_m20_final_action_overlay_seam():
    kernel = (ROOT / "src/forex/m20_policy_kernel.py").read_text()
    listener = (ROOT / "t480/m20_demo_trading_session.py").read_text()
    assert "m1_event_risk_gate" not in kernel
    assert "evaluate_new_entry" in listener
    assert "_apply_m1_calendar_overlay(" in listener
