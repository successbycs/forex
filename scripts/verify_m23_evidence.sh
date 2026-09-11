#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
python3 - "$root" "$1" <<'PY'
import hashlib,json,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
r,b=Path(sys.argv[1]),Path(sys.argv[2]).resolve(); m=json.loads((b/'manifest.json').read_text()); assert b.is_relative_to(r/'runs/evidence/M23') and m['milestone_id']=='M23' and not m['dirty_worktree']; assert m['git_revision']==subprocess.check_output(['git','rev-parse','HEAD'],cwd=r,text=True).strip(); assert (datetime.now(timezone.utc)-datetime.fromisoformat(m['captured_at'].replace('Z','+00:00'))).total_seconds()<168*3600
for a in m['artifacts']:
 p=b/a['path']; assert p.is_file() and hashlib.sha256(p.read_bytes()).hexdigest()==a['sha256']
d=json.loads((b/'sizing-drill.json').read_text()); x={v['intent_id']:v for v in d['results']}; assert d['marker']=='FOREX_M23_SIZING_DRILL_OK' and x['sized']['planned_loss_aud']<=100 and x['risk-refused']['reason']=='RISK_NOT_APPROVED' and x['too-small']['reason']=='MINIMUM_VOLUME_EXCEEDS_RISK_BUDGET'; print('FOREX_M23_EVIDENCE_VERIFIED')
PY
