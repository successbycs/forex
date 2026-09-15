import hashlib,json,subprocess,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]; V=ROOT/'scripts/verify_m29_evidence.sh'
def h(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def test_lean_m29_verifier_accepts_held_flat_recovery_and_refuses_tamper():
 p=Path(tempfile.mkdtemp(dir=ROOT/'runs/evidence/M29')); rev=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(); fp=json.loads(subprocess.check_output(['python3','scripts/forex_milestones.py','status','--json'],cwd=ROOT,text=True))['configuration_fingerprint']; account={'server':'GOMarketsMU-Demo','currency':'AUD','position_observation':'AVAILABLE','open_positions':0}
 def e(op,x,n): return {'operation':op,'ok':True,'result':{'ok':True,'exit_code':0,'started_at':f'2026-09-15T00:00:0{n}+00:00','finished_at':f'2026-09-15T00:00:0{n+1}+00:00','stdout':json.dumps(x)}}
 deployment={'application_revision':rev,'configuration_fingerprint':fp}
 data={'m29-continuity.json':e('m20_listener_continuity_status',{'observation':'AVAILABLE','record':{'state':'PASS','release_id':'release-1','handoff':{'state':'RECOVERED'},'baseline':{'account':account,'deployment':deployment},'postflight':{'deployment':deployment}}},0),'postflight-listener.json':e('m20_listener_status',{'running':True,'state':'MAINTENANCE_HOLD','release_id':'release-1','protection_observation':'LAST_KNOWN_UNVERIFIED'},2),'postflight-account.json':e('m20_demo_account_liquidity',account,4),'postflight-diagnostics.json':e('m20_listener_diagnostics',{'maintenance_hold_present':True,'logon_type':'S4U','deployment_binding':{'observation':'VALID','application_revision':rev,'configuration_fingerprint':fp}},6)}
 try:
  for n,x in data.items(): (p/n).write_text(json.dumps(x))
  for n,x in {'tests.txt':'ok','governance.txt':'ok','revision.txt':rev,'summary.txt':'FOREX_M29_PROOF_OK'}.items(): (p/n).write_text(x)
  a=[{'path':x.name,'sha256':h(x)} for x in sorted(p.iterdir())]; (p/'manifest.json').write_text(json.dumps({'milestone_id':'M29','git_revision':rev,'dirty_worktree':False,'configuration_fingerprint':fp,'artifacts':a}))
  assert subprocess.run(['bash',str(V),str(p)],cwd=ROOT).returncode==0
  data['postflight-diagnostics.json']['result']['stdout']=json.dumps({'maintenance_hold_present':True,'logon_type':'S4U','deployment_binding':{'observation':'VALID','application_revision':'different','configuration_fingerprint':fp}}); (p/'postflight-diagnostics.json').write_text(json.dumps(data['postflight-diagnostics.json']))
  a=[{'path':x.name,'sha256':h(x)} for x in sorted(p.iterdir()) if x.name!='manifest.json']; (p/'manifest.json').write_text(json.dumps({'milestone_id':'M29','git_revision':rev,'dirty_worktree':False,'configuration_fingerprint':fp,'artifacts':a}))
  assert subprocess.run(['bash',str(V),str(p)],cwd=ROOT).returncode!=0
  data['postflight-diagnostics.json']['result']['stdout']=json.dumps({'maintenance_hold_present':True,'logon_type':'S4U','deployment_binding':{'observation':'VALID','application_revision':rev,'configuration_fingerprint':fp}}); (p/'postflight-diagnostics.json').write_text(json.dumps(data['postflight-diagnostics.json']))
  data['postflight-listener.json']['result']['stdout']=json.dumps({'running':True,'state':'MAINTENANCE_HOLD','release_id':'release-1','protection_observation':'OBSERVED_ACTIVE'}); (p/'postflight-listener.json').write_text(json.dumps(data['postflight-listener.json']))
  a=[{'path':x.name,'sha256':h(x)} for x in sorted(p.iterdir()) if x.name!='manifest.json']; (p/'manifest.json').write_text(json.dumps({'milestone_id':'M29','git_revision':rev,'dirty_worktree':False,'configuration_fingerprint':fp,'artifacts':a}))
  assert subprocess.run(['bash',str(V),str(p)],cwd=ROOT).returncode!=0
  data['m29-continuity.json']['result']['stdout']=json.dumps({'observation':'AVAILABLE','record':{'state':'PASS','release_id':'release-1','handoff':{'state':'RECOVERED'},'baseline':{'account':account,'deployment':{**deployment,'application_revision':'different'}},'postflight':{'deployment':deployment}}}); (p/'m29-continuity.json').write_text(json.dumps(data['m29-continuity.json']))
  a=[{'path':x.name,'sha256':h(x)} for x in sorted(p.iterdir()) if x.name!='manifest.json']; (p/'manifest.json').write_text(json.dumps({'milestone_id':'M29','git_revision':rev,'dirty_worktree':False,'configuration_fingerprint':fp,'artifacts':a}))
  assert subprocess.run(['bash',str(V),str(p)],cwd=ROOT).returncode!=0
  (p/'summary.txt').write_text('bad'); assert subprocess.run(['bash',str(V),str(p)],cwd=ROOT).returncode!=0
 finally: __import__('shutil').rmtree(p)
def test_lean_m29_docs_are_explicit():
 assert 'FOREX_M29_PROOF_OK' in (ROOT/'scripts/capture_m29_evidence.sh').read_text()
 assert 'outside the MVP M29 contract' in (ROOT/'docs/milestones/M29-proof.md').read_text()
