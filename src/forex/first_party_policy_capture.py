"""Immutable retention for one fixed first-party policy-calendar observation.

The transport observation is retained whether it succeeds or fails.  Publisher
bytes are retained only after the probe's complete, fixed-endpoint HTML success
envelope has been strictly validated.  This module has no scheduler, parser,
event selection, or execution authority.
"""
from __future__ import annotations

import base64
from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any
from enum import Enum


# Kept local so the historical supplied-bytes API remains importable from the
# installed ``src`` package (where repository-root ``t480`` is intentionally
# not on ``sys.path``).  The T480 probe owns the executable counterpart and
# uses the same fixed values.
MAX_BODY_BYTES = 2 * 1024 * 1024
SCHEMA_VERSION = "forex.first-party-policy-calendar-observation.v1"
_PROBE_URLS = {
    "FOMC_POLICY_DECISION": "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm",
    "ECB_POLICY_DECISION": "https://www.ecb.europa.eu/press/calendars/mgcgc/html/index.en.html",
}


def requested_url(family: Any) -> str:
    """Return the fixed probe endpoint for a real policy-family enum value."""
    if not isinstance(family, Enum) or not isinstance(family.value, str) or family.value not in _PROBE_URLS:
        raise PolicyCalendarCaptureError("family must be a declared policy calendar enum value")
    return _PROBE_URLS[family.value]


# Public local-only capture API.  This predates the fixed T480 transport
# collector below and intentionally keeps its own simple ``<root>/<id>``
# layout.  It accepts already-retained bytes only; it never opens a network
# connection or implies a qualified policy-decision time.
SOURCES = {
    "FOMC_POLICY_DECISION": (
        "federal-reserve-fomc-calendar",
        "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm",
        "America/New_York",
    ),
    "ECB_POLICY_DECISION": (
        # This is the canonical source identifier used by the primary-event
        # contract and the decision/risk consumers.  The retained September
        # 2026 ECB timing publication was projected with this identifier; a
        # later local alias here made the verifier reconstruct a different
        # event from the same immutable bytes.
        "ecb-monetary-policy-calendar",
        "https://www.ecb.europa.eu/press/calendars/mgcgc/html/index.en.html",
        "Europe/Berlin",
    ),
}


class PolicyCaptureError(ValueError):
    """Local supplied policy-calendar material is malformed or unsafe."""


def _local_utc(value: Any) -> str:
    if not isinstance(value, str):
        raise PolicyCaptureError("capture completion timestamp is invalid")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise PolicyCaptureError("capture completion timestamp is invalid") from exc
    if parsed.tzinfo is None:
        raise PolicyCaptureError("capture completion timestamp is invalid")
    return parsed.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _local_text(raw: bytes) -> str:
    if not isinstance(raw, bytes) or not raw:
        raise PolicyCaptureError("supplied policy calendar bytes are invalid")
    try:
        return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", raw.decode("utf-8")))
    except UnicodeDecodeError as exc:
        raise PolicyCaptureError("supplied policy calendar is not UTF-8") from exc


def parse_retained_policy_html(raw: bytes, *, family_id: str, source_url: str,
                               capture_completed_at_utc: str) -> dict[str, Any]:
    """Record only date-level policy-calendar observations as quarantined.

    The calendar pages alone do not establish an intraday statement/release
    time.  They therefore never emit an exact event record.
    """
    if family_id not in SOURCES or source_url != SOURCES[family_id][1]:
        raise PolicyCaptureError("policy source URL is not allowlisted")
    text = _local_text(raw)
    completed = _local_utc(capture_completed_at_utc)
    if family_id == "FOMC_POLICY_DECISION":
        found = re.search(r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2}\s*[-–]\s*\d{1,2}\b", text, re.I)
        reason = "FOMC_MEETING_DATE_ONLY_STATEMENT_TIME_UNDECLARED" if found else "OFFICIAL_POLICY_CALENDAR_PATTERN_NOT_FOUND"
    else:
        found = re.search(r"\b(?:\d{1,2}\s*[-–]\s*\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+20\d{2}|\d{1,2}/\d{1,2}/20\d{2}).{0,240}\b(?:Governing Council|monetary policy)\b", text, re.I)
        reason = "ECB_POLICY_MEETING_DATE_ONLY_DECISION_TIME_UNDECLARED" if found else "OFFICIAL_POLICY_CALENDAR_PATTERN_NOT_FOUND"
    return {
        "schema_version": "forex.first-party-policy-calendar-local-parse.v1",
        "family_id": family_id,
        "source_id": SOURCES[family_id][0],
        "source_url": source_url,
        "capture_completed_at_utc": completed,
        "raw_sha256": _sha(raw),
        "records": [],
        "quarantined": [{"event": family_id + "@" + _sha(raw), "reason": reason}],
        "coverage_status": "UNKNOWN",
        "execution_authority": False,
    }


