#!/usr/bin/env python3
"""Inspect a local immutable M20 assessment spool without changing it."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from forex.m20_assessment_spool import AssessmentSpoolError, read_immutable_spool  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--listener-release-id", required=True)
    args = parser.parse_args(argv)
    try:
        print(json.dumps(read_immutable_spool(args.root, listener_release_id=args.listener_release_id),
                         sort_keys=True, separators=(",", ":"), allow_nan=False))
    except (OSError, ValueError, TypeError) as exc:
        print(f"M20 assessment spool inspection refused: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
