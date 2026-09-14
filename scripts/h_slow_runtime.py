#!/usr/bin/env python3
"""Evaluate retained H_SLOW runtime inputs; emits JSON and never submits orders."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from forex.h_slow_runtime import evaluate_runtime_observation


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate field: {key}")
        result[key] = value
    return result


def _constant(value):
    raise ValueError(f"nonfinite constant: {value}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="retained JSON evaluation arguments")
    args = parser.parse_args()
    try:
        payload = json.loads(args.input.read_bytes(), object_pairs_hook=_object, parse_constant=_constant)
        if not isinstance(payload, dict):
            raise ValueError("evaluation arguments must be a JSON object")
        result = evaluate_runtime_observation(**payload)
        print(json.dumps(result, sort_keys=True, allow_nan=False))
    except (OSError, ValueError, TypeError) as exc:
        print(f"H_SLOW runtime evaluation refused: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
