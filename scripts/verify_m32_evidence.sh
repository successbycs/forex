#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root"
[[ $# -eq 1 ]] || { echo 'usage: verify_m32_evidence.sh <bundle>' >&2; exit 2; }
exec python3 scripts/m32_quality_assessment.py verify --bundle "$1"
