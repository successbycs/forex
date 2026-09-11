#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
python3 - "$root" "$1" <<'PY'
import hashlib, json, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path

root, bundle = Path(sys.argv[1]), Path(sys.argv[2]).resolve()
manifest = json.loads((bundle / "manifest.json").read_text())
assert bundle.is_relative_to(root / "runs/evidence/M21")
assert manifest["milestone_id"] == "M21" and manifest["dirty_worktree"] is False
assert manifest["git_revision"] == subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
assert (datetime.now(timezone.utc) - datetime.fromisoformat(manifest["captured_at"].replace("Z", "+00:00"))).total_seconds() < 168 * 3600
for artifact in manifest["artifacts"]:
    path = bundle / artifact["path"]
    assert path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == artifact["sha256"]
drill = json.loads((bundle / "event-quality-drill.json").read_text())
assert [item["event_id"] for item in drill["accepted"]] == ["ecb-hicp-2026-10"]
assert drill["accepted"][0]["revision"] == 2
reasons = {item["reason"] for item in drill["quarantined"]}
assert {"SUPERSEDED_REVISION", "CANCELLED", "TIME_PRECISION_INSUFFICIENT", "LOOKAHEAD", "DST_NONEXISTENT_LOCAL_TIME"} <= reasons
assert "FOREX_M21_PROOF_OK" in (bundle / "summary.txt").read_text()
print("FOREX_M21_EVIDENCE_VERIFIED")
PY
