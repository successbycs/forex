#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
test "$#" -eq 1
python3 "$root/scripts/m20_demo_evidence_contract.py" verify --root "$root" --bundle "$1"
