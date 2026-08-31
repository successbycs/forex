#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
python3 - "$root" "$1" <<'PY'
import hashlib,json,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
root,b=Path(sys.argv[1]),Path(sys.argv[2]).resolve(); m=json.loads((b/'manifest.json').read_text())
if not b.is_relative_to(root/'runs'/'evidence'/'M7') or m.get('milestone_id')!='M7' or m.get('exit_code')!=0 or m.get('dirty_worktree') is not False: raise SystemExit('M7 manifest invalid')
if m.get('git_revision')!=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(): raise SystemExit('M7 revision mismatch')
if (datetime.now(timezone.utc)-datetime.fromisoformat(m['captured_at'].replace('Z','+00:00'))).total_seconds()>168*3600: raise SystemExit('M7 evidence stale')
for artifact in m['artifacts']:
 p=b/artifact['path']; assert p.is_file() and hashlib.sha256(p.read_bytes()).hexdigest()==artifact['sha256']
registry=json.loads((root/'config/source_qualification.json').read_text()); candidates={x['source_id']:x for x in registry['candidates']}
samples=json.loads((b/'source-samples.json').read_text())['samples']; observed={x['source_id']:x for x in samples}
assert set(candidates)==set(observed)
assert candidates['ecb-data-portal-euro-macro']['decision']=='QUALIFIED'
assert candidates['fred-alfred-us-macro']['decision']=='CONDITIONALLY_QUALIFIED'
assert candidates['trading-economics-calendar']['decision']=='DEFERRED'
assert candidates['gdelt-sentiment-prototype']['decision']=='EXPERIMENTAL_AGGREGATES_ONLY'
for source_id in ('fred-alfred-us-macro','ecb-data-portal-euro-macro','gdelt-sentiment-prototype'):
 assert observed[source_id]['status']==200 and observed[source_id]['sample_bytes']>0
assert 'FOREX_M7_PROOF_OK' in (b/'summary.txt').read_text(); print('FOREX_M7_EVIDENCE_VERIFIED')
PY
