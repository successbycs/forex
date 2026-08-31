#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
python3 - "$root" "$1" <<'PY'
import hashlib, json, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path

root, bundle = Path(sys.argv[1]), Path(sys.argv[2]).resolve()
manifest = json.loads((bundle / "manifest.json").read_text())
if not bundle.is_relative_to(root / "runs" / "evidence" / "M11"):
    raise SystemExit("M11 evidence bundle path is invalid")
if manifest.get("milestone_id") != "M11" or manifest.get("dirty_worktree") is not False:
    raise SystemExit("M11 evidence manifest is invalid")
if manifest.get("git_revision") != subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip():
    raise SystemExit("M11 evidence revision does not match the current revision")
captured_at = datetime.fromisoformat(manifest["captured_at"].replace("Z", "+00:00"))
if (datetime.now(timezone.utc) - captured_at).total_seconds() > 168 * 3600:
    raise SystemExit("M11 evidence is stale")
for artifact in manifest["artifacts"]:
    path = bundle / artifact["path"]
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != artifact["sha256"]:
        raise SystemExit(f"M11 artifact hash mismatch: {artifact['path']}")
n8n = json.loads((bundle / "n8n-execution.json").read_text())
postgres = json.loads((bundle / "postgres-data.json").read_text())
schema = json.loads((bundle / "postgres-schema.json").read_text())
if n8n.get("execution", {}).get("status") != "success":
    raise SystemExit("M11 n8n execution was not successful")
if "FOREX_M11_GDELT_DATA_VERIFY_OK" not in postgres.get("result", {}).get("stdout", ""):
    raise SystemExit("M11 data result is absent")
if "complete_interval_coverage=true" not in postgres["result"]["stdout"]:
    raise SystemExit("M11 evidence does not establish all 96 closed-day source observations")
if "no_article_columns=true" not in postgres["result"]["stdout"] or "provenance_linkage_ok=true" not in postgres["result"]["stdout"]:
    raise SystemExit("M11 safety or provenance boundary failed")
if "FOREX_M11_GDELT_SCHEMA_VERIFY_OK" not in schema.get("result", {}).get("stdout", ""):
    raise SystemExit("M11 schema result is absent")
if "FOREX_M11_PROOF_OK" not in (bundle / "summary.txt").read_text():
    raise SystemExit("M11 proof marker is absent")
print("FOREX_M11_EVIDENCE_VERIFIED")
PY
