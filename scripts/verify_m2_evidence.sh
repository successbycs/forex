#!/usr/bin/env bash
set -euo pipefail
if [[ $# -ne 1 ]]; then echo "usage: $0 BUNDLE" >&2; exit 2; fi
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
bundle="$(cd "$1" && pwd)"
case "$bundle" in "$repo_root"/runs/evidence/M2/*) ;; *) echo 'bundle must be beneath runs/evidence/M2' >&2; exit 2;; esac
python3 - "$repo_root" "$bundle" <<'PY'
import hashlib, json, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path

root, bundle = Path(sys.argv[1]), Path(sys.argv[2])
manifest = json.loads((bundle / 'manifest.json').read_text())
if manifest.get('milestone_id') != 'M2' or manifest.get('schema_version') != '1.0.0': raise SystemExit('M2 manifest mismatch')
if manifest.get('exit_code') != 0 or manifest.get('dirty_worktree') is not False: raise SystemExit('M2 capture was unsuccessful or dirty')
if manifest.get('surface') != 'private T480 AI Lab PostgreSQL storing the retained M1 EUR/USD H1 snapshot in the Forex-owned schema': raise SystemExit('M2 proof surface mismatch')
captured = datetime.fromisoformat(manifest['captured_at'].replace('Z', '+00:00'))
if (datetime.now(timezone.utc) - captured).total_seconds() > 168 * 3600: raise SystemExit('M2 evidence is stale')
revision = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=root, text=True, capture_output=True).stdout.strip()
if manifest.get('git_revision') != revision: raise SystemExit('Git revision mismatch')
state = json.loads((root / 'project_state.json').read_text())
digest = hashlib.sha256()
for rel in sorted(state['governed_configuration_paths']): digest.update(rel.encode()); digest.update(b'\0'); digest.update((root / rel).read_bytes()); digest.update(b'\0')
if manifest.get('configuration_fingerprint') != 'sha256:' + digest.hexdigest(): raise SystemExit('configuration fingerprint mismatch')
for artifact in manifest.get('artifacts', []):
    path = bundle / artifact['path']
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != artifact['sha256']: raise SystemExit('artifact hash mismatch: ' + artifact['path'])
combined = ''.join((bundle / a['path']).read_text(errors='replace') for a in manifest['artifacts'])
if 'FOREX_M2_PROOF_OK' not in combined or 'FOREX_REPOSITORY_VERIFICATION_OK' not in combined: raise SystemExit('success marker missing')
if not any(marker in combined for marker in ('FOREX_M2_POSTGRES_IMPORT_OK', 'FOREX_M2_IMPORT_ALREADY_PRESENT')): raise SystemExit('PostgreSQL import marker missing')
if not any(marker in combined for marker in ('FOREX_M2_SCHEMA_APPLIED', 'FOREX_M2_SCHEMA_ALREADY_APPLIED')) or 'FOREX_M2_POSTGRES_VERIFY_OK' not in combined: raise SystemExit('shared PostgreSQL operation marker missing')
if '1|1|1|720|sha256:' not in combined: raise SystemExit('expected PostgreSQL import row counts and snapshot hash are missing')
for required in ('source_status=DEMO_ONLY', 'snapshot=EUR/USD:H1', 'lineage_ok=true', 'bar_availability_ok=true', 'point_in_time_triggers=2', 'sealed_provenance_triggers=2', 'FOREX_M2_SEALED_PROVENANCE_NEGATIVE_CONTROL_OK'):
    if required not in combined: raise SystemExit('required schema/lineage verification is missing: ' + required)
print('FOREX_M2_EVIDENCE_VERIFIED')
PY
