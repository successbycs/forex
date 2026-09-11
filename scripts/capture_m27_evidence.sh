#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"; cd "$root"; export PYTHONPATH="$root/src${PYTHONPATH:+:$PYTHONPATH}"
bundle="${1:-runs/evidence/M27/$(date -u +%Y%m%dT%H%M%SZ)}"; mkdir -p "$bundle"; git diff --quiet
python3 -m pytest -q tests/milestones/test_m27.py >"$bundle/tests.txt" 2>&1; python3 scripts/forex_milestones.py validate >"$bundle/governance.txt" 2>&1; python3 scripts/t480_adapter.py execute --operation m27_demo_tick >"$bundle/tick-response.json"
python3 - "$bundle" <<'PY'
import json,sys
from datetime import datetime,timezone
from pathlib import Path
b=Path(sys.argv[1]); outer=json.loads((b/'tick-response.json').read_text()); tick=json.loads(outer['result']['stdout']); captured=datetime.fromisoformat(tick['captured_at_utc'].replace('Z','+00:00')); tick_at=datetime.fromtimestamp(tick['tick_time_msc']/1000,timezone.utc); age=(datetime.now(timezone.utc)-tick_at).total_seconds(); assert outer['operation']=='m27_demo_tick' and outer['approval_required'] is False and outer['approved'] is False and outer['result']['exit_code']==0 and outer['result']['ok'] and tick['ok'] and tick['server']=='GOMarketsMU-Demo' and tick['symbol']=='EURUSD' and tick['bid']>0 and tick['ask']>=tick['bid'] and 0<=age<=15 and 0<=(captured-tick_at).total_seconds()<=15; (b/'tick-proof.json').write_text(json.dumps({'operation':outer['operation'],'server':tick['server'],'symbol':tick['symbol'],'bid':tick['bid'],'ask':tick['ask'],'tick_time_msc':tick['tick_time_msc'],'tick_captured_at_utc':tick['captured_at_utc'],'tick_age_seconds':age},indent=2)+'\n')
PY
git rev-parse HEAD >"$bundle/revision.txt"
python3 - "$bundle" <<'PY'
import hashlib,json,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
b=Path(sys.argv[1]); s=json.loads(subprocess.check_output(['python3','scripts/forex_milestones.py','status','--json'])); (b/'summary.txt').write_text('FOREX_M27_PROOF_OK\n'); a=[{'path':p.name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(b.iterdir()) if p.is_file()]; m={'schema_version':'1.0.0','milestone_id':'M27','captured_at':datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),'git_revision':(b/'revision.txt').read_text().strip(),'dirty_worktree':False,'configuration_fingerprint':s['configuration_fingerprint'],'surface':'installed Windows MT5 terminal on GOMarketsMU-Demo with a fresh EUR/USD tick','operation':'fixed read-only M27 Demo tick','expected_result':'fresh Demo EURUSD bid/ask tick','observed_result':'FOREX_M27_PROOF_OK','exit_code':0,'redactions':['No credentials, account values, orders, or positions retained. The fixed raw tick response contains only Demo server identity, EURUSD bid/ask, and timestamps.'],'summary':'FOREX_M27_PROOF_OK','artifacts':a}; (b/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
PY
echo "$bundle"
