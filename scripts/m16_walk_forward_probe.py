#!/usr/bin/env python3
"""Fixed T480 M16 walk-forward drill; it is historical research only."""
from __future__ import annotations
import json, os, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from forex.walk_forward import evaluate_walk_forward


def query(sql: str) -> list[list[str]]:
    command = ["docker", "compose", "-f", "/home/chris/projects/cs-ai-lab-infra/compose.yaml", "exec", "-T", "postgres", "psql", "-At", "-F", "|", "-U", os.environ["POSTGRES_USER"], "-d", os.environ["POSTGRES_DB"], "-c", sql]
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    return [line.split("|") for line in result.stdout.splitlines() if line]


bars = [{"time_utc": time, "available_at_utc": available, "close": close, "high": high, "low": low} for time, available, close, high, low in query("""SELECT time_utc::text, available_at_utc::text, close, high, low FROM forex.price_bar WHERE snapshot_id='m2-m1-eurusd-h1-720' AND time_utc <= '2026-08-29T00:00:00Z' AND available_at_utc <= '2026-08-29T00:00:00Z' ORDER BY time_utc;""")]
sentiment = [{"time_utc": bucket, "available_at_utc": available} for bucket, available in query("""SELECT bucket_time_utc::text, available_at_utc::text FROM forex.gdelt_h1_aggregate WHERE bucket_time_utc <= '2026-08-29T00:00:00Z' AND available_at_utc <= '2026-08-29T00:00:00Z' ORDER BY bucket_time_utc;""")]
result = evaluate_walk_forward(bars, contexts={"macro": [], "calendar": [], "sentiment": sentiment})
assert len(bars) == 720 and result["marker"] == "FOREX_M16_WALK_FORWARD_OK" and len(result["windows"]) == 3
print(json.dumps({"marker": "FOREX_M16_WALK_FORWARD_PROBE_OK", "snapshot": "m2-m1-eurusd-h1-720", "source": "gomarketsmu-demo-m1", "evaluation": result}, separators=(",", ":")))
