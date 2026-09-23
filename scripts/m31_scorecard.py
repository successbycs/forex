#!/usr/bin/env python3
"""Render a pure M31 scorecard from immutable local input files."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from forex.m31_scorecard import M31ScorecardInputError, render_terminal, scorecard_from_raw  # noqa: E402


def _read(path: Path) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise M31ScorecardInputError(f"input is not a regular file: {path}")
    return path.read_bytes()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", required=True, type=Path)
    parser.add_argument("--completeness", required=True, type=Path)
    parser.add_argument("--lifecycle", required=True, type=Path)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)
    try:
        scorecard = scorecard_from_raw(protocol_raw=_read(args.protocol), completeness_raw=_read(args.completeness), lifecycle_raw=_read(args.lifecycle))
    except (OSError, M31ScorecardInputError) as exc:
        print(f"M31 scorecard refused: {exc}", file=sys.stderr)
        return 2
    print(render_terminal(scorecard) if args.format == "text" else json.dumps(scorecard, indent=2, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
