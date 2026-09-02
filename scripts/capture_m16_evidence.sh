#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"; cd "$root"; export PYTHONPATH="$root/src${PYTHONPATH:+:$PYTHONPATH}"
bundle="${1:-runs/evidence/M16/$(date -u +%Y%m%dT%H%M%SZ)}"; mkdir -p "$bundle"
python3 -m pytest -q tests/milestones/test_m16.py >"$bundle/tests.txt" 2>&1
python3 scripts/forex_milestones.py validate >"$bundle/governance.txt" 2>&1
python3 scripts/postgres_pgvector_adapter.py forex-m16-walk-forward-probe >"$bundle/walk-forward-probe.json"
git diff --quiet; git rev-parse HEAD >"$bundle/revision.txt"
python3 - "$bundle" <<'PY'
import hashlib,json,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
b=Path(sys.argv[1]); p=json.loads((b/'walk-forward-probe.json').read_text()); result=json.loads(p['result']['stdout'])['evaluation']
assert p['ok'] and result['marker']=='FOREX_M16_WALK_FORWARD_OK' and len(result['windows'])==3 and result['bars']==720 and result['chronological_only'] and not result['random_shuffling_used'] and not result['live_fitting_used'] and result['research_only'] and not result['profitability_claim']
assert result['overall']['no_change']['actionable_sessions']==0 and set(result['context_coverage'])=={'macro','calendar','sentiment'}
s=json.loads(subprocess.check_output(['python3','scripts/forex_milestones.py','status','--json']))
(b/'summary.txt').write_text('FOREX_M16_PROOF_OK\n')
a=[{'path':x.name,'sha256':hashlib.sha256(x.read_bytes()).hexdigest()} for x in sorted(b.iterdir()) if x.is_file()]
m={'schema_version':'1.0.0','milestone_id':'M16','captured_at':datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),'git_revision':(b/'revision.txt').read_text().strip(),'dirty_worktree':False,'configuration_fingerprint':s['configuration_fingerprint'],'surface':'reproducible historical walk-forward evaluation environment','operation':'fixed T480 PostgreSQL M16 chronological walk-forward probe','expected_result':'frozen historical M15 baseline versus no-change and deterministic baselines','observed_result':'FOREX_M16_PROOF_OK','exit_code':0,'redactions':['No account, order, live server, or article text retained.'],'summary':'FOREX_M16_PROOF_OK','artifacts':a}
(b/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
PY
echo "$bundle"
