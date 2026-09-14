#!/usr/bin/env python3
"""Emit canonical facts from one verified, explicit retained BLS store."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store", type=Path, required=True, help="Explicit retained BLS event-capture-store root")
    args = parser.parse_args(argv)
    try:
        from forex.bls_retained_calendar_facts import project_retained_bls_store
        result = project_retained_bls_store(args.store)
    except (OSError, ValueError, TypeError, RuntimeError) as exc:
        print(f"retained BLS calendar projection refused: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
