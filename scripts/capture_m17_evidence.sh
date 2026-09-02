#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"; cd "$root"; export PYTHONPATH="$root/src${PYTHONPATH:+:$PYTHONPATH}"
bundle="${1:-runs/evidence/M17/$(date -u +%Y%m%dT%H%M%SZ)}"; mkdir -p "$bundle"
python3 -m pytest -q tests/milestones/test_m17.py >"$bundle/tests.txt" 2>&1
python3 scripts/forex_milestones.py validate >"$bundle/governance.txt" 2>&1
python3 scripts/postgres_pgvector_adapter.py forex-m17-context-probe >"$bundle/context-probe.json"
git diff --quiet; git rev-parse HEAD >"$bundle/revision.txt"
python3 - "$bundle" <<'PY'
import hashlib,json,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
b=Path(sys.argv[1]); p=json.loads((b/'context-probe.json').read_text()); x=json.loads(p['result']['stdout'])
assert p['ok'] and x['marker']=='FOREX_M17_CONTEXT_PROBE_OK' and x['bars']>0 and x['context']['agent_authority']=='NONE' and not x['context']['order_capability'] and not x['context']['live_trading_capability']
(b/'summary.txt').write_text('FOREX_M17_PROOF_OK\n'); s=json.loads(subprocess.check_output(['python3','scripts/forex_milestones.py','status','--json']))
a=[{'path':f.name,'sha256':hashlib.sha256(f.read_bytes()).hexdigest()} for f in sorted(b.iterdir()) if f.is_file()]
(b/'manifest.json').write_text(json.dumps({'schema_version':'1.0.0','milestone_id':'M17','captured_at':datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),'git_revision':(b/'revision.txt').read_text().strip(),'dirty_worktree':False,'configuration_fingerprint':s['configuration_fingerprint'],'surface':'offline non-executing agent-context contract','operation':'fixed T480 M17 context probe','expected_result':'historical bounded context with no agent or order authority','observed_result':'FOREX_M17_PROOF_OK','exit_code':0,'redactions':['No account, credential, order, or live data retained.'],'summary':'FOREX_M17_PROOF_OK','artifacts':a},indent=2)+'\n')
PY
echo "$bundle"
