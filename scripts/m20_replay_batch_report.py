#!/usr/bin/env python3
"""Emit a read-only inventory of direct retained M20 operation exports."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from forex.m20_replay_batch import ReplayBatchInputError, build_retained_replay_batch  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path, help="trusted retained M20 evidence root")
    arguments = parser.parse_args(argv)
    try:
        report = build_retained_replay_batch(root=arguments.root)
    except (OSError, ReplayBatchInputError) as exc:
        print(f"m20 replay batch report: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, sort_keys=True, separators=(",", ":"), allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
