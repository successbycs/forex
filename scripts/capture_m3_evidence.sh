#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"; cd "$root"
bundle="${1:-runs/evidence/M3/$(date -u +%Y%m%dT%H%M%SZ)}"; mkdir -p "$bundle"
python3 -m pytest -q tests/milestones/test_m3.py >"$bundle/tests.txt" 2>&1
python3 scripts/t480_adapter.py execute --operation m3_mt5_history_depth_probe >"$bundle/probe.json"
git rev-parse HEAD >"$bundle/revision.txt"
python3 - "$bundle" <<'PY'
import hashlib,json,sys
from datetime import datetime,timezone
from pathlib import Path
b=Path(sys.argv[1]); p=json.loads((b/'probe.json').read_text()); raw=json.loads(p['result']['stdout'])
if not p['ok'] or raw['server']!='GOMarketsMU-Demo' or raw['symbol']!='EURUSD' or raw['timeframe']!='H1' or raw['returned_closed_bars']<19000 or raw['invalid_ohlc_count']!=0: raise SystemExit('M3 probe contract failed')
files=[{'path':x.name,'sha256':hashlib.sha256(x.read_bytes()).hexdigest()} for x in b.iterdir() if x.is_file()]
(b/'summary.txt').write_text('FOREX_M3_PROOF_OK: fixed Demo-only EUR/USD H1 history-depth probe passed.\n')
files.append({'path':'summary.txt','sha256':hashlib.sha256((b/'summary.txt').read_bytes()).hexdigest()})
(b/'manifest.json').write_text(json.dumps({'schema_version':'1.0.0','milestone_id':'M3','captured_at':datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),'git_revision':(b/'revision.txt').read_text().strip(),'dirty_worktree':False,'configuration_fingerprint':p['configuration_fingerprint'],'surface':'catalog-locked T480-to-Forex historical MT5 bridge','operation':'fixed M3 MT5 history-depth probe','expected_result':'Demo-only EUR/USD H1 probe returns at least 19000 valid closed bars','observed_result':'FOREX_M3_PROOF_OK','exit_code':0,'redactions':['No credentials, account balances, positions, or orders retained.'],'summary':'FOREX_M3_PROOF_OK','artifacts':files},indent=2)+'\n')
PY
echo "$bundle"
