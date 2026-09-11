#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
python3 - "$root" "$1" <<'PY'
import hashlib,json,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
r,b=Path(sys.argv[1]),Path(sys.argv[2]).resolve(); m=json.loads((b/'manifest.json').read_text()); assert b.is_relative_to(r/'runs/evidence/M25') and m['milestone_id']=='M25' and not m['dirty_worktree']; assert m['git_revision']==subprocess.check_output(['git','rev-parse','HEAD'],cwd=r,text=True).strip(); assert (datetime.now(timezone.utc)-datetime.fromisoformat(m['captured_at'].replace('Z','+00:00'))).total_seconds()<168*3600
for a in m['artifacts']:
 p=b/a['path']; assert p.is_file() and hashlib.sha256(p.read_bytes()).hexdigest()==a['sha256']
d=json.loads((b/'approval-drill.json').read_text())['results']; assert d['accepted']['outcome']=='APPROVED_FOR_FUTURE_REVALIDATION_ONLY' and d['rejected']['reason']=='HUMAN_REJECTED' and d['expired']['reason']=='APPROVAL_EXPIRED' and d['mismatch']['reason']=='INTENT_MISMATCH'; print('FOREX_M25_EVIDENCE_VERIFIED')
PY
