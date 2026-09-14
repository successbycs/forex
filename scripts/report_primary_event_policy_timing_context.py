#!/usr/bin/env python3
"""Read verified local policy timing evidence into primary context; no mutation."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from forex.primary_event_context import PrimaryEventContextError, load_contract
from forex.primary_event_context_integration import (
    PrimaryEventContextIntegrationError,
    report_policy_timing_context,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store", required=True, type=Path, help="explicit existing local timing-store root")
    parser.add_argument("--contract", required=True, type=Path, help="existing primary-event context contract JSON")
    args = parser.parse_args(argv)
    try:
        report = report_policy_timing_context(store_root=args.store, contract=load_contract(args.contract))
    except (PrimaryEventContextError, PrimaryEventContextIntegrationError) as exc:
        print(f"policy timing context report refused: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, sort_keys=True, separators=(",", ":"), allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
