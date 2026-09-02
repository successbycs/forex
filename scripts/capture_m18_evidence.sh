#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root"
export PYTHONPATH="$root/src${PYTHONPATH:+:$PYTHONPATH}"
bundle="${1:-runs/evidence/M18/$(date -u +%Y%m%dT%H%M%SZ)}"
mkdir -p "$bundle"

git diff --quiet
python3 -m pytest -q tests/milestones/test_m18.py >"$bundle/tests.txt" 2>&1
python3 scripts/forex_milestones.py validate >"$bundle/governance.txt" 2>&1
python3 scripts/validate_config.py --root "$root" --json >"$bundle/configuration.json"
python3 scripts/postgres_pgvector_adapter.py forex-m18-ollama-probe >"$bundle/ollama-probe.json"
git rev-parse HEAD >"$bundle/revision.txt"

python3 - "$bundle" <<'PY'
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

b = Path(sys.argv[1])
probe = json.loads((b / "ollama-probe.json").read_text())
result = json.loads(probe["result"]["stdout"])
assert probe["ok"] and result["marker"] == "FOREX_M18_OLLAMA_PROBE_OK"
assert result["model"] == "qwen2.5:3b"
assert result["prompt_template_version"] == "forex.m18.sentiment.v1"
assert result["model_definition_sha256"].startswith("sha256:")
assert result["input_context_sha256"].startswith("sha256:")
assert result["output_sha256"].startswith("sha256:")
assert result["source"] == "DEMO_ONLY_HISTORICAL"
assert result["order_capability"] is False and result["live_trading_capability"] is False
assert result["response"]["order_capability"] is False and result["response"]["research_only"] is True
(b / "source-model-prompt.json").write_text(json.dumps({
    "source": result["source"],
    "model": result["model"],
    "model_definition_sha256": result["model_definition_sha256"],
    "prompt_template_version": result["prompt_template_version"],
    "input_context_sha256": result["input_context_sha256"],
    "output_sha256": result["output_sha256"],
}, indent=2) + "\n")
(b / "summary.txt").write_text("FOREX_M18_PROOF_OK\n")
status = json.loads(subprocess.check_output(["python3", "scripts/forex_milestones.py", "status", "--json"]))
artifacts = [
    {"path": f.name, "sha256": hashlib.sha256(f.read_bytes()).hexdigest()}
    for f in sorted(b.iterdir()) if f.is_file()
]
manifest = {
    "schema_version": "1.0.0",
    "milestone_id": "M18",
    "captured_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    "git_revision": (b / "revision.txt").read_text().strip(),
    "dirty_worktree": False,
    "configuration_fingerprint": status["configuration_fingerprint"],
    "surface": "offline Ollama sentiment-assistance validation workflow",
    "operation": "fixed T480 M18 Ollama probe",
    "expected_result": "schema-constrained research response or abstention from qwen2.5:3b",
    "observed_result": "FOREX_M18_PROOF_OK",
    "exit_code": 0,
    "redactions": ["No account, credential, order, live-server or raw model prompt retained."],
    "summary": "FOREX_M18_PROOF_OK",
    "artifacts": artifacts,
}
(b / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
PY

echo "$bundle"
