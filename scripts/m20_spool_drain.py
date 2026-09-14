#!/usr/bin/env python3
"""Retain immutable M20 listener spool records locally; never delete source."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from forex.m20_spool_drain import drain  # noqa: E402

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spool-root", required=True, type=Path)
    parser.add_argument("--capture-root", required=True, type=Path)
    parser.add_argument("--listener-release-id", required=True)
    args = parser.parse_args(argv)
    try:
        print(json.dumps(drain(spool_root=args.spool_root, capture_root=args.capture_root,
                               listener_release_id=args.listener_release_id), sort_keys=True, allow_nan=False))
    except (OSError, ValueError, TypeError) as exc:
        print(f"M20 spool drain refused: {exc}", file=sys.stderr)
        return 2
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
