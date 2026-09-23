#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root"
[[ $# -eq 1 ]] || { echo 'usage: verify_m33_evidence.sh <bundle>' >&2; exit 2; }
exec python3 scripts/m33_pro_forma_evidence.py verify --bundle "$1"
