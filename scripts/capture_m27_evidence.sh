#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"; cd "$root"; export PYTHONPATH="$root/src${PYTHONPATH:+:$PYTHONPATH}"
bundle="${1:-runs/evidence/M27/$(date -u +%Y%m%dT%H%M%SZ)}"; mkdir -p "$bundle"; git diff --quiet
python3 -m pytest -q tests/milestones/test_m27.py >"$bundle/tests.txt" 2>&1; python3 scripts/forex_milestones.py validate >"$bundle/governance.txt" 2>&1; python3 scripts/t480_adapter.py execute --operation m20_listener_status >"$bundle/listener-status.json"
python3 - "$bundle" <<'PY'
import json,sys
from datetime import datetime,timezone
from pathlib import Path
b=Path(sys.argv[1]); outer=json.loads((b/'listener-status.json').read_text()); state=json.loads(outer['result']['stdout']); result=state['last_result']; captured=datetime.fromisoformat(result['captured_at_utc'].replace('Z','+00:00')); age=(datetime.now(timezone.utc)-captured).total_seconds(); assert state['running'] and state['state'] not in {'STALE','STOPPED','STARTUP_FAILED'} and result['server']=='GOMarketsMU-Demo' and result['symbol']=='EURUSD' and 0<=age<=15; (b/'tick-proof.json').write_text(json.dumps({'server':result['server'],'symbol':result['symbol'],'assessment_captured_at_utc':result['captured_at_utc'],'age_seconds':age,'listener_state':state['state']},indent=2)+'\n')
PY
git rev-parse HEAD >"$bundle/revision.txt"
python3 - "$bundle" <<'PY'
import hashlib,json,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
b=Path(sys.argv[1]); s=json.loads(subprocess.check_output(['python3','scripts/forex_milestones.py','status','--json'])); (b/'summary.txt').write_text('FOREX_M27_PROOF_OK\n'); a=[{'path':p.name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(b.iterdir()) if p.is_file()]; m={'schema_version':'1.0.0','milestone_id':'M27','captured_at':datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),'git_revision':(b/'revision.txt').read_text().strip(),'dirty_worktree':False,'configuration_fingerprint':s['configuration_fingerprint'],'surface':'installed Windows MT5 terminal on GOMarketsMU-Demo with a fresh EUR/USD tick','operation':'fixed read-only listener status','expected_result':'fresh Demo EURUSD assessment','observed_result':'FOREX_M27_PROOF_OK','exit_code':0,'redactions':['No credentials or account balances retained. The fixed raw listener status retains read-only position-protection identifiers and prices; it contains no order-control surface.'],'summary':'FOREX_M27_PROOF_OK','artifacts':a}; (b/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
PY
echo "$bundle"
