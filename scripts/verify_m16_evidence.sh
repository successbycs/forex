#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"; python3 - "$root" "$1" <<'PY'
import hashlib,json,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
r,b=Path(sys.argv[1]),Path(sys.argv[2]).resolve(); m=json.loads((b/'manifest.json').read_text())
assert b.is_relative_to(r/'runs/evidence/M16') and m['milestone_id']=='M16' and not m['dirty_worktree'] and m['git_revision']==subprocess.check_output(['git','rev-parse','HEAD'],cwd=r,text=True).strip()
assert (datetime.now(timezone.utc)-datetime.fromisoformat(m['captured_at'].replace('Z','+00:00'))).total_seconds()<168*3600
for a in m['artifacts']:
 p=b/a['path']; assert p.is_file() and hashlib.sha256(p.read_bytes()).hexdigest()==a['sha256']
p=json.loads((b/'walk-forward-probe.json').read_text()); result=json.loads(p['result']['stdout'])['evaluation']
assert p['ok'] and result['marker']=='FOREX_M16_WALK_FORWARD_OK' and len(result['windows'])==3 and result['bars']==720 and result['chronological_only'] and not result['random_shuffling_used'] and not result['live_fitting_used'] and result['research_only'] and not result['profitability_claim'] and result['overall']['no_change']['actionable_sessions']==0
assert result['availability_policy']=='RETROSPECTIVE_H1_BAR_CLOSE_ASSUMPTION' and 'assumption' in result['availability_policy_assumption'].lower()
assert (b/'repository-verification.txt').is_file() and 'FOREX_REPOSITORY_VERIFICATION_OK' in (b/'repository-verification.txt').read_text()
assert 'FOREX_M16_PROOF_OK' in (b/'summary.txt').read_text(); print('FOREX_M16_EVIDENCE_VERIFIED')
PY
