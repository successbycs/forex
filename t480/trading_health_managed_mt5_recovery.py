"""Pure fail-closed M33 MT5 recovery contract helpers.

No function in this module starts, stops, imports or connects to MT5.  The
later fixed adapter may invoke an effect only after these checks and a second
under-mutex inventory observation agree exactly.
"""
from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

REQUEST_SCHEMA = "forex.trading-health-mt5-recovery-request.v1"
COORDINATOR_SCHEMA = "forex.trading-health-recovery-coordinator.v1"
NONTERMINAL = {"PENDING", "CLAIMED", "DISPATCHED"}
ACTIONS = {"START_ONE_MT5", "RECYCLE_MANAGED_SET_FLAT"}


def digest(value: dict[str, Any]) -> str:
    return "sha256:" + hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def inventory_digest(inventory: dict[str, Any]) -> str:
    value = {key: value for key, value in inventory.items() if key != "inventory_sha256"}
    return digest(value)


def classify_inventory(rows: list[dict[str, Any]], binding: dict[str, Any]) -> dict[str, Any]:
    """Classify exact process identities; any other terminal is unattributable."""
    expected_path = binding.get("terminal_path")
    expected_session = binding.get("session_id")
    if not isinstance(expected_path, str) or not expected_path or expected_session != 0:
        raise ValueError("TASK_BINDING_INVALID")
    required = {"pid", "path", "session_id", "command_line_sha256", "parent_pid", "parent_path", "creation_id"}
    if not isinstance(rows, list) or any(not isinstance(row, dict) or set(row) != required for row in rows):
        raise ValueError("INVENTORY_SHAPE_INVALID")
    seen: set[tuple[int, str]] = set(); classified: list[dict[str, Any]] = []
    managed: list[dict[str, Any]] = []
    for row in rows:
        if (type(row["pid"]) is not int or row["pid"] <= 0 or type(row["parent_pid"]) is not int
                or not all(isinstance(row[key], str) and row[key] for key in ("path", "parent_path", "command_line_sha256", "creation_id"))
                or type(row["session_id"]) is not int):
            raise ValueError("INVENTORY_IDENTITY_INVALID")
        key = (row["pid"], row["creation_id"])
        if key in seen: raise ValueError("INVENTORY_DUPLICATE_IDENTITY")
        seen.add(key)
        item = dict(row)
        if (row["path"].casefold() == expected_path.casefold() and row["session_id"] == expected_session
                and row["parent_path"].casefold() == str(binding.get("parent_path", "")).casefold()
                and row["command_line_sha256"] == binding.get("command_line_sha256")):
            managed.append(item)
        else:
            item["classification"] = "UNATTRIBUTABLE"; classified.append(item)
    managed.sort(key=lambda row: (row["creation_id"], row["pid"]))
    for index, item in enumerate(managed):
        item["classification"] = "PRIMARY_MANAGED" if index == 0 else "ADDITIONAL_MANAGED"; classified.append(item)
    value = {"schema_version": "forex.trading-health-mt5-inventory.v1", "processes": sorted(classified, key=lambda row: row["pid"]), "inventory_sha256": None}
    value["inventory_sha256"] = inventory_digest(value)
    return value


def validate_request(request: dict[str, Any], coordinator: dict[str, Any] | None, *, now: datetime,
                     binding_sha256: str, inventory_sha256: str, boot_id: str, fingerprint: str) -> str | None:
    required = {"schema_version", "state", "request_id", "generation", "recovery_epoch", "boot_id", "configuration_fingerprint", "account_scope_sha256", "profile_sha256", "task_binding_sha256", "inventory_sha256", "action", "issued_at_utc", "expires_at_utc", "entry_eligible"}
    if set(request) != required or request.get("schema_version") != REQUEST_SCHEMA or request.get("state") != "PENDING": return "REQUEST_SHAPE_INVALID"
    if request.get("action") not in ACTIONS or request.get("entry_eligible") is not False: return "REQUEST_ACTION_OR_ENTRY_INVALID"
    if request.get("boot_id") != boot_id or request.get("configuration_fingerprint") != fingerprint or request.get("task_binding_sha256") != binding_sha256 or request.get("inventory_sha256") != inventory_sha256: return "REQUEST_BINDING_MISMATCH"
    try: expiry = datetime.fromisoformat(str(request["expires_at_utc"]).replace("Z", "+00:00")).astimezone(UTC)
    except ValueError: return "REQUEST_TIME_INVALID"
    if expiry <= now.astimezone(UTC): return "REQUEST_STALE"
    if coordinator is not None:
        if (coordinator.get("schema_version") != COORDINATOR_SCHEMA or coordinator.get("phase") in NONTERMINAL
                or coordinator.get("boot_id") != boot_id or coordinator.get("configuration_fingerprint") != fingerprint):
            return "CROSS_PROTOCOL_RECOVERY_ACTIVE_OR_INVALID"
    return None


def verify_duplicate_targets(inventory: dict[str, Any], fresh: dict[str, Any]) -> list[dict[str, Any]]:
    """Return stoppable duplicates only if every dynamic identity survived re-enumeration."""
    if inventory.get("inventory_sha256") != inventory_digest(inventory) or fresh.get("inventory_sha256") != inventory_digest(fresh):
        raise ValueError("INVENTORY_DIGEST_INVALID")
    original = {item["pid"]: item for item in inventory.get("processes", []) if item.get("classification") == "ADDITIONAL_MANAGED"}
    fresh_by_pid = {item["pid"]: item for item in fresh.get("processes", [])}
    if not original: raise ValueError("NO_ATTRIBUTABLE_DUPLICATE")
    for pid, item in original.items():
        other = fresh_by_pid.get(pid)
        if other is None or any(other.get(key) != item.get(key) for key in ("creation_id", "path", "session_id", "command_line_sha256", "parent_pid", "parent_path")):
            raise ValueError("DUPLICATE_IDENTITY_CHANGED")
    if any(item.get("classification") == "UNATTRIBUTABLE" for item in fresh.get("processes", [])):
        raise ValueError("UNATTRIBUTABLE_PROCESS_PRESENT")
    return [original[pid] for pid in sorted(original)]
