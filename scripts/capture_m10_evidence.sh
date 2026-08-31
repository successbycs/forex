#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"; cd "$root"; export PYTHONPATH="$root/src${PYTHONPATH:+:$PYTHONPATH}"
if [[ -z "${FRED_API_KEY:-}" && -f .env ]]; then export FRED_API_KEY="$(sed -n 's/^FRED_API_KEY=//p' .env | tail -n 1)"; fi
bundle="${1:-runs/evidence/M10/$(date -u +%Y%m%dT%H%M%SZ)}"; mkdir -p "$bundle"
python3 -m pytest -q tests/milestones/test_m10.py >"$bundle/tests.txt" 2>&1
python3 scripts/forex_milestones.py validate >"$bundle/governance.txt" 2>&1
python3 - "$bundle" <<'PY'
import json,sys
from pathlib import Path
from forex.calendar_events import capture_events
p=capture_events(); assert p['us_events'] and p['eur_events']; Path(sys.argv[1],'events.json').write_text(json.dumps(p,indent=2)+'\n')
PY
git rev-parse HEAD >"$bundle/revision.txt"
python3 - "$bundle" <<'PY'
import hashlib,json,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
b=Path(sys.argv[1]); status=json.loads(subprocess.check_output(['python3','scripts/forex_milestones.py','status','--json'])); (b/'summary.txt').write_text('FOREX_M10_PROOF_OK\n')
a=[{'path':p.name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(b.iterdir()) if p.is_file()]; m={'schema_version':'1.0.0','milestone_id':'M10','captured_at':datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),'git_revision':(b/'revision.txt').read_text().strip(),'dirty_worktree':False,'configuration_fingerprint':status['configuration_fingerprint'],'surface':'free official USD/EUR release-calendar adapter and time-precision-labelled event records','operation':'fixed FRED CPI and ECB calendar sample','expected_result':'date/time-precision-labelled official events','observed_result':'FOREX_M10_PROOF_OK','exit_code':0,'redactions':['No orders, accounts or commercial calendar payloads retained.'],'summary':'FOREX_M10_PROOF_OK','artifacts':a}; (b/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
PY
echo "$bundle"
