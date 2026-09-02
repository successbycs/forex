#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
python3 - "$root" "$1" <<'PY'
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

root, bundle = Path(sys.argv[1]), Path(sys.argv[2]).resolve()
manifest = json.loads((bundle / "manifest.json").read_text())
assert bundle.is_relative_to(root / "runs/evidence/M18")
assert manifest["milestone_id"] == "M18" and manifest["dirty_worktree"] is False
assert manifest["git_revision"] == subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
assert (datetime.now(timezone.utc) - datetime.fromisoformat(manifest["captured_at"].replace("Z", "+00:00"))).total_seconds() < 168 * 3600
for artifact in manifest["artifacts"]:
    path = bundle / artifact["path"]
    assert path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == artifact["sha256"]
probe = json.loads((bundle / "ollama-probe.json").read_text())
result = json.loads(probe["result"]["stdout"])
binding = json.loads((bundle / "source-model-prompt.json").read_text())
assert probe["ok"] and result["marker"] == "FOREX_M18_OLLAMA_PROBE_OK"
assert result["model"] == binding["model"] == "qwen2.5:3b"
assert result["source"] == binding["source"] == "DEMO_ONLY_HISTORICAL"
for key in ("model_definition_sha256", "input_context_sha256", "output_sha256"):
    assert result[key] == binding[key] and result[key].startswith("sha256:")
assert result["prompt_template_version"] == binding["prompt_template_version"] == "forex.m18.sentiment.v1"
assert result["response"]["sentiment"] in {"POSITIVE", "NEGATIVE", "NEUTRAL", "ABSTAIN"}
assert result["response"]["research_only"] is True and result["response"]["order_capability"] is False
assert result["order_capability"] is False and result["live_trading_capability"] is False
assert "FOREX_M18_PROOF_OK" in (bundle / "summary.txt").read_text()
print("FOREX_M18_EVIDENCE_VERIFIED")
PY
