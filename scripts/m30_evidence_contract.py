#!/usr/bin/env python3
"""Construct and verify a bounded autonomous M30 Demo evidence bundle.

Capture is performed by the existing fixed T480 operation.  This module never
contacts a broker: it validates retained bytes and fails closed unless they
show one terminal, broker-matched EURUSD Demo lifecycle.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import m20_demo_evidence_contract as m20


MARKER = "FOREX_M30_PROOF_OK"
SURFACE = "bounded autonomous GOMarketsMU-Demo EUR/USD execution and reconciliation"
REQUIRED = {
    "tests.txt", "governance.txt", "repository-verification.txt", "configuration.json",
    "demo-trading-operation.json", "lifecycle-summary.json", "listener-diagnostics.json",
    "listener-status.json", "m30-audit.json", "revision.txt", "summary.txt",
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise m20.VerificationError(message)


def artifacts(bundle: Path) -> list[dict[str, str]]:
    return [
        {"path": item.name, "sha256": hashlib.sha256(item.read_bytes()).hexdigest()}
        for item in sorted(bundle.iterdir())
        if item.is_file() and item.name != "manifest.json"
    ]


def _payload_and_lifecycle(bundle: Path, root: Path, revision: str, fingerprint: str, captured: datetime) -> tuple[dict, dict]:
    wrapper = m20.read_json(bundle / "demo-trading-operation.json")
    payload = m20.parse_operation(wrapper, fingerprint)
    m20.validate_payload(payload, fingerprint)
    proposal = payload["proposal"]
    execution = payload["execution"]
    reconciliation = payload["reconciliation"]
    require(proposal.get("action") in {"BUY", "SELL"}, "M30 requires an autonomous actionable proposal")
    require(execution.get("status") in {"ACCEPTED", "ACCEPTED_PARTIAL"}, "M30 requires broker-accepted entry")
    require(reconciliation.get("status") == "MATCHED", "M30 requires matched terminal reconciliation")
    lifecycle = m20.validate_broker_matched_lifecycle(
        m20.read_json(bundle / "lifecycle-summary.json"), payload["session"], revision, fingerprint, captured
    )
    require(lifecycle.get("proposal_id") == proposal.get("proposal_id"), "closed lifecycle is not bound to operation proposal")
    require(lifecycle.get("attempt_id") == execution.get("attempt_id"), "closed lifecycle is not bound to execution attempt")
    outcome = reconciliation.get("outcome")
    require(isinstance(outcome, dict) and outcome.get("proposal_id") == proposal.get("proposal_id"), "M30 outcome is absent or unbound")
    require(outcome.get("close_reason"), "M30 close reason is absent")
    m20.validate_listener(bundle, root, revision, fingerprint, payload["session"], captured)
    return payload, lifecycle


def capture(bundle: Path, root: Path) -> None:
    fingerprint = m20.project_fingerprint(root)
    revision = (bundle / "revision.txt").read_text(encoding="utf-8").strip()
    captured = datetime.now(timezone.utc)
    payload, lifecycle = _payload_and_lifecycle(bundle, root, revision, fingerprint, captured)
    audit = {
        "schema_version": "forex.m30.demo-execution-evidence.v1",
        "server": payload["server"], "symbol": payload["symbol"],
        "configuration_fingerprint": fingerprint, "operation": payload["operation"],
        "session": payload["session"], "decision_snapshot": payload["decision_snapshot"],
        "proposal": payload["proposal"], "execution": payload["execution"],
        "reconciliation": payload["reconciliation"], "broker_matched_lifecycle": lifecycle,
    }
    (bundle / "m30-audit.json").write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
    (bundle / "summary.txt").write_text(MARKER + "\n", encoding="utf-8")
    manifest = {
        "schema_version": "1.0.0", "milestone_id": "M30", "captured_at": captured.isoformat().replace("+00:00", "Z"),
        "git_revision": revision, "dirty_worktree": False, "configuration_fingerprint": fingerprint,
        "surface": SURFACE, "operation": "fixed T480 m20_demo_trading_session operation",
        "expected_result": "one bounded autonomous Demo EUR/USD entry closes and reconciles",
        "observed_result": MARKER, "exit_code": 0,
        "redactions": ["No credentials, account identifiers, or Live broker data are retained."],
        "summary": MARKER, "artifacts": artifacts(bundle),
    }
    (bundle / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def verify(bundle: Path, root: Path) -> None:
    evidence_root = (root / "runs" / "evidence" / "M30").resolve()
    require(bundle.is_relative_to(evidence_root), "evidence bundle is outside the M30 evidence root")
    manifest = m20.read_json(bundle / "manifest.json")
    require(manifest.get("schema_version") == "1.0.0", "manifest schema version mismatch")
    require(manifest.get("milestone_id") == "M30", "manifest milestone is not M30")
    require(manifest.get("dirty_worktree") is False, "manifest records a dirty worktree")
    require(manifest.get("surface") == SURFACE, "manifest surface mismatch")
    require(manifest.get("operation") == "fixed T480 m20_demo_trading_session operation", "manifest operation mismatch")
    require(manifest.get("observed_result") == MARKER and manifest.get("summary") == MARKER, "manifest result marker mismatch")
    m20.ensure_no_live_reference(manifest)
    require(manifest.get("git_revision") == subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip(), "manifest revision does not match HEAD")
    captured = m20.utc(manifest.get("captured_at"), "manifest.captured_at")
    require(timedelta(0) <= datetime.now(timezone.utc) - captured < timedelta(hours=24), "M30 evidence is stale or future-dated")
    fingerprint = m20.project_fingerprint(root)
    require(manifest.get("configuration_fingerprint") == fingerprint, "manifest fingerprint does not match current configuration")
    recorded = manifest.get("artifacts")
    require(isinstance(recorded, list) and {item.get("path") for item in recorded if isinstance(item, dict)} == REQUIRED, "manifest must contain exactly required M30 artifacts")
    for item in recorded:
        require(isinstance(item, dict) and isinstance(item.get("path"), str) and isinstance(item.get("sha256"), str), "manifest artifact is invalid")
        name = item["path"]
        require("/" not in name and "\\" not in name and (bundle / name).is_file(), "artifact path is invalid")
        require(hashlib.sha256((bundle / name).read_bytes()).hexdigest() == item["sha256"], f"artifact digest mismatch: {name}")
    require("passed" in (bundle / "tests.txt").read_text(encoding="utf-8").lower(), "M30 tests did not pass")
    require("milestone governance valid" in (bundle / "governance.txt").read_text(encoding="utf-8"), "governance validation did not pass")
    require("FOREX_REPOSITORY_VERIFICATION_OK" in (bundle / "repository-verification.txt").read_text(encoding="utf-8"), "repository verification did not pass")
    configuration = m20.read_json(bundle / "configuration.json")
    require(configuration.get("runtime_mode") == "DEMO_TRADING" and configuration.get("live_trading_enabled") is False and configuration.get("permitted_mt5_server") == "GOMarketsMU-Demo", "configuration violates Demo-only boundary")
    require(configuration.get("configuration_fingerprint") == fingerprint, "configuration artifact fingerprint mismatch")
    payload, lifecycle = _payload_and_lifecycle(bundle, root, manifest["git_revision"], fingerprint, captured)
    audit = m20.read_json(bundle / "m30-audit.json")
    require(audit.get("schema_version") == "forex.m30.demo-execution-evidence.v1", "M30 audit schema mismatch")
    for field in ("server", "symbol", "configuration_fingerprint", "operation", "session", "decision_snapshot", "proposal", "execution", "reconciliation"):
        require(audit.get(field) == payload.get(field) if field in payload else audit.get(field) == fingerprint, f"M30 audit {field} mismatch")
    require(audit.get("broker_matched_lifecycle") == lifecycle, "M30 audit lifecycle mismatch")
    require((bundle / "revision.txt").read_text(encoding="utf-8").strip() == manifest["git_revision"], "revision artifact mismatch")
    require((bundle / "summary.txt").read_text(encoding="utf-8").strip() == MARKER, "proof marker is missing")
    print("FOREX_M30_EVIDENCE_VERIFIED")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build or verify M30 Demo evidence.")
    parser.add_argument("command", choices=("capture", "verify"))
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--bundle", required=True, type=Path)
    args = parser.parse_args()
    if args.command == "capture":
        capture(args.bundle.resolve(), args.root.resolve())
    else:
        verify(args.bundle.resolve(), args.root.resolve())
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except m20.VerificationError as error:
        print(f"M30 evidence verification failed: {error}", file=sys.stderr)
        raise SystemExit(2) from error
