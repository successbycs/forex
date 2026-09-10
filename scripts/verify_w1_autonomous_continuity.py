#!/usr/bin/env python3
"""Offline verifier for one retained Wave 1 autonomous-continuity bundle."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from datetime import datetime, timezone


def fail(message: str) -> None:
    raise ValueError(message)


def load(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid retained JSON: {path.name}") from error
    if not isinstance(value, dict):
        fail(f"retained JSON object required: {path.name}")
    return value


def verify(bundle: Path) -> dict:
    raw = bundle / "raw"
    diagnostics_path = raw / "postflight-diagnostics.json"
    diagnostics = load(diagnostics_path)
    stdout = diagnostics.get("result", {}).get("stdout", "")
    try:
        observed = json.loads(stdout)
    except (TypeError, json.JSONDecodeError) as error:
        raise ValueError("postflight diagnostics are unavailable") from error
    record_path = raw / "continuity-protocol.json"
    status_path = raw / "postflight-continuity-status.json"
    if record_path.is_file():
        record = load(record_path)
    elif status_path.is_file():
        record = load(status_path).get("result", {}).get("stdout", "")
        try:
            record = json.loads(record).get("record")
        except (TypeError, json.JSONDecodeError) as error:
            raise ValueError("retained continuity status is unavailable") from error
    else:
        record = None
    if not isinstance(record, dict) or record.get("schema_version") != "forex.m20.continuity-protocol.v1" or record.get("state") != "PASS":
        fail("protocol did not pass")
    baseline = record.get("baseline")
    samples = record.get("samples")
    if not isinstance(baseline, dict) or not isinstance(samples, list) or len(samples) < 2:
        fail("baseline or heartbeat samples are incomplete")
    if baseline.get("listener_logon_type") != "S4U":
        fail("baseline listener identity is not S4U")
    account = baseline.get("account")
    if not isinstance(account, dict) or (account.get("server"), account.get("currency"), account.get("position_observation"), account.get("open_positions")) != ("GOMarketsMU-Demo", "AUD", "AVAILABLE", 0):
        fail("baseline Demo account was not flat and available")
    deployment = baseline.get("deployment")
    if not isinstance(deployment, dict) or deployment.get("release_id") != record.get("release_id") or not isinstance(deployment.get("payload_sha256"), dict) or not deployment.get("persistent_risk_policy"):
        fail("baseline deployment, lease, or Option B binding is incomplete")
    if baseline.get("unresolved_execution", {}).get("state") != "CLEAR":
        fail("baseline unresolved-execution state is not clear")
    if any(not isinstance(row, dict) or row.get("valid") is not True or row.get("state") != "MAINTENANCE_HOLD" or row.get("release_id") != record.get("release_id") or float(row.get("heartbeat_age_seconds", 999)) >= 30 for row in samples):
        fail("heartbeat continuity or hold invariant failed")
    if record.get("incident_delivery", {}).get("state") not in {"SENT", "DISABLED"} or record.get("recovery_delivery", {}).get("state") not in {"SENT", "DISABLED"}:
        fail("incident or recovery delivery lacks a terminal retained result")
    if observed.get("maintenance_hold_present") is not True or observed.get("logon_type") != "S4U":
        fail("postflight hold or task identity changed")
    if not observed.get("processes") or any(row.get("SessionId") != 0 for row in observed["processes"] if isinstance(row, dict)):
        fail("postflight listener process is not confined to Session 0")
    handoff = record.get("handoff")
    if not isinstance(handoff, dict) or handoff.get("state") != "RECOVERED" or not handoff.get("requested_at_utc") or not handoff.get("recovered_at_utc"):
        fail("exactly one recovered worker handoff is not retained")
    postflight = record.get("postflight")
    if not isinstance(postflight, dict) or postflight.get("account") != account or postflight.get("deployment") != deployment or postflight.get("unresolved_execution", {}).get("state") != "CLEAR":
        fail("postflight account, lease, risk, deployment, or unresolved state changed")
    try:
        started = datetime.fromisoformat(str(record["started_at_utc"]).replace("Z", "+00:00")).astimezone(timezone.utc)
        completed = datetime.fromisoformat(str(record["completed_at_utc"]).replace("Z", "+00:00")).astimezone(timezone.utc)
        captured = [datetime.fromisoformat(str(row["captured_at_utc"]).replace("Z", "+00:00")).astimezone(timezone.utc) for row in samples]
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("protocol timestamps are invalid") from error
    if (completed - started).total_seconds() < 30 * 60 or any((later - earlier).total_seconds() > 30 for earlier, later in zip(captured, captured[1:])):
        fail("retained heartbeat interval does not prove 30-minute continuity")
    hashes = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(raw.glob("*.json"))}
    return {"marker": "FOREX_W1_AUTONOMOUS_CONTINUITY_PROOF_OK", "bundle": str(bundle),
            "run_id": record["run_id"], "release_id": record["release_id"], "raw_sha256": hashes}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("bundle", type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(verify(args.bundle), indent=2, sort_keys=True))
    except ValueError as error:
        print(f"verification failed: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
