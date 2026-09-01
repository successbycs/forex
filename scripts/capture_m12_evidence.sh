#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"; cd "$root"; export PYTHONPATH="$root/src${PYTHONPATH:+:$PYTHONPATH}"
bundle="${1:-runs/evidence/M12/$(date -u +%Y%m%dT%H%M%SZ)}"; mkdir -p "$bundle"
python3 -m pytest -q tests/milestones/test_m12.py >"$bundle/tests.txt" 2>&1
python3 scripts/forex_milestones.py validate >"$bundle/governance.txt" 2>&1
python3 scripts/postgres_pgvector_adapter.py forex-m12-quality-probe >"$bundle/quality-probe.json"
git diff --quiet; git rev-parse HEAD >"$bundle/revision.txt"
python3 - "$bundle" <<'PY'
import hashlib,json,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
b=Path(sys.argv[1]); p=json.loads((b/'quality-probe.json').read_text()); assert p['ok'] and 'FOREX_M12_QUALITY_PROBE_OK' in p['result']['stdout']
s=json.loads(subprocess.check_output(['python3','scripts/forex_milestones.py','status','--json'])); (b/'summary.txt').write_text('FOREX_M12_PROOF_OK\n')
a=[{'path':x.name,'sha256':hashlib.sha256(x.read_bytes()).hexdigest()} for x in sorted(b.iterdir()) if x.is_file()]
m={'schema_version':'1.0.0','milestone_id':'M12','captured_at':datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),'git_revision':(b/'revision.txt').read_text().strip(),'dirty_worktree':False,'configuration_fingerprint':s['configuration_fingerprint'],'surface':'normalisation, quality, and quarantine processing path','operation':'fixed T480 M12 quality probe','expected_result':'one accepted observation and explicit quarantine results','observed_result':'FOREX_M12_PROOF_OK','exit_code':0,'redactions':['No market, account, order or article data retained.'],'summary':'FOREX_M12_PROOF_OK','artifacts':a}; (b/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
PY
echo "$bundle"
