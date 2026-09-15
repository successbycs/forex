"""Read-only verification and projection for n8n-retained BLS captures."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from forex.bls_journal_calendar_projection import project_bls_journal
from forex.bls_collection import validate_response
from forex.bls_n8n_retention import RECEIPT_SCHEMA, validate_workflow_binding
from forex.bls_primary_source_verifier import BLSPrimarySourceVerificationError, verify_bls_primary_source
from forex.event_capture_store import EventCaptureStoreError, _invalid_constant, _no_symlink_ancestors, _sha, _unique_fields
from forex.bls_monthly_events import _source_month


class BLSN8nProjectionError(ValueError):
    pass


_RECEIPT_FIELDS = {
    "schema_version", "capture_id", "observation_sha256", "requested_url",
    "n8n_claimed_started_at_utc", "n8n_claimed_completed_at_utc",
    "configured_workflow_id", "configured_workflow_sha256", "authentication",
    "publisher_authenticity", "execution_authority",
}


def _acquisition_observation(root: Path, capture: dict[str, Any]) -> dict[str, Any]:
    directory = root / "acquisitions" / capture["capture_id"]
    _no_symlink_ancestors(directory)
    paths = list(directory.glob("*.json"))
    if len(paths) != 1 or paths[0].is_symlink() or not paths[0].is_file():
        raise BLSN8nProjectionError("exactly one BLS acquisition receipt is required")
    try:
        year, month = _source_month(capture["source_url"])
        value, _ = validate_response(paths[0].read_bytes(), year=year, month=month)
    except (OSError, ValueError, TypeError) as exc:
        raise BLSN8nProjectionError("BLS acquisition receipt is invalid") from exc
    return value


def _receipt(root: Path, capture: dict[str, Any], *, expected_workflow_id: str,
             expected_workflow_sha256: str) -> str:
    capture_id = capture["capture_id"]
    directory = root / "n8n-receipts" / capture_id
    try:
        _no_symlink_ancestors(directory)
    except EventCaptureStoreError as exc:
        raise BLSN8nProjectionError("n8n receipt path is unsafe") from exc
    if directory.is_symlink() or not directory.is_dir():
        raise BLSN8nProjectionError("n8n receipt is missing")
    paths = list(directory.glob("*.json"))
    if len(paths) != 1 or paths[0].is_symlink() or not paths[0].is_file():
        raise BLSN8nProjectionError("exactly one n8n receipt is required")
    try:
        raw = paths[0].read_bytes()
        value = json.loads(raw, object_pairs_hook=_unique_fields, parse_constant=_invalid_constant)
    except (OSError, json.JSONDecodeError, EventCaptureStoreError) as exc:
        raise BLSN8nProjectionError("n8n receipt JSON is invalid") from exc
    if paths[0].stem != _sha(raw).removeprefix("sha256:"):
        raise BLSN8nProjectionError("n8n receipt hash does not match its filename")
    if not isinstance(value, dict) or set(value) != _RECEIPT_FIELDS:
        raise BLSN8nProjectionError("n8n receipt fields are invalid")
    acquisition = capture["acquisition_receipt"]
    observation = _acquisition_observation(root, capture)
    if (value["schema_version"] != RECEIPT_SCHEMA or value["capture_id"] != capture_id
            or value["observation_sha256"] != acquisition["observation_sha256"]
            or value["requested_url"] != capture["source_url"]
            or value["n8n_claimed_started_at_utc"] != observation["started_at_utc"]
            # Receipt claims bind the exact acquisition envelope spelling. The
            # event journal may normalize equivalent RFC 3339 timestamps.
            or value["n8n_claimed_completed_at_utc"] != observation["completed_at_utc"]
            or value["configured_workflow_id"] != expected_workflow_id
            or value["configured_workflow_sha256"] != expected_workflow_sha256
            or value["authentication"] != "BEARER_TOKEN_ONLY"
            or value["publisher_authenticity"] != "NOT_VERIFIED_BY_LOCAL_SERVICE"
            or value["execution_authority"] is not False):
        raise BLSN8nProjectionError("n8n receipt does not bind retained acquisition")
    try:
        validate_workflow_binding(value["configured_workflow_id"], value["configured_workflow_sha256"])
    except ValueError as exc:
        raise BLSN8nProjectionError("n8n receipt workflow binding is invalid") from exc
    return _sha(raw)


def project_verified_n8n_bls_store(root: Path, *, expected_workflow_id: str,
                                   expected_workflow_sha256: str) -> dict[str, Any]:
    """Verify receipt -> acquisition -> raw HTML before canonical projection.

    The resulting facts bind the n8n receipt hash. That receipt remains explicit
    about its limited authenticity claim; it is not a substitute for external
    publisher verification.
    """
    if not isinstance(root, Path):
        raise BLSN8nProjectionError("store root must be an explicit pathlib.Path")
    try:
        validate_workflow_binding(expected_workflow_id, expected_workflow_sha256)
    except ValueError as exc:
        raise BLSN8nProjectionError("expected n8n workflow binding is invalid") from exc
    try:
        verified = verify_bls_primary_source(root)
    except BLSPrimarySourceVerificationError as exc:
        raise BLSN8nProjectionError("BLS capture/acquisition/raw verification failed") from exc
    expected_ids = {capture["capture_id"] for capture in verified["captures"]}
    category = root / "n8n-receipts"
    if category.is_symlink() or not category.is_dir():
        raise BLSN8nProjectionError("n8n receipt category is missing")
    actual_ids = {item.name for item in category.iterdir() if item.is_dir() and not item.is_symlink()}
    if actual_ids != expected_ids:
        raise BLSN8nProjectionError("n8n receipt identities do not match retained captures")
    receipt_by_capture = {capture["capture_id"]: _receipt(root, capture,
                                                             expected_workflow_id=expected_workflow_id,
                                                             expected_workflow_sha256=expected_workflow_sha256)
                          for capture in verified["captures"]}
    try:
        return project_bls_journal(_journal(root, verified), capture_receipt_sha256_by_id=receipt_by_capture)
    except (ValueError, EventCaptureStoreError) as exc:
        raise BLSN8nProjectionError("verified n8n BLS projection failed") from exc


def _journal(root: Path, verified: dict[str, Any]) -> dict[str, Any]:
    # The primary verifier has just checked the store. Re-read only its journal
    # through the existing verified reader; this operation remains read-only.
    from forex.event_capture_store import read_capture_journal
    journal = read_capture_journal(root)
    if journal.get("journal_sha256") != verified.get("journal_sha256"):
        raise BLSN8nProjectionError("retained journal changed during verification")
    return journal
