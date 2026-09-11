#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
python3 - "$root" "$1" <<'PY'
import hashlib,json,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
r,b=Path(sys.argv[1]),Path(sys.argv[2]).resolve(); m=json.loads((b/'manifest.json').read_text()); assert b.is_relative_to(r/'runs/evidence/M26') and m['milestone_id']=='M26' and not m['dirty_worktree']; assert m['git_revision']==subprocess.check_output(['git','rev-parse','HEAD'],cwd=r,text=True).strip(); assert (datetime.now(timezone.utc)-datetime.fromisoformat(m['captured_at'].replace('Z','+00:00'))).total_seconds()<168*3600
for a in m['artifacts']:
 p=b/a['path']; assert p.is_file() and hashlib.sha256(p.read_bytes()).hexdigest()==a['sha256']
d=json.loads((b/'revalidation-drill.json').read_text())['results']; assert d['valid']['outcome']=='REVALIDATED_SIMULATION' and d['stale']['reasons']==['QUOTE_NOT_FRESH'] and d['spread']['reasons']==['SPREAD_LIMIT'] and d['market']['reasons']==['MARKET_STATE_CHANGED'] and d['expired']['reasons']==['APPROVAL_EXPIRED']; print('FOREX_M26_EVIDENCE_VERIFIED')
PY
