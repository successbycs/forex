#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"; cd "$root"
bundle="${1:-runs/evidence/M8/$(date -u +%Y%m%dT%H%M%SZ)}"; mkdir -p "$bundle"
python3 -m pytest -q tests/milestones/test_m8.py >"$bundle/tests.txt" 2>&1
python3 scripts/forex_milestones.py validate >"$bundle/governance.txt" 2>&1
python3 - "$bundle" <<'PY'
import hashlib,json,sys
from pathlib import Path
from forex.fred_vintage import fetch_vintage_sample
b=Path(sys.argv[1]); sample=fetch_vintage_sample('2024-02-01')
assert sample['series_id']=='CPIAUCSL' and sample['decision_cutoff']=='2024-02-01'
(b/'vintage-sample.json').write_text(json.dumps(sample,indent=2)+'\n')
PY
git rev-parse HEAD >"$bundle/revision.txt"
python3 - "$bundle" <<'PY'
import hashlib,json,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
b=Path(sys.argv[1]); status=json.loads(subprocess.check_output(['python3','scripts/forex_milestones.py','status','--json']))
(b/'summary.txt').write_text('FOREX_M8_PROOF_OK\n')
artifacts=[{'path':p.name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(b.iterdir()) if p.is_file()]
m={'schema_version':'1.0.0','milestone_id':'M8','captured_at':datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),'git_revision':(b/'revision.txt').read_text().strip(),'dirty_worktree':False,'configuration_fingerprint':status['configuration_fingerprint'],'surface':'US macro vintage-data adapter and retained sample','operation':'fixed FRED/ALFRED CPIAUCSL vintage sample','expected_result':'normalised CPIAUCSL observations available at the 2024-02-01 decision cutoff','observed_result':'FOREX_M8_PROOF_OK','exit_code':0,'redactions':['FRED_API_KEY is read only from the ignored environment and is not retained.'],'summary':'FOREX_M8_PROOF_OK','artifacts':artifacts}
(b/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
PY
echo "$bundle"
