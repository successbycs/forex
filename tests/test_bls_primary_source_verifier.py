import base64,hashlib,json
import pytest
from forex.bls_collection import retain_response
from forex.bls_primary_source_verifier import BLSPrimarySourceVerificationError,verify_bls_primary_source

URL="https://www.bls.gov/schedule/2026/09_sched_list.htm"
HTML=(b"<html><body><p>NOTE: All times on calendar are Eastern Time.</p><table><tr><th>Date</th><th>Time</th><th>Release</th></tr>"
 b"<tr><td>Friday, September 4, 2026</td><td>08:30 AM</td><td>Employment Situation for August 2026</td></tr>"
 b"<tr><td>Friday, September 11, 2026</td><td>08:30 AM</td><td>Consumer Price Index for August 2026</td></tr></table></body></html>")
def _response(body=HTML,completed="2026-01-01T00:00:01Z"):
 return json.dumps({"schema_version":"forex.bls-http-observation.v1","requested_url":URL,"started_at_utc":"2026-01-01T00:00:00Z","completed_at_utc":completed,"status_code":200,"content_type":"text/html","body_base64":base64.b64encode(body).decode(),"body_complete":True,"outcome":"SUCCESS","error_code":None,"execution_authority":False}).encode()
def _retain(root,capture_id="sep",**changes):return retain_response(root,capture_id=capture_id,raw=_response(**changes),year=2026,month=9)
def test_valid_monthly_evidence_is_verified_but_template_limitation_is_explicit(tmp_path):
 _retain(tmp_path);report=verify_bls_primary_source(tmp_path)
 assert {row["family_id"] for row in report["context_candidates"]}=={"US_CPI","US_EMPLOYMENT_SITUATION"}
 assert {row["family_id"] for row in report["primary_context_observations"]}=={"US_CPI","US_EMPLOYMENT_SITUATION"}
 assert report["primary_context_policy"]["state"]=="ACTIVE_EXACT_BLS_MONTHLY_TEMPLATE_MATCHING"
 assert report["coverage_status"]=="UNKNOWN" and report["execution_authority"] is False
def test_tamper_partial_and_unsafe_root_refuse(tmp_path):
 _retain(tmp_path);next((tmp_path/"acquisitions/sep").glob("*.json")).write_bytes(b"{}")
 with pytest.raises(BLSPrimarySourceVerificationError):verify_bls_primary_source(tmp_path)
 partial=tmp_path/"partial";(partial/"raw").mkdir(parents=True);(partial/"metadata").mkdir();(partial/"journals").mkdir();(partial/"raw"/"orphan.html").write_bytes(HTML)
 with pytest.raises(BLSPrimarySourceVerificationError):verify_bls_primary_source(partial)
 actual=tmp_path/"actual";actual.mkdir();link=tmp_path/"link";link.symlink_to(actual,target_is_directory=True)
 with pytest.raises(BLSPrimarySourceVerificationError):verify_bls_primary_source(link)
def test_duplicate_month_captures_remain_separate_candidates(tmp_path):
 _retain(tmp_path,"one",completed="2026-01-01T00:00:01Z");_retain(tmp_path,"two",completed="2026-01-01T00:00:02Z")
 report=verify_bls_primary_source(tmp_path)
 assert len(report["captures"])==2 and len(report["context_candidates"])==4
def test_equivalent_fractional_receipt_time_is_normalized_but_different_instant_refuses(tmp_path):
 _retain(tmp_path,completed="2026-01-01T00:00:01.635Z")
 assert verify_bls_primary_source(tmp_path)["captures"]
 directory=tmp_path/"acquisitions"/"sep";old=next(directory.glob("*.json"));different=_response(completed="2026-01-01T00:00:01.636Z")
 old.unlink();(directory/(hashlib.sha256(different).hexdigest()+".json")).write_bytes(different)
 with pytest.raises(BLSPrimarySourceVerificationError,match="provenance conflicts"):
  verify_bls_primary_source(tmp_path)
