#!/usr/bin/env python3
"""Fixed T480 M15 historical baseline drill; no caller input or order surface."""
from __future__ import annotations
import json, os, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from forex.daily_hypothesis import advisory, train_baseline

query = """SELECT close, high, low FROM forex.price_bar
WHERE snapshot_id='m2-m1-eurusd-h1-720'
  AND time_utc <= '2026-09-01T08:00:00Z'
  AND available_at_utc <= '2026-09-01T08:00:00Z'
ORDER BY time_utc;"""
command = ["docker", "compose", "-f", "/home/chris/projects/cs-ai-lab-infra/compose.yaml", "exec", "-T", "postgres", "psql", "-At", "-F", "|", "-U", os.environ["POSTGRES_USER"], "-d", os.environ["POSTGRES_DB"], "-c", query]
result = subprocess.run(command, check=True, capture_output=True, text=True)
bars = [{"close": a, "high": b, "low": c} for line in result.stdout.splitlines() if line for a, b, c in [line.split("|")]]
model = train_baseline(bars)
output = advisory(bars[-3:], model=model)
assert len(bars) == 720 and output["research_only"] and output["action"] in {"BUY", "SELL", "NO_TRADE"}
print(json.dumps({"marker": "FOREX_M15_BASELINE_PROBE_OK", "bars": len(bars), "model": model, "advisory": output, "snapshot": "m2-m1-eurusd-h1-720", "source": "gomarketsmu-demo-m1"}, separators=(",", ":")))
