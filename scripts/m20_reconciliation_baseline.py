#!/usr/bin/env python3
"""Read-only exact-identity reconciliation of retained M1 assessments to MT5 history."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from forex.m20_reconciliation_baseline import ReconciliationBaselineError, reconcile_files

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--history", type=Path, required=True)
    parser.add_argument("--assessment", type=Path, action="append", default=[])
    args = parser.parse_args(argv)
    try:
        report = reconcile_files(history_path=args.history, assessment_paths=args.assessment)
    except (OSError, ReconciliationBaselineError) as exc:
        print(f"m20 reconciliation baseline: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, sort_keys=True, separators=(",", ":"), allow_nan=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
