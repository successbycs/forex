#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
python3 - "$root" "$1" <<'PY'
import hashlib,json,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
r,b=Path(sys.argv[1]),Path(sys.argv[2]).resolve(); m=json.loads((b/'manifest.json').read_text())
assert b.is_relative_to(r/'runs/evidence/M10') and m['milestone_id']=='M10' and m['dirty_worktree'] is False and m['git_revision']==subprocess.check_output(['git','rev-parse','HEAD'],cwd=r,text=True).strip()
assert (datetime.now(timezone.utc)-datetime.fromisoformat(m['captured_at'].replace('Z','+00:00'))).total_seconds()<168*3600
for a in m['artifacts']: p=b/a['path']; assert p.is_file() and hashlib.sha256(p.read_bytes()).hexdigest()==a['sha256']
e=json.loads((b/'events.json').read_text()); assert e['us_events'] and e['eur_events']; assert all(x['time_precision']=='DATE_ONLY' for x in e['us_events']); assert all(x['time_precision']=='CET_SCHEDULED_TIME' for x in e['eur_events']); print('FOREX_M10_EVIDENCE_VERIFIED')
PY
