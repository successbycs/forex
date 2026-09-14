"""Copy immutable M20 listener spool records into local assessment captures.

The source spool is never deleted or acknowledged remotely.  A local cursor is
advanced only after every corresponding immutable capture is complete, making
it a post-retention acknowledgement rather than a permission to discard source
evidence.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any

from forex.m20_assessment_spool import AssessmentSpoolError, read_immutable_spool


SCHEMA = "forex.m20.spool-drain-receipt.v1"
CURSOR_SCHEMA = "forex.m20.spool-drain-cursor.v1"
_CURSOR = ".m20-spool-drain-cursor.json"
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}")


class SpoolDrainError(ValueError):
    """A source, local capture, or acknowledgement state is unsafe."""


def _canonical(value: Any) -> bytes:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise SpoolDrainError("drain record is not finite JSON") from exc


def _sha(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _trusted(path: Path, *, label: str) -> Path:
    from forex.event_capture_store import _no_symlink_ancestors
    if not isinstance(path, Path) or not path.exists() or path.is_symlink() or not path.is_dir():
        raise SpoolDrainError(f"{label} must name an existing trusted directory")
    _no_symlink_ancestors(path)
    return path


def _write_new(path: Path, raw: bytes) -> None:
    with path.open("xb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())


def _cursor_path(root: Path) -> Path:
    return root / _CURSOR


def _load_cursor(root: Path) -> dict[str, Any] | None:
    path = _cursor_path(root)
    if not path.exists():
        return None
    if path.is_symlink() or not path.is_file():
        raise SpoolDrainError("spool drain cursor is unsafe")
    try:
        value = json.loads(path.read_bytes())
    except (OSError, json.JSONDecodeError) as exc:
        raise SpoolDrainError("spool drain cursor is invalid") from exc
    if (not isinstance(value, dict) or set(value) != {"schema_version", "listener_release_id", "assessment_sequence", "source_sha256"}
            or value.get("schema_version") != CURSOR_SCHEMA or not isinstance(value.get("listener_release_id"), str)
            or isinstance(value.get("assessment_sequence"), bool) or not isinstance(value.get("assessment_sequence"), int)
            or value["assessment_sequence"] <= 0 or not isinstance(value.get("source_sha256"), str)
            or _DIGEST.fullmatch(value["source_sha256"]) is None):
        raise SpoolDrainError("spool drain cursor is invalid")
    return value


def _store_cursor(root: Path, *, release: str, sequence: int, source_sha256: str) -> None:
    raw = _canonical({"schema_version": CURSOR_SCHEMA, "listener_release_id": release,
                      "assessment_sequence": sequence, "source_sha256": source_sha256})
    target = _cursor_path(root)
    temporary = target.with_suffix(".tmp")
    try:
        # A completed matching staging file can be left behind if the process
        # was interrupted after fsync but before the atomic rename. Reusing it
        # is safe and lets the next read-only export recover. Any different,
        # partial, or symlinked staging file remains an investigation stop.
        if temporary.exists() or temporary.is_symlink():
            if temporary.is_symlink() or not temporary.is_file() or temporary.read_bytes() != raw:
                raise SpoolDrainError("spool drain cursor temporary path is unsafe")
        else:
            _write_new(temporary, raw)
        temporary.replace(target)
        directory = os.open(root, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    except SpoolDrainError:
        raise
    except OSError as exc:
        raise SpoolDrainError("spool drain cursor cannot be published") from exc


def _target(root: Path, *, release: str, sequence: int, source_sha256: str) -> Path:
    return root / f"{release}-{sequence:020d}-{source_sha256[7:23]}"


def _retain_one(root: Path, *, release: str, row: dict[str, Any]) -> tuple[Path, str]:
    source_raw = Path(row["source_path"]).read_bytes()
    source_sha = row["source_sha256"]
    record = row["record"]
    assessment_raw = _canonical(record["assessment"])
    sequence = row["assessment_sequence"]
    receipt_content = {"schema_version": SCHEMA, "listener_release_id": release,
                       "assessment_sequence": sequence, "source_record_sha256": source_sha,
                       "assessment_raw_sha256": _sha(assessment_raw), "execution_authority": False}
    receipt = {**receipt_content, "receipt_sha256": _sha(_canonical(receipt_content))}
    expected = {"listener-spool-record.json": source_raw, "receipt.json": _canonical(receipt),
                "demo-trading-operation.json": assessment_raw}
    target = _target(root, release=release, sequence=sequence, source_sha256=source_sha)
    try:
        target.mkdir(mode=0o700)
        created = True
    except FileExistsError:
        created = False
    if not created:
        if target.is_symlink() or not target.is_dir() or {item.name for item in target.iterdir()} != set(expected):
            raise SpoolDrainError("existing spool capture is incomplete or unsafe")
        if any((target / name).is_symlink() or (target / name).read_bytes() != raw for name, raw in expected.items()):
            raise SpoolDrainError("existing spool capture conflicts")
        return target, "EXISTING"
    try:
        _write_new(target / "listener-spool-record.json", expected["listener-spool-record.json"])
        _write_new(target / "receipt.json", expected["receipt.json"])
        # Existing M1 discovery treats this final file as the completeness gate.
        _write_new(target / "demo-trading-operation.json", expected["demo-trading-operation.json"])
    except BaseException:
        raise
    return target, "CREATED"


def drain(*, spool_root: Path, capture_root: Path, listener_release_id: str) -> dict[str, Any]:
    """Retain every new source record, then atomically advance local progress."""
    target_root = _trusted(capture_root, label="capture_root")
    try:
        source = read_immutable_spool(spool_root, listener_release_id=listener_release_id)
    except AssessmentSpoolError as exc:
        raise SpoolDrainError(f"spool source refused: {exc}") from exc
    cursor = _load_cursor(target_root)
    if cursor is not None and cursor["listener_release_id"] != listener_release_id:
        raise SpoolDrainError("spool drain cursor release differs from source")
    previous = cursor["assessment_sequence"] if cursor else None
    new = [row for row in source["records"] if previous is None or row["assessment_sequence"] > previous]
    if cursor is not None:
        matching = [row for row in source["records"] if row["assessment_sequence"] == previous]
        if not matching or matching[0]["source_sha256"] != cursor["source_sha256"]:
            raise SpoolDrainError("spool drain cursor does not bind current source")
    retained = []
    for row in new:
        path, publication = _retain_one(target_root, release=listener_release_id, row=row)
        retained.append({"assessment_sequence": row["assessment_sequence"], "capture_path": str(path),
                         "source_sha256": row["source_sha256"], "publication": publication})
    if retained:
        last = retained[-1]
        _store_cursor(target_root, release=listener_release_id, sequence=last["assessment_sequence"],
                      source_sha256=last["source_sha256"])
    return {"schema_version": "forex.m20.spool-drain-result.v1", "listener_release_id": listener_release_id,
            "source_coverage_status": source["coverage_status"], "source_record_count": len(source["records"]),
            "retained_count": len(retained), "retained": retained,
            "acknowledgement": "LOCAL_CURSOR_ADVANCED_AFTER_IMMUTABLE_RETENTION" if retained else "NO_NEW_SOURCE_RECORDS",
            "execution_authority": False}
