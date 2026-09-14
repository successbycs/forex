"""Retain fixed BLS HTTP observations and feed only successful HTML to parsing."""
from __future__ import annotations

import base64
from datetime import datetime, UTC
import json
import os
from pathlib import Path

from .event_capture_store import (_layout, _existing_layout, _lock, _read_lock,
    _directory, _safe_id, _sha, _publish_exclusive, _unique_fields, _invalid_constant,
    retain_bls_capture, EventCaptureStoreError)
from .event_capture_recovery import resume_bls_capture

MAX_BODY_BYTES = 2 * 1024 * 1024
FIELDS = {"schema_version", "requested_url", "started_at_utc", "completed_at_utc",
          "status_code", "content_type", "body_base64", "body_complete", "outcome",
          "error_code", "execution_authority"}


def monthly_url(year: int, month: int) -> str:
    if type(year) is not int or not 2000 <= year <= 2099 or type(month) is not int or not 1 <= month <= 12:
        raise ValueError("BLS collection requires a year 2000..2099 and month 1..12")
    return f"https://www.bls.gov/schedule/{year}/{month:02d}_sched_list.htm"


def validate_response(raw: bytes, *, year: int, month: int):
    if not isinstance(raw, bytes) or len(raw) > MAX_BODY_BYTES * 2:
        raise ValueError("BLS response envelope exceeds its limit")
    value = json.loads(raw, object_pairs_hook=_unique_fields, parse_constant=_invalid_constant)
    if not isinstance(value, dict) or set(value) != FIELDS:
        raise ValueError("BLS response fields are invalid")
    if value["schema_version"] != "forex.bls-http-observation.v1" or value["execution_authority"] is not False:
        raise ValueError("BLS response schema or authority is invalid")
    if value["requested_url"] != monthly_url(year, month):
        raise ValueError("BLS response does not bind requested month")
    times = []
    for field in ("started_at_utc", "completed_at_utc"):
        stamp = value[field]
        if not isinstance(stamp, str):
            raise ValueError("BLS response timestamps must be strings")
        parsed = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError("BLS response timestamps need offsets")
        times.append(parsed.astimezone(UTC))
    if times[1] < times[0]:
        raise ValueError("BLS response completion precedes start")
    status = value["status_code"]
    if status is not None and (type(status) is not int or not 100 <= status <= 599):
        raise ValueError("BLS response HTTP status is invalid")
    if type(value["body_complete"]) is not bool:
        raise ValueError("BLS response completeness must be Boolean")
    if value["content_type"] is not None and not isinstance(value["content_type"], str):
        raise ValueError("BLS response content type is invalid")
    if value["outcome"] not in {"SUCCESS", "HTTP_ERROR", "TRANSPORT_ERROR", "BODY_TOO_LARGE", "UNSUPPORTED_CONTENT_TYPE"}:
        raise ValueError("BLS response outcome is invalid")
    if value["error_code"] is not None and value["error_code"] not in {"HTTP_STATUS", "TRANSPORT_ERROR", "BODY_TOO_LARGE", "UNSUPPORTED_CONTENT_TYPE", "TIMEOUT", "TLS_ERROR", "URL_ERROR", "INCOMPLETE_BODY", "EMPTY_BODY"}:
        raise ValueError("BLS response error code is invalid")
    body = base64.b64decode(value["body_base64"], validate=True)
    if len(body) > MAX_BODY_BYTES:
        raise ValueError("BLS response body exceeds its limit")
    if value["outcome"] == "SUCCESS" and (status != 200 or not value["body_complete"]
            or value["error_code"] is not None or not body
            or (value["content_type"] or "").split(";", 1)[0].strip().lower() not in {"text/html", "application/xhtml+xml"}):
        raise ValueError("BLS success does not contain a complete HTML 200 response")
    return value, body


def retain_response(root: Path, *, capture_id: str, raw: bytes, year: int, month: int):
    """Publish exact observation bytes once; repeat bytes are idempotent."""
    _safe_id(capture_id)
    validate_response(raw, year=year, month=month)
    _retain_bytes(root, category="acquisitions", capture_id=capture_id, raw=raw)
    return apply_retained_response(root, capture_id=capture_id, year=year, month=month)


def _retain_bytes(root, *, category, capture_id, raw):
    _safe_id(capture_id)
    _layout(root)
    with _lock(root):
        directory = root / category / capture_id
        _directory(directory)
        for parent in (root, directory.parent):
            fd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
        paths = list(directory.glob("*.json"))
        path = directory / (_sha(raw).removeprefix("sha256:") + ".json")
        if paths:
            if paths != [path] or path.is_symlink() or path.read_bytes() != raw:
                raise EventCaptureStoreError("capture acquisition identity already has different bytes")
        else:
            _publish_exclusive(path, raw)


