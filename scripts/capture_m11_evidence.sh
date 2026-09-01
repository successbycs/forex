#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root"
export PYTHONPATH="$root/src${PYTHONPATH:+:$PYTHONPATH}"

bundle="${1:-runs/evidence/M11/$(date -u +%Y%m%dT%H%M%SZ)}"
mkdir -p "$bundle"

python3 -m pytest -q tests/milestones/test_m11.py tests/test_n8n_forex_adapter.py >"$bundle/tests.txt" 2>&1
python3 scripts/forex_milestones.py validate >"$bundle/governance.txt" 2>&1
python3 scripts/n8n_forex_adapter.py recent-execution >"$bundle/n8n-execution.json"
python3 scripts/postgres_pgvector_adapter.py forex-m11-verify-schema >"$bundle/postgres-schema.json"
python3 scripts/postgres_pgvector_adapter.py forex-m11-r1-verify-hour >"$bundle/postgres-data.json"
git rev-parse HEAD >"$bundle/revision.txt"
git diff --quiet

python3 - "$bundle" <<'PY'
import hashlib, json, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path

bundle = Path(sys.argv[1])
n8n = json.loads((bundle / "n8n-execution.json").read_text())
postgres = json.loads((bundle / "postgres-data.json").read_text())
execution = n8n.get("execution", {})
if not n8n.get("ok") or execution.get("status") != "success":
    raise SystemExit("M11 requires a successful T480 n8n execution")
if not postgres.get("ok") or "FOREX_M11_R1_HOUR_VERIFY_OK" not in postgres.get("result", {}).get("stdout", ""):
    raise SystemExit("M11 PostgreSQL data verification did not pass")
required = ("source_count=4", "quarters_complete=true", "hashes_present=true", "availability_present=true", "one_aggregate=true", "lineage_ok=true")
if not all(marker in postgres["result"]["stdout"] for marker in required):
    raise SystemExit("M11 did not retain one complete provenance-linked closed-hour aggregate")
status = json.loads(subprocess.check_output(["python3", "scripts/forex_milestones.py", "status", "--json"]))
(bundle / "summary.txt").write_text("FOREX_M11_PROOF_OK\n")
artifacts = [{"path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()} for path in sorted(bundle.iterdir()) if path.is_file()]
manifest = {
    "schema_version": "1.0.0",
    "milestone_id": "M11",
    "captured_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    "git_revision": (bundle / "revision.txt").read_text().strip(),
    "dirty_worktree": False,
    "configuration_fingerprint": status["configuration_fingerprint"],
    "surface": "T480 n8n GDELT workflow and normalised H1 aggregate records",
    "operation": "fixed M11 n8n execution summary plus fixed PostgreSQL verification",
    "expected_result": "successful independent n8n hourly stage/finalise flow and one provenance-linked derived GDELT H1 context record",
    "observed_result": "FOREX_M11_PROOF_OK",
    "exit_code": 0,
    "redactions": ["No article text, credentials, accounts, signals or order data retained."],
    "summary": "FOREX_M11_PROOF_OK",
    "artifacts": artifacts,
}
(bundle / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
PY

echo "$bundle"
