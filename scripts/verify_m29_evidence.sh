#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"; export PYTHONPATH="$root/src${PYTHONPATH:+:$PYTHONPATH}"
python3 - "$root" "$1" <<'PY'
import hashlib,json,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
from forex.milestones import configuration_fingerprint
root,b=Path(sys.argv[1]).resolve(),Path(sys.argv[2]).resolve()
def q(x,m):
 if not x: raise RuntimeError(m)
def o(n,op):
 x=json.loads((b/n).read_text()); q(x.get('operation')==op and x.get('ok') is True,'invalid '+n); r=x.get('result',{}); q(r.get('ok') is True and r.get('exit_code')==0,'failed '+n); return json.loads(r['stdout'])
m=json.loads((b/'manifest.json').read_text()); need={'tests.txt','governance.txt','m29-continuity.json','postflight-listener.json','postflight-account.json','postflight-diagnostics.json','revision.txt','summary.txt'}; q(m.get('milestone_id')=='M29' and m.get('git_revision')==subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),'revision mismatch'); q(m.get('configuration_fingerprint')==configuration_fingerprint(root,json.loads((root/'project_state.json').read_text())),'configuration mismatch'); q({x['path'] for x in m['artifacts']}==need,'artifact set invalid'); q((b/'summary.txt').read_text().strip()=='FOREX_M29_PROOF_OK','marker absent')
for x in m['artifacts']: q(hashlib.sha256((b/x['path']).read_bytes()).hexdigest()==x['sha256'],'artifact hash mismatch')
c=o('m29-continuity.json','m20_listener_continuity_status'); r=c.get('record',{}); q(c.get('observation')=='AVAILABLE' and r.get('state')=='PASS' and r.get('handoff',{}).get('state')=='RECOVERED','recovery did not pass'); a=r.get('baseline',{}).get('account',{}); q(a.get('server')=='GOMarketsMU-Demo' and a.get('currency')=='AUD' and a.get('open_positions')==0,'baseline not flat Demo')
l=o('postflight-listener.json','m20_listener_status'); q(l.get('running') is True and l.get('state')=='MAINTENANCE_HOLD','listener not held'); a=o('postflight-account.json','m20_demo_account_liquidity'); q(a.get('server')=='GOMarketsMU-Demo' and a.get('currency')=='AUD' and a.get('open_positions')==0,'postflight not flat Demo'); d=o('postflight-diagnostics.json','m20_listener_diagnostics'); q(d.get('maintenance_hold_present') is True and d.get('logon_type')=='S4U' and d.get('deployment_binding',{}).get('application_revision')==m['git_revision'],'binding invalid'); print('FOREX_M29_PROOF_OK')
PY
