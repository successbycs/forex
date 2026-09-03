#!/usr/bin/env bash
# Deprecated compatibility entry point.  M20 is now a bounded Demo trading
# proof, not an Ollama historical evaluation.
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
exec "$root/scripts/capture_m20_demo_evidence.sh" "$@"
