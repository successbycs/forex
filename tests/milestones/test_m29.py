import hashlib
import json
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest
from forex.config import load_configuration

ROOT = Path(__file__).resolve().parents[2]
VERIFY = ROOT / 'scripts/verify_m29_evidence.sh'

def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()

def bundle():
    # Synthetic evidence is isolated below the declared evidence root and removed by the caller.
    directory = Path(tempfile.mkdtemp(prefix='pytest-m29-', dir=ROOT / 'runs/evidence/M29'))
    fingerprint = json.loads(subprocess.check_output(['python3','scripts/forex_milestones.py','status','--json'],cwd=ROOT,text=True))['configuration_fingerprint']
    revision = subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    now = datetime.now(timezone.utc).replace(microsecond=0); offset = load_configuration(ROOT, environ={}).mt5.broker_tick_time_offset_seconds
    tick = {'ok':True,'server':'GOMarketsMU-Demo','symbol':'EURUSD','bid':1.1,'ask':1.1001,'tick_time_msc':int((now.timestamp()+offset)*1000),'broker_timestamp_offset_seconds':offset,'broker_timestamp_offset_source':'governed_configuration','captured_at_utc':now.isoformat().replace('+00:00','Z')}
    def envelope(): return {'operation':'m27_demo_tick','approval_required':False,'approved':False,'ok':True,'configuration_fingerprint':fingerprint,'result':{'ok':True,'exit_code':0,'stdout':json.dumps(tick)}}
    for name in ('pre-interruption-response.json','recovery-response.json'): (directory/name).write_text(json.dumps(envelope()))
    for name, text in {'interrupted-client-attempt.txt':'client timed out\n','governance.txt':'ok\n','tests.txt':'ok\n','revision.txt':revision+'\n','summary.txt':'FOREX_M29_OBSERVATION_CAPTURED_UNSUPPORTED\n'}.items(): (directory/name).write_text(text)
    record = {'operation':'m27_demo_tick','server':tick['server'],'symbol':tick['symbol'],'bid':tick['bid'],'ask':tick['ask'],'tick_time_msc':tick['tick_time_msc'],'broker_timestamp_offset_seconds':offset,'broker_timestamp_offset_source':'governed_configuration','tick_captured_at_utc':tick['captured_at_utc']}
    proof={'request_identity':'m27_demo_tick:GOMarketsMU-Demo:EURUSD','raw_envelopes':{'pre_interruption_response_sha256':digest(directory/'pre-interruption-response.json'),'recovery_response_sha256':digest(directory/'recovery-response.json')},'pre_interruption':record,'interruption':{'state':'INTERRUPTED_CLIENT_SIDE','exit_code':124,'remote_mutation':'STRUCTURALLY_DISABLED','note':'The timeout terminates only the local adapter client before response processing.'},'recovery':record,'idempotency':'REPEATED_FIXED_READ_ONLY_REQUEST_NO_PERSISTENT_MUTATION'}
    (directory/'recovery-proof.json').write_text(json.dumps(proof))
    artifacts=[{'path':p.name,'sha256':digest(p)} for p in sorted(directory.iterdir())]
    (directory/'manifest.json').write_text(json.dumps({'schema_version':'1.0.0','milestone_id':'M29','captured_at':now.isoformat().replace('+00:00','Z'),'git_revision':revision,'dirty_worktree':False,'configuration_fingerprint':fingerprint,'exit_code':0,'artifacts':artifacts}))
    return directory

def verify(path): return subprocess.run(['bash',str(VERIFY),str(path)],cwd=ROOT,text=True,capture_output=True)

def refresh_manifest(path, changed):
    manifest=json.loads((path/'manifest.json').read_text())
    for artifact in manifest['artifacts']:
        if artifact['path'] in changed: artifact['sha256']=digest(path/artifact['path'])
    (path/'manifest.json').write_text(json.dumps(manifest))

def test_m29_refuses_unsupported_stateless_recovery_closeout():
    with tempfile.TemporaryDirectory(prefix='pytest-m29-holder-'):
        path=bundle()
        try:
            result=verify(path); assert result.returncode != 0; assert 'FOREX_M29_OBSERVATION_CAPTURED_UNSUPPORTED' in result.stderr
        finally: __import__('shutil').rmtree(path)

@pytest.mark.parametrize('mutation, message',[('wrong_server','wrong server or symbol'),('future_tick','future tick refused'),('stale_tick','stale or invalid response tick'),('raw_binding','raw-envelope binding mismatch'),('path_escape','artifact path invalid'),('bad_fingerprint','current configuration mismatch')])
def test_m29_rejects_invalid_or_unbound_evidence_before_closeout(mutation,message):
    path=bundle()
    try:
        manifest=json.loads((path/'manifest.json').read_text())
        if mutation in {'wrong_server','future_tick','stale_tick'}:
            raw=json.loads((path/'recovery-response.json').read_text()); tick=json.loads(raw['result']['stdout'])
            if mutation=='wrong_server': tick['server']='GOMarketsMU-Live'
            if mutation=='future_tick': tick['tick_time_msc'] += 60000
            if mutation=='stale_tick': tick['tick_time_msc'] -= 60000
            raw['result']['stdout']=json.dumps(tick); (path/'recovery-response.json').write_text(json.dumps(raw)); refresh_manifest(path,{'recovery-response.json'})
        elif mutation=='raw_binding':
            proof=json.loads((path/'recovery-proof.json').read_text()); proof['raw_envelopes']['recovery_response_sha256']='0'*64; (path/'recovery-proof.json').write_text(json.dumps(proof)); refresh_manifest(path,{'recovery-proof.json'})
        elif mutation=='path_escape': manifest['artifacts'][0]['path']='../outside.txt'; (path/'manifest.json').write_text(json.dumps(manifest))
        else: manifest['configuration_fingerprint']='sha256:'+'0'*64; (path/'manifest.json').write_text(json.dumps(manifest))
        result=verify(path); assert result.returncode != 0; assert message in result.stderr
    finally: __import__('shutil').rmtree(path)

def test_m29_capture_refuses_overwrite_and_documents_unsupported_claims():
    capture=(ROOT/'scripts/capture_m29_evidence.sh').read_text(); proof=(ROOT/'docs/milestones/M29-proof.md').read_text()
    assert 'Refusing to overwrite evidence bundle' in capture
    assert 'closeout intentionally refused' in capture
    assert 'collector restart' in proof
