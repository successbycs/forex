#!/usr/bin/env python3
"""Capture and independently verify the bounded M33 Demo reporting surface."""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
MARKER = "FOREX_M33_PRO_FORMA_COMMISSION_OK"
REQUIRED_ARTIFACTS = frozenset({
    "revision.txt",
    "milestone-status.json",
    "m33-verify.json",
    "m33-projection.json",
    "m20-lifecycle.json",
    "postgres-preflight.json",
    "m33-stage.json",
    "m33-apply.json",
    "m33-refresh-stage.json",
    "m33-refresh-apply.json",
    "terminal-ledger.txt",
    "daily-coverage.json",
    "m33-daily-stage.json",
    "m33-daily-apply.json",
    "daily-terminal-report.txt",
    "daily-web.html",
    "daily-email-preview.txt",
    "summary.txt",
})
REQUIRED_MANIFEST_KEYS = frozenset({
    "schema_version",
    "milestone_id",
    "captured_at",
    "git_revision",
    "configuration_fingerprint",
    "surface",
    "operation",
    "expected_result",
    "observed_result",
    "exit_code",
    "dirty_worktree",
    "summary",
    "redactions",
    "artifacts",
})
REQUIRED_ARTIFACT_KEYS = frozenset({"path", "sha256"})
SURFACE = "fixed PostgreSQL commission-adjusted Demo P&L coverage, terminal report, loopback webpage, and email preview"
OPERATION = "fixed M33 PostgreSQL coverage schema/read verification and read-only operator render"
DAILY_EVIDENCE_DATE = "2026-09-23"
REDACTION = "No credentials, account balances, open-position details, order actions, or MT5 settings are retained."


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
    return hashlib.sha256(path.read_bytes()).hexdigest()


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
    require(not run("git", "status", "--porcelain").strip(), "M33 evidence capture requires a clean committed worktree")
    bundle.mkdir(parents=True)
    try:
        revision = run("git", "rev-parse", "HEAD").strip() + b"\n"
        status = run(sys.executable, "scripts/forex_milestones.py", "status", "--json")
        verify = run(sys.executable, "scripts/postgres_pgvector_adapter.py", "forex-m33-pro-forma-commission-verify")
        projection = run(sys.executable, "scripts/postgres_pgvector_adapter.py", "forex-m33-pro-forma-commission-summary")
        lifecycle = run(sys.executable, "scripts/postgres_pgvector_adapter.py", "forex-m20-lifecycle-summary")
        preflight = run(sys.executable, "scripts/postgres_pgvector_adapter.py", "preflight")
        stage = run(sys.executable, "scripts/postgres_pgvector_adapter.py", "forex-m33-stage-pro-forma-commission-schema", "--approve")
        apply = run(sys.executable, "scripts/postgres_pgvector_adapter.py", "forex-m33-apply-pro-forma-commission-schema", "--approve")
        refresh_stage = run(sys.executable, "scripts/postgres_pgvector_adapter.py", "forex-m33-stage-pro-forma-commission-refresh-schema", "--approve")
        refresh_apply = run(sys.executable, "scripts/postgres_pgvector_adapter.py", "forex-m33-apply-pro-forma-commission-refresh-schema", "--approve")
        daily_coverage = run(sys.executable, "scripts/postgres_pgvector_adapter.py", "forex-m33-daily-commission-coverage-summary", "--date", DAILY_EVIDENCE_DATE)
        daily_stage = run(sys.executable, "scripts/postgres_pgvector_adapter.py", "forex-m33-stage-daily-commission-coverage-schema", "--approve")
        daily_apply = run(sys.executable, "scripts/postgres_pgvector_adapter.py", "forex-m33-apply-daily-commission-coverage-schema", "--approve")
        daily_terminal = run(sys.executable, "scripts/m33_daily_pnl_report.py", "--date", DAILY_EVIDENCE_DATE, "--once")
        sys.path.insert(0, str(ROOT))
        from scripts.m33_daily_pnl_report import fetch_day
        from scripts.m33_daily_pnl_web import render_html
        daily_web = render_html(fetch_day(__import__("datetime").date.fromisoformat(DAILY_EVIDENCE_DATE))).encode()
        daily_email = run(sys.executable, "scripts/m33_daily_pnl_email.py", "--date", DAILY_EVIDENCE_DATE)
        write_new(bundle / "revision.txt", revision)
        write_new(bundle / "milestone-status.json", status)
        write_new(bundle / "m33-verify.json", verify)
        write_new(bundle / "m33-projection.json", projection)
        write_new(bundle / "m20-lifecycle.json", lifecycle)
        write_new(bundle / "postgres-preflight.json", preflight)
        write_new(bundle / "m33-stage.json", stage)
        write_new(bundle / "m33-apply.json", apply)
        write_new(bundle / "m33-refresh-stage.json", refresh_stage)
        write_new(bundle / "m33-refresh-apply.json", refresh_apply)
        write_new(bundle / "terminal-ledger.txt", _terminal_render())
        write_new(bundle / "daily-coverage.json", daily_coverage)
        write_new(bundle / "m33-daily-stage.json", daily_stage)
        write_new(bundle / "m33-daily-apply.json", daily_apply)
        write_new(bundle / "daily-terminal-report.txt", daily_terminal)
        write_new(bundle / "daily-web.html", daily_web)
        write_new(bundle / "daily-email-preview.txt", daily_email)
        captured = datetime.now(timezone.utc).replace(microsecond=0)
        summary = (f"{MARKER}\n"
                   "Demo-only closed-trade commission comparison; no order, risk, account or MT5 setting changed.\n").encode()
        write_new(bundle / "summary.txt", summary)
        names = sorted(path.name for path in bundle.iterdir() if path.is_file())
        manifest = {
            "schema_version": "1.0.0",
            "milestone_id": "M33",
            "captured_at": captured.isoformat().replace("+00:00", "Z"),
            "git_revision": revision.decode().strip(),
            "configuration_fingerprint": json.loads(status)["configuration_fingerprint"],
            "surface": SURFACE,
            "operation": OPERATION,
            "expected_result": MARKER,
            "observed_result": MARKER,
            "exit_code": 0,
            "dirty_worktree": False,
            "summary": MARKER,
            "redactions": [REDACTION],
            "artifacts": [{"path": name, "sha256": digest(bundle / name)} for name in names],
        }
        write_new(bundle / "manifest.json", json.dumps(manifest, indent=2, sort_keys=True).encode() + b"\n")
    except Exception:
        raise
    print(f"{MARKER} bundle={bundle}")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def validate_manifest(bundle: Path, manifest: object, *, current_revision: str,
                      current_fingerprint: str, now: datetime | None = None) -> None:
    """Fail closed unless the bundle is exactly the M33 capture contract."""
    require(isinstance(manifest, dict), "M33 manifest must be an object")
    require(set(manifest) == REQUIRED_MANIFEST_KEYS, "M33 manifest keys do not match the capture contract")
    require(manifest["schema_version"] == "1.0.0", "wrong M33 manifest schema")
    require(manifest["milestone_id"] == "M33", "wrong milestone")
    require(manifest["surface"] == SURFACE, "wrong M33 evidence surface")
    require(manifest["operation"] == OPERATION, "wrong M33 evidence operation")
    require(manifest["expected_result"] == MARKER and manifest["observed_result"] == MARKER,
            "M33 manifest success markers do not match")
    require(manifest["exit_code"] == 0 and type(manifest["exit_code"]) is int,
            "M33 manifest exit code is not successful")
    require(manifest["dirty_worktree"] is False, "M33 capture was not clean")
    require(manifest["summary"] == MARKER, "M33 manifest summary does not match")
    require(manifest["redactions"] == [REDACTION], "M33 manifest redaction contract does not match")
    captured = datetime.fromisoformat(manifest["captured_at"].replace("Z", "+00:00"))
    require(captured.tzinfo is not None, "M33 capture timestamp has no timezone")
    age = (now or datetime.now(timezone.utc)) - captured.astimezone(timezone.utc)
    require(timedelta(0) <= age <= timedelta(hours=24), "M33 evidence exceeds 24-hour freshness")
    require(manifest["git_revision"] == current_revision, "capture revision differs from current source")
    require(manifest["configuration_fingerprint"] == current_fingerprint,
            "capture configuration differs from current configuration")
    artifacts = manifest["artifacts"]
    require(isinstance(artifacts, list), "M33 manifest artifacts must be a list")
    names: list[str] = []
    for artifact in artifacts:
        require(isinstance(artifact, dict) and set(artifact) == REQUIRED_ARTIFACT_KEYS,
                "M33 artifact entry does not match the capture contract")
        name, checksum = artifact["path"], artifact["sha256"]
        require(isinstance(name, str) and isinstance(checksum, str), "M33 artifact entry has invalid types")
        relative = Path(name)
        require(not relative.is_absolute() and len(relative.parts) == 1 and relative.name == name,
                f"invalid M33 artifact path: {name}")
        require(len(checksum) == 64 and all(char in "0123456789abcdef" for char in checksum),
                f"invalid M33 artifact digest: {name}")
        names.append(name)
    require(len(names) == len(set(names)), "M33 manifest has duplicate artifact paths")
    require(set(names) == REQUIRED_ARTIFACTS, "M33 manifest artifact set does not match the capture contract")
    actual_files = {path.name for path in bundle.iterdir() if path.is_file()}
    require(actual_files == REQUIRED_ARTIFACTS | {"manifest.json"}, "M33 bundle has unexpected or missing files")
    for artifact in artifacts:
        path = bundle / artifact["path"]
        require(path.is_file() and digest(path) == artifact["sha256"],
                f"artifact hash mismatch: {artifact['path']}")