def _assert_local_path_safe(root: Path) -> Path:
    if not isinstance(root, Path):
        raise PolicyCaptureError("local capture root must be an explicit pathlib.Path")
    if any(item.is_symlink() for item in (root, *root.parents)):
        raise PolicyCaptureError("local capture root is unsafe")
    if root.exists() and not root.is_dir():
        raise PolicyCaptureError("local capture root is unsafe")
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    if root.is_symlink() or not root.is_dir():
        raise PolicyCaptureError("local capture root is unsafe")
    return root


def retain_policy_capture(root: Path, *, capture_id: str, raw: bytes, family_id: str,
                          source_url: str, capture_completed_at_utc: str) -> dict[str, Any]:
    """Retain caller-supplied local bytes once, without fetching or parsing time."""
    if not isinstance(capture_id, str) or not _CAPTURE_ID.fullmatch(capture_id):
        raise PolicyCaptureError("capture_id is invalid")
    parser_result = parse_retained_policy_html(raw=raw, family_id=family_id, source_url=source_url,
                                               capture_completed_at_utc=capture_completed_at_utc)
    root = _assert_local_path_safe(root)
    target = root / capture_id
    if target.exists() or target.is_symlink():
        raise PolicyCaptureError("local policy capture already exists")
    try:
        target.mkdir(mode=0o700)
        _write_new(target / "raw.html", raw)
        receipt = {
            "schema_version": "forex.first-party-policy-calendar-local-receipt.v1",
            "capture_id": capture_id,
            "source_url": source_url,
            "raw_sha256": _sha(raw),
            "capture_completed_at_utc": parser_result["capture_completed_at_utc"],
            "execution_authority": False,
        }
        _write_new(target / "receipt.json", _canonical(receipt))
        _write_new(target / "parser-result.json", _canonical(parser_result))
    except Exception as exc:
        raise PolicyCaptureError("local capture left immutable partial state; replacement is refused") from exc
    return {
        "schema_version": "forex.first-party-policy-calendar-local-capture.v1",
        "capture_id": capture_id,
        "capture_path": str(target),
        "raw_sha256": _sha(raw),
        "parser_result": parser_result,
        "coverage_status": "UNKNOWN",
        "execution_authority": False,
    }


_CAPTURE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
_ENVELOPE_FIELDS = {
    "schema_version", "requested_url", "started_at_utc", "completed_at_utc",
    "status_code", "content_type", "body_base64", "body_complete", "outcome",
    "error_code", "execution_authority",
}


class PolicyCalendarCaptureError(ValueError):
    """A capture cannot safely be retained or treated as publisher material."""


