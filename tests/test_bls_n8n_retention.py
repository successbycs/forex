import base64, tempfile
from pathlib import Path
from forex.bls_n8n_envelope import build_observation
from forex.bls_n8n_retention import retain
def test_retains_receipt_and_observation():
 v={"capture_id":"x","year":2026,"month":9,"started_at_utc":"2026-09-14T00:00:00Z","completed_at_utc":"2026-09-14T00:00:01Z","status_code":200,"content_type":"text/html","body_base64":base64.b64encode(b"<html>x</html>").decode(),"body_complete":True}
 cid,raw=build_observation(v)
 with tempfile.TemporaryDirectory() as d:
  r=retain(Path(d),capture_id=cid,observation=raw,year=2026,month=9,workflow_id="fixed",workflow_sha256="sha256:"+"a"*64)
  replay=retain(Path(d),capture_id=cid,observation=raw,year=2026,month=9,workflow_id="fixed",workflow_sha256="sha256:"+"a"*64)
  assert r == replay and r["execution_authority"] is False and (Path(d)/"n8n-receipts"/"x").exists()
