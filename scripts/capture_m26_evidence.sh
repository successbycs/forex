#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"; cd "$root"; export PYTHONPATH="$root/src${PYTHONPATH:+:$PYTHONPATH}"
bundle="${1:-runs/evidence/M26/$(date -u +%Y%m%dT%H%M%SZ)}"; mkdir -p "$bundle"; git diff --quiet
python3 -m pytest -q tests/milestones/test_m26.py >"$bundle/tests.txt" 2>&1; python3 scripts/forex_milestones.py validate >"$bundle/governance.txt" 2>&1
python3 - "$bundle" <<'PY'
import json,sys
from pathlib import Path
from forex.execution_revalidation import drill_revalidation
r=drill_revalidation(); assert r['marker']=='FOREX_M26_REVALIDATION_DRILL_OK'; Path(sys.argv[1],'revalidation-drill.json').write_text(json.dumps(r,indent=2)+'\n')
PY
git rev-parse HEAD >"$bundle/revision.txt"
python3 - "$bundle" <<'PY'
import hashlib,json,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
b=Path(sys.argv[1]); s=json.loads(subprocess.check_output(['python3','scripts/forex_milestones.py','status','--json'])); (b/'summary.txt').write_text('FOREX_M26_PROOF_OK\n'); a=[{'path':p.name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(b.iterdir()) if p.is_file()]; m={'schema_version':'1.0.0','milestone_id':'M26','captured_at':datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),'git_revision':(b/'revision.txt').read_text().strip(),'dirty_worktree':False,'configuration_fingerprint':s['configuration_fingerprint'],'surface':'offline execution-revalidation evaluation workflow','operation':'fixed M26 revalidation drill','expected_result':'revalidate only current safe simulated intent','observed_result':'FOREX_M26_PROOF_OK','exit_code':0,'redactions':['No broker, account, order, or credential data retained.'],'summary':'FOREX_M26_PROOF_OK','artifacts':a}; (b/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
PY
echo "$bundle"