def retain_transport_observation(root, *, capture_id, year, month, observation,
                                 probe_sha256, source_declaration_sha256, program_sha256=None):
    """Retain the actual shared transport result, including failure evidence."""
    monthly_url(year, month)
    payload = {"schema_version": "forex.bls-transport-receipt.v1", "requested_url": monthly_url(year, month),
               "probe_sha256": probe_sha256, "source_declaration_sha256": source_declaration_sha256,
               "transport_observation": observation}
    if program_sha256 is not None:
        payload["program_sha256"] = program_sha256
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    _retain_bytes(root, category="transport", capture_id=capture_id, raw=raw)
    return _sha(raw)


def apply_retained_response(root: Path, *, capture_id: str, year: int, month: int):
    """Resume local processing of an immutable response, without a network call."""
    _safe_id(capture_id)
    _existing_layout(root)
    with _read_lock(root):
        directory = root / "acquisitions" / capture_id
        from .event_capture_store import _no_symlink_ancestors
        _no_symlink_ancestors(directory)
        paths = list(directory.glob("*.json"))
        if len(paths) != 1 or paths[0].is_symlink() or not paths[0].is_file():
            raise EventCaptureStoreError("exactly one retained acquisition response is required")
        raw = paths[0].read_bytes()
        if paths[0].stem != _sha(raw).removeprefix("sha256:"):
            raise EventCaptureStoreError("retained acquisition hash mismatch")
        observed, body = validate_response(raw, year=year, month=month)
    result = {"schema_version": "forex.bls-collection-result.v1", "capture_id": capture_id,
              "observation_sha256": _sha(raw), "outcome": observed["outcome"],
              "status_code": observed["status_code"], "completed_at_utc": observed["completed_at_utc"],
              "coverage_status": "UNKNOWN", "execution_authority": False}
    if observed["outcome"] != "SUCCESS":
        return {**result, "processing": "RETRIEVAL_FAILURE_RETAINED"}
    capture = resume_bls_capture if (root / "raw" / f"{capture_id}.html").exists() else retain_bls_capture
    retained = capture(root, capture_id=capture_id, raw=body, source_family="BLS_MONTHLY",
        capture_completed_at_utc=observed["completed_at_utc"], source_url=observed["requested_url"])
    return {**result, "processing": "CAPTURE_RETAINED", "journal_sha256": retained["journal"]["journal_sha256"],
            "parser_quarantined": retained["parser_result"]["quarantined"]}


def resume_collection(root: Path, *, capture_id: str, year: int, month: int):
    """Recover after transport retention, including a crash before parsing."""
    _safe_id(capture_id)
    _existing_layout(root)
    from .event_capture_store import _no_symlink_ancestors
    acquisition = root / "acquisitions" / capture_id
    _no_symlink_ancestors(acquisition)
    if list(acquisition.glob("*.json")):
        return apply_retained_response(root, capture_id=capture_id, year=year, month=month)
    with _read_lock(root):
        directory = root / "transport" / capture_id
        _no_symlink_ancestors(directory)
        paths = list(directory.glob("*.json"))
        if len(paths) != 1 or paths[0].is_symlink() or not paths[0].is_file():
            raise EventCaptureStoreError("exactly one retained transport response is required")
        raw = paths[0].read_bytes()
        if paths[0].stem != _sha(raw).removeprefix("sha256:"):
            raise EventCaptureStoreError("retained transport hash mismatch")
        receipt = json.loads(raw, object_pairs_hook=_unique_fields, parse_constant=_invalid_constant)
        if not isinstance(receipt, dict) or receipt.get("schema_version") != "forex.bls-transport-receipt.v1" or receipt.get("requested_url") != monthly_url(year, month):
            raise ValueError("retained transport does not bind the requested month")
        observation = receipt["transport_observation"]
        if not isinstance(observation, dict) or type(observation.get("ok")) is not bool or not isinstance(observation.get("result"), dict):
            raise ValueError("retained transport observation structure is invalid")
        if type(observation["result"].get("exit_code")) is not int:
            raise ValueError("retained transport exit code is invalid")
    if observation.get("ok") is not True or observation.get("result", {}).get("exit_code") != 0:
        return {"schema_version": "forex.bls-collection-result.v1", "capture_id": capture_id,
                "observation_sha256": _sha(raw), "outcome": "TRANSPORT_ERROR",
                "status_code": None, "completed_at_utc": None,
                "processing": "TRANSPORT_FAILURE_RETAINED", "coverage_status": "UNKNOWN", "execution_authority": False}
    if not isinstance(observation["result"].get("stdout"), str):
        raise ValueError("retained transport stdout must be text")
    return retain_response(root, capture_id=capture_id, year=year, month=month,
                           raw=observation["result"]["stdout"].encode("utf-8"))