def validate_receipt(bundle: Path, name: str, operation: str) -> None:
    receipt = json.loads((bundle / name).read_text())
    require(receipt.get("tool_id") == "forex_postgres_pgvector_t480", f"wrong M33 receipt tool: {name}")
    require(receipt.get("operation") == operation and receipt.get("ok") is True,
            f"M33 fixed operation did not succeed: {name}")
    result = receipt.get("result")
    require(isinstance(result, dict) and result.get("ok") is True and result.get("exit_code") == 0,
            f"M33 receipt has unsuccessful result: {name}")
    require(isinstance(receipt.get("asset_sha256"), str) and receipt["asset_sha256"].startswith("sha256:"),
            f"M33 receipt lacks hash-bound asset: {name}")


def verify(bundle: Path) -> None:
    bundle = bundle.resolve()
    manifest = json.loads((bundle / "manifest.json").read_text())
    current_status = json.loads(run(sys.executable, "scripts/forex_milestones.py", "status", "--json"))
    validate_manifest(
        bundle,
        manifest,
        current_revision=run("git", "rev-parse", "HEAD").decode().strip(),
        current_fingerprint=current_status["configuration_fingerprint"],
    )
    for name, operation in (
        ("m33-stage.json", "forex_m33_stage_pro_forma_commission_schema"),
        ("m33-apply.json", "forex_m33_apply_pro_forma_commission_schema"),
        ("m33-refresh-stage.json", "forex_m33_stage_pro_forma_commission_refresh_schema"),
        ("m33-refresh-apply.json", "forex_m33_apply_pro_forma_commission_refresh_schema"),
        ("m33-daily-stage.json", "forex_m33_stage_daily_commission_coverage_schema"),
        ("m33-daily-apply.json", "forex_m33_apply_daily_commission_coverage_schema"),
    ):
        validate_receipt(bundle, name, operation)
    database = json.loads((bundle / "m33-verify.json").read_text())
    output = database["result"]["stdout"]
    for token in ("FOREX_M33_PRO_FORMA_COMMISSION_DB_OK", "profile=true", "immutable=true", "refresh_trigger=true", "formula=true", "rounding=true", "source_bound=true", "open_position_overlap=false"):
        require(token in output, f"M33 database verification missing {token}")
    projection = json.loads(json.loads((bundle / "m33-projection.json").read_text())["result"]["stdout"])
    decimal = lambda value: Decimal(str(value))
    require(any(decimal(row["volume_lots"]) == Decimal("0.01") and decimal(row["estimated_round_trip_commission_aud"]) == Decimal("-0.06") for row in projection), "missing 0.01 lot / -0.06 M33 projection")
    require(all(decimal(row["pro_forma_live_pnl_aud"]) == decimal(row["actual_broker_net_aud"]) - decimal(row["actual_broker_commission_aud"]) + decimal(row["estimated_round_trip_commission_aud"]) for row in projection), "pro-forma equation failed")
    lifecycle = json.loads(json.loads((bundle / "m20-lifecycle.json").read_text())["result"]["stdout"])
    lifecycle_by_proposal = {row.get("proposal_id"): row for row in lifecycle}
    require(all(row["proposal_id"] in lifecycle_by_proposal and decimal(row["actual_broker_net_aud"]) == decimal(lifecycle_by_proposal[row["proposal_id"]]["realized_pnl_account"]) and decimal(row["actual_broker_commission_aud"]) == decimal(lifecycle_by_proposal[row["proposal_id"]]["commission_account"]) for row in projection), "projection does not match retained broker lifecycle values")
    daily = json.loads(json.loads((bundle / "daily-coverage.json").read_text())["result"]["stdout"])
    require(daily["date"] == DAILY_EVIDENCE_DATE, "wrong daily coverage date")
    require(daily["closed_outcome_count"] == len(daily["rows"]), "daily coverage omits a closed outcome")
    require(daily["closed_outcome_count"] > 0, "daily coverage has no closed outcomes")
    for row in daily["rows"]:
        require(row["coverage_status"] in ("APPLIED", "UNAVAILABLE"), "invalid daily coverage status")
        if row["coverage_status"] == "APPLIED":
            require(row["unavailable_reason"] is None, "applied row has unavailable reason")
            require(decimal(row["commission_adjusted_pnl_aud"]) == decimal(row["actual_broker_net_aud"]) - decimal(row["actual_broker_commission_aud"]) + decimal(row["expected_round_trip_commission_aud"]), "daily adjusted P&L equation failed")
        else:
            require(row["unavailable_reason"] is not None and row["expected_round_trip_commission_aud"] is None and row["commission_adjusted_pnl_aud"] is None, "unavailable row is unsafe")
    daily_terminal = (bundle / "daily-terminal-report.txt").read_text()
    daily_web = (bundle / "daily-web.html").read_text()
    daily_email = (bundle / "daily-email-preview.txt").read_text()
    for rendered in (daily_terminal, daily_web, daily_email):
        require(DAILY_EVIDENCE_DATE in rendered and "Actual" in rendered, "daily operator render is incomplete")
    require("ASSUMED GO Plus+ AUD" in daily_web and "Adjusted P&amp;L" in daily_web, "daily webpage labels are incomplete")
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
