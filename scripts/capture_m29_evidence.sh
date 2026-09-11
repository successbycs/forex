#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"; cd "$root"; export PYTHONPATH="$root/src${PYTHONPATH:+:$PYTHONPATH}"
bundle="${1:-runs/evidence/M29/$(date -u +%Y%m%dT%H%M%SZ)}"; mkdir -p "$bundle"; git diff --quiet
python3 -m pytest -q tests/milestones/test_m29.py >"$bundle/tests.txt" 2>&1
python3 scripts/forex_milestones.py validate >"$bundle/governance.txt" 2>&1
python3 scripts/t480_adapter.py execute --operation m27_demo_tick >"$bundle/pre-interruption-response.json"
set +e
timeout 0.001s python3 scripts/t480_adapter.py execute --operation m27_demo_tick >"$bundle/interrupted-client-attempt.txt" 2>&1
interrupted_exit=$?
set -e
if [ "$interrupted_exit" -ne 124 ]; then echo "Expected client timeout, got $interrupted_exit" >&2; exit 1; fi
python3 scripts/t480_adapter.py execute --operation m27_demo_tick >"$bundle/recovery-response.json"
python3 - "$bundle" <<'PY'
import json,sys
from datetime import datetime,timezone
from pathlib import Path
b=Path(sys.argv[1])
def tick(name):
 o=json.loads((b/name).read_text()); t=json.loads(o['result']['stdout']); at=datetime.fromtimestamp(t['tick_time_msc']/1000-t['broker_timestamp_offset_seconds'],timezone.utc); age=(datetime.now(timezone.utc)-at).total_seconds()
 if not (o['operation']=='m27_demo_tick' and o['ok'] and o['approval_required'] is False and o['approved'] is False and o['result']['exit_code']==0 and t['ok'] and t['server']=='GOMarketsMU-Demo' and t['symbol']=='EURUSD' and t['bid']>0 and t['ask']>=t['bid'] and 0<=age<=15): raise RuntimeError('fresh fixed Demo tick required')
 return {'operation':o['operation'],'server':t['server'],'symbol':t['symbol'],'bid':t['bid'],'ask':t['ask'],'tick_time_msc':t['tick_time_msc'],'broker_timestamp_offset_seconds':t['broker_timestamp_offset_seconds'],'tick_age_seconds':age,'order_submission':'STRUCTURALLY_DISABLED'}
pre=tick('pre-interruption-response.json'); recovered=tick('recovery-response.json')
(b/'recovery-proof.json').write_text(json.dumps({'workflow':'read-only collection -> interrupted client -> fresh retry','request_identity':'m27_demo_tick:GOMarketsMU-Demo:EURUSD','pre_interruption':pre,'interruption':{'state':'INTERRUPTED_CLIENT_SIDE','exit_code':124,'remote_mutation':'STRUCTURALLY_DISABLED','note':'The timeout terminates only the local adapter client before response processing.'},'recovery':recovered,'idempotency':'REPEATED_FIXED_READ_ONLY_REQUEST_NO_PERSISTENT_MUTATION'},indent=2)+'\n')
PY
git rev-parse HEAD >"$bundle/revision.txt"
python3 - "$bundle" <<'PY'
import hashlib,json,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
b=Path(sys.argv[1]); s=json.loads(subprocess.check_output(['python3','scripts/forex_milestones.py','status','--json'])); (b/'summary.txt').write_text('FOREX_M29_PROOF_OK\n')
a=[{'path':p.name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(b.iterdir()) if p.is_file()]
m={'schema_version':'1.0.0','milestone_id':'M29','captured_at':datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),'git_revision':(b/'revision.txt').read_text().strip(),'dirty_worktree':False,'configuration_fingerprint':s['configuration_fingerprint'],'surface':'real-time GOMarketsMU-Demo read-only EURUSD collection and client-interruption recovery workflow','operation':'fixed m27_demo_tick before and after a bounded client timeout','expected_result':'fresh Demo collection recovers after interrupted client without an order or persistent mutation','observed_result':'FOREX_M29_PROOF_OK','exit_code':0,'redactions':['No credentials, account values, orders, positions, or endpoint details retained.'],'summary':'FOREX_M29_PROOF_OK','artifacts':a}; (b/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
PY
echo "$bundle"
