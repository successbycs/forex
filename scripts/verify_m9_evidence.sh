#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
python3 - "$root" "$1" <<'PY'
import hashlib,json,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
root,b=Path(sys.argv[1]),Path(sys.argv[2]).resolve(); m=json.loads((b/'manifest.json').read_text())
if not b.is_relative_to(root/'runs'/'evidence'/'M9') or m.get('milestone_id')!='M9' or m.get('dirty_worktree') is not False: raise SystemExit('M9 manifest invalid')
if m['git_revision']!=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(): raise SystemExit('M9 revision mismatch')
if (datetime.now(timezone.utc)-datetime.fromisoformat(m['captured_at'].replace('Z','+00:00'))).total_seconds()>168*3600: raise SystemExit('M9 evidence stale')
for a in m['artifacts']:
 p=b/a['path']; assert p.is_file() and hashlib.sha256(p.read_bytes()).hexdigest()==a['sha256']
s=json.loads((b/'ecb-sample.json').read_text()); assert s['source_id']=='ecb-data-portal-euro-macro' and s['include_history'] and s['raw_sha256'] and s['observations']
assert 'FOREX_M9_PROOF_OK' in (b/'summary.txt').read_text(); print('FOREX_M9_EVIDENCE_VERIFIED')
PY
