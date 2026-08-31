#!/usr/bin/env bash
set -euo pipefail
python3 - "$1" <<'PY'
import hashlib,json,sys
from pathlib import Path
b=Path(sys.argv[1]); m=json.loads((b/'manifest.json').read_text())
assert m['milestone_id']=='M3'
for x in m['artifacts']:
 p=b/x['path']; assert p.is_file() and hashlib.sha256(p.read_bytes()).hexdigest()==x['sha256']
p=json.loads(json.loads((b/'probe.json').read_text())['result']['stdout']); assert p['server']=='GOMarketsMU-Demo' and p['returned_closed_bars']>=19000 and p['invalid_ohlc_count']==0
assert 'FOREX_M3_PROOF_OK' in (b/'summary.txt').read_text(); print('FOREX_M3_EVIDENCE_VERIFIED')
PY
