#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
python3 - "$root" "$1" <<'PY'
import hashlib,json,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
r,b=Path(sys.argv[1]),Path(sys.argv[2]).resolve(); m=json.loads((b/'manifest.json').read_text()); assert b.is_relative_to(r/'runs/evidence/M27') and m['milestone_id']=='M27' and not m['dirty_worktree']; assert m['git_revision']==subprocess.check_output(['git','rev-parse','HEAD'],cwd=r,text=True).strip(); assert (datetime.now(timezone.utc)-datetime.fromisoformat(m['captured_at'].replace('Z','+00:00'))).total_seconds()<24*3600
for a in m['artifacts']:
 p=b/a['path']; assert p.is_file() and hashlib.sha256(p.read_bytes()).hexdigest()==a['sha256']
t=json.loads((b/'tick-proof.json').read_text()); assert t['server']=='GOMarketsMU-Demo' and t['symbol']=='EURUSD' and 0<=t['age_seconds']<=15 and t['listener_state'] not in {'STALE','STOPPED','STARTUP_FAILED'}; print('FOREX_M27_EVIDENCE_VERIFIED')
PY
