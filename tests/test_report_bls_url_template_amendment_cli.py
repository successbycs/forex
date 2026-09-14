import json,subprocess,sys
from pathlib import Path
from tests.test_bls_primary_source_verifier import _retain
ROOT=Path(__file__).parents[1];SCRIPT=ROOT/"scripts/report_bls_url_template_amendment.py"
def test_cli_reports_nonactive_draft(tmp_path):
 result=subprocess.run([sys.executable,str(SCRIPT),"--baseline",str(ROOT/"config/primary_event_context.json"),"--draft",str(ROOT/"docs/milestones/W2-bls-monthly-url-template-amendment-draft.json")],text=True,capture_output=True,check=False)
 assert result.returncode==0 and json.loads(result.stdout)["activation"]=="NOT_APPLIED"
def test_cli_store_mode_uses_read_only_verified_candidates(tmp_path):
 _retain(tmp_path)
 result=subprocess.run([sys.executable,str(SCRIPT),"--baseline",str(ROOT/"config/primary_event_context.json"),"--draft",str(ROOT/"docs/milestones/W2-bls-monthly-url-template-amendment-draft.json"),"--store",str(tmp_path)],text=True,capture_output=True,check=False)
 report=json.loads(result.stdout)
 assert result.returncode==0 and report["activation"]=="NOT_APPLIED" and {row["family_id"] for row in report["matching_candidates"]}=={"US_CPI","US_EMPLOYMENT_SITUATION"}
def test_cli_refuses_candidates_and_store_together(tmp_path):
 candidate=tmp_path/"candidates.json";candidate.write_text("[]")
 result=subprocess.run([sys.executable,str(SCRIPT),"--baseline",str(ROOT/"config/primary_event_context.json"),"--draft",str(ROOT/"docs/milestones/W2-bls-monthly-url-template-amendment-draft.json"),"--candidates",str(candidate),"--store",str(tmp_path)],text=True,capture_output=True,check=False)
 assert result.returncode==2
