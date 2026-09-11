#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"; cd "$root"; export PYTHONPATH="$root/src${PYTHONPATH:+:$PYTHONPATH}"
bundle="${1:-runs/evidence/M25/$(date -u +%Y%m%dT%H%M%SZ)}"; mkdir -p "$bundle"; git diff --quiet
python3 -m pytest -q tests/milestones/test_m25.py >"$bundle/tests.txt" 2>&1; python3 scripts/forex_milestones.py validate >"$bundle/governance.txt" 2>&1
python3 - "$bundle" <<'PY'
import json,sys
from pathlib import Path
from forex.human_approval import drill_approvals
r=drill_approvals(); assert r['marker']=='FOREX_M25_APPROVAL_DRILL_OK'; Path(sys.argv[1],'approval-drill.json').write_text(json.dumps(r,indent=2)+'\n')
PY
git rev-parse HEAD >"$bundle/revision.txt"
python3 - "$bundle" <<'PY'
import hashlib,json,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
b=Path(sys.argv[1]); s=json.loads(subprocess.check_output(['python3','scripts/forex_milestones.py','status','--json'])); (b/'summary.txt').write_text('FOREX_M25_PROOF_OK\n'); a=[{'path':p.name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(b.iterdir()) if p.is_file()]; m={'schema_version':'1.0.0','milestone_id':'M25','captured_at':datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),'git_revision':(b/'revision.txt').read_text().strip(),'dirty_worktree':False,'configuration_fingerprint':s['configuration_fingerprint'],'surface':'offline human-approval workflow','operation':'fixed M25 approval drill','expected_result':'scoped acceptance plus rejection, expiry, and tamper refusals','observed_result':'FOREX_M25_PROOF_OK','exit_code':0,'redactions':['No broker, account, order, or credential data retained.'],'summary':'FOREX_M25_PROOF_OK','artifacts':a}; (b/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
PY
echo "$bundle"
