from copy import deepcopy
from pathlib import Path
import pytest
from forex.first_party_policy_timing_store import retain_policy_timing_bundle
from forex.policy_timing_amendment import PolicyTimingAmendmentError,load_draft,report_amendment,validate_draft
from forex.primary_event_context import load_contract
ROOT=Path(__file__).parents[1];DRAFT=load_draft(ROOT/"docs/milestones/W2-policy-timing-source-qualification-amendment-draft.json");BASELINE=load_contract(ROOT/"config/primary_event_context.json")
def _preapproval_baseline():
 baseline=deepcopy(BASELINE)
 for row in baseline["required_families"]:
  if row["family_id"] in {"FOMC_POLICY_DECISION","ECB_POLICY_DECISION"}:
   row.pop("source_url_matching_policy");row["qualification_state"]="PENDING_RETAINED_CAPTURE"
 return baseline
def _store(root):
 retain_policy_timing_bundle(root,family_id="FOMC_POLICY_DECISION",target_date="2026-09-16",calendar_raw=b"#### 2026 FOMC Meetings September 15-16",calendar_capture_completed_at_utc="2026-01-01T00:00:00Z",timing_raw=b"The Committee releases a policy statement at 2 p.m. Eastern Time.",timing_capture_completed_at_utc="2026-01-01T00:01:00Z")
 retain_policy_timing_bundle(root,family_id="ECB_POLICY_DECISION",target_date="2026-10-29",calendar_raw=b"29/10/2026 Governing Council monetary policy meeting (Day 2)",calendar_capture_completed_at_utc="2026-01-01T00:00:00Z",timing_raw=b"The ECB monetary policy decisions are published in a press release at 14:15 CET.",timing_capture_completed_at_utc="2026-01-01T00:01:00Z")
def test_exact_pending_bundle_evidence_reports_nonactive_no_authority(tmp_path):
 _store(tmp_path);r=report_amendment(baseline_contract=_preapproval_baseline(),draft=DRAFT,store_root=tmp_path)
 assert r["activation"]=="NOT_APPLIED" and r["execution_authority"] is False and {x["family_id"] for x in r["verified_retained_bundles"]}=={"FOMC_POLICY_DECISION","ECB_POLICY_DECISION"}
def test_tamper_and_timing_source_mismatch_refuse(tmp_path):
 _store(tmp_path);(tmp_path/"FOMC_POLICY_DECISION"/"2026-09-16"/"timing.html").write_bytes(b"tamper")
 with pytest.raises(PolicyTimingAmendmentError):report_amendment(baseline_contract=_preapproval_baseline(),draft=DRAFT,store_root=tmp_path)
 _store(tmp_path/"clean");bad=deepcopy(DRAFT);bad["amendments"][0]["timing_url"]="https://wrong.example"
 with pytest.raises(PolicyTimingAmendmentError):validate_draft(bad)
def test_draft_cannot_widen_or_activate():
 for field,value in [("calendar_url","https://www.federalreserve.gov/anything"),("execution_authority",True),("target_date","2026-09-17")]:
  bad=deepcopy(DRAFT);bad["amendments"][0][field]=value
  with pytest.raises(PolicyTimingAmendmentError):validate_draft(bad)
