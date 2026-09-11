#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"; cd "$root"; export PYTHONPATH="$root/src${PYTHONPATH:+:$PYTHONPATH}"
bundle="${1:-runs/evidence/M22/$(date -u +%Y%m%dT%H%M%SZ)}"; mkdir -p "$bundle"
git diff --quiet
python3 -m pytest -q tests/milestones/test_m22.py >"$bundle/tests.txt" 2>&1
python3 scripts/forex_milestones.py validate >"$bundle/governance.txt" 2>&1
python3 - "$bundle" <<'PY'
import json,sys
from pathlib import Path
from forex.simulated_risk import drill
result=drill(Path.cwd()); assert result['marker']=='FOREX_M22_RISK_DRILL_OK'; Path(sys.argv[1],'risk-drill.json').write_text(json.dumps(result,indent=2)+'\n')
PY
git rev-parse HEAD >"$bundle/revision.txt"
python3 - "$bundle" <<'PY'
import hashlib,json,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
b=Path(sys.argv[1]); status=json.loads(subprocess.check_output(['python3','scripts/forex_milestones.py','status','--json'])); (b/'summary.txt').write_text('FOREX_M22_PROOF_OK\n')
artifacts=[{'path':p.name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(b.iterdir()) if p.is_file()]
manifest={'schema_version':'1.0.0','milestone_id':'M22','captured_at':datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),'git_revision':(b/'revision.txt').read_text().strip(),'dirty_worktree':False,'configuration_fingerprint':status['configuration_fingerprint'],'surface':'offline simulated risk-engine evaluation','operation':'fixed M22 risk drill','expected_result':'one simulation approval and explicit refusals for every limit','observed_result':'FOREX_M22_PROOF_OK','exit_code':0,'redactions':['No credentials, broker, account, price, position, or order data retained.'],'summary':'FOREX_M22_PROOF_OK','artifacts':artifacts}; (b/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
PY
echo "$bundle"
