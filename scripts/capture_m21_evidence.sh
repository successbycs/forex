#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root"
export PYTHONPATH="$root/src${PYTHONPATH:+:$PYTHONPATH}"
bundle="${1:-runs/evidence/M21/$(date -u +%Y%m%dT%H%M%SZ)}"
mkdir -p "$bundle"

git diff --quiet
python3 -m pytest -q tests/milestones/test_m21.py >"$bundle/tests.txt" 2>&1
python3 scripts/forex_milestones.py validate >"$bundle/governance.txt" 2>&1
python3 - "$bundle" <<'PY'
import json, sys
from pathlib import Path
from forex.event_quality import fixture_records, qualify_events

result = qualify_events(fixture_records(), "2026-10-15T00:00:00Z")
assert [item["event_id"] for item in result["accepted"]] == ["ecb-hicp-2026-10"]
assert result["accepted"][0]["revision"] == 2
Path(sys.argv[1], "event-quality-drill.json").write_text(json.dumps(result, indent=2) + "\n")
PY
git rev-parse HEAD >"$bundle/revision.txt"
python3 - "$bundle" <<'PY'
import hashlib, json, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path

bundle = Path(sys.argv[1])
status = json.loads(subprocess.check_output(["python3", "scripts/forex_milestones.py", "status", "--json"]))
drill = json.loads((bundle / "event-quality-drill.json").read_text())
assert drill["accepted"] and drill["quarantined"]
(bundle / "summary.txt").write_text("FOREX_M21_PROOF_OK\n")
artifacts = [{"path": item.name, "sha256": hashlib.sha256(item.read_bytes()).hexdigest()} for item in sorted(bundle.iterdir()) if item.is_file()]
manifest = {
    "schema_version": "1.0.0", "milestone_id": "M21",
    "captured_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    "git_revision": (bundle / "revision.txt").read_text().strip(), "dirty_worktree": False,
    "configuration_fingerprint": status["configuration_fingerprint"],
    "surface": "historical economic-event quality-control pipeline",
    "operation": "fixed source-labelled FRED/ECB event-quality operational drill",
    "expected_result": "latest usable revision accepted; unsafe records quarantined",
    "observed_result": "FOREX_M21_PROOF_OK", "exit_code": 0,
    "redactions": ["No credentials, forecasts, accounts, prices, positions, or orders retained."],
    "summary": "FOREX_M21_PROOF_OK", "artifacts": artifacts,
}
(bundle / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
PY
echo "$bundle"
