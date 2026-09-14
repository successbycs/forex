import json,subprocess,sys
from pathlib import Path
from tests.test_bls_primary_source_verifier import _retain
SCRIPT=Path(__file__).parents[1]/"scripts/verify_bls_primary_source.py"
def test_cli_reports_template_limitation(tmp_path):
 _retain(tmp_path);result=subprocess.run([sys.executable,str(SCRIPT),"--store",str(tmp_path)],text=True,capture_output=True,check=False)
 assert result.returncode==0 and json.loads(result.stdout)["primary_context_observations"]
