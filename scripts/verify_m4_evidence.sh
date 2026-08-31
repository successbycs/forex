#!/usr/bin/env bash
set -euo pipefail
python3 - "$1" <<'PY'
import json,hashlib,sys
from pathlib import Path
b=Path(sys.argv[1]); m=json.load(open(b/'manifest.json')); assert m['milestone_id']=='M4' and m['exit_code']==0
for x in m['artifacts']: assert hashlib.sha256((b/x['path']).read_bytes()).hexdigest()==x['sha256']
assert (b/'application.txt').read_text().strip()=='1'; print('FOREX_M4_EVIDENCE_VERIFIED')
PY
