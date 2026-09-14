import json,subprocess,sys
from pathlib import Path
from tests.test_policy_timing_amendment import _store
ROOT=Path(__file__).parents[1]
def test_cli_reports_nonactive_timing_draft(tmp_path):
 _store(tmp_path);r=subprocess.run([sys.executable,str(ROOT/"scripts/report_policy_timing_amendment.py"),"--baseline",str(ROOT/"config/primary_event_context.json"),"--draft",str(ROOT/"docs/milestones/W2-policy-timing-source-qualification-amendment-draft.json"),"--store",str(tmp_path)],text=True,capture_output=True,check=False)
 assert r.returncode==0 and json.loads(r.stdout)["activation"]=="NOT_APPLIED"
