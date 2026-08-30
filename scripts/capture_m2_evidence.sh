#!/usr/bin/env bash
set -uo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"
postgres_adapter="python3 scripts/postgres_pgvector_adapter.py"
run_id="$(date -u +%Y%m%dT%H%M%SZ)"
bundle="${1:-$repo_root/runs/evidence/M2/$run_id}"
mkdir -p "$bundle"

git_revision="$(git rev-parse --verify HEAD 2>/dev/null || printf UNBORN)"
material_changes="$(git status --porcelain --untracked-files=all | sed -E 's/^.. //' | grep -Ev '^(project_state\.json|runs/run_history\.json)$' || true)"
if [[ "$git_revision" == UNBORN || -n "$material_changes" ]]; then dirty_worktree=true; else dirty_worktree=false; fi
configuration_fingerprint="$(python3 scripts/forex_milestones.py status --json | python3 -c 'import json,sys; print(json.load(sys.stdin)["configuration_fingerprint"])')"

python3 -m pytest -q tests/milestones/test_m2.py >"$bundle/m2-tests.stdout.txt" 2>"$bundle/m2-tests.stderr.txt"; tests_exit=$?
python3 scripts/check_m2_schema.py --root . >"$bundle/postgres-schema.stdout.txt" 2>"$bundle/postgres-schema.stderr.txt"; schema_exit=$?
git -C /home/chris/projects/cs-ai-lab-infra rev-parse HEAD >"$bundle/shared-postgres-adapter.txt" 2>&1
sha256sum /home/chris/projects/cs-ai-lab-infra/scripts/postgres_pgvector_adapter.py >>"$bundle/shared-postgres-adapter.txt"
$postgres_adapter preflight >"$bundle/postgres-preflight.stdout.json" 2>"$bundle/postgres-preflight.stderr.txt"; preflight_exit=$?
$postgres_adapter forex-m2-apply-schema --approve >"$bundle/postgres-schema-apply.stdout.json" 2>"$bundle/postgres-schema-apply.stderr.txt"; apply_exit=$?
$postgres_adapter forex-m2-import --approve >"$bundle/postgres-import.stdout.json" 2>"$bundle/postgres-import.stderr.txt"; import_exit=$?
$postgres_adapter forex-m2-verify >"$bundle/postgres-verify.stdout.json" 2>"$bundle/postgres-verify.stderr.txt"; postgres_verify_exit=$?
$postgres_adapter forex-m2-provenance-negative-control >"$bundle/postgres-provenance-negative-control.stdout.json" 2>"$bundle/postgres-provenance-negative-control.stderr.txt"; provenance_negative_control_exit=$?
python3 scripts/forex_milestones.py validate >"$bundle/governance.stdout.txt" 2>"$bundle/governance.stderr.txt"; governance_exit=$?
python3 scripts/validate_config.py --root . --json >"$bundle/configuration.stdout.json" 2>"$bundle/configuration.stderr.txt"; configuration_exit=$?
bash scripts/verify_project.sh >"$bundle/repository-verification.stdout.txt" 2>"$bundle/repository-verification.stderr.txt"; repository_exit=$?

overall=0
for code in "$tests_exit" "$schema_exit" "$preflight_exit" "$apply_exit" "$import_exit" "$postgres_verify_exit" "$provenance_negative_control_exit" "$governance_exit" "$configuration_exit" "$repository_exit"; do [[ "$code" -eq 0 ]] || overall=1; done
{
  printf 'm2_tests=%s\n' "$tests_exit"
  printf 'postgres_schema=%s\n' "$schema_exit"
  printf 'postgres_preflight=%s\n' "$preflight_exit"
  printf 'postgres_schema_apply=%s\n' "$apply_exit"
  printf 'postgres_import=%s\n' "$import_exit"
  printf 'postgres_verify=%s\n' "$postgres_verify_exit"
  printf 'postgres_provenance_negative_control=%s\n' "$provenance_negative_control_exit"
  printf 'governance=%s\n' "$governance_exit"
  printf 'configuration=%s\n' "$configuration_exit"
  printf 'repository_verification=%s\n' "$repository_exit"
  printf 'overall=%s\n' "$overall"
} >"$bundle/exit-codes.txt"
if [[ "$overall" -eq 0 && "$dirty_worktree" == false ]]; then
  summary='FOREX_M2_PROOF_OK: canonical historical-data contracts, private T480 shared-PostgreSQL migration and retained M1 snapshot import, point-in-time validation, governance, configuration, and repository verification passed.'
else
  summary='FOREX_M2_PROOF_FAILED: inspect retained raw outputs and worktree declaration.'
fi
printf '%s\n' "$summary" >"$bundle/summary.txt"

export FOREX_M2_BUNDLE="$bundle" FOREX_M2_REVISION="$git_revision" FOREX_M2_DIRTY="$dirty_worktree" FOREX_M2_CONFIG="$configuration_fingerprint" FOREX_M2_OVERALL="$overall" FOREX_M2_SUMMARY="$summary"
python3 - <<'PY'
import hashlib, json, os
from datetime import datetime, timezone
from pathlib import Path

bundle = Path(os.environ['FOREX_M2_BUNDLE'])
artifacts = [{"path": p.name, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(bundle.iterdir()) if p.is_file()]
manifest = {
  "schema_version": "1.0.0", "milestone_id": "M2",
  "captured_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
  "git_revision": os.environ['FOREX_M2_REVISION'], "dirty_worktree": os.environ['FOREX_M2_DIRTY'] == 'true',
  "configuration_fingerprint": os.environ['FOREX_M2_CONFIG'],
  "surface": "T480 AI Lab PostgreSQL storing the retained M1 EUR/USD H1 snapshot in the Forex-owned schema, with administrator access on the closed home LAN",
  "operation": "M2 deterministic contract and repository verification",
  "expected_result": "M2 contracts reject invalid lineage, hash, and look-ahead inputs; all declared checks exit zero.",
  "observed_result": os.environ['FOREX_M2_SUMMARY'], "exit_code": int(os.environ['FOREX_M2_OVERALL']),
  "redactions": ["No credentials, account values, positions, order data, or raw broker payload are retained."],
  "summary": os.environ['FOREX_M2_SUMMARY'], "artifacts": artifacts,
}
(bundle / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
PY
printf '%s\n' "$bundle"
exit "$overall"
