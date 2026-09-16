"""Build a derived, immutable envelope for one retained M1 assessment.

This module reads caller-supplied bytes only.  It never writes source evidence,
contacts a service, or grants execution authority.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from typing import Any


SCHEMA = "forex.m1.assessment-envelope.v1"
SPOOL_SCHEMA = "forex.m20.latest-assessment.v1"


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON field")
        result[key] = value
    return result


def _json(raw: bytes) -> Any:
    return json.loads(raw, object_pairs_hook=_pairs,
                      parse_constant=lambda _value: (_ for _ in ()).throw(ValueError("nonfinite JSON value")))


def _utc(value: Any) -> datetime:
    if not isinstance(value, str) or not value:
        raise ValueError("missing timestamp")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp has no timezone")
    return parsed.astimezone(timezone.utc)


def _refusal(source: dict[str, Any], code: str) -> dict[str, Any]:
    return {"schema_version": SCHEMA, "source": source,
            "terminal": {"disposition": "OPERATIONAL_REFUSAL", "reason_code": code},
            "execution_authority": False}


def build_envelope(raw: bytes, *, source_reference: str) -> dict[str, Any]:
    """Derive a terminal decision or safe operational refusal from raw bytes.

    ``source_reference`` is an operator-supplied immutable location identifier;
    the source digest always binds the exact supplied bytes.  Invalid retained
    bytes return a refusal rather than being repaired or rewritten.
    """
    if not isinstance(raw, bytes):
        raise TypeError("raw must be bytes")
    if not isinstance(source_reference, str) or not source_reference:
        raise ValueError("source_reference is required")
    source: dict[str, Any] = {"reference": source_reference,
                              "sha256": "sha256:" + hashlib.sha256(raw).hexdigest()}
    try:
        value = _json(raw)
    except (ValueError, json.JSONDecodeError, UnicodeDecodeError):
        return _refusal(source, "ASSESSMENT_OPERATION_OUTPUT_NOT_JSON")
    if not isinstance(value, dict):
        return _refusal(source, "UNSUPPORTED_SNAPSHOT_SCHEMA")

    assessment = value
    if value.get("schema_version") == SPOOL_SCHEMA:
        assessment = value.get("assessment")
        source.update({"kind": "LISTENER_SPOOL_RECORD", "listener_release_id": value.get("listener_release_id"),
                       "assessment_sequence": value.get("assessment_sequence"),
                       "assessment_started_at_utc": value.get("assessment_started_at_utc"),
                       "assessment_completed_at_utc": value.get("assessment_completed_at_utc")})
        try:
            if not isinstance(assessment, dict):
                raise ValueError("assessment missing")
            started = _utc(value.get("assessment_started_at_utc"))
            completed = _utc(value.get("assessment_completed_at_utc"))
            if started > completed:
                raise ValueError("clock order")
        except ValueError:
            return _refusal(source, "ASSESSMENT_CLOCK_ORDER_INVALID")
    elif value.get("operation") == "m20_demo_trading_session":
        source["kind"] = "FIXED_OPERATION_OUTPUT"
    elif isinstance(value.get("result"), dict) and isinstance(value["result"].get("stdout"), str):
        source["kind"] = "FIXED_OPERATION_WRAPPER"
        try:
            assessment = _json(value["result"]["stdout"].encode())
        except (ValueError, json.JSONDecodeError, UnicodeDecodeError):
            return _refusal(source, "ASSESSMENT_OPERATION_OUTPUT_NOT_JSON")
    else:
        return _refusal(source, "UNSUPPORTED_SNAPSHOT_SCHEMA")

    if not isinstance(assessment, dict):
        return _refusal(source, "UNSUPPORTED_SNAPSHOT_SCHEMA")
    snapshot, proposal = assessment.get("decision_snapshot"), assessment.get("proposal")
    if assessment.get("server") != "GOMarketsMU-Demo" or assessment.get("symbol") != "EURUSD" or not isinstance(snapshot, dict) or not isinstance(proposal, dict):
        return _refusal(source, "UNSUPPORTED_SNAPSHOT_SCHEMA")
    action = proposal.get("action")
    proposal_id, snapshot_id = proposal.get("proposal_id"), snapshot.get("snapshot_id")
    if action not in {"BUY", "SELL", "NO_TRADE"} or not isinstance(proposal_id, str) or not proposal_id or not isinstance(snapshot_id, str) or not snapshot_id or proposal.get("snapshot_id") != snapshot_id:
        return _refusal(source, "MISSING_REQUIRED_PROVENANCE")
    decision_at = proposal.get("decision_at_utc")
    if decision_at is not None:
        try:
            _utc(decision_at)
        except ValueError:
            return _refusal(source, "ASSESSMENT_CLOCK_ORDER_INVALID")
    return {"schema_version": SCHEMA, "source": source,
            "assessment": {"server": "GOMarketsMU-Demo", "symbol": "EURUSD",
                           "snapshot_id": snapshot_id, "proposal_id": proposal_id,
                           "decision_at_utc": decision_at},
            "terminal": {"disposition": "TERMINAL_DECISION", "action": action},
            "execution_authority": False}
