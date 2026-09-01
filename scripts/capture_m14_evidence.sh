#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"; cd "$root"; export PYTHONPATH="$root/src${PYTHONPATH:+:$PYTHONPATH}"
bundle="${1:-runs/evidence/M14/$(date -u +%Y%m%dT%H%M%SZ)}"; mkdir -p "$bundle"
python3 -m pytest -q tests/milestones/test_m14.py >"$bundle/tests.txt" 2>&1
python3 scripts/forex_milestones.py validate >"$bundle/governance.txt" 2>&1
python3 scripts/postgres_pgvector_adapter.py forex-m14-regime-probe >"$bundle/regime-probe.json"
git diff --quiet; git rev-parse HEAD >"$bundle/revision.txt"
python3 - "$bundle" <<'PY'
import hashlib,json,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
b=Path(sys.argv[1]); p=json.loads((b/'regime-probe.json').read_text()); out=p['result']['stdout']
assert p['ok'] and 'FOREX_M14_REGIME_PROBE_OK' in out and 'bars=6' in out and 'regime=' in out and 'event_window=EVENT_BLACKOUT' in out and 'decision_at=2026-08-28 08:00:00+00' in out and 'flat_by=2026-08-28 20:00:00+00' in out and 'daylight_saving=UTC_FIXED' in out
s=json.loads(subprocess.check_output(['python3','scripts/forex_milestones.py','status','--json']))
(b/'summary.txt').write_text('FOREX_M14_PROOF_OK\n')
a=[{'path':x.name,'sha256':hashlib.sha256(x.read_bytes()).hexdigest()} for x in sorted(b.iterdir()) if x.is_file()]
m={'schema_version':'1.0.0','milestone_id':'M14','captured_at':datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),'git_revision':(b/'revision.txt').read_text().strip(),'dirty_worktree':False,'configuration_fingerprint':s['configuration_fingerprint'],'surface':'deterministic historical regime and event-window engine','operation':'fixed T480 PostgreSQL M14 regime probe','expected_result':'deterministic historical regime and UTC session output','observed_result':'FOREX_M14_PROOF_OK','exit_code':0,'redactions':['No account, order, or live data retained.'],'summary':'FOREX_M14_PROOF_OK','artifacts':a}; (b/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
PY
echo "$bundle"
