"""Deterministic research decision record for the disabled H_SLOW stream."""
from __future__ import annotations

import hashlib
import json
from typing import Any

from .h_slow_data import h_slow_daily_input
from .h_slow_policy import POLICY_VERSION, monthly_target


DECISION_SCHEMA_VERSION = "forex.h-slow.research-decision.v1"
_BASE_CONTENT_KEYS = {
    "decision_schema_version", "policy_version", "snapshot_id",
    "snapshot_artifact_sha256", "policy_input_sha256", "decision_at_utc",
    "target", "event_annotation_status",
}
_DECISION_KEYS = _BASE_CONTENT_KEYS | {"decision_sha256", "record_status", "execution_authority"}
_ANNOTATION_KEYS = {
    "annotation_type", "decision_at_utc", "window", "qualified_result_sha256",
    "coverage", "events", "quarantined", "quarantine_window_membership", "annotation_sha256",
}


def _digest(value: dict[str, Any]) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def evaluate_h_slow_snapshot(snapshot: dict[str, Any], *, decision_at_utc: str) -> dict[str, Any]:
    """Bind one point-in-time data snapshot to a research target.

    This function deliberately stops at a versioned research record.  It has
    no account, terminal, routing, sizing, lease, persistence or order
    argument, so a ``BUY``/``SELL`` target cannot be mistaken for authority.
    """
    policy_input = h_slow_daily_input(snapshot, decision_at_utc=decision_at_utc)
    target = monthly_target(
        decision_at_utc=policy_input["decision_at_utc"],
        daily_bars=policy_input["daily_bars"],
    )
    content = {
        "decision_schema_version": DECISION_SCHEMA_VERSION,
        "policy_version": POLICY_VERSION,
        "snapshot_id": policy_input["snapshot_id"],
        "snapshot_artifact_sha256": policy_input["snapshot_artifact_sha256"],
        "policy_input_sha256": policy_input["input_sha256"],
        "decision_at_utc": policy_input["decision_at_utc"],
        "target": target,
        "event_annotation_status": "NOT_ATTACHED",
    }
    return {
        **content,
        "decision_sha256": _digest(content),
        "record_status": "RESEARCH_TARGET_ONLY",
        "execution_authority": False,
    }


def attach_event_context(decision: dict[str, Any], annotation: dict[str, Any]) -> dict[str, Any]:
    """Bind a verified context-only event annotation without changing a target.

    Event context is evidence for later review, never an entry or veto input in
    H_SLOW v1.  Both supplied records must retain their own canonical digest,
    so a caller cannot silently attach a context from another decision time.
    """
    if not isinstance(decision, dict) or set(decision) != _DECISION_KEYS:
        raise ValueError("decision record fields are invalid")
    content = {key: decision[key] for key in _BASE_CONTENT_KEYS}
    if (decision.get("decision_schema_version") != DECISION_SCHEMA_VERSION
            or decision.get("record_status") != "RESEARCH_TARGET_ONLY"
            or decision.get("execution_authority") is not False
            or decision.get("decision_sha256") != _digest(content)):
        raise ValueError("decision record is not a verified research-only record")
    if content["event_annotation_status"] != "NOT_ATTACHED":
        raise ValueError("decision already has event context")
    if not isinstance(annotation, dict) or set(annotation) != _ANNOTATION_KEYS:
        raise ValueError("event annotation fields are invalid")
    annotation_content = {key: annotation[key] for key in _ANNOTATION_KEYS - {"annotation_sha256"}}
    if (annotation.get("annotation_type") != "EVENT_CONTEXT_ONLY"
            or annotation.get("annotation_sha256") != _digest(annotation_content)
            or annotation.get("decision_at_utc") != content["decision_at_utc"]):
        raise ValueError("event annotation is not a verified matching context-only record")
    attached = {
        # Do not retain caller-owned nested target values: a later mutation of
        # the input decision must not invalidate this record silently.
        **json.loads(json.dumps(content, sort_keys=True, separators=(",", ":"))),
        "event_annotation_status": "ATTACHED_CONTEXT_ONLY",
        "event_annotation": json.loads(json.dumps(annotation, sort_keys=True, separators=(",", ":"))),
    }
    return {
        **attached,
        "decision_sha256": _digest(attached),
        "record_status": "RESEARCH_TARGET_ONLY",
        "execution_authority": False,
    }
