#!/usr/bin/env python3
"""Validate one n8n BLS handoff; no network, storage, or trading action."""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from forex.bls_n8n_envelope import BLSN8nEnvelopeError, build_observation, parse_handoff_json

try:
    value = parse_handoff_json(sys.stdin.buffer.read())
    capture_id, raw = build_observation(value)
    import json
    print(json.dumps({"capture_id": capture_id, "observation": json.loads(raw), "execution_authority": False}, separators=(",", ":"), allow_nan=False))
except (BLSN8nEnvelopeError, ValueError) as exc:
    print(f"FOREX_BLS_N8N_HANDOFF_REFUSED: {exc}", file=sys.stderr)
    raise SystemExit(2)
