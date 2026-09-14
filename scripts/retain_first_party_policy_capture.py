#!/usr/bin/env python3
"""Retain supplied FOMC/ECB calendar bytes locally; never fetch or trade."""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from forex.first_party_policy_capture import PolicyCaptureError, SOURCES, retain_policy_capture

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Already-retained UTF-8 publisher HTML bytes")
    parser.add_argument("--store", type=Path, required=True, help="Explicit machine-local capture root")
    parser.add_argument("--capture-id", required=True)
    parser.add_argument("--family", choices=sorted(SOURCES), required=True)
    parser.add_argument("--capture-completed-at", required=True)
    args = parser.parse_args(argv)
    try:
        _, source_url, _ = SOURCES[args.family]
        result = retain_policy_capture(args.store, capture_id=args.capture_id, raw=args.input.read_bytes(),
                                       family_id=args.family, source_url=source_url,
                                       capture_completed_at_utc=args.capture_completed_at)
    except (OSError, PolicyCaptureError) as exc:
        print(f"first-party policy capture refused: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True, separators=(",", ":"), allow_nan=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
