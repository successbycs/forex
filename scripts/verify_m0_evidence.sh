#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: $0 BUNDLE" >&2
  exit 2
fi

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
bundle="$(cd "$1" 2>/dev/null && pwd)" || { echo "evidence bundle does not exist" >&2; exit 2; }

case "$bundle" in
  "$repo_root"/runs/evidence/M0/*) ;;
  *) echo "evidence bundle is outside runs/evidence/M0" >&2; exit 2 ;;
esac

python3 - "$repo_root" "$bundle" <<'PY'
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone

root = Path(sys.argv[1]).resolve()
bundle = Path(sys.argv[2]).resolve()
sys.path.insert(0, str(root / "src"))
from forex.t480_dependency import inspect_dependency
from forex.evidence_runner import verify_bundle as verify_runner_bundle
from forex.m0_evidence import M0_EVIDENCE_ARTIFACTS
manifest_path = bundle / "manifest.json"
manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
required = {
    "schema_version", "milestone_id", "captured_at", "git_revision", "dirty_worktree",
    "configuration_fingerprint", "surface", "operation", "expected_result",
    "observed_result", "exit_code", "redactions", "summary", "external_dependencies", "artifacts",
}
missing = required - manifest.keys()
if missing:
    raise SystemExit(f"manifest missing fields: {sorted(missing)}")
if manifest["schema_version"] != "1.0.0" or manifest["milestone_id"] != "M0":
    raise SystemExit("manifest schema or milestone mismatch")
registry = json.loads((root / "milestone_registry.json").read_text(encoding="utf-8"))
m0 = next(item for item in registry["milestones"] if item["milestone_id"] == "M0")
if manifest["surface"] != m0["real_world_proof"]["surface"]:
    raise SystemExit("execution surface mismatch")
if manifest["exit_code"] != 0:
    raise SystemExit("captured operation failed")
if manifest["dirty_worktree"] is not False:
    raise SystemExit("captured worktree was dirty")
captured_at = datetime.fromisoformat(manifest["captured_at"].replace("Z", "+00:00"))
age_hours = (datetime.now(timezone.utc) - captured_at).total_seconds() / 3600
if age_hours < -0.1 or age_hours > m0["real_world_proof"]["freshness_hours"]:
    raise SystemExit("evidence is outside the declared freshness window")
state = json.loads((root / "project_state.json").read_text(encoding="utf-8"))
fingerprint = hashlib.sha256()
for relative in sorted(state["governed_configuration_paths"]):
    fingerprint.update(relative.encode("utf-8"))
    fingerprint.update(b"\0")
    fingerprint.update((root / relative).read_bytes())
    fingerprint.update(b"\0")
current_fingerprint = f"sha256:{fingerprint.hexdigest()}"
if manifest["configuration_fingerprint"] != current_fingerprint:
    raise SystemExit("configuration fingerprint mismatch")
revision = subprocess.run(
    ["git", "rev-parse", "HEAD"], cwd=root, text=True, capture_output=True, check=False
)
current_revision = revision.stdout.strip() if revision.returncode == 0 else "UNBORN"
if manifest["git_revision"] != current_revision:
    raise SystemExit("Git revision mismatch")
adapter_config = json.loads((root / "config" / "t480.json").read_text(encoding="utf-8"))
dependency = inspect_dependency(adapter_config)
if not dependency["ok"]:
    raise SystemExit("T480 shared-core dependency is not immutable: " + "; ".join(dependency["errors"]))
if manifest["external_dependencies"] != [dependency]:
    raise SystemExit("external dependency attestation mismatch")
try:
    verify_runner_bundle(root, bundle)
except Exception as exc:
    raise SystemExit(f"self-attested runner verification failed: {exc}") from exc
declared_artifacts = {artifact.get("path") for artifact in manifest["artifacts"] if isinstance(artifact, dict)}
if declared_artifacts != M0_EVIDENCE_ARTIFACTS:
    raise SystemExit("M0 evidence manifest does not contain the canonical artifact set")
for artifact in manifest["artifacts"]:
    path = (bundle / artifact["path"]).resolve()
    if not path.is_relative_to(bundle) or not path.is_file():
        raise SystemExit(f"missing or unsafe artifact: {artifact['path']}")
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != artifact["sha256"]:
        raise SystemExit(f"hash mismatch: {artifact['path']}")
combined = "".join(
    (bundle / artifact["path"]).read_text(encoding="utf-8", errors="replace")
    for artifact in manifest["artifacts"]
)
for marker in m0["real_world_proof"]["success_markers"]:
    if marker not in combined:
        raise SystemExit(f"missing success marker: {marker}")
exit_codes = (bundle / "exit-codes.txt").read_text(encoding="utf-8")
required_zeroes = {"t480_dependency=0", "venv=0", "install=0", "governance=0", "configuration=0", "tests=0", "repository_verification=0", "overall=0"}
if not required_zeroes.issubset(set(exit_codes.splitlines())):
    raise SystemExit("one or more required exit codes are absent or non-zero")
print("FOREX_M0_EVIDENCE_VERIFIED")
PY
