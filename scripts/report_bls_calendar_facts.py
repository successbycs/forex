#!/usr/bin/env python3
"""Read and validate fixed BLS calendar-fact lineage from PostgreSQL.

This command has no arguments, writes nothing, and never fetches a source,
contacts a broker, or evaluates an event/trading policy.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from forex.bls_calendar_fact_report import BLSCalendarFactReportError, build_bls_calendar_fact_report  # noqa: E402
from postgres_admin_adapter import read_bls_calendar_facts  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    if argv:
        print("BLS calendar fact report refused: this fixed read accepts no arguments", file=sys.stderr)
        return 2
    try:
        report = build_bls_calendar_fact_report(read_bls_calendar_facts())
    except (RuntimeError, TypeError, ValueError, json.JSONDecodeError, BLSCalendarFactReportError) as exc:
        print(f"BLS calendar fact report refused: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, sort_keys=True, separators=(",", ":"), allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
