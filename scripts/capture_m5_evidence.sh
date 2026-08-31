#!/usr/bin/env bash
# Capture the fixed, idempotent M5 persistence proof on the T480 PostgreSQL surface.
set -uo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"; cd "$root"
bundle="${1:-runs/evidence/M5/$(date -u +%Y%m%dT%H%M%SZ)}"; mkdir -p "$bundle"
revision="$(git rev-parse --verify HEAD 2>/dev/null || printf UNBORN)"
material_changes="$(git status --porcelain --untracked-files=all | sed -E 's/^.. //' | grep -Ev '^(project_state\.json|runs/run_history\.json)$' || true)"
[[ "$revision" != UNBORN && -z "$material_changes" ]] && dirty_worktree=false || dirty_worktree=true
configuration_fingerprint="$(python3 scripts/forex_milestones.py status --json | python3 -c 'import json,sys; print(json.load(sys.stdin)["configuration_fingerprint"])')"
python3 -m pytest -q tests/milestones/test_m5.py >"$bundle/tests.txt" 2>&1; tests_exit=$?
python3 scripts/forex_milestones.py validate >"$bundle/governance.txt" 2>&1; governance_exit=$?
python3 scripts/validate_config.py --root . --json >"$bundle/configuration.json" 2>&1; configuration_exit=$?
bash scripts/verify_project.sh >"$bundle/repository-verification.txt" 2>&1; repository_exit=$?
# The only mutation is the fixed retained-snapshot import; it is idempotent.
python3 scripts/postgres_pgvector_adapter.py forex-m2-import --approve >"$bundle/reimport.json" 2>&1; reimport_exit=$?
python3 scripts/postgres_pgvector_adapter.py forex-m2-verify >"$bundle/verify.json" 2>&1; postgres_verify_exit=$?
python3 scripts/postgres_pgvector_adapter.py forex-m2-provenance-negative-control >"$bundle/provenance-negative-control.json" 2>&1; provenance_exit=$?
{ printf 'tests=%s\n' "$tests_exit"; printf 'governance=%s\n' "$governance_exit"; printf 'configuration=%s\n' "$configuration_exit"; printf 'repository_verification=%s\n' "$repository_exit"; printf 'reimport=%s\n' "$reimport_exit"; printf 'postgres_verify=%s\n' "$postgres_verify_exit"; printf 'provenance_negative_control=%s\n' "$provenance_exit"; } >"$bundle/exit-codes.txt"
overall=0; for code in "$tests_exit" "$governance_exit" "$configuration_exit" "$repository_exit" "$reimport_exit" "$postgres_verify_exit" "$provenance_exit"; do [[ "$code" -eq 0 ]] || overall=1; done; [[ "$dirty_worktree" == false ]] || overall=1
printf '%s\n' "$revision" >"$bundle/revision.txt"
[[ "$overall" -eq 0 ]] && printf 'FOREX_M5_PROOF_OK\n' >"$bundle/summary.txt" || printf 'FOREX_M5_PROOF_FAILED\n' >"$bundle/summary.txt"
export FOREX_M5_REVISION="$revision" FOREX_M5_DIRTY="$dirty_worktree" FOREX_M5_CONFIG="$configuration_fingerprint" FOREX_M5_OVERALL="$overall"
python3 - "$bundle" <<'PY'
import hashlib,json,os,sys
from datetime import datetime,timezone
from pathlib import Path
b=Path(sys.argv[1]); artifacts=[{'path':p.name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(b.iterdir()) if p.is_file() and p.name!='manifest.json']
m={'schema_version':'1.0.0','milestone_id':'M5','captured_at':datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),'git_revision':os.environ['FOREX_M5_REVISION'],'dirty_worktree':os.environ['FOREX_M5_DIRTY']=='true','configuration_fingerprint':os.environ['FOREX_M5_CONFIG'],'surface':'application-to-PostgreSQL historical-data persistence and idempotent reimport workflow','operation':'fixed PostgreSQL reimport, verification, and sealed-observation negative control','expected_result':'canonical retained snapshot is not duplicated and provenance mutation is rejected','observed_result':(b/'summary.txt').read_text().strip(),'exit_code':int(os.environ['FOREX_M5_OVERALL']),'redactions':['No credentials or connection strings are retained.'],'summary':(b/'summary.txt').read_text().strip(),'artifacts':artifacts}
(b/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
PY
echo "$bundle"; exit "$overall"
