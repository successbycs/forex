"""Immutable local retention and read-only verification of H_SLOW OOS runs.

Retention is the sole writer. Verification never creates directories, repairs
records, or calls retention; it only reads one exact regular file and reports a
hash-bound receipt. These records carry no trading authority.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any


SCHEMA = "forex.h-slow.forward-oos-evidence.v1"
RECEIPT_SCHEMA = "forex.h-slow.forward-oos-verification.v1"
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}\Z")
_RECORD_ID = re.compile(r"[a-z0-9][a-z0-9._-]{0,127}\Z")


class HSlowOOSEvidenceError(ValueError):
    """A retention record or its local storage boundary is invalid."""


def _canonical(value: Any) -> bytes:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise HSlowOOSEvidenceError("OOS record must be finite JSON") from exc


def _sha(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _digest(value: Any, label: str) -> str:
    if not isinstance(value, str) or not _DIGEST.fullmatch(value):
        raise HSlowOOSEvidenceError(f"{label} must be a canonical SHA-256 digest")
    return value


def _decimal(value: Any, label: str, *, nonnegative: bool = False) -> None:
    if isinstance(value, bool):
        raise HSlowOOSEvidenceError(f"{label} must be finite numeric")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise HSlowOOSEvidenceError(f"{label} must be finite numeric") from exc
    if not number.is_finite() or (nonnegative and number < 0):
        raise HSlowOOSEvidenceError(f"{label} must be finite numeric")
    if label == "max_drawdown" and number > 1:
        raise HSlowOOSEvidenceError("max_drawdown must be between zero and one")


def _utc(value: Any) -> None:
    if not isinstance(value, str):
        raise HSlowOOSEvidenceError("decision_at_utc is invalid")
    try:
        instant = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise HSlowOOSEvidenceError("decision_at_utc is invalid") from exc
    if instant.tzinfo is None or instant.utcoffset() != UTC.utcoffset(instant):
        raise HSlowOOSEvidenceError("decision_at_utc must be UTC")


def _validate_record(record: Any) -> dict[str, Any]:
    fields = {"schema_version", "record_id", "research_decision_sha256", "strategy_policy_version",
              "decision_at_utc", "metrics", "source_snapshot_sha256", "execution_authority"}
    if (not isinstance(record, dict) or set(record) != fields or record.get("schema_version") != SCHEMA
            or record.get("execution_authority") is not False
            or not isinstance(record.get("record_id"), str) or not _RECORD_ID.fullmatch(record["record_id"])
            or not isinstance(record.get("strategy_policy_version"), str) or not record["strategy_policy_version"]):
        raise HSlowOOSEvidenceError("OOS record fields are invalid")
    _utc(record["decision_at_utc"])
    _digest(record.get("research_decision_sha256"), "research_decision_sha256")
    _digest(record.get("source_snapshot_sha256"), "source_snapshot_sha256")
    metrics = record.get("metrics")
    if (not isinstance(metrics, dict) or set(metrics) != {"sample_count", "net_after_cost_return", "max_drawdown"}
            or type(metrics.get("sample_count")) is not int or metrics["sample_count"] < 1):
        raise HSlowOOSEvidenceError("OOS metrics are invalid")
    _decimal(metrics["net_after_cost_return"], "net_after_cost_return")
    _decimal(metrics["max_drawdown"], "max_drawdown", nonnegative=True)
    return json.loads(_canonical(record))


def _root_is_safe(root: Path, *, must_exist: bool) -> Path:
    if not isinstance(root, Path) or any(component.is_symlink() for component in (root, *root.parents)):
        raise HSlowOOSEvidenceError("OOS evidence root is invalid")
    if must_exist and not root.is_dir():
        raise HSlowOOSEvidenceError("OOS evidence root is invalid")
    if root.exists() and not root.is_dir():
        raise HSlowOOSEvidenceError("OOS evidence root is not a directory")
    return root


def _ensure_root(root: Path) -> None:
    """Create a safe root and persist each newly created directory entry."""
    missing: list[Path] = []
    cursor = root
    while not cursor.exists():
        missing.append(cursor)
        cursor = cursor.parent
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    if root.is_symlink() or not root.is_dir():
        raise HSlowOOSEvidenceError("OOS evidence root became unsafe")
    for created in reversed(missing):
        descriptor = os.open(created.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


def _path(root: Path, record_id: str) -> Path:
    if not isinstance(record_id, str) or not _RECORD_ID.fullmatch(record_id):
        raise HSlowOOSEvidenceError("OOS record ID is invalid")
    return root / f"{record_id}.json"


def retain_oos_record(root: Path, record: dict[str, Any]) -> dict[str, Any]:
    """Write exactly one canonical record, or confirm byte-identical retention."""
    validated = _validate_record(record)
    root = _root_is_safe(root, must_exist=False)
    _ensure_root(root)
    path = _path(root, validated["record_id"])
    raw = _canonical(validated)
    if path.exists():
        if path.is_symlink() or not path.is_file() or path.read_bytes() != raw:
            raise HSlowOOSEvidenceError("immutable OOS record conflicts")
        # A crash after publication but before staging cleanup leaves evidence,
        # not an error to repair. Preserve that staging file and fsync the
        # final directory again before confirming the idempotent record.
        directory_descriptor = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory_descriptor)
        finally:
            os.close(directory_descriptor)
    else:
        if any(root.glob(f".{validated['record_id']}.*.staging")):
            raise HSlowOOSEvidenceError("unfinished OOS retention staging exists")
        staging = root / f".{validated['record_id']}.{secrets.token_hex(16)}.staging"
        try:
            descriptor = os.open(staging, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        except FileExistsError as exc:
            raise HSlowOOSEvidenceError("immutable OOS record raced") from exc
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        published = False
        try:
            os.link(staging, path, follow_symlinks=False)
            directory_descriptor = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory_descriptor)
            finally:
                os.close(directory_descriptor)
            published = True
        except FileExistsError as exc:
            raise HSlowOOSEvidenceError("immutable OOS record raced") from exc
        finally:
            # An unsuccessful link or fsync leaves the staging artifact for
            # explicit recovery; deleting it would turn a durable capture into
            # silent data loss. Delete only after final publication is durable.
            if published and staging.exists() and not staging.is_symlink():
                staging.unlink()
                directory_descriptor = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
                try:
                    os.fsync(directory_descriptor)
                finally:
                    os.close(directory_descriptor)
    return {"schema_version": RECEIPT_SCHEMA, "record_id": validated["record_id"],
            "record_sha256": _sha(raw), "record": validated, "execution_authority": False}


def verify_oos_record(root: Path, record_id: str, *, expected_record_sha256: str | None = None) -> dict[str, Any]:
    """Read and validate one record without creating or modifying anything."""
    root = _root_is_safe(root, must_exist=True)
    path = _path(root, record_id)
    if path.is_symlink() or not path.is_file():
        raise HSlowOOSEvidenceError("OOS record is missing or unsafe")
    try:
        raw = path.read_bytes()
        decoded = json.loads(raw)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HSlowOOSEvidenceError("OOS record is unreadable") from exc
    record = _validate_record(decoded)
    if record["record_id"] != record_id:
        raise HSlowOOSEvidenceError("OOS record body does not match requested ID")
    if raw != _canonical(record):
        raise HSlowOOSEvidenceError("OOS record is not canonical immutable JSON")
    actual_digest = _sha(raw)
    if expected_record_sha256 is not None and actual_digest != _digest(expected_record_sha256, "expected_record_sha256"):
        raise HSlowOOSEvidenceError("OOS record digest does not match expected retained record")
    return {"schema_version": RECEIPT_SCHEMA, "record_id": record["record_id"],
            "record_sha256": actual_digest, "record": record, "execution_authority": False}
