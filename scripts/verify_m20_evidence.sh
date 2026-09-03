#!/usr/bin/env bash
# Deprecated compatibility entry point.  It intentionally validates only the
# active M20 Demo-trading evidence shape.
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
exec "$root/scripts/verify_m20_demo_evidence.sh" "$@"
