#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
python3 - "$root" "$1" <<'PY'
import hashlib,json,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
r,b=Path(sys.argv[1]),Path(sys.argv[2]).resolve(); m=json.loads((b/'manifest.json').read_text())
assert b.is_relative_to(r/'runs/evidence/M22') and m['milestone_id']=='M22' and not m['dirty_worktree']
assert m['git_revision']==subprocess.check_output(['git','rev-parse','HEAD'],cwd=r,text=True).strip()
assert (datetime.now(timezone.utc)-datetime.fromisoformat(m['captured_at'].replace('Z','+00:00'))).total_seconds()<168*3600
for a in m['artifacts']:
 p=b/a['path']; assert p.is_file() and hashlib.sha256(p.read_bytes()).hexdigest()==a['sha256']
d=json.loads((b/'risk-drill.json').read_text()); results={x['intent_id']:x for x in d['results']}
assert d['marker']=='FOREX_M22_RISK_DRILL_OK' and results['allowed']['order_submission']=='STRUCTURALLY_DISABLED'
assert {'ONE_POSITION_LIMIT','LOSS_LIMIT','SPREAD_LIMIT','MANDATORY_FLAT_BY_CUTOFF','SCHEDULED_EVENT_BLACKOUT'} == {x['reasons'][0] for x in d['results'] if x['outcome']=='REFUSE'}
assert 'FOREX_M22_PROOF_OK' in (b/'summary.txt').read_text(); print('FOREX_M22_EVIDENCE_VERIFIED')
PY
