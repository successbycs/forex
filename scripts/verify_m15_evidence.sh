#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"; python3 - "$root" "$1" <<'PY'
import hashlib,json,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
r,b=Path(sys.argv[1]),Path(sys.argv[2]).resolve(); manifest=json.loads((b/'manifest.json').read_text())
assert b.is_relative_to(r/'runs/evidence/M15') and manifest['milestone_id']=='M15' and not manifest['dirty_worktree'] and manifest['git_revision']==subprocess.check_output(['git','rev-parse','HEAD'],cwd=r,text=True).strip()
assert (datetime.now(timezone.utc)-datetime.fromisoformat(manifest['captured_at'].replace('Z','+00:00'))).total_seconds()<168*3600
for artifact in manifest['artifacts']:
 p=b/artifact['path']; assert p.is_file() and hashlib.sha256(p.read_bytes()).hexdigest()==artifact['sha256']
payload=json.loads((b/'baseline-probe.json').read_text()); result=json.loads(payload['result']['stdout']); assert payload['ok'] and result['marker']=='FOREX_M15_BASELINE_PROBE_OK' and result['bars']==720 and result['model']['training_examples']==717 and result['advisory']['research_only'] is True and 0<=result['advisory']['advisory_score']<=100
assert 'FOREX_M15_PROOF_OK' in (b/'summary.txt').read_text(); print('FOREX_M15_EVIDENCE_VERIFIED')
PY
