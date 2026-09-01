#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"; python3 - "$root" "$1" <<'PY'
import hashlib,json,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
r,b=Path(sys.argv[1]),Path(sys.argv[2]).resolve(); m=json.loads((b/'manifest.json').read_text())
assert b.is_relative_to(r/'runs/evidence/M14') and m['milestone_id']=='M14' and not m['dirty_worktree'] and m['git_revision']==subprocess.check_output(['git','rev-parse','HEAD'],cwd=r,text=True).strip()
assert (datetime.now(timezone.utc)-datetime.fromisoformat(m['captured_at'].replace('Z','+00:00'))).total_seconds()<168*3600
for a in m['artifacts']:
 p=b/a['path']; assert p.is_file() and hashlib.sha256(p.read_bytes()).hexdigest()==a['sha256']
p=json.loads((b/'regime-probe.json').read_text()); out=p['result']['stdout']; assert p['ok'] and 'FOREX_M14_REGIME_PROBE_OK' in out and 'bars=6' in out and 'eligible_bars=6' in out and 'regime=' in out and 'event_window=EVENT_BLACKOUT' in out and 'decision_at=2026-09-01 20:00:00+12' in out and 'flat_by=2026-09-02 08:00:00+12' in out and 'snapshot=m2-m1-eurusd-h1-720' in out and 'source=gomarketsmu-demo-m1' in out and 'daylight_saving=UTC_FIXED' in out
assert 'FOREX_M14_PROOF_OK' in (b/'summary.txt').read_text(); print('FOREX_M14_EVIDENCE_VERIFIED')
PY
