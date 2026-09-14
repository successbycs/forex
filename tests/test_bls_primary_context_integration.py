from pathlib import Path
from forex.bls_primary_context_integration import report_bls_primary_context
from forex.primary_event_context import load_contract
from tests.test_bls_primary_source_verifier import _retain
CONTRACT=load_contract(Path(__file__).parents[1]/"config/primary_event_context.json")
def _family(report,family):return next(row for row in report["primary_context"]["families"] if row["family_id"]==family)
def test_active_exact_bls_template_is_partial_unknown_not_complete(tmp_path):
 _retain(tmp_path);report=report_bls_primary_context(store_root=tmp_path,contract=CONTRACT)
 assert (_family(report,"US_CPI")["state"],_family(report,"US_EMPLOYMENT_SITUATION")["state"])==("PARTIAL","PARTIAL")
 assert report["coverage_status"]=="UNKNOWN" and report["execution_authority"] is False
def test_duplicate_bls_month_captures_stay_ambiguous(tmp_path):
 _retain(tmp_path,"one",completed="2026-01-01T00:00:01Z");_retain(tmp_path,"two",completed="2026-01-01T00:00:02Z")
 report=report_bls_primary_context(store_root=tmp_path,contract=CONTRACT)
 assert _family(report,"US_CPI")["reason"]=="MULTIPLE_SOURCE_OBSERVATIONS"
