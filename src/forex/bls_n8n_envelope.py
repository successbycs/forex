"""Closed validation for the BLS JSON handoff sent by the fixed n8n flow.

The handoff describes what n8n says it fetched. Validating its shape makes it
safe to retain, but does not authenticate BLS or prove that n8n made the claim.
"""
from __future__ import annotations

import base64
import json
from datetime import UTC, datetime
from typing import Any

from forex.bls_collection import MAX_BODY_BYTES, monthly_url, validate_response
from forex.event_capture_store import EventCaptureStoreError, _invalid_constant, _safe_id, _unique_fields


class BLSN8nEnvelopeError(ValueError):
    """The untrusted n8n handoff is not the fixed BLS shape."""


FIELDS = frozenset({
    "capture_id", "year", "month", "started_at_utc", "completed_at_utc",
    "status_code", "content_type", "body_base64", "body_complete",
})
MAX_HANDOFF_JSON_BYTES = ((MAX_BODY_BYTES + 2) // 3) * 4 + 16 * 1024


def parse_handoff_json(raw: bytes) -> dict[str, Any]:
    """Decode one bounded JSON object, refusing duplicate keys and NaN values."""
    if not isinstance(raw, bytes) or not raw or len(raw) > MAX_HANDOFF_JSON_BYTES:
        raise BLSN8nEnvelopeError("n8n BLS handoff size is invalid")
    try:
        value = json.loads(raw, object_pairs_hook=_unique_fields, parse_constant=_invalid_constant)
    except (json.JSONDecodeError, EventCaptureStoreError) as exc:
        raise BLSN8nEnvelopeError("n8n BLS handoff JSON is invalid") from exc
    if not isinstance(value, dict):
        raise BLSN8nEnvelopeError("n8n BLS handoff must be an object")
    return value


def _timestamp(value: Any) -> None:
    if not isinstance(value, str):
        raise BLSN8nEnvelopeError("n8n BLS timestamps are invalid")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise BLSN8nEnvelopeError("n8n BLS timestamps are invalid") from exc
    if parsed.tzinfo is None:
        raise BLSN8nEnvelopeError("n8n BLS timestamps are invalid")
    parsed.astimezone(UTC)


def build_observation(value: dict[str, Any]) -> tuple[str, bytes]:
    """Build the established BLS observation envelope from a closed handoff.

    This preserves n8n's stated values. ``validate_response`` establishes
    transport-envelope consistency; it cannot turn an n8n claim into
    independent publisher authentication.
    """
    if not isinstance(value, dict) or set(value) != FIELDS:
        raise BLSN8nEnvelopeError("n8n BLS handoff fields are invalid")
    capture_id, year, month = value["capture_id"], value["year"], value["month"]
    try:
        _safe_id(capture_id)
        url = monthly_url(year, month)
    except (EventCaptureStoreError, ValueError) as exc:
        raise BLSN8nEnvelopeError("n8n BLS capture identity or month is invalid") from exc
    if not isinstance(value["body_base64"], str) or type(value["body_complete"]) is not bool:
        raise BLSN8nEnvelopeError("n8n BLS body is invalid")
    if value["status_code"] is not None and (type(value["status_code"]) is not int or not 100 <= value["status_code"] <= 599):
        raise BLSN8nEnvelopeError("n8n BLS status is invalid")
    if value["content_type"] is not None and not isinstance(value["content_type"], str):
        raise BLSN8nEnvelopeError("n8n BLS content type is invalid")
    for key in ("started_at_utc", "completed_at_utc"):
        _timestamp(value[key])
    try:
        body = base64.b64decode(value["body_base64"], validate=True)
    except (TypeError, ValueError) as exc:
        raise BLSN8nEnvelopeError("n8n BLS body encoding is invalid") from exc
    if len(body) > MAX_BODY_BYTES:
        raise BLSN8nEnvelopeError("n8n BLS body is too large")
    envelope = {
        "schema_version": "forex.bls-http-observation.v1", "requested_url": url,
        "started_at_utc": value["started_at_utc"], "completed_at_utc": value["completed_at_utc"],
        "status_code": value["status_code"], "content_type": value["content_type"],
        "body_base64": value["body_base64"], "body_complete": value["body_complete"],
        "outcome": "SUCCESS", "error_code": None, "execution_authority": False,
    }
    try:
        raw = json.dumps(envelope, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
        validate_response(raw, year=year, month=month)
    except (TypeError, ValueError) as exc:
        raise BLSN8nEnvelopeError("n8n BLS envelope is invalid") from exc
    return capture_id, raw
