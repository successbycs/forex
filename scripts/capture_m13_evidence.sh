#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"; cd "$root"; export PYTHONPATH="$root/src${PYTHONPATH:+:$PYTHONPATH}"
bundle="${1:-runs/evidence/M13/$(date -u +%Y%m%dT%H%M%SZ)}"; mkdir -p "$bundle"
python3 -m pytest -q tests/milestones/test_m13.py >"$bundle/tests.txt" 2>&1; python3 scripts/forex_milestones.py validate >"$bundle/governance.txt" 2>&1; python3 scripts/postgres_pgvector_adapter.py forex-m13-replay-probe >"$bundle/replay-probe.json"; git diff --quiet; git rev-parse HEAD >"$bundle/revision.txt"
python3 - "$bundle" <<'PY'
import hashlib,json,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
b=Path(sys.argv[1]); p=json.loads((b/'replay-probe.json').read_text()); out=p['result']['stdout']; assert p['ok'] and 'FOREX_M13_REPLAY_PROBE_OK' in out and 'FOREX_M13_POSTGRES_REPLAY_OK' in out and 'snapshot=m2-m1-eurusd-h1-720' in out and 'bars=720' in out and 'future_records=0' in out; s=json.loads(subprocess.check_output(['python3','scripts/forex_milestones.py','status','--json'])); (b/'summary.txt').write_text('FOREX_M13_PROOF_OK\n'); a=[{'path':x.name,'sha256':hashlib.sha256(x.read_bytes()).hexdigest()} for x in sorted(b.iterdir()) if x.is_file()]; m={'schema_version':'1.0.0','milestone_id':'M13','captured_at':datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),'git_revision':(b/'revision.txt').read_text().strip(),'dirty_worktree':False,'configuration_fingerprint':s['configuration_fingerprint'],'surface':'point-in-time alignment engine and historical replay environment','operation':'fixed T480 PostgreSQL M2/M11 replay drill','expected_result':'strict UTC cutoff excludes future records','observed_result':'FOREX_M13_PROOF_OK','exit_code':0,'redactions':['No market, account, order or live data retained.'],'summary':'FOREX_M13_PROOF_OK','artifacts':a}; (b/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
PY
echo "$bundle"
