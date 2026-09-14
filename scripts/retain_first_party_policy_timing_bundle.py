#!/usr/bin/env python3
"""Locally retain supplied FOMC/ECB calendar and timing documents; never fetch."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from forex.first_party_policy_capture import SOURCES
from forex.first_party_policy_timing_store import PolicyTimingStoreError, retain_policy_timing_bundle


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("calendar", type=Path, help="already-retained official calendar UTF-8 bytes")
    parser.add_argument("timing", type=Path, help="already-retained official timing declaration UTF-8 bytes")
    parser.add_argument("--store", type=Path, required=True, help="explicit machine-local trusted root")
    parser.add_argument("--family", choices=sorted(SOURCES), required=True)
    parser.add_argument("--target-date", required=True)
    parser.add_argument("--calendar-capture-completed-at", required=True)
    parser.add_argument("--timing-capture-completed-at", required=True)
    parser.add_argument("--revision", type=int, default=1)
    args = parser.parse_args(argv)
    try:
        result = retain_policy_timing_bundle(args.store, family_id=args.family, target_date=args.target_date,
                                             calendar_raw=args.calendar.read_bytes(),
                                             calendar_capture_completed_at_utc=args.calendar_capture_completed_at,
                                             timing_raw=args.timing.read_bytes(),
                                             timing_capture_completed_at_utc=args.timing_capture_completed_at,
                                             revision=args.revision)
    except (OSError, PolicyTimingStoreError) as exc:
        print(f"policy timing retention refused: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True, separators=(",", ":"), allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