def _sha(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _canonical(value: Any) -> bytes:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise PolicyCalendarCaptureError("transport observation must be JSON serializable") from exc


def _unique_fields(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise PolicyCalendarCaptureError("probe envelope contains duplicate fields")
        result[key] = value
    return result


def _utc(value: Any, field: str) -> datetime:
    if not isinstance(value, str):
        raise PolicyCalendarCaptureError(f"{field} must be an offset timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise PolicyCalendarCaptureError(f"{field} must be an offset timestamp") from exc
    if parsed.tzinfo is None:
        raise PolicyCalendarCaptureError(f"{field} must be an offset timestamp")
    return parsed.astimezone(UTC)


def validate_successful_envelope(raw: bytes, *, family: Any) -> tuple[dict[str, Any], bytes]:
    """Accept exactly a complete success from the fixed family endpoint."""
    if not isinstance(raw, bytes) or len(raw) > MAX_BODY_BYTES * 2:
        raise PolicyCalendarCaptureError("probe envelope exceeds its bounded size")
    try:
        envelope = json.loads(raw, object_pairs_hook=_unique_fields, parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        if isinstance(exc, PolicyCalendarCaptureError):
            raise
        raise PolicyCalendarCaptureError("probe envelope is not valid JSON") from exc
    if not isinstance(envelope, dict) or set(envelope) != _ENVELOPE_FIELDS:
        raise PolicyCalendarCaptureError("probe envelope fields are invalid")
    if envelope["schema_version"] != SCHEMA_VERSION or envelope["requested_url"] != requested_url(family):
        raise PolicyCalendarCaptureError("probe envelope does not bind the fixed policy source")
    started = _utc(envelope["started_at_utc"], "started_at_utc")
    completed = _utc(envelope["completed_at_utc"], "completed_at_utc")
    if completed < started:
        raise PolicyCalendarCaptureError("probe completion precedes start")
    if envelope["status_code"] != 200 or envelope["content_type"] != "text/html":
        raise PolicyCalendarCaptureError("probe envelope is not a successful HTML 200 response")
    if envelope["body_complete"] is not True or envelope["outcome"] != "SUCCESS" or envelope["error_code"] is not None:
        raise PolicyCalendarCaptureError("probe envelope does not declare a complete success")
    if envelope["execution_authority"] is not False:
        raise PolicyCalendarCaptureError("probe execution authority must be false")
    if not isinstance(envelope["body_base64"], str):
        raise PolicyCalendarCaptureError("probe body must be base64 text")
    try:
        body = base64.b64decode(envelope["body_base64"], validate=True)
    except (ValueError, TypeError) as exc:
        raise PolicyCalendarCaptureError("probe body is not valid base64") from exc
    if not body or len(body) > MAX_BODY_BYTES:
        raise PolicyCalendarCaptureError("probe body is empty or exceeds its bound")
    return envelope, body


def _no_symlink_ancestors(root: Path) -> None:
    if any(item.is_symlink() for item in (root, *root.parents)):
        raise PolicyCalendarCaptureError("policy-calendar capture root is unsafe")


def _fsync_directory(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _mkdir_durable(path: Path) -> None:
    """Create each missing directory one level at a time and persist it."""
    missing: list[Path] = []
    current = path
    while not current.exists():
        if current.is_symlink():
            raise PolicyCalendarCaptureError("policy-calendar capture root is unsafe")
        missing.append(current)
        current = current.parent
    if current.is_symlink() or not current.is_dir():
        raise PolicyCalendarCaptureError("policy-calendar capture root is unsafe")
    for directory in reversed(missing):
        # Its parent was checked above and is either pre-existing or was just
        # created/f-synced by this loop.
        directory.mkdir(mode=0o700)
        if directory.is_symlink() or not directory.is_dir():
            raise PolicyCalendarCaptureError("policy-calendar capture root is unsafe")
        _fsync_directory(directory.parent)
        _fsync_directory(directory)


def _capture_parent(root: Path, *, create: bool) -> Path:
    root = Path(root)
    _no_symlink_ancestors(root)
    if root.exists() and not root.is_dir():
        raise PolicyCalendarCaptureError("policy-calendar capture root is unsafe")
    if create:
        _mkdir_durable(root)
    elif not root.is_dir():
        raise PolicyCalendarCaptureError("policy-calendar capture root is unsafe")
    captures = root / "policy-calendar-captures"
    _no_symlink_ancestors(captures)
    if create:
        _mkdir_durable(captures)
    if captures.is_symlink() or not captures.is_dir():
        raise PolicyCalendarCaptureError("policy-calendar capture root is unsafe")
    return captures


def _capture_directory(root: Path, capture_id: str) -> Path:
    if not isinstance(capture_id, str) or not _CAPTURE_ID.fullmatch(capture_id):
        raise PolicyCalendarCaptureError("capture_id is invalid")
    captures = _capture_parent(root, create=True)
    directory = captures / capture_id
    try:
        directory.mkdir(mode=0o700)
    except FileExistsError as exc:
        raise PolicyCalendarCaptureError("capture_id already exists; remote retry is refused") from exc
    _fsync_directory(captures)
    _fsync_directory(directory)
    return directory


def reserve_transport_capture(root: Path, *, capture_id: str) -> Path:
    """Atomically reserve an ID before a remote transport call is attempted."""
    return _capture_directory(Path(root), capture_id)


def _write_new(path: Path, raw: bytes) -> None:
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise PolicyCalendarCaptureError("immutable capture file already exists") from exc
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        # The capture directory is deliberately retained and becomes
        # non-retryable rather than risking replacement after a partial write.
        raise
    directory_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


def retain_transport_result(
    root: Path,
    *,
    capture_id: str,
    family: Any,
    transport_observation: dict[str, Any],
    probe_sha256: str,
    program_sha256: str,
    reservation: Path | None = None,
) -> dict[str, Any]:
    """Create an immutable capture directory for one and only one transport call."""
    try:
        family_name = family.value if isinstance(family, Enum) else None
        expected_url = requested_url(family)
    except PolicyCalendarCaptureError:
        raise PolicyCalendarCaptureError("family must be a declared policy calendar enum value") from None
    if not isinstance(transport_observation, dict):
        raise PolicyCalendarCaptureError("transport observation must be a mapping")
    if not all(isinstance(value, str) and re.fullmatch(r"sha256:[0-9a-f]{64}", value) for value in (probe_sha256, program_sha256)):
        raise PolicyCalendarCaptureError("probe and program hashes must be sha256 values")
    if reservation is None:
        directory = _capture_directory(Path(root), capture_id)
    else:
        directory = Path(reservation)
        expected_parent = _capture_parent(Path(root), create=False)
        if (directory.name != capture_id or directory.parent != expected_parent
                or directory.is_symlink() or not directory.is_dir()):
            raise PolicyCalendarCaptureError("transport capture reservation is unsafe")
    observation_raw = _canonical(transport_observation)
    observation_sha256 = _sha(observation_raw)
    _write_new(directory / "transport-observation.json", observation_raw)
    receipt = {
        "schema_version": "forex.first-party-policy-calendar-transport-receipt.v1",
        "capture_id": capture_id,
        "family": family_name,
        "requested_url": expected_url,
        "probe_sha256": probe_sha256,
        "program_sha256": program_sha256,
        "transport_observation_sha256": observation_sha256,
        "execution_authority": False,
    }
    _write_new(directory / "receipt.json", _canonical(receipt))

    result = transport_observation.get("result")
    if transport_observation.get("ok") is not True or not isinstance(result, dict) or result.get("exit_code") != 0:
        return {
            "schema_version": "forex.first-party-policy-calendar-collection-result.v1",
            "capture_id": capture_id,
            "family": family_name,
            "outcome": "TRANSPORT_FAILURE_RETAINED",
            "transport_observation_sha256": observation_sha256,
            "publisher_capture_retained": False,
            "execution_authority": False,
        }
    stdout = result.get("stdout")
    if not isinstance(stdout, str):
        return {
            "schema_version": "forex.first-party-policy-calendar-collection-result.v1",
            "capture_id": capture_id,
            "family": family_name,
            "outcome": "PUBLISHER_CAPTURE_REJECTED",
            "reason": "TRANSPORT_STDOUT_NOT_TEXT",
            "transport_observation_sha256": observation_sha256,
            "publisher_capture_retained": False,
            "execution_authority": False,
        }
    try:
        envelope, body = validate_successful_envelope(stdout.encode("utf-8"), family=family)
    except (UnicodeEncodeError, PolicyCalendarCaptureError) as exc:
        return {
            "schema_version": "forex.first-party-policy-calendar-collection-result.v1",
            "capture_id": capture_id,
            "family": family_name,
            "outcome": "PUBLISHER_CAPTURE_REJECTED",
            "reason": str(exc),
            "transport_observation_sha256": observation_sha256,
            "publisher_capture_retained": False,
            "execution_authority": False,
        }
    _write_new(directory / "publisher.html", body)
    publisher_sha256 = _sha(body)
    _write_new(directory / "publisher.html.sha256", (publisher_sha256 + "\n").encode("ascii"))
    return {
        "schema_version": "forex.first-party-policy-calendar-collection-result.v1",
        "capture_id": capture_id,
        "family": family_name,
        "outcome": "SUCCESS",
        "requested_url": envelope["requested_url"],
        "completed_at_utc": envelope["completed_at_utc"],
        "transport_observation_sha256": observation_sha256,
        "publisher_body_sha256": publisher_sha256,
        "publisher_capture_retained": True,
        "execution_authority": False,
    }
