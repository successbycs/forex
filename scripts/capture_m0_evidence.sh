#!/usr/bin/env bash
set -uo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

run_id="$(date -u +%Y%m%dT%H%M%SZ)"
bundle="${1:-$repo_root/runs/evidence/M0/$run_id}"
mkdir -p "$bundle"
temporary_environment="$(mktemp -d)"
trap 'rm -rf -- "$temporary_environment"' EXIT

started_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
if git_revision="$(git rev-parse --verify HEAD 2>/dev/null)"; then
  :
else
  git_revision="UNBORN"
fi
material_changes="$(
  git status --porcelain --untracked-files=all 2>/dev/null \
    | sed -E 's/^.. //' \
    | grep -Ev '^(project_state\.json|runs/run_history\.json)$' \
    || true
)"
if [[ "$git_revision" == "UNBORN" || -n "$material_changes" ]]; then
  dirty_worktree=true
else
  dirty_worktree=false
fi
configuration_fingerprint="$(python3 scripts/forex_milestones.py status --json | python3 -c 'import json,sys; print(json.load(sys.stdin)["configuration_fingerprint"])')"

python3 -m venv "$temporary_environment/venv" >"$bundle/venv.stdout.txt" 2>"$bundle/venv.stderr.txt"
venv_exit=$?

if [[ $venv_exit -eq 0 ]]; then
  "$temporary_environment/venv/bin/python" -m pip install -e '.[dev]' >"$bundle/install.stdout.txt" 2>"$bundle/install.stderr.txt"
  install_exit=$?
else
  install_exit=125
  : >"$bundle/install.stdout.txt"
  printf 'Skipped because virtual-environment creation failed.\n' >"$bundle/install.stderr.txt"
fi

if [[ $install_exit -eq 0 ]]; then
  "$temporary_environment/venv/bin/forex-milestones" --root "$repo_root" validate >"$bundle/governance.stdout.txt" 2>"$bundle/governance.stderr.txt"
  governance_exit=$?
  "$temporary_environment/venv/bin/forex-config" --root "$repo_root" --json >"$bundle/configuration.stdout.txt" 2>"$bundle/configuration.stderr.txt"
  configuration_exit=$?
  "$temporary_environment/venv/bin/python" -m pytest -q >"$bundle/tests.stdout.txt" 2>"$bundle/tests.stderr.txt"
  tests_exit=$?
  "$temporary_environment/venv/bin/python" -m pip freeze >"$bundle/dependencies.txt" 2>&1
else
  governance_exit=125
  configuration_exit=125
  tests_exit=125
  : >"$bundle/governance.stdout.txt"
  printf 'Skipped because package installation failed.\n' >"$bundle/governance.stderr.txt"
  : >"$bundle/tests.stdout.txt"
  printf 'Skipped because package installation failed.\n' >"$bundle/tests.stderr.txt"
  : >"$bundle/configuration.stdout.txt"
  printf 'Skipped because package installation failed.\n' >"$bundle/configuration.stderr.txt"
  : >"$bundle/dependencies.txt"
fi

bash scripts/verify_project.sh >"$bundle/repository-verification.stdout.txt" 2>"$bundle/repository-verification.stderr.txt"
repository_exit=$?
overall_exit=0
for code in "$venv_exit" "$install_exit" "$governance_exit" "$configuration_exit" "$tests_exit" "$repository_exit"; do
  if [[ "$code" -ne 0 ]]; then
    overall_exit=1
  fi
done

{
  printf 'venv=%s\n' "$venv_exit"
  printf 'install=%s\n' "$install_exit"
  printf 'governance=%s\n' "$governance_exit"
  printf 'configuration=%s\n' "$configuration_exit"
  printf 'tests=%s\n' "$tests_exit"
  printf 'repository_verification=%s\n' "$repository_exit"
  printf 'overall=%s\n' "$overall_exit"
} >"$bundle/exit-codes.txt"

if [[ "$overall_exit" -eq 0 ]]; then
  summary="FOREX_M0_PROOF_OK: dependency-isolated installation, typed configuration, governance validation, non-empty tests, and repository verification passed in a fresh temporary virtual environment."
else
  summary="FOREX_M0_PROOF_FAILED: one or more clean-environment checks failed; inspect retained raw output."
fi
printf '%s\n' "$summary" >"$bundle/summary.txt"

finished_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
export FOREX_BUNDLE="$bundle"
export FOREX_CAPTURED_AT="$finished_at"
export FOREX_GIT_REVISION="$git_revision"
export FOREX_DIRTY_WORKTREE="$dirty_worktree"
export FOREX_CONFIG_FINGERPRINT="$configuration_fingerprint"
export FOREX_OVERALL_EXIT="$overall_exit"
export FOREX_SUMMARY="$summary"
export FOREX_STARTED_AT="$started_at"

python3 - <<'PY'
import hashlib
import json
import os
from pathlib import Path

bundle = Path(os.environ["FOREX_BUNDLE"])
artifacts = []
for path in sorted(bundle.glob("*.txt")):
    artifacts.append({"path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
manifest = {
    "schema_version": "1.0.0",
    "milestone_id": "M0",
    "captured_at": os.environ["FOREX_CAPTURED_AT"],
    "git_revision": os.environ["FOREX_GIT_REVISION"],
    "dirty_worktree": os.environ["FOREX_DIRTY_WORKTREE"] == "true",
    "configuration_fingerprint": os.environ["FOREX_CONFIG_FINGERPRINT"],
    "surface": "fresh temporary Python environment",
    "operation": f"M0 clean-environment verification started {os.environ['FOREX_STARTED_AT']}",
    "expected_result": "Install, governance validation, tests, and repository verification all exit zero.",
    "observed_result": os.environ["FOREX_SUMMARY"],
    "exit_code": int(os.environ["FOREX_OVERALL_EXIT"]),
    "redactions": ["Temporary environment path is not retained."],
    "summary": os.environ["FOREX_SUMMARY"],
    "artifacts": artifacts,
}
(bundle / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
PY

printf '%s\n' "$bundle"
exit "$overall_exit"
