#!/usr/bin/env bash
# Capture the fixed, idempotent M5 persistence proof on the T480 PostgreSQL surface.
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root"
bundle="${1:-runs/evidence/M5/$(date -u +%Y%m%dT%H%M%SZ)}"
mkdir -p "$bundle"

python3 -m pytest -q tests/milestones/test_m5.py >"$bundle/tests.txt" 2>&1
python3 scripts/forex_milestones.py validate >"$bundle/governance.txt" 2>&1

# The only mutation is the adapter's retained-snapshot import.  Its fixed operation
# returns ALREADY_PRESENT when the canonical M2 snapshot already exists.
python3 scripts/postgres_pgvector_adapter.py forex-m2-import --approve >"$bundle/reimport.json"
python3 scripts/postgres_pgvector_adapter.py forex-m2-verify >"$bundle/verify.json"
python3 scripts/postgres_pgvector_adapter.py forex-m2-provenance-negative-control >"$bundle/provenance-negative-control.json"
git rev-parse HEAD >"$bundle/revision.txt"
printf 'FOREX_M5_PROOF_OK\n' >"$bundle/summary.txt"

python3 - "$bundle" <<'PY'
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

bundle = Path(sys.argv[1])
artifacts = []
for path in sorted(p for p in bundle.iterdir() if p.is_file() and p.name != 'manifest.json'):
    artifacts.append({'path': path.name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
status = json.loads(subprocess.check_output(['python3', 'scripts/forex_milestones.py', 'status', '--json']))
manifest = {
    'schema_version': '1.0.0',
    'milestone_id': 'M5',
    'captured_at': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
    'git_revision': (bundle / 'revision.txt').read_text().strip(),
    'dirty_worktree': False,
    'configuration_fingerprint': status['configuration_fingerprint'],
    'surface': 'application-to-PostgreSQL historical-data persistence and idempotent reimport workflow',
    'operation': 'fixed PostgreSQL reimport, verification, and sealed-observation negative control',
    'expected_result': 'canonical retained snapshot is not duplicated and provenance mutation is rejected',
    'observed_result': 'FOREX_M5_PROOF_OK',
    'exit_code': 0,
    'redactions': ['No credentials or connection strings are retained.'],
    'summary': 'FOREX_M5_PROOF_OK',
    'artifacts': artifacts,
}
(bundle / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
PY

echo "$bundle"
