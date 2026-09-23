#!/usr/bin/env python3
"""Create one immutable, pre-declared M31 evaluation protocol and receipt."""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from forex.m31_scorecard import M31ScorecardInputError, parse_protocol  # noqa: E402


def utc(value: str) -> datetime:
    if not value.endswith("Z"):
        raise ValueError("UTC instant requires Z suffix")
    parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    if parsed.tzinfo != timezone.utc or parsed.microsecond:
        raise ValueError("UTC instant must be whole-second")
    return parsed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--from-utc", required=True)
    parser.add_argument("--to-utc", required=True)
    args = parser.parse_args(argv)
    try:
        start, end = utc(args.from_utc), utc(args.to_utc)
        if not start < end or (end - start).total_seconds() > 86400:
            raise ValueError("interval must be positive and at most 24 hours")
        if start <= datetime.now(timezone.utc):
            raise ValueError("interval start must still be in the future")
        if subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, text=True, capture_output=True, check=True).stdout:
            raise ValueError("protocol declaration requires a clean committed checkout")
        if args.directory.exists():
            raise ValueError("protocol directory already exists")
        protocol = {"schema_version": "forex.m31.evaluation-protocol.v1", "interval": {"from_utc": args.from_utc, "to_utc": args.to_utc, "bounds": "inclusive/exclusive"}, "baseline": {"kind": "NO_CHANGE", "trade_count": 0, "realized_pnl_aud": 0, "cost_aud": 0}, "server": "GOMarketsMU-Demo", "symbol": "EURUSD", "captured_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")}
        parse_protocol(json.dumps(protocol))
        revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
        raw = json.dumps(protocol, sort_keys=True, indent=2).encode() + b"\n"
        receipt = {"schema_version": "forex.m31.protocol-receipt.v1", "declared_at_utc": protocol["captured_at_utc"], "git_revision": revision, "protocol_sha256": "sha256:" + hashlib.sha256(raw).hexdigest(), "execution_authority": False}
        args.directory.mkdir(parents=True)
        (args.directory / "protocol.json").write_bytes(raw)
        (args.directory / "receipt.json").write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n")
        print(json.dumps({"state": "DECLARED", "directory": str(args.directory), "interval": protocol["interval"], "git_revision": revision, "execution_authority": False}, sort_keys=True))
        return 0
    except (OSError, ValueError, M31ScorecardInputError) as exc:
        print(f"M31 protocol declaration refused: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
