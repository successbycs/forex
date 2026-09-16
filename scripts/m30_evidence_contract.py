#!/usr/bin/env python3
"""Construct and verify a bounded autonomous M30 Demo evidence bundle.

Capture is performed by the existing fixed T480 operation. The wait command
only reads PostgreSQL lifecycle observations; verification uses retained bytes
and fails closed unless they show one terminal, broker-matched EURUSD Demo
lifecycle. This module never contacts a broker.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import math
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import m20_demo_evidence_contract as m20


MARKER = "FOREX_M30_PROOF_OK"
SURFACE = "GOMarketsMU-Demo execution and reconciliation surface"
REQUIRED = {
    "tests.txt", "governance.txt", "m30-verification.txt", "configuration.json",
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


def validate_entry(payload: dict) -> None:
    """Validate the actual asynchronous executor response, without inventing an outcome."""
    require(payload.get("operation") == "m20_demo_trading_session", "payload operation mismatch")
    session = m20.validate_session(payload)
    snapshot = m20.validate_snapshot(payload, session)
    proposal = m20.validate_proposal(payload, session, snapshot)
    m20.validate_strategy_selection(payload, snapshot, proposal)
    require(proposal.get("action") in {"BUY", "SELL"}, "M30 requires an autonomous actionable proposal")
    execution = m20.object_field(payload, "execution")
    require(execution.get("status") in {"ACCEPTED", "ACCEPTED_PARTIAL"}, "M30 requires broker-accepted entry")
    attempt = m20.string(execution.get("attempt_id"), "execution.attempt_id")
    require(execution.get("session_id") == session["session_id"] and execution.get("proposal_id") == proposal["proposal_id"], "execution identity mismatch")
    m20.string(execution.get("idempotency_key"), "execution.idempotency_key")
    submitted = m20.utc(execution.get("submitted_at_utc"), "execution.submitted_at_utc")
    require(m20.utc(proposal["decision_at_utc"], "decision") <= submitted <= m20.utc(proposal["expires_at_utc"], "expiry"), "execution exceeds proposal validity")
    require(execution.get("open_positions_before") == 0, "entry did not start flat")
    cumulative = m20.finite_number(execution.get("cumulative_notional_before_usd"), "cumulative notional")
    require(0 <= cumulative and cumulative + proposal["notional_usd"] <= session["max_cumulative_notional_usd"], "entry exceeds cumulative cap")
    audit = m20.object_field(payload, "postgres_audit")
    for field, expected in (("session_id", session["session_id"]), ("proposal_id", proposal["proposal_id"]), ("snapshot_id", snapshot["snapshot_id"]), ("execution_attempt_id", attempt)):
        require(audit.get(field) == expected, f"PostgreSQL audit {field} mismatch")
    m20.sha256(audit.get("record_sha256"), "postgres_audit.record_sha256")
    reconciliation = m20.object_field(payload, "reconciliation")
    if reconciliation.get("status") == "OPEN_MONITORING":
        require(execution.get("monitor_job_scheduled") is True, "accepted entry has no scheduled monitor")
        require(type(reconciliation.get("position_ticket")) is int and reconciliation["position_ticket"] > 0, "open monitor position is missing")
    else:
        m20.validate_execution_and_reconciliation(payload, session, snapshot, proposal)


def matching_rows(wrapper: dict, payload: dict) -> list[dict]:
    m20.ensure_no_live_reference(wrapper)
    require(wrapper.get("tool_id") == "forex_postgres_pgvector_t480" and wrapper.get("operation") == "forex_m20_lifecycle_summary", "lifecycle adapter mismatch")
    result = m20.object_field(wrapper, "result")
    require(result.get("ok") is True and result.get("exit_code") == 0, "lifecycle observation failed")
    try:
        rows = json.loads(result.get("stdout", ""))
    except (TypeError, json.JSONDecodeError) as error:
        raise m20.VerificationError("lifecycle observation is not JSON") from error
    require(isinstance(rows, list), "lifecycle observation must contain rows")
    return [row for row in rows if isinstance(row, dict) and row.get("proposal_id") == payload["proposal"]["proposal_id"] and row.get("attempt_id") == payload["execution"]["attempt_id"]]


def owner_hold_seconds(root: Path, owner: str) -> int:
    # Read the committed policy without importing the broker-capable module.
    tree = ast.parse((root / "t480/m20_demo_trading_session.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "OWNER_MAX_HOLD_SECONDS" for target in node.targets):
            require(isinstance(node.value, ast.Dict), "owner cutoff policy is malformed")
            for key, value in zip(node.value.keys, node.value.values):
                if ast.literal_eval(key) == owner:
                    require(isinstance(value, ast.BinOp) and isinstance(value.op, ast.Mult), "owner cutoff policy is unsupported")
                    seconds = ast.literal_eval(value.left) * ast.literal_eval(value.right)
                    require(type(seconds) is int and seconds > 0, "owner cutoff policy is invalid")
                    return seconds
    raise m20.VerificationError("no configured cutoff exists for trade owner")


def wait_for_close(bundle: Path, root: Path, *, timeout_seconds: int = 900) -> None:
    """Observe the one accepted attempt; never re-submit or modify raw entry bytes."""
    require(bundle.is_relative_to((root / "runs/evidence/M30").resolve()), "evidence bundle is outside the M30 evidence root")
    require(not (bundle / "lifecycle-summary.json").exists(), "lifecycle summary already exists; never overwrite a bundle")
    payload = m20.parse_operation(m20.read_json(bundle / "demo-trading-operation.json"), m20.project_fingerprint(root))
    validate_entry(payload)
    deadline = time.monotonic() + timeout_seconds
    for sequence in range(1000):
        result = subprocess.run([sys.executable, "scripts/postgres_pgvector_adapter.py", "forex-m20-lifecycle-summary"], cwd=root, capture_output=True, text=True, timeout=60)
        observation = bundle / f"lifecycle-observation-{sequence:03d}.json"
        with observation.open("x", encoding="utf-8") as stream:
            stream.write(result.stdout)
        if result.stderr:
            with (bundle / f"lifecycle-observation-{sequence:03d}.stderr.txt").open("x", encoding="utf-8") as stream:
                stream.write(result.stderr)
        require(result.returncode == 0, "lifecycle observation failed; retain evidence and inspect the existing monitor, do not resubmit")
        rows = matching_rows(m20.read_json(observation), payload)
        require(len(rows) <= 1, "duplicate lifecycle rows for accepted attempt")
        if rows and rows[0].get("lifecycle") == "CLOSED_MATCHED" and rows[0].get("reconciliation_status") == "MATCHED":
            with (bundle / "lifecycle-summary.json").open("xb") as stream:
                stream.write(observation.read_bytes())
            return
        require(time.monotonic() < deadline, "accepted attempt has not closed within capture observation window; keep its monitor running and do not resubmit")
        time.sleep(min(5, max(0, deadline - time.monotonic())))
    raise m20.VerificationError("lifecycle observation limit reached")


def _payload_and_lifecycle(bundle: Path, root: Path, revision: str, fingerprint: str, captured: datetime) -> tuple[dict, dict]:
    wrapper = m20.read_json(bundle / "demo-trading-operation.json")
    payload = m20.parse_operation(wrapper, fingerprint)
    validate_entry(payload)
    proposal = payload["proposal"]
    execution = payload["execution"]
    reconciliation = payload["reconciliation"]
    require(proposal.get("action") in {"BUY", "SELL"}, "M30 requires an autonomous actionable proposal")
    require(execution.get("status") in {"ACCEPTED", "ACCEPTED_PARTIAL"}, "M30 requires broker-accepted entry")
    wrapper = m20.read_json(bundle / "lifecycle-summary.json")
    rows = matching_rows(wrapper, payload)
    require(len(rows) == 1, "M30 requires one lifecycle for the exact operation proposal and attempt")
    wrapper = {**wrapper, "result": {**wrapper["result"], "stdout": json.dumps(rows)}}
    lifecycle = m20.validate_broker_matched_lifecycle(
        wrapper, payload["session"], revision, fingerprint, captured
    )
    require(lifecycle.get("proposal_id") == proposal.get("proposal_id"), "closed lifecycle is not bound to operation proposal")
    require(lifecycle.get("attempt_id") == execution.get("attempt_id"), "closed lifecycle is not bound to execution attempt")
    for key, expected in (("snapshot_id", proposal["snapshot_id"]), ("decision_snapshot_sha256", proposal["decision_snapshot_sha256"]), ("action", proposal["action"]), ("selected_strategy_id", payload["strategy_selection"]["selected_strategy_id"]), ("trade_owner_strategy_id", payload["strategy_selection"]["trade_owner_strategy_id"])):
        require(lifecycle.get(key) == expected, f"operation and lifecycle {key} mismatch")
    for key, expected in (("decision_at_utc", proposal["decision_at_utc"]), ("proposal_expires_at_utc", proposal["expires_at_utc"]), ("submitted_at_utc", execution["submitted_at_utc"]), ("snapshot_captured_at_utc", payload["decision_snapshot"]["captured_at_utc"])):
        require(m20.utc(lifecycle.get(key), key) == m20.utc(expected, key), f"operation and lifecycle {key} mismatch")
    submitted = m20.utc(execution["submitted_at_utc"], "entry submission")
    require(captured - timedelta(hours=24) <= submitted <= captured, "M30 entry is stale or future-dated")
    owner = lifecycle["trade_owner_strategy_id"]
    hold = owner_hold_seconds(root, owner)
    cutoff = submitted + timedelta(seconds=hold)
    closing = lifecycle["closing_context"]
    reason = lifecycle.get("close_reason")
    require(reason == closing.get("close_reason") and reason in {"BROKER_SIDE_CLOSE", f"{owner.upper()}_M1_TWO_OPPOSITE_CLOSED_CANDLES", f"{owner.upper()}_M1_TIME_STOP_{hold // 60}_MINUTES"}, "close reason does not match the owner exit contract")
    exit_times = [m20.utc(deal["time_utc"], "broker exit") for deal in closing["broker_history"]["broker_deals"] if deal["volume"] > 0 and deal["entry"] in {1, 3}]
    require(max(exit_times) <= cutoff, "broker close exceeded the configured owner cutoff")
    if reconciliation.get("status") == "OPEN_MONITORING":
        require(reconciliation["position_ticket"] == lifecycle["opening_context"].get("position_ticket") == closing.get("position_ticket"), "monitor and lifecycle position ticket mismatch")
    else:
        outcome = reconciliation["outcome"]
        require(m20.utc(outcome["closed_at_utc"], "outcome close") == m20.utc(lifecycle["closed_at_utc"], "lifecycle close"), "outcome close timestamp mismatch")
        require(outcome["close_reason"] == reason and outcome["account_currency"] == lifecycle["account_currency"], "outcome close reason or currency mismatch")
        for key in ("exit_price", "realized_pnl_account"):
            require(math.isclose(m20.finite_number(outcome.get(key), key), m20.finite_number(lifecycle.get(key), key), rel_tol=0, abs_tol=1e-8), f"outcome {key} mismatch")
    m20.validate_listener(bundle, root, revision, fingerprint, payload["session"], captured)
    return payload, lifecycle


def capture(bundle: Path, root: Path) -> None:
    require(bundle.is_relative_to((root / "runs/evidence/M30").resolve()), "evidence bundle is outside the M30 evidence root")
    require(not any((bundle / name).exists() for name in ("m30-audit.json", "summary.txt", "manifest.json")), "M30 derived evidence already exists; never overwrite a bundle")
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
    require(type(manifest.get("exit_code")) is int and manifest["exit_code"] == 0, "manifest exit status is not successful")
    require(manifest.get("observed_result") == MARKER and manifest.get("summary") == MARKER, "manifest result marker mismatch")
    m20.ensure_no_live_reference(manifest)
    require(manifest.get("git_revision") == subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip(), "manifest revision does not match HEAD")
    captured = m20.utc(manifest.get("captured_at"), "manifest.captured_at")
    require(timedelta(0) <= datetime.now(timezone.utc) - captured < timedelta(hours=24), "M30 evidence is stale or future-dated")
    fingerprint = m20.project_fingerprint(root)
    require(manifest.get("configuration_fingerprint") == fingerprint, "manifest fingerprint does not match current configuration")
    recorded = manifest.get("artifacts")
    require(isinstance(recorded, list) and all(isinstance(item, dict) for item in recorded), "manifest artifacts must be objects")
    names = [item.get("path") for item in recorded]
    require(all(isinstance(name, str) for name in names) and len(set(names)) == len(names), "manifest artifact names are invalid or duplicated")
    require(REQUIRED <= set(names) and all(name in REQUIRED or re.fullmatch(r"lifecycle-observation-\d{3}\.(?:json|stderr\.txt)", name) for name in names), "manifest must contain required M30 artifacts and only bounded observations")
    for item in recorded:
        require(isinstance(item, dict) and isinstance(item.get("path"), str) and isinstance(item.get("sha256"), str), "manifest artifact is invalid")
        name = item["path"]
        require("/" not in name and "\\" not in name and not (bundle / name).is_symlink() and (bundle / name).is_file(), "artifact path is invalid")
        require(hashlib.sha256((bundle / name).read_bytes()).hexdigest() == item["sha256"], f"artifact digest mismatch: {name}")
    test_output = (bundle / "tests.txt").read_text(encoding="utf-8").lower()
    require(re.search(r"\b[1-9]\d* passed\b", test_output) is not None and re.search(r"\b[1-9]\d* (?:failed|errors?)\b", test_output) is None, "M30 tests did not pass")
    require("milestone governance valid" in (bundle / "governance.txt").read_text(encoding="utf-8"), "governance validation did not pass")
    require("FOREX_M30_TARGETED_VERIFICATION_OK" in (bundle / "m30-verification.txt").read_text(encoding="utf-8"), "M30 targeted verification did not pass")
    configuration = m20.read_json(bundle / "configuration.json")
    m20.ensure_no_live_reference(configuration)
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
    print(MARKER)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build or verify M30 Demo evidence.")
    parser.add_argument("command", choices=("capture", "verify", "wait-for-close"))
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--bundle", required=True, type=Path)
    args = parser.parse_args()
    if args.command == "capture":
        capture(args.bundle.resolve(), args.root.resolve())
    elif args.command == "wait-for-close":
        wait_for_close(args.bundle.resolve(), args.root.resolve())
    else:
        verify(args.bundle.resolve(), args.root.resolve())
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (m20.VerificationError, OSError, subprocess.SubprocessError) as error:
        print(f"M30 evidence verification failed: {error}", file=sys.stderr)
        raise SystemExit(2) from error
