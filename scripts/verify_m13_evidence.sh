#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"; python3 - "$root" "$1" <<'PY'
import hashlib,json,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
r,b=Path(sys.argv[1]),Path(sys.argv[2]).resolve(); m=json.loads((b/'manifest.json').read_text()); assert b.is_relative_to(r/'runs/evidence/M13') and m['milestone_id']=='M13' and not m['dirty_worktree'] and m['git_revision']==subprocess.check_output(['git','rev-parse','HEAD'],cwd=r,text=True).strip(); assert (datetime.now(timezone.utc)-datetime.fromisoformat(m['captured_at'].replace('Z','+00:00'))).total_seconds()<168*3600
for a in m['artifacts']: p=b/a['path']; assert p.is_file() and hashlib.sha256(p.read_bytes()).hexdigest()==a['sha256']
p=json.loads((b/'replay-probe.json').read_text()); out=p['result']['stdout']; assert p['ok'] and 'FOREX_M13_POSTGRES_REPLAY_OK' in out and 'snapshot=m2-m1-eurusd-h1-720' in out and 'bars=720' in out and 'replay_days=' in out and 'aligned_context_days=1' in out and 'price_lineage_ok=true' in out and 'context_lineage_ok=true' in out and 'future_price_records=0' in out and 'future_context_records=' in out; assert 'FOREX_M13_PROOF_OK' in (b/'summary.txt').read_text(); print('FOREX_M13_EVIDENCE_VERIFIED')
PY
