#!/usr/bin/env python3
"""Quarantine one already-retained late BLS capture without rewriting history."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store", type=Path, required=True)
    parser.add_argument("--capture-id", required=True)
    args = parser.parse_args()
    try:
        from forex.event_capture_store import isolate_late_capture
        marker = isolate_late_capture(args.store, capture_id=args.capture_id)
        print(json.dumps({
            "schema_version": "forex.bls-isolation-command.v1",
            "isolation": marker,
            "coverage_status": "UNKNOWN",
            "execution_authority": False,
        }, sort_keys=True, allow_nan=False))
    except (OSError, ValueError, TypeError, OverflowError, RuntimeError) as exc:
        print(f"BLS capture isolation refused: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
