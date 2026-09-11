#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
python3 - "$root" "$1" <<'PY'
import hashlib,json,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
r,b=Path(sys.argv[1]),Path(sys.argv[2]).resolve(); m=json.loads((b/'manifest.json').read_text()); assert b.is_relative_to(r/'runs/evidence/M24') and m['milestone_id']=='M24' and not m['dirty_worktree']; assert m['git_revision']==subprocess.check_output(['git','rev-parse','HEAD'],cwd=r,text=True).strip(); assert (datetime.now(timezone.utc)-datetime.fromisoformat(m['captured_at'].replace('Z','+00:00'))).total_seconds()<168*3600
for a in m['artifacts']:
 p=b/a['path']; assert p.is_file() and hashlib.sha256(p.read_bytes()).hexdigest()==a['sha256']
d=json.loads((b/'intent-drill.json').read_text()); x={v['intent_id']:v for v in d['results']}; assert d['marker']=='FOREX_M24_INTENT_DRILL_OK' and x['buy']['action']=='BUY' and x['sell']['action']=='SELL' and x['no-trade']['action']=='NO_TRADE' and x['risk-refused']['action']=='NO_TRADE'; print('FOREX_M24_EVIDENCE_VERIFIED')
PY
