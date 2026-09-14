#!/usr/bin/env python3
"""Emit a strict read-only summary of one retained M20 Demo history export."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from forex.m20_history_report import HistoryReportInputError, load_and_build_history_report  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("history", type=Path)
    arguments = parser.parse_args(argv)
    try:
        report = load_and_build_history_report(arguments.history)
    except (OSError, HistoryReportInputError) as exc:
        print(f"m20 history report: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, sort_keys=True, separators=(",", ":"), allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
