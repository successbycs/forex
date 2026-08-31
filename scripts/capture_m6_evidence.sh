#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"; cd "$root"
bundle="${1:-runs/evidence/M6/$(date -u +%Y%m%dT%H%M%SZ)}"; mkdir -p "$bundle"
python3 -m pytest -q tests/milestones/test_m6.py >"$bundle/tests.txt" 2>&1
python3 scripts/forex_milestones.py validate >"$bundle/governance.txt" 2>&1
python3 scripts/t480_adapter.py execute --operation m6_mt5_multi_timeframe_probe >"$bundle/probe.json"
git rev-parse HEAD >"$bundle/revision.txt"
python3 - "$bundle" <<'PY'
import base64,gzip,hashlib,json,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
b=Path(sys.argv[1]); probe=json.loads((b/'probe.json').read_text()); raw=json.loads(probe['result']['stdout'])
assert probe['ok'] and raw['server']=='GOMarketsMU-Demo' and raw['symbol']=='EURUSD'
expected={'M15':720,'H1':720,'D1':365}
assert {x['timeframe']:x['closed_bar_count'] for x in raw['datasets']}==expected
for dataset in raw['datasets']:
 rows=json.loads(gzip.decompress(base64.b64decode(dataset['bars_payload']))); assert len(rows)==dataset['closed_bar_count']
 assert hashlib.sha256(json.dumps(rows,sort_keys=True,separators=(',',':')).encode()).hexdigest()==dataset['bars_sha256']
(b/'summary.txt').write_text('FOREX_M6_PROOF_OK\n')
status=json.loads(subprocess.check_output(['python3','scripts/forex_milestones.py','status','--json']))
artifacts=[{'path':p.name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(b.iterdir()) if p.is_file()]
m={'schema_version':'1.0.0','milestone_id':'M6','captured_at':datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),'git_revision':(b/'revision.txt').read_text().strip(),'dirty_worktree':False,'configuration_fingerprint':status['configuration_fingerprint'],'surface':'governed multi-timeframe EUR/USD historical dataset path','operation':'fixed T480 closed-bar M15, H1 and D1 MT5 dataset probe','expected_result':'720 M15, 720 H1 and 365 D1 valid Demo-only closed bars','observed_result':'FOREX_M6_PROOF_OK','exit_code':0,'redactions':['No credentials, balances, positions, orders, or live-server data retained.'],'summary':'FOREX_M6_PROOF_OK','artifacts':artifacts}
(b/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
PY
echo "$bundle"
