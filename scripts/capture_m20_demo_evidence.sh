#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root"
export PYTHONPATH="$root/src${PYTHONPATH:+:$PYTHONPATH}"
bundle="${1:-runs/evidence/M20/$(date -u +%Y%m%dT%H%M%SZ)}"
mkdir -p "$(dirname "$bundle")"
# Captured bytes are immutable, including failed or incomplete captures.
mkdir "$bundle"

# A clean implementation/configuration revision is required before the only
# broker-facing command below.  Mutable governance state and append-only run
# history are deliberately excluded by the milestone store and must not make
# a valid post-remediation capture impossible.
material_changes="$(git status --porcelain --untracked-files=all | awk 'substr($0,4) != "project_state.json" && substr($0,4) != "runs/run_history.json"')"
test -z "$material_changes"
python3 -m pytest tests/milestones/test_m20_demo_trading.py >"$bundle/tests.txt" 2>&1
python3 scripts/forex_milestones.py validate >"$bundle/governance.txt" 2>&1
bash scripts/verify_project.sh >"$bundle/repository-verification.txt" 2>&1
python3 scripts/validate_config.py --root "$root" --json >"$bundle/configuration.json"
# The runtime-config digest is useful context, but evidence must bind the
# complete governed configuration set used by the adapter and milestone state.
python3 - "$bundle/configuration.json" <<'PY'
import json
import subprocess
import sys

path = sys.argv[1]
configuration = json.loads(open(path, encoding="utf-8").read())
runtime_fingerprint = configuration["configuration_fingerprint"]
state = json.loads(subprocess.check_output(
    ["python3", "scripts/forex_milestones.py", "status", "--json"], text=True
))
configuration["runtime_configuration_fingerprint"] = runtime_fingerprint
configuration["configuration_fingerprint"] = state["configuration_fingerprint"]
open(path, "w", encoding="utf-8").write(json.dumps(configuration, indent=2) + "\n")
PY

# This is deliberately the sole external action.  The adapter exposes no
# parameters: its committed fixed operation owns the server, symbol, lease,
# proposal-first rule, and bounded execution contract.
python3 scripts/t480_adapter.py execute --operation m20_demo_trading_session >"$bundle/demo-trading-operation.json"
python3 scripts/postgres_pgvector_adapter.py forex-m20-lifecycle-summary >"$bundle/lifecycle-summary.json"
python3 scripts/t480_adapter.py execute --operation m20_listener_diagnostics >"$bundle/listener-diagnostics.json"
python3 scripts/t480_adapter.py execute --operation m20_listener_status >"$bundle/listener-status.json"
git rev-parse HEAD >"$bundle/revision.txt"
python3 scripts/m20_demo_evidence_contract.py capture --root "$root" --bundle "$bundle"

echo "$bundle"
