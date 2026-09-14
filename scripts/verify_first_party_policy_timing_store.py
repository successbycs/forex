#!/usr/bin/env python3
"""Read and verify a local FOMC/ECB timing store; never fetch or mutate it."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from forex.first_party_policy_source_verifier import PolicySourceVerificationError, verify_policy_timing_store


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store", required=True, type=Path, help="explicit existing local timing-store root")
    args = parser.parse_args(argv)
    try:
        result = verify_policy_timing_store(args.store)
    except PolicySourceVerificationError as exc:
        print(f"policy timing verification refused: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True, separators=(",", ":"), allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
