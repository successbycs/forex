import base64, json, subprocess, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
def test_cli_outputs_only_verified_observation():
 v={"capture_id":"x","year":2026,"month":9,"started_at_utc":"2026-09-14T00:00:00Z","completed_at_utc":"2026-09-14T00:00:01Z","status_code":200,"content_type":"text/html","body_base64":base64.b64encode(b"<html>x</html>").decode(),"body_complete":True}
 r=subprocess.run([sys.executable,"scripts/validate_bls_n8n_handoff.py"],cwd=ROOT,input=json.dumps(v),text=True,capture_output=True)
 assert r.returncode==0 and json.loads(r.stdout)["execution_authority"] is False
