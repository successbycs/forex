import json,subprocess,sys
from pathlib import Path
from tests.test_bls_primary_source_verifier import _retain
ROOT=Path(__file__).parents[1]
def test_cli_reports_partial_bls_context(tmp_path):
 _retain(tmp_path);result=subprocess.run([sys.executable,str(ROOT/"scripts/report_bls_primary_context.py"),"--store",str(tmp_path),"--contract",str(ROOT/"config/primary_event_context.json")],text=True,capture_output=True,check=False)
 assert result.returncode==0 and json.loads(result.stdout)["primary_context"]["context_state"]=="UNAVAILABLE"
