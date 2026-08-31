#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
python3 - "$root" "$1" <<'PY'
import base64,gzip,hashlib,json,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
root,b=Path(sys.argv[1]),Path(sys.argv[2]).resolve(); m=json.loads((b/'manifest.json').read_text())
if not b.is_relative_to(root/'runs'/'evidence'/'M6') or m.get('milestone_id')!='M6' or m.get('exit_code')!=0 or m.get('dirty_worktree') is not False: raise SystemExit('M6 manifest invalid')
if m.get('git_revision')!=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(): raise SystemExit('M6 revision mismatch')
if (datetime.now(timezone.utc)-datetime.fromisoformat(m['captured_at'].replace('Z','+00:00'))).total_seconds()>168*3600: raise SystemExit('M6 evidence stale')
for artifact in m['artifacts']:
 p=b/artifact['path']; assert p.is_file() and hashlib.sha256(p.read_bytes()).hexdigest()==artifact['sha256']
p=json.loads((b/'probe.json').read_text()); raw=json.loads(p['result']['stdout']); assert p['ok'] and raw['server']=='GOMarketsMU-Demo' and raw['symbol']=='EURUSD'
assert {x['timeframe']:x['closed_bar_count'] for x in raw['datasets']}=={'M15':720,'H1':720,'D1':365}
for dataset in raw['datasets']:
 rows=json.loads(gzip.decompress(base64.b64decode(dataset['bars_payload']))); assert len(rows)==dataset['closed_bar_count']
 assert hashlib.sha256(json.dumps(rows,sort_keys=True,separators=(',',':')).encode()).hexdigest()==dataset['bars_sha256']
 assert dataset['quality_label']=='CLOSED_OHLC_VALIDATED' and rows[-1]['time_utc'] < dataset['capture_cutoff_utc']
assert 'FOREX_M6_PROOF_OK' in (b/'summary.txt').read_text(); print('FOREX_M6_EVIDENCE_VERIFIED')
PY
