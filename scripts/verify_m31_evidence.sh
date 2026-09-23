#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: $0 runs/evidence/M31/<timestamp>" >&2
  exit 2
fi

bundle=$1
if python3 - "$bundle/manifest.json" <<'PY'
import json, sys
try:
    value = json.load(open(sys.argv[1]))
    raise SystemExit(0 if value.get("schema_version") == "1.0.0" else 1)
except (OSError, ValueError):
    raise SystemExit(1)
PY
then
  exec python3 scripts/m31_retained_evidence.py verify --bundle "$bundle"
fi
PYTHONPATH=src python3 - "$bundle" <<'PY'
from pathlib import Path
import json
import sys
from forex.m31_evidence import M31EvidenceError, verify_bundle
try:
    print(json.dumps(verify_bundle(Path(sys.argv[1])), sort_keys=True))
except M31EvidenceError as exc:
    raise SystemExit(f"M31 evidence verification refused: {exc}")
PY
