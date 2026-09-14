"""Validate and retain the fixed latest-M20-assessment adapter export.

The live listener owns the replace-only source record.  This module only turns
one successful read-only adapter observation into an immutable local directory
that existing annotation/replay tooling can consume.  It never polls MT5,
changes the listener, or creates a trade instruction.
"""
from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import re
from typing import Any

from forex.m20_retained_export import RetainedExportInputError, adapt_retained_m20_export


SCHEMA = "forex.m20.current-assessment-export.v1"
OPERATION = "m20_listener_latest_assessment"
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}\Z")
_RELEASE = re.compile(r"[0-9a-f]{16}\Z")
_CURSOR_SCHEMA = "forex.m20.current-assessment-export-cursor.v1"
_CURSOR_NAME = ".m20-current-assessment-export-cursor.json"


class CurrentAssessmentExportError(ValueError):
    """The fixed adapter result is absent, malformed, or unsafe to retain."""


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise CurrentAssessmentExportError("duplicate JSON field")
        result[key] = value
    return result


def _constant(value: str) -> None:
    raise CurrentAssessmentExportError(f"nonfinite JSON value: {value}")


def _json(raw: bytes | str) -> Any:
    try:
        return json.loads(raw, object_pairs_hook=_pairs, parse_constant=_constant)
    except (TypeError, json.JSONDecodeError) as exc:
        raise CurrentAssessmentExportError("adapter result is not valid JSON") from exc


def _canonical(value: Any) -> bytes:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise CurrentAssessmentExportError("adapter result contains non-JSON values") from exc


