#!/usr/bin/env python3
"""Capture and independently verify the bounded M33 Demo reporting surface."""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
MARKER = "FOREX_M33_PRO_FORMA_COMMISSION_OK"


def run(*argv: str) -> bytes:
    completed = subprocess.run(argv, cwd=ROOT, capture_output=True, check=False)
    if completed.returncode:
        raise RuntimeError(f"{' '.join(argv)} failed: {completed.stderr.decode(errors='replace')}")
    return completed.stdout


def write_new(path: Path, data: bytes) -> None:
    if path.exists():
        raise RuntimeError(f"refusing to overwrite evidence: {path}")
    path.write_bytes(data)


def digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _terminal_render() -> bytes:
    sys.path.insert(0, str(ROOT))
    from scripts.m20_trade_ledger_dashboard import _nz_datetime, render, trade_rows

    rows = trade_rows()
    eligible = [row for row in rows if row.get("pro_forma_live_pnl_aud") is not None]
    if not eligible:
        raise RuntimeError("no eligible M33 projection is available for terminal evidence")
    latest_day = max(_nz_datetime(row["submitted_at_utc"]).date() for row in eligible)
    rendered = render(rows, nz_day=latest_day)
    if "Commission-adjusted Demo P&L — GO Plus+ AUD assumption" not in rendered:
        raise RuntimeError("terminal ledger did not render the explicit M33 label")
    return rendered.encode() + b"\n"


def capture(bundle: Path) -> None:
    bundle = bundle.resolve()
    if bundle.exists():
        raise RuntimeError(f"evidence directory already exists: {bundle}")
    bundle.mkdir(parents=True)
    try:
        revision = run("git", "rev-parse", "HEAD").strip() + b"\n"
        status = run(sys.executable, "scripts/forex_milestones.py", "status", "--json")
        verify = run(sys.executable, "scripts/postgres_pgvector_adapter.py", "forex-m33-pro-forma-commission-verify")
        projection = run(sys.executable, "scripts/postgres_pgvector_adapter.py", "forex-m33-pro-forma-commission-summary")
        lifecycle = run(sys.executable, "scripts/postgres_pgvector_adapter.py", "forex-m20-lifecycle-summary")
        preflight = run(sys.executable, "scripts/postgres_pgvector_adapter.py", "preflight")
        write_new(bundle / "revision.txt", revision)
        write_new(bundle / "milestone-status.json", status)
        write_new(bundle / "m33-verify.json", verify)
        write_new(bundle / "m33-projection.json", projection)
        write_new(bundle / "m20-lifecycle.json", lifecycle)
        write_new(bundle / "postgres-preflight.json", preflight)
        write_new(bundle / "terminal-ledger.txt", _terminal_render())
        captured = datetime.now(timezone.utc).replace(microsecond=0)
        summary = (f"{MARKER}\n"
                   "Demo-only closed-trade commission comparison; no order, risk, account or MT5 setting changed.\n").encode()
        write_new(bundle / "summary.txt", summary)
        names = sorted(path.name for path in bundle.iterdir() if path.is_file())
        manifest = {
            "schema_version": "forex.m33.evidence-bundle.v1",
            "milestone_id": "M33",
            "captured_at_utc": captured.isoformat().replace("+00:00", "Z"),
            "git_revision": revision.decode().strip(),
            "configuration_fingerprint": json.loads(status)["configuration_fingerprint"],
            "surface": "fixed PostgreSQL commission-adjusted Demo P&L projection and read-only terminal ledger",
            "operation": "fixed M33 PostgreSQL schema/projection verification and read-only terminal render",
            "observed_result": MARKER,
            "execution_authority": False,
            "redactions": ["No credentials, account balances, open-position details, order actions, or MT5 settings are retained."],
            "artifacts": [{"path": name, "sha256": digest(bundle / name)} for name in names],
        }
        write_new(bundle / "manifest.json", json.dumps(manifest, indent=2, sort_keys=True).encode() + b"\n")
    except Exception:
        raise
    print(f"{MARKER} bundle={bundle}")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def verify(bundle: Path) -> None:
    bundle = bundle.resolve()
    manifest = json.loads((bundle / "manifest.json").read_text())
    require(manifest.get("schema_version") == "forex.m33.evidence-bundle.v1", "wrong M33 manifest schema")
    require(manifest.get("milestone_id") == "M33", "wrong milestone")
    captured = datetime.fromisoformat(manifest["captured_at_utc"].replace("Z", "+00:00"))
    require(datetime.now(timezone.utc) - captured <= timedelta(hours=24), "M33 evidence exceeds 24-hour freshness")
    require(manifest.get("git_revision") == run("git", "rev-parse", "HEAD").decode().strip(), "capture revision differs from current source")
    for artifact in manifest["artifacts"]:
        path = bundle / artifact["path"]
        require(path.is_file() and digest(path) == artifact["sha256"], f"artifact hash mismatch: {artifact['path']}")
    database = json.loads((bundle / "m33-verify.json").read_text())
    output = database["result"]["stdout"]
    for token in ("FOREX_M33_PRO_FORMA_COMMISSION_DB_OK", "profile=true", "immutable=true", "formula=true", "rounding=true", "source_bound=true", "open_positions_included=false"):
        require(token in output, f"M33 database verification missing {token}")
    projection = json.loads(json.loads((bundle / "m33-projection.json").read_text())["result"]["stdout"])
    require(any(row["volume_lots"] == 0.01 and row["estimated_round_trip_commission_aud"] == -0.06 for row in projection), "missing 0.01 lot / -0.06 M33 projection")
    require(all(row["pro_forma_live_pnl_aud"] == row["actual_broker_net_aud"] - row["actual_broker_commission_aud"] + row["estimated_round_trip_commission_aud"] for row in projection), "pro-forma equation failed")
    terminal = (bundle / "terminal-ledger.txt").read_text()
    require("Actual broker P&L:" in terminal and "Commission-adjusted Demo P&L — GO Plus+ AUD assumption:" in terminal, "terminal comparison label missing")
    require(MARKER in (bundle / "summary.txt").read_text(), "M33 success marker missing")
    print(MARKER)


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture or verify M33 Demo commission evidence.")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("capture", "verify"):
        child = sub.add_parser(name)
        child.add_argument("--bundle", required=True, type=Path)
    args = parser.parse_args()
    try:
        if args.command == "capture":
            capture(args.bundle)
        else:
            verify(args.bundle)
    except (RuntimeError, KeyError, ValueError, json.JSONDecodeError) as error:
        print(f"M33 evidence error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
