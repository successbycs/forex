#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root"
export PYTHONPATH="$root/src${PYTHONPATH:+:$PYTHONPATH}"
bundle="${1:-runs/evidence/M20/$(date -u +%Y%m%dT%H%M%SZ)}"
mkdir -p "$bundle"

# A clean revision is required before the only broker-facing command below.
git diff --quiet
python3 -m pytest tests/milestones/test_m20_demo_trading.py >"$bundle/tests.txt" 2>&1
python3 scripts/forex_milestones.py validate >"$bundle/governance.txt" 2>&1
python3 scripts/validate_config.py --root "$root" --json >"$bundle/configuration.json"

# This is deliberately the sole external action.  The adapter exposes no
# parameters: its committed fixed operation owns the server, symbol, lease,
# proposal-first rule, and bounded execution contract.
python3 scripts/t480_adapter.py execute --operation m20_demo_trading_session >"$bundle/demo-trading-operation.json"
git rev-parse HEAD >"$bundle/revision.txt"
python3 scripts/m20_demo_evidence_contract.py capture --root "$root" --bundle "$bundle"

echo "$bundle"
