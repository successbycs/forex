#!/usr/bin/env bash
set -euo pipefail
python3 - "$1" <<'PY'
import hashlib,json,sys
from pathlib import Path
b=Path(sys.argv[1]); m=json.load(open(b/'manifest.json')); assert m['milestone_id']=='M5' and m['exit_code']==0
for x in m['artifacts']: assert hashlib.sha256((b/x['path']).read_bytes()).hexdigest()==x['sha256']
assert 'FOREX_M2_IMPORT_ALREADY_PRESENT' in (b/'reimport.json').read_text()
assert 'FOREX_M2_POSTGRES_VERIFY_OK' in (b/'verify.json').read_text()
assert 'FOREX_M5_PROOF_OK' in (b/'summary.txt').read_text(); print('FOREX_M5_EVIDENCE_VERIFIED')
PY
