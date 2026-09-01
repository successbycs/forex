#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
python3 - "$root" "$1" <<'PY'
import hashlib,json,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
r,b=Path(sys.argv[1]),Path(sys.argv[2]).resolve(); m=json.loads((b/'manifest.json').read_text())
assert b.is_relative_to(r/'runs/evidence/M12') and m['milestone_id']=='M12' and not m['dirty_worktree'] and m['git_revision']==subprocess.check_output(['git','rev-parse','HEAD'],cwd=r,text=True).strip()
assert (datetime.now(timezone.utc)-datetime.fromisoformat(m['captured_at'].replace('Z','+00:00'))).total_seconds()<168*3600
for a in m['artifacts']: p=b/a['path']; assert p.is_file() and hashlib.sha256(p.read_bytes()).hexdigest()==a['sha256']
p=json.loads((b/'quality-probe.json').read_text()); assert p['ok'] and 'FOREX_M12_QUALITY_PROBE_OK' in p['result']['stdout']; assert 'FOREX_M12_PROOF_OK' in (b/'summary.txt').read_text(); print('FOREX_M12_EVIDENCE_VERIFIED')
PY
