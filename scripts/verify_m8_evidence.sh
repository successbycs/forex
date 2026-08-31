#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
python3 - "$root" "$1" <<'PY'
import hashlib,json,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
root,b=Path(sys.argv[1]),Path(sys.argv[2]).resolve(); m=json.loads((b/'manifest.json').read_text())
if not b.is_relative_to(root/'runs'/'evidence'/'M8') or m.get('milestone_id')!='M8' or m.get('exit_code')!=0 or m.get('dirty_worktree') is not False: raise SystemExit('M8 manifest invalid')
if m.get('git_revision')!=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(): raise SystemExit('M8 revision mismatch')
if (datetime.now(timezone.utc)-datetime.fromisoformat(m['captured_at'].replace('Z','+00:00'))).total_seconds()>168*3600: raise SystemExit('M8 evidence stale')
for artifact in m['artifacts']:
 p=b/artifact['path']; assert p.is_file() and hashlib.sha256(p.read_bytes()).hexdigest()==artifact['sha256']
sample=json.loads((b/'vintage-sample.json').read_text()); assert sample['series_id']=='CPIAUCSL' and sample['decision_cutoff']=='2024-02-01'
assert sample['observations'] and all(x['observation_date']<=sample['decision_cutoff'] and x['vintage_start']<=sample['decision_cutoff'] for x in sample['observations'])
assert 'FOREX_M8_PROOF_OK' in (b/'summary.txt').read_text(); print('FOREX_M8_EVIDENCE_VERIFIED')
PY
