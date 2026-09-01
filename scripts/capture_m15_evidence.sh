#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"; cd "$root"; export PYTHONPATH="$root/src${PYTHONPATH:+:$PYTHONPATH}"
bundle="${1:-runs/evidence/M15/$(date -u +%Y%m%dT%H%M%SZ)}"; mkdir -p "$bundle"
python3 -m pytest -q tests/milestones/test_m15.py >"$bundle/tests.txt" 2>&1
python3 scripts/forex_milestones.py validate >"$bundle/governance.txt" 2>&1
python3 scripts/postgres_pgvector_adapter.py forex-m15-baseline-probe >"$bundle/baseline-probe.json"
git diff --quiet; git rev-parse HEAD >"$bundle/revision.txt"
python3 - "$bundle" <<'PY'
import hashlib,json,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
b=Path(sys.argv[1]); payload=json.loads((b/'baseline-probe.json').read_text()); result=json.loads(payload['result']['stdout'])
assert payload['ok'] and result['marker']=='FOREX_M15_BASELINE_PROBE_OK' and result['bars']==720 and result['model']['training_examples']==717 and result['advisory']['action'] in {'BUY','SELL','NO_TRADE'} and 0<=result['advisory']['advisory_score']<=100 and result['advisory']['research_only'] is True
(b/'summary.txt').write_text('FOREX_M15_PROOF_OK\n')
status=json.loads(subprocess.check_output(['python3','scripts/forex_milestones.py','status','--json']))
artifacts=[{'path':p.name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(b.iterdir()) if p.is_file()]
(b/'manifest.json').write_text(json.dumps({'schema_version':'1.0.0','milestone_id':'M15','captured_at':datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),'git_revision':(b/'revision.txt').read_text().strip(),'dirty_worktree':False,'configuration_fingerprint':status['configuration_fingerprint'],'surface':'deterministic daily market-hypothesis and ledger workflow','operation':'fixed T480 M15 historical baseline probe','expected_result':'offline advisory from retained Demo-only bars','observed_result':'FOREX_M15_PROOF_OK','exit_code':0,'redactions':['No account, order, or live data retained.'],'summary':'FOREX_M15_PROOF_OK','artifacts':artifacts},indent=2)+'\n')
PY
echo "$bundle"
