#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"; cd "$root"; export PYTHONPATH="$root/src${PYTHONPATH:+:$PYTHONPATH}"
bundle="${1:-runs/evidence/M28/$(date -u +%Y%m%dT%H%M%SZ)}"; mkdir -p "$bundle"; git diff --quiet
python3 -m pytest -q tests/milestones/test_m28.py >"$bundle/tests.txt" 2>&1; python3 scripts/forex_milestones.py validate >"$bundle/governance.txt" 2>&1; python3 scripts/t480_adapter.py execute --operation m27_demo_tick >"$bundle/tick-response.json"
python3 - "$bundle" <<'PY'
import json,sys,yaml
from datetime import datetime,timezone
from pathlib import Path
b=Path(sys.argv[1]); o=json.loads((b/'tick-response.json').read_text()); t=json.loads(o['result']['stdout']); risk=yaml.safe_load(open('config/risk.yaml')); point=.00001; spread=(t['ask']-t['bid'])/point; tick_at=datetime.fromtimestamp(t['tick_time_msc']/1000-t['broker_timestamp_offset_seconds'],timezone.utc); age=(datetime.now(timezone.utc)-tick_at).total_seconds(); assert o['operation']=='m27_demo_tick' and o['ok'] and t['ok'] and t['server']=='GOMarketsMU-Demo' and t['symbol']=='EURUSD' and 0<=age<=15; limit=float(risk['maximum_spread_points']); disposition='ACCEPTED_FOR_SIMULATED_INTENT_ONLY' if spread<=limit else 'SPREAD_LIMIT'; (b/'market-conditions.json').write_text(json.dumps({'server':t['server'],'symbol':t['symbol'],'bid':t['bid'],'ask':t['ask'],'spread_points':spread,'maximum_spread_points':limit,'tick_age_seconds':age,'market_condition':disposition,'order_submission':'STRUCTURALLY_DISABLED'},indent=2)+'\n')
PY
git rev-parse HEAD >"$bundle/revision.txt"
python3 - "$bundle" <<'PY'
import hashlib,json,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
b=Path(sys.argv[1]);s=json.loads(subprocess.check_output(['python3','scripts/forex_milestones.py','status','--json']));(b/'summary.txt').write_text('FOREX_M28_PROOF_OK\n');a=[{'path':p.name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(b.iterdir()) if p.is_file()];m={'schema_version':'1.0.0','milestone_id':'M28','captured_at':datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),'git_revision':(b/'revision.txt').read_text().strip(),'dirty_worktree':False,'configuration_fingerprint':s['configuration_fingerprint'],'surface':'real-time GOMarketsMU-Demo tick, spread, and broker-condition collection path','operation':'fixed read-only Demo tick with configured spread guard','expected_result':'fresh Demo tick and bounded spread disposition','observed_result':'FOREX_M28_PROOF_OK','exit_code':0,'redactions':['No credentials, account values, orders, or positions retained.'],'summary':'FOREX_M28_PROOF_OK','artifacts':a};(b/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
PY
echo "$bundle"
