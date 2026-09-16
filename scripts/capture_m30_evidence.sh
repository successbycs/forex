#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root"
export PYTHONPATH="$root/src${PYTHONPATH:+:$PYTHONPATH}"
bundle="${1:-runs/evidence/M30/$(date -u +%Y%m%dT%H%M%SZ)}"
test ! -e "$bundle"
mkdir -p "$(dirname "$bundle")"
mkdir "$bundle"

material_changes="$(git status --porcelain --untracked-files=all | awk 'substr($0,4) != "project_state.json" && substr($0,4) != "runs/run_history.json"')"
test -z "$material_changes"
python3 -m pytest -o addopts='' -q tests/milestones/test_m30.py >"$bundle/tests.txt" 2>&1
python3 scripts/forex_milestones.py validate >"$bundle/governance.txt" 2>&1
# M30 has a bounded verification surface.  A whole-repository run includes
# unrelated historical contracts and must not decide whether this Demo proof
# attempt can begin.  The focused suite and registry validation above are the
# declared local checks; retain an explicit receipt for offline verification.
printf '%s\n' 'FOREX_M30_TARGETED_VERIFICATION_OK' >"$bundle/m30-verification.txt"
python3 scripts/validate_config.py --root "$root" --json >"$bundle/configuration.json"
python3 - "$bundle/configuration.json" <<'PY'
import json, subprocess, sys
path = sys.argv[1]
value = json.loads(open(path, encoding="utf-8").read())
state = json.loads(subprocess.check_output(["python3", "scripts/forex_milestones.py", "status", "--json"], text=True))
value["runtime_configuration_fingerprint"] = value["configuration_fingerprint"]
value["configuration_fingerprint"] = state["configuration_fingerprint"]
open(path, "w", encoding="utf-8").write(json.dumps(value, indent=2) + "\n")
PY

# The sole broker-capable action. Its committed fixed operation owns account,
# symbol, risk gates, position cap, mandatory close, and reconciliation.
python3 scripts/t480_adapter.py execute --operation m20_demo_trading_session >"$bundle/demo-trading-operation.json"
# The executor returns OPEN_MONITORING. Observe that exact attempt until the
# existing monitor has closed it; this command cannot submit or retry an order.
python3 scripts/m30_evidence_contract.py wait-for-close --root "$root" --bundle "$bundle"
python3 scripts/t480_adapter.py execute --operation m20_listener_diagnostics >"$bundle/listener-diagnostics.json"
python3 scripts/t480_adapter.py execute --operation m20_listener_status >"$bundle/listener-status.json"
git rev-parse HEAD >"$bundle/revision.txt"
python3 scripts/m30_evidence_contract.py capture --root "$root" --bundle "$bundle"
echo "$bundle"