def _sha(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _utc(value: object, *, field: str) -> str:
    if not isinstance(value, str):
        raise CurrentAssessmentExportError(f"{field} must be a timezone-aware timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise CurrentAssessmentExportError(f"{field} must be a timezone-aware timestamp") from exc
    if parsed.tzinfo is None:
        raise CurrentAssessmentExportError(f"{field} must be a timezone-aware timestamp")
    return parsed.astimezone(UTC).isoformat().replace("+00:00", "Z")


def parse_adapter_result(raw: bytes) -> dict[str, Any]:
    """Validate one raw adapter CLI response without filling any missing data."""
    outer = _json(raw)
    if not isinstance(outer, dict) or outer.get("operation") != OPERATION or outer.get("ok") is not True:
        raise CurrentAssessmentExportError("result is not a successful fixed latest-assessment operation")
    result = outer.get("result")
    if not isinstance(result, dict) or not isinstance(result.get("stdout"), str):
        raise CurrentAssessmentExportError("adapter result has no fixed operation stdout")
    observed = _json(result["stdout"])
    if not isinstance(observed, dict):
        raise CurrentAssessmentExportError("latest-assessment operation stdout is not an object")
    observation = observed.get("observation")
    if observation in {"LISTENER_STATUS_ABSENT", "LATEST_ASSESSMENT_ABSENT"}:
        return {"state": "ASSESSMENT_ABSENT", "observation": observation, "execution_authority": False}
    if observation != "AVAILABLE":
        raise CurrentAssessmentExportError("latest-assessment operation returned an unknown observation")
    release = observed.get("listener_release_id")
    if not isinstance(release, str) or _RELEASE.fullmatch(release) is None:
        raise CurrentAssessmentExportError("latest-assessment release ID is invalid")
    sequence = observed.get("assessment_sequence")
    if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence <= 0:
        raise CurrentAssessmentExportError("latest-assessment sequence is invalid")
    if not isinstance(observed.get("raw_sha256"), str) or _DIGEST.fullmatch(observed["raw_sha256"]) is None:
        raise CurrentAssessmentExportError("latest-assessment source digest is invalid")
    try:
        adapted = adapt_retained_m20_export(outer)
    except RetainedExportInputError as exc:
        raise CurrentAssessmentExportError(f"latest assessment cannot form one retained replay pair: {exc}") from exc
    if (adapted["retained_export_coverage"].get("replayable_pair_count") != 1
            or adapted["retained_export_coverage"].get("coverage_only_row_count") != 0):
        raise CurrentAssessmentExportError("latest assessment does not contain exactly one replayable pair")
    assessment = observed.get("assessment")
    if not isinstance(assessment, dict):
        raise CurrentAssessmentExportError("latest-assessment body is invalid")
    completed = _utc(observed.get("assessment_completed_at_utc"), field="assessment_completed_at_utc")
    started = _utc(observed.get("assessment_started_at_utc"), field="assessment_started_at_utc")
    if completed < started:
        raise CurrentAssessmentExportError("latest-assessment timestamps are not chronological")
    assessment_raw = _canonical(assessment)
    stdout_raw = result["stdout"].encode("utf-8")
    return {
        "state": "AVAILABLE",
        "listener_release_id": release,
        "assessment_sequence": sequence,
        "assessment_started_at_utc": started,
        "assessment_completed_at_utc": completed,
        "listener_record_sha256": observed["raw_sha256"],
        "adapter_stdout_sha256": _sha(stdout_raw),
        "adapter_response_sha256": _sha(raw),
        "assessment_raw_sha256": _sha(assessment_raw),
        "assessment_raw": assessment_raw,
        "adapter_response_raw": raw,
        "execution_authority": False,
    }


def _trusted(root: Path) -> Path:
    from forex.event_capture_store import _no_symlink_ancestors
    if not root.exists() or root.is_symlink() or not root.is_dir():
        raise CurrentAssessmentExportError("assessment export root must be an existing trusted directory")
    _no_symlink_ancestors(root)
    return root


def _name(record: dict[str, Any]) -> str:
    stamp = record["assessment_completed_at_utc"].replace("-", "").replace(":", "").replace(".", "")
    return f"{record['listener_release_id']}-{record['assessment_sequence']:012d}-{stamp}-{record['assessment_raw_sha256'][7:23]}"


def _write_new(path: Path, raw: bytes) -> None:
    with path.open("xb") as handle:
        handle.write(raw)
        handle.flush()
        # A future batch must not observe a source file before this local write
        # is durable enough to be represented by the receipt below.
        import os
        os.fsync(handle.fileno())


def _cursor_path(root: Path) -> Path:
    return root / _CURSOR_NAME


def _load_cursor(root: Path) -> dict[str, Any] | None:
    path = _cursor_path(root)
    if not path.exists():
        return None
    if path.is_symlink() or not path.is_file():
        raise CurrentAssessmentExportError("assessment export cursor is unsafe")
    value = _json(path.read_bytes())
    if (not isinstance(value, dict) or set(value) != {"schema_version", "listener_release_id", "assessment_sequence", "assessment_raw_sha256"}
            or value.get("schema_version") != _CURSOR_SCHEMA or not isinstance(value.get("listener_release_id"), str)
            or _RELEASE.fullmatch(value["listener_release_id"]) is None
            or isinstance(value.get("assessment_sequence"), bool)
            or not isinstance(value.get("assessment_sequence"), int) or value["assessment_sequence"] <= 0
            or not isinstance(value.get("assessment_raw_sha256"), str)
            or _DIGEST.fullmatch(value["assessment_raw_sha256"]) is None):
        raise CurrentAssessmentExportError("assessment export cursor is invalid")
    return value


def _coverage(root: Path, record: dict[str, Any]) -> dict[str, Any]:
    prior = _load_cursor(root)
    if prior is None or prior["listener_release_id"] != record["listener_release_id"]:
        return {"coverage_status": "BASELINE_UNVERIFIED", "missed_assessment_count": None,
                "previous_assessment_sequence": None}
    previous = prior["assessment_sequence"]
    current = record["assessment_sequence"]
    if current < previous:
        raise CurrentAssessmentExportError("assessment sequence regressed within one listener release")
    if current == previous:
        if prior["assessment_raw_sha256"] != record["assessment_raw_sha256"]:
            raise CurrentAssessmentExportError("assessment sequence duplicates a different retained body")
        return {"coverage_status": "DUPLICATE", "missed_assessment_count": 0,
                "previous_assessment_sequence": previous}
    missed = current - previous - 1
    return {"coverage_status": "CONTIGUOUS" if missed == 0 else "GAP_OBSERVED",
            "missed_assessment_count": missed, "previous_assessment_sequence": previous}


def _store_cursor(root: Path, record: dict[str, Any]) -> None:
    value = {"schema_version": _CURSOR_SCHEMA, "listener_release_id": record["listener_release_id"],
             "assessment_sequence": record["assessment_sequence"],
             "assessment_raw_sha256": record["assessment_raw_sha256"]}
    raw = _canonical(value)
    path = _cursor_path(root)
    temporary = path.with_suffix(".tmp")
    if temporary.exists() or temporary.is_symlink():
        raise CurrentAssessmentExportError("assessment export cursor temporary path is unsafe")
    try:
        _write_new(temporary, raw)
        temporary.replace(path)
    except OSError as exc:
        raise CurrentAssessmentExportError("assessment export cursor cannot be published") from exc


def retain(root: Path, record: dict[str, Any]) -> tuple[Path, str]:
    """Publish immutable raw response, assessment body, then receipt in one child.

    The assessment file is written last so the existing one-level M1 batch does
    not discover a partial capture. Existing matching captures are idempotent;
    conflicts or incomplete directories fail rather than being repaired.
    """
    root = _trusted(root)
    if record.get("state") != "AVAILABLE":
        raise CurrentAssessmentExportError("only an available assessment can be retained")
    if "coverage" not in record:
        record = {**record, "coverage": _coverage(root, record)}
    target = root / _name(record)
    receipt_content = {
        "schema_version": SCHEMA,
        "listener_release_id": record["listener_release_id"],
        "assessment_sequence": record["assessment_sequence"],
        "assessment_started_at_utc": record["assessment_started_at_utc"],
        "assessment_completed_at_utc": record["assessment_completed_at_utc"],
        "listener_record_sha256": record["listener_record_sha256"],
        "adapter_stdout_sha256": record["adapter_stdout_sha256"],
        "adapter_response_sha256": record["adapter_response_sha256"],
        "assessment_raw_sha256": record["assessment_raw_sha256"],
        "coverage_status": record["coverage"]["coverage_status"],
        "missed_assessment_count": record["coverage"]["missed_assessment_count"],
        "previous_assessment_sequence": record["coverage"]["previous_assessment_sequence"],
        "execution_authority": False,
    }
    receipt_raw = _canonical({**receipt_content, "receipt_sha256": _sha(_canonical(receipt_content))})
    expected = {
        "adapter-operation.json": record["adapter_response_raw"],
        "receipt.json": receipt_raw,
        "demo-trading-operation.json": record["assessment_raw"],
    }
    try:
        target.mkdir(mode=0o700)
        created = True
    except FileExistsError:
        created = False
    if not created:
        required = set(expected)
        if target.is_symlink() or not target.is_dir() or set(item.name for item in target.iterdir()) != required:
            raise CurrentAssessmentExportError("existing assessment capture is incomplete or unsafe")
        for name in ("adapter-operation.json", "demo-trading-operation.json"):
            if (target / name).is_symlink() or (target / name).read_bytes() != expected[name]:
                raise CurrentAssessmentExportError("existing assessment capture conflicts")
        try:
            receipt = _json((target / "receipt.json").read_bytes())
        except OSError as exc:
            raise CurrentAssessmentExportError("existing assessment receipt cannot be read") from exc
        if (not isinstance(receipt, dict) or receipt.get("assessment_raw_sha256") != record["assessment_raw_sha256"]
                or receipt.get("listener_release_id") != record["listener_release_id"]
                or receipt.get("assessment_sequence") != record["assessment_sequence"]):
            raise CurrentAssessmentExportError("existing assessment capture conflicts")
        _store_cursor(root, record)
        return target, "EXISTING"
    try:
        _write_new(target / "adapter-operation.json", expected["adapter-operation.json"])
        _write_new(target / "receipt.json", expected["receipt.json"])
        _write_new(target / "demo-trading-operation.json", expected["demo-trading-operation.json"])
    except BaseException:
        # Preserve the incomplete directory as an observable refusal. Never
        # delete it or overwrite a partial capture.
        raise
    _store_cursor(root, record)
    return target, "CREATED"
