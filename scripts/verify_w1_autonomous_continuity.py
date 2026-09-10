#!/usr/bin/env python3
"""Offline verifier for one retained Wave 1 autonomous-continuity bundle."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys


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
    record_path = raw / "continuity-protocol.json"
    diagnostics_path = raw / "postflight-diagnostics.json"
    record = load(record_path)
    diagnostics = load(diagnostics_path)
    if record.get("schema_version") != "forex.m20.continuity-protocol.v1" or record.get("state") != "PASS":
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
    if any(not isinstance(row, dict) or row.get("valid") is not True or row.get("state") != "MAINTENANCE_HOLD" or row.get("release_id") != record.get("release_id") or float(row.get("heartbeat_age_seconds", 999)) >= 30 for row in samples):
        fail("heartbeat continuity or hold invariant failed")
    if record.get("incident_delivery", {}).get("state") not in {"SENT", "DISABLED"} or record.get("recovery_delivery", {}).get("state") not in {"SENT", "DISABLED"}:
        fail("incident or recovery delivery lacks a terminal retained result")
    stdout = diagnostics.get("result", {}).get("stdout", "")
    try:
        observed = json.loads(stdout)
    except (TypeError, json.JSONDecodeError) as error:
        raise ValueError("postflight diagnostics are unavailable") from error
    if observed.get("maintenance_hold_present") is not True or observed.get("logon_type") != "S4U":
        fail("postflight hold or task identity changed")
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
