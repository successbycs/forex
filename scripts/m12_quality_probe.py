#!/usr/bin/env python3
"""Fixed M12 T480 quality drill; no caller-supplied data or commands."""
from __future__ import annotations
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from forex.quality import normalise

good = {"observation_id":"m12-good","source_id":"fixture","observed_at_utc":"2026-09-01T03:00:00Z","available_at_utc":"2026-09-01T03:15:00Z","payload_sha256":"sha256:" + "a" * 64}
accepted, quarantined = normalise([good, good, {**good, "observation_id":"m12-late", "available_at_utc":"2026-09-01T05:00:00Z"}, {"observation_id":"m12-bad"}], "2026-09-01T04:00:00Z")
assert len(accepted) == 1 and {item["reason"] for item in quarantined} == {"DUPLICATE", "LATE_OR_LOOKAHEAD", "MISSING_REQUIRED_FIELD"}
print(json.dumps({"marker":"FOREX_M12_QUALITY_PROBE_OK","accepted":len(accepted),"quarantined":quarantined}, separators=(",", ":")))
