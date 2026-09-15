"""Execute workflow JavaScript against n8n-shaped data, including refusals."""
import base64
import json
from pathlib import Path
import subprocess

import pytest

from scripts.build_bls_n8n_workflow import workflow
from forex.bls_n8n_envelope import build_observation

ROOT = Path(__file__).resolve().parents[1]


def run_envelope(status=200, headers=None, body='<html>fixture</html>'):
    code = next(n['parameters']['jsCode'] for n in workflow()['nodes'] if n['id']=='envelope')
    script = """const {code,status,headers,body}=JSON.parse(require('fs').readFileSync(0,'utf8'));
const $=()=>({first:()=>({json:{capture_id:'test-1',year:2026,month:9,started_at_utc:'2026-09-14T00:00:00Z'}})});
const $input={first:()=>({json:{statusCode:status,headers}})};
const ctx={helpers:{getBinaryDataBuffer:async()=>Buffer.from(body)}};
new (Object.getPrototypeOf(async function(){}).constructor)('$','$input',code).call(ctx,$,$input)
 .then(r=>process.stdout.write(JSON.stringify(r[0].json))).catch(()=>process.exit(2));"""
    return subprocess.run(['node','-e',script], input=json.dumps({
        'code':code,'status':status,'headers':headers if headers is not None else {'content-type':'text/html'},'body':body}),
        capture_output=True,text=True)


def test_observed_envelope_round_trips_into_python_validator():
    # An array gives Buffer exact bytes, including bytes invalid as UTF-8.
    original=b'<html>\xff\x80\x00fixture</html>'
    r=run_envelope(body=list(original))
    assert r.returncode==0, r.stderr
    cid, raw=build_observation(json.loads(r.stdout))
    assert cid=='test-1'
    assert json.loads(raw)['status_code']==200
    assert base64.b64decode(json.loads(raw)['body_base64'])==original


@pytest.mark.parametrize('kwargs',[{'status':403},{'headers':{}},{'headers':{'content-type':'application/json'}},{'body':''},{'body':'x'*2097153}])
def test_refuses_invalid_publisher_results(kwargs):
    assert run_envelope(**kwargs).returncode==2


def test_artifact_matches_renderer_and_requires_manual_authenticated_capture():
    w=workflow()
    assert json.loads((ROOT/'n8n/forex-bls-calendar-retention.json').read_text())==w
    assert not w['active']
    assert all(not n['retryOnFail'] for n in w['nodes'])
    assert w['nodes'][-1]['parameters']['authentication']=='genericCredentialType'
    assert w['nodes'][2]['parameters']['options']['redirect']['redirect']['followRedirects'] is False
    assert not any(n['type'].endswith(('scheduleTrigger','executeCommand')) for n in w['nodes'])
