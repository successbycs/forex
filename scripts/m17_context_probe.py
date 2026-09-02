#!/usr/bin/env python3
"""Fixed T480 drill for M17's offline context boundary."""
from __future__ import annotations
import json, os, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from forex.agent_context import build_context

command = ["docker", "compose", "-f", "/home/chris/projects/cs-ai-lab-infra/compose.yaml", "exec", "-T", "postgres", "psql", "-At", "-F", "|", "-U", os.environ["POSTGRES_USER"], "-d", os.environ["POSTGRES_DB"], "-c", "SELECT time_utc::text, available_at_utc::text, open, high, low, close, volume FROM forex.price_bar WHERE snapshot_id='m2-m1-eurusd-h1-720' ORDER BY time_utc LIMIT 12;"]
result = subprocess.run(command, check=True, capture_output=True, text=True)
bars = [dict(zip(("time_utc","available_at_utc","open","high","low","close","volume"), line.split("|"))) for line in result.stdout.splitlines() if line]
cutoff = bars[-1]["available_at_utc"]
context = build_context(bars=bars, cutoff_utc=cutoff, features={"source":"DEMO_ONLY_HISTORICAL"})
assert len(context["price_bars"]) == len(bars) and context["agent_authority"] == "NONE"
print(json.dumps({"marker":"FOREX_M17_CONTEXT_PROBE_OK","bars":len(bars),"context":context}, separators=(",", ":")))
