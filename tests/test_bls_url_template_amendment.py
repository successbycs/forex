from copy import deepcopy
from pathlib import Path
import pytest
from forex.bls_url_template_amendment import BLSURLTemplateAmendmentError,load_draft,matches_candidate,report_amendment,validate_draft
from forex.primary_event_context import load_contract
ROOT=Path(__file__).parents[1]
DRAFT=load_draft(ROOT/"docs/milestones/W2-bls-monthly-url-template-amendment-draft.json")
BASELINE=load_contract(ROOT/"config/primary_event_context.json")
def test_exact_actual_monthly_url_matches_only_nonactive_draft():
 row=next(item for item in DRAFT["amendments"] if item["family_id"]=="US_CPI")
 observation={"source_id":"bls-monthly-release-calendar","source_url":"https://www.bls.gov/schedule/2026/09_sched_list.htm","capture_state":"RETAINED","coverage_status":"UNKNOWN"}
 assert matches_candidate(amendment=row,observation=observation)
 report=report_amendment(baseline_contract=BASELINE,draft=DRAFT,candidates=[{"family_id":"US_CPI","event_id":"bls-cpi-2026-08","observation":observation}])
 assert report["status"]=="DRAFT_NOT_ACTIVE" and report["activation"]=="NOT_APPLIED" and report["execution_authority"] is False
def test_widening_unknown_family_and_authority_are_refused():
 for field,value in [("source_url_template","https://www.bls.gov/schedule/{year}/{month}_sched_list.htm"),("family_id","ANY"),("execution_authority",True)]:
  bad=deepcopy(DRAFT);bad["amendments"][0][field]=value
  with pytest.raises(BLSURLTemplateAmendmentError):validate_draft(bad)
def test_baseline_is_not_mutated_and_baseline_mismatch_refuses():
 before=deepcopy(BASELINE);report_amendment(baseline_contract=BASELINE,draft=DRAFT,candidates=[]);assert BASELINE==before
 bad=deepcopy(BASELINE);next(row for row in bad["required_families"] if row["family_id"]=="US_CPI")["source_url"]="https://wrong.example"
 with pytest.raises(BLSURLTemplateAmendmentError):report_amendment(baseline_contract=bad,draft=DRAFT,candidates=[])
