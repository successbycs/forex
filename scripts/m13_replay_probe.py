#!/usr/bin/env python3
"""Fixed M13 T480 replay drill; no trading or caller supplied input."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/'src'))
from forex.replay import align_at_cutoff
bars=[{'time_utc':'2026-09-01T00:00:00Z','available_at_utc':'2026-09-01T01:00:00Z'},{'time_utc':'2026-09-01T01:00:00Z','available_at_utc':'2026-09-01T02:00:00Z'}]
contexts=[{'available_at_utc':'2026-09-01T01:15:00Z'},{'available_at_utc':'2026-09-01T03:00:00Z'}]
result=align_at_cutoff(bars,contexts,'2026-09-01T02:00:00Z')
assert result == {'cutoff_utc':'2026-09-01T02:00:00Z','bar_count':2,'context_count':1,'latest_bar_utc':'2026-09-01T01:00:00Z','no_lookahead':True}
print(json.dumps({'marker':'FOREX_M13_REPLAY_PROBE_OK','result':result},separators=(',',':')))
