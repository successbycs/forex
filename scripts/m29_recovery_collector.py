#!/usr/bin/env python3
"""Create or verify a non-trading M29 recovery-collector bundle."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from forex.m29_recovery_collector import RecoveryCollectorError, collect, verify

ROLES = ("preflight-listener", "preflight-diagnostics", "preflight-spool-page", "continuity-status",
         "postflight-listener", "postflight-diagnostics", "postflight-spool-page")

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    command = parser.add_subparsers(dest="command", required=True)
    capture = command.add_parser("capture")
    capture.add_argument("--evidence-root", type=Path, required=True)
    capture.add_argument("--run-id", required=True)
    for role in ROLES:
        capture.add_argument("--" + role, type=Path, required=True)
    check = command.add_parser("verify")
    check.add_argument("--bundle", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "verify":
            result = verify(bundle=args.bundle)
        else:
            envelopes = {role: getattr(args, role.replace("-", "_")).read_bytes() for role in ROLES}
            result = collect(evidence_root=args.evidence_root, run_id=args.run_id, envelopes=envelopes)
        print(json.dumps(result, sort_keys=True, allow_nan=False))
        return 0
    except (OSError, RecoveryCollectorError) as exc:
        print(json.dumps({"schema_version": "forex.m29.recovery-collector-error.v1", "state": "REFUSED",
                          "reason": str(exc), "execution_authority": False}, sort_keys=True), file=sys.stderr)
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
