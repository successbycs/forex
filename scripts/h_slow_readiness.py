#!/usr/bin/env python3
"""Produce one local, submission-disabled H_SLOW readiness report."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON field: {key}")
        result[key] = value
    return result


def _constant(value):
    raise ValueError(f"nonfinite JSON constant: {value}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="retained H_SLOW readiness JSON")
    args = parser.parse_args()
    try:
        from forex.h_slow_readiness import evaluate_h_slow_readiness
        payload = json.loads(args.input.read_bytes(), object_pairs_hook=_pairs, parse_constant=_constant)
        result = evaluate_h_slow_readiness(payload)
        print(json.dumps(result, sort_keys=True, allow_nan=False))
        return 0
    except (OSError, ValueError, TypeError, OverflowError) as exc:
        print(f"H_SLOW readiness refused: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
