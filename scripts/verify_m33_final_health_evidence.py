#!/usr/bin/env python3
"""Fail-closed verifier for the final M33 T480-local health proof bundle.

This verifier deliberately accepts only a complete final-release bundle.  It
does not turn a healthy held listener, an old boot receipt, a historical Demo
trade, or a no-trade observation into the M33 health success marker.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path


MARKER = "FOREX_M33_LOCAL_TRADING_HEALTH_OK"
SCHEMA = "forex.m33.final-health-evidence.v1"
REQUIRED_RECEIPTS = frozenset({
    "recovery-before.json", "recovery-action.json", "recovery-executor.json",
    "recovery-after.json", "cold-boot-1-before.json", "cold-boot-1-after.json",
    "cold-boot-2-before.json", "cold-boot-2-after.json", "lifecycle-pnl.json",
})
MAX_SOAK_GAP = timedelta(minutes=15)
MIN_SOAK = timedelta(hours=24)


def fail(message: str) -> None:
    raise ValueError(message)


def load_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid JSON receipt: {path.name}") from error
    if not isinstance(value, dict):
        fail(f"receipt is not an object: {path.name}")
    return value


def sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def utc(value: object, *, field: str) -> datetime:
    if not isinstance(value, str):
        fail(f"{field} is absent or invalid")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError(f"{field} is absent or invalid") from error
    if parsed.tzinfo is None:
        fail(f"{field} has no timezone")
    return parsed.astimezone(timezone.utc)


def exact(value: object, expected: object, *, field: str) -> None:
    if value != expected:
        fail(f"{field} is invalid")


def receipt(manifest: dict, bundle: Path, name: str) -> dict:
    entries = manifest.get("receipts")
    if not isinstance(entries, list):
        fail("manifest receipts is invalid")
    matches = [entry for entry in entries if isinstance(entry, dict) and entry.get("path") == name]
    if len(matches) != 1:
        fail(f"missing or duplicate manifest receipt: {name}")
    entry = matches[0]
    if set(entry) != {"path", "sha256", "captured_at_utc", "operation_id", "redaction"}:
        fail(f"receipt manifest shape is invalid: {name}")
    path = bundle / name
    if not path.is_file() or entry["sha256"] != sha256(path):
        fail(f"receipt hash does not match: {name}")
    utc(entry["captured_at_utc"], field=f"receipt captured_at_utc {name}")
    if not isinstance(entry["operation_id"], str) or not entry["operation_id"]:
        fail(f"receipt operation is invalid: {name}")
    if entry["redaction"] != "no credentials or account numbers":
        fail(f"receipt redaction is invalid: {name}")
    return load_json(path)


def bound(receipt_value: dict, identity: dict, *, name: str) -> None:
    for field in ("configuration_fingerprint", "listener_release_id", "guardian_release_id", "boot_id"):
        exact(receipt_value.get(field), identity[field], field=f"{name} {field}")
    exact(receipt_value.get("entry_eligible"), False, field=f"{name} entry fence")
    exact(receipt_value.get("maintenance_hold"), True, field=f"{name} maintenance hold")
    exact(receipt_value.get("broker_mutation"), "NONE", field=f"{name} broker mutation")


def verify_recovery(manifest: dict, bundle: Path, identity: dict) -> None:
    before = receipt(manifest, bundle, "recovery-before.json")
    action = receipt(manifest, bundle, "recovery-action.json")
    executor = receipt(manifest, bundle, "recovery-executor.json")
    after = receipt(manifest, bundle, "recovery-after.json")
    for name, value in (("recovery before", before), ("recovery action", action),
                        ("recovery executor", executor), ("recovery after", after)):
        bound(value, identity, name=name)
    exact(before.get("managed_mt5_count"), 1, field="recovery before managed client count")
    exact(before.get("unattributable_mt5_count"), 0, field="recovery before unknown client count")
    exact(before.get("open_positions"), 0, field="recovery before positions")
    exact(before.get("pending_orders"), 0, field="recovery before pending orders")
    exact(action.get("action"), "RESTART_LISTENER", field="recovery action")
    request_id = action.get("request_id")
    if not isinstance(request_id, str) or not request_id:
        fail("recovery action request identity is invalid")
    exact(executor.get("request_id"), request_id, field="recovery executor request identity")
    exact(executor.get("state"), "VERIFIED", field="recovery executor state")
    exact(after.get("request_id"), request_id, field="recovery after request identity")
    exact(after.get("monitor_state"), "IDLE", field="recovery monitor restoration")
    exact(after.get("managed_mt5_count"), 1, field="recovery after managed client count")
    exact(after.get("unattributable_mt5_count"), 0, field="recovery after unknown client count")
    exact(after.get("open_positions"), 0, field="recovery after positions")
    exact(after.get("pending_orders"), 0, field="recovery after pending orders")


def verify_boots(manifest: dict, bundle: Path, identity: dict) -> None:
    boot_ids: list[str] = []
    for number in (1, 2):
        before = receipt(manifest, bundle, f"cold-boot-{number}-before.json")
        after = receipt(manifest, bundle, f"cold-boot-{number}-after.json")
        bound(before, identity, name=f"cold boot {number} before")
        bound(after, identity, name=f"cold boot {number} after")
        boot_id = after.get("observed_boot_id")
        if not isinstance(boot_id, str) or not boot_id or boot_id == before.get("observed_boot_id"):
            fail(f"cold boot {number} identity is not fresh")
        exact(after.get("human_sign_in"), False, field=f"cold boot {number} human sign-in")
        exact(after.get("listener_task_s4u"), True, field=f"cold boot {number} listener task")
        exact(after.get("guardian_task_s4u"), True, field=f"cold boot {number} guardian task")
        exact(after.get("first_cycles_ok"), True, field=f"cold boot {number} first cycles")
        boot_ids.append(boot_id)
    if boot_ids[0] == boot_ids[1]:
        fail("cold boots are not distinct")


def verify_soak(manifest: dict, bundle: Path, identity: dict) -> None:
    observations = manifest.get("soak_observations")
    if not isinstance(observations, list) or len(observations) < 2:
        fail("soak observations are missing")
    points: list[datetime] = []
    names: set[str] = set()
    for entry in observations:
        if not isinstance(entry, dict) or set(entry) != {"path", "sha256"}:
            fail("soak manifest entry is invalid")
        name = entry["path"]
        if not isinstance(name, str) or name in names or not name.startswith("soak-") or not name.endswith(".json"):
            fail("soak path is invalid")
        names.add(name)
        path = bundle / name
        if not path.is_file() or entry["sha256"] != sha256(path):
            fail(f"soak receipt hash does not match: {name}")
        value = load_json(path)
        bound(value, identity, name=f"soak {name}")
        exact(value.get("t16_connected"), False, field=f"soak {name} T16 state")
        exact(value.get("monitor_state"), "IDLE", field=f"soak {name} monitor")
        exact(value.get("managed_mt5_count"), 1, field=f"soak {name} managed clients")
        exact(value.get("unattributable_mt5_count"), 0, field=f"soak {name} unknown clients")
        points.append(utc(value.get("observed_at_utc"), field=f"soak {name} time"))
    if points != sorted(points) or len(set(points)) != len(points):
        fail("soak timestamps are not strictly monotonic")
    if points[-1] - points[0] < MIN_SOAK:
        fail("soak is shorter than 24 active-market hours")
    if any(later - earlier > MAX_SOAK_GAP for earlier, later in zip(points, points[1:])):
        fail("soak observation gap exceeds bound")


def verify_lifecycle(manifest: dict, bundle: Path, identity: dict) -> None:
    value = receipt(manifest, bundle, "lifecycle-pnl.json")
    bound(value, identity, name="lifecycle")
    exact(value.get("state"), "CLOSED_MATCHED", field="lifecycle state")
    for field in ("proposal_id", "attempt_id", "position_identifier", "broker_close_ticket"):
        if not isinstance(value.get(field), str) or not value[field]:
            fail(f"lifecycle {field} is invalid")
    exact(value.get("account_currency"), "AUD", field="lifecycle account currency")
    if not isinstance(value.get("actual_broker_pnl_aud"), (int, float)):
        fail("lifecycle actual broker P&L is invalid")
    if not isinstance(value.get("postgres_coverage_row_id"), str) or not value["postgres_coverage_row_id"]:
        fail("lifecycle PostgreSQL coverage identity is invalid")


def verify(bundle: Path) -> None:
    manifest = load_json(bundle / "manifest.json")
    if set(manifest) != {"schema_version", "final_release", "receipts", "soak_observations"}:
        fail("final evidence manifest shape is invalid")
    exact(manifest.get("schema_version"), SCHEMA, field="final evidence schema")
    identity = manifest.get("final_release")
    if not isinstance(identity, dict) or set(identity) != {"configuration_fingerprint", "listener_release_id", "guardian_release_id", "boot_id"}:
        fail("final release binding is invalid")
    for field, value in identity.items():
        if not isinstance(value, str) or not value:
            fail(f"final release {field} is invalid")
    paths = {entry.get("path") for entry in manifest.get("receipts", []) if isinstance(entry, dict)}
    if paths != REQUIRED_RECEIPTS:
        fail("final evidence receipt set is incomplete")
    verify_recovery(manifest, bundle, identity)
    verify_boots(manifest, bundle, identity)
    verify_soak(manifest, bundle, identity)
    verify_lifecycle(manifest, bundle, identity)
    print(json.dumps({"marker": MARKER, "bundle": str(bundle)}, separators=(",", ":")))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("bundle", type=Path)
    args = parser.parse_args()
    try:
        verify(args.bundle)
    except ValueError as error:
        print(f"M33 final health evidence error: {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
