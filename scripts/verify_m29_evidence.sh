#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
python3 - "$root" "$1" <<'PY'
import hashlib,json,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
r,b=Path(sys.argv[1]),Path(sys.argv[2]).resolve()
def require(value,message):
 if not value: raise RuntimeError(message)
m=json.loads((b/'manifest.json').read_text())
require(b.is_relative_to(r/'runs/evidence/M29'),'bundle location invalid')
require(m['milestone_id']=='M29' and not m['dirty_worktree'],'manifest identity invalid')
require(m['git_revision']==subprocess.check_output(['git','rev-parse','HEAD'],cwd=r,text=True).strip(),'revision mismatch')
require((datetime.now(timezone.utc)-datetime.fromisoformat(m['captured_at'].replace('Z','+00:00'))).total_seconds() < 24*3600,'evidence stale')
for a in m['artifacts']:
 p=b/a['path']; require(p.is_file() and hashlib.sha256(p.read_bytes()).hexdigest()==a['sha256'],'artifact hash mismatch')
proof=json.loads((b/'recovery-proof.json').read_text())
require(proof['request_identity']=='m27_demo_tick:GOMarketsMU-Demo:EURUSD','unexpected operation')
require(proof['interruption']=={'state':'INTERRUPTED_CLIENT_SIDE','exit_code':124,'remote_mutation':'STRUCTURALLY_DISABLED','note':'The timeout terminates only the local adapter client before response processing.'},'interruption not bounded')
for name in ('pre_interruption','recovery'):
 t=proof[name]; require(t['operation']=='m27_demo_tick' and t['server']=='GOMarketsMU-Demo' and t['symbol']=='EURUSD' and t['bid']>0 and t['ask']>=t['bid'] and 0<=t['tick_age_seconds']<=15 and t['order_submission']=='STRUCTURALLY_DISABLED',name+' tick invalid')
require(proof['idempotency']=='REPEATED_FIXED_READ_ONLY_REQUEST_NO_PERSISTENT_MUTATION','idempotency declaration invalid')
require((b/'summary.txt').read_text().strip()=='FOREX_M29_PROOF_OK','proof marker absent')
print('FOREX_M29_EVIDENCE_VERIFIED')
PY
