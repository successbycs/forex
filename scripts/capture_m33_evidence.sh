#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root"
if [[ $# -eq 0 ]]; then
  bundle="runs/evidence/M33/m33-$(date -u +%Y%m%dT%H%M%SZ)"
elif [[ $# -eq 2 && "$1" == "--bundle" ]]; then
  bundle="$2"
else
  echo 'usage: capture_m33_evidence.sh [--bundle <new-directory>]' >&2
  exit 2
fi
exec python3 scripts/m33_pro_forma_evidence.py capture --bundle "$bundle"
