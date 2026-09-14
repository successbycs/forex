#!/usr/bin/env python3
"""Qualify supplied retained primary-event source observations; never fetch or trade."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from forex.primary_event_context import PrimaryEventContextError, load_contract, qualify_context

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, default=ROOT / "config" / "primary_event_context.json")
    parser.add_argument("--observations", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        observations = json.loads(args.observations.read_bytes())
        report = qualify_context(contract=load_contract(args.contract), observations=observations)
    except (OSError, json.JSONDecodeError, PrimaryEventContextError) as exc:
        print(f"primary event context refused: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, sort_keys=True, separators=(",", ":"), allow_nan=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
