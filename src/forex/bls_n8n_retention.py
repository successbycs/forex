"""Immutable retention of a validated n8n BLS handoff."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from forex.bls_collection import _retain_bytes, monthly_url, retain_response, validate_response
from forex.event_capture_store import EventCaptureStoreError, _safe_id

_DIGEST = re.compile(r"sha256:[0-9a-f]{64}\Z")
_WORKFLOW = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\Z")
RECEIPT_SCHEMA = "forex.bls-n8n-receipt.v2"


def _sha(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def validate_workflow_binding(workflow_id: Any, workflow_sha256: Any) -> None:
    if (not isinstance(workflow_id, str) or not _WORKFLOW.fullmatch(workflow_id)
            or not isinstance(workflow_sha256, str) or not _DIGEST.fullmatch(workflow_sha256)):
        raise ValueError("n8n workflow binding is invalid")


def receipt_bytes(*, capture_id: str, observation: bytes, year: int, month: int,
                  workflow_id: str, workflow_sha256: str) -> bytes:
    """Return deterministic receipt bytes so exact retries are idempotent."""
    try:
        _safe_id(capture_id)
        response, _ = validate_response(observation, year=year, month=month)
        monthly_url(year, month)
    except (EventCaptureStoreError, ValueError) as exc:
        raise ValueError("n8n BLS retention observation is invalid") from exc
    validate_workflow_binding(workflow_id, workflow_sha256)
    receipt = {
        "schema_version": RECEIPT_SCHEMA, "capture_id": capture_id,
        "observation_sha256": _sha(observation), "requested_url": response["requested_url"],
        "n8n_claimed_started_at_utc": response["started_at_utc"],
        "n8n_claimed_completed_at_utc": response["completed_at_utc"],
        "configured_workflow_id": workflow_id, "configured_workflow_sha256": workflow_sha256,
        "authentication": "BEARER_TOKEN_ONLY",
        "publisher_authenticity": "NOT_VERIFIED_BY_LOCAL_SERVICE",
        "execution_authority": False,
    }
    return json.dumps(receipt, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def retain(root: Path, *, capture_id: str, observation: bytes, year: int, month: int,
           workflow_id: str, workflow_sha256: str) -> dict[str, Any]:
    """Validate all inputs, then publish receipt and acquisition immutably."""
    receipt = receipt_bytes(capture_id=capture_id, observation=observation, year=year, month=month,
                            workflow_id=workflow_id, workflow_sha256=workflow_sha256)
    _retain_bytes(root, category="n8n-receipts", capture_id=capture_id, raw=receipt)
    result = retain_response(root, capture_id=capture_id, raw=observation, year=year, month=month)
    return {**result, "n8n_receipt_sha256": _sha(receipt), "execution_authority": False}
