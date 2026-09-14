"""Closed event-context binding for disabled H_SLOW entry preparation.

This is deliberately a *preparation* boundary, rather than a calendar source
or an execution gate.  Wave 2 owns source collection and policy.  This module
only makes a future H_SLOW preparation fail closed unless its supplied
eligibility conclusion is bound to the exact retained research decision and
the decision's point-in-time event annotation.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from typing import Any, Mapping

from .h_slow_policy import POLICY_VERSION


EVENT_ELIGIBILITY_SCHEMA_VERSION = "forex.h-slow.event-eligibility.v1"
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}$")
_ENTRY_STATUSES = frozenset({"ALLOW", "NO_NEW_ENTRY"})
_PRIMARY_SOURCES = {
    "US_CPI": ("bls-monthly-release-calendar", "https://www.bls.gov/schedule/{year}/{month:02d}_sched_list.htm"),
    "US_EMPLOYMENT_SITUATION": ("bls-monthly-release-calendar", "https://www.bls.gov/schedule/{year}/{month:02d}_sched_list.htm"),
    "FOMC_POLICY_DECISION": ("federal-reserve-fomc-calendar", "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm"),
    "ECB_POLICY_DECISION": ("ecb-monetary-policy-calendar", "https://www.ecb.europa.eu/press/calendars/mgcgc/html/index.en.html"),
}
_DECISION_BASE = {
    "decision_schema_version", "policy_version", "snapshot_id", "snapshot_artifact_sha256",
    "policy_input_sha256", "decision_at_utc", "target", "event_annotation_status",
}
_ANNOTATION_FIELDS = {
    "annotation_type", "decision_at_utc", "window", "qualified_result_sha256",
    "coverage", "events", "quarantined", "quarantine_window_membership", "annotation_sha256",
}
_RECORD_FIELDS = {
    "schema_version", "decision_sha256", "annotation_sha256", "qualified_result_sha256",
    "primary_context_sha256", "entry_status", "policy_version", "execution_authority",
    "eligibility_sha256",
}


class HSlowEventEligibilityError(ValueError):
    """An event-eligibility record is incomplete, unbound or unsafe."""


def _digest(value: Mapping[str, Any]) -> str:
    return "sha256:" + hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()


def _copy(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise HSlowEventEligibilityError(f"{label} must be an object")
    try:
        copied = json.loads(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False))
    except (TypeError, ValueError) as exc:
        raise HSlowEventEligibilityError(f"{label} must be finite JSON") from exc
    if not isinstance(copied, dict):
        raise HSlowEventEligibilityError(f"{label} must be an object")
    return copied


def _attached_annotation(research_decision: Mapping[str, Any]) -> tuple[str, dict[str, Any]]:
    """Return a digest-verified attached annotation from one research record."""
    decision = _copy(research_decision, "research decision")
    expected = _DECISION_BASE | {"event_annotation", "decision_sha256", "record_status", "execution_authority"}
    if set(decision) != expected or decision.get("event_annotation_status") != "ATTACHED_CONTEXT_ONLY":
        raise HSlowEventEligibilityError("research decision has no attached event context")
    content = {key: decision[key] for key in expected - {"decision_sha256", "record_status", "execution_authority"}}
    if (decision.get("record_status") != "RESEARCH_TARGET_ONLY"
            or decision.get("execution_authority") is not False
            or decision.get("decision_schema_version") != "forex.h-slow.research-decision.v1"
            or decision.get("policy_version") != POLICY_VERSION
            or not isinstance(decision.get("decision_sha256"), str)
            or decision["decision_sha256"] != _digest(content)):
        raise HSlowEventEligibilityError("research decision digest is invalid")
    target = decision.get("target")
    if (not isinstance(target, dict) or target.get("policy_version") != POLICY_VERSION
            or target.get("instrument") != "EUR/USD" or target.get("action") not in {"BUY", "SELL", "NO_TRADE"}
            or target.get("research_only") is not True or target.get("execution_authority") is not False):
        raise HSlowEventEligibilityError("research decision target is invalid")
    annotation = decision.get("event_annotation")
    if not isinstance(annotation, dict) or set(annotation) != _ANNOTATION_FIELDS:
        raise HSlowEventEligibilityError("research decision event annotation fields are invalid")
    annotation_content = {key: annotation[key] for key in _ANNOTATION_FIELDS - {"annotation_sha256"}}
    if (annotation.get("annotation_type") != "EVENT_CONTEXT_ONLY"
            or annotation.get("decision_at_utc") != decision.get("decision_at_utc")
            or not isinstance(annotation.get("annotation_sha256"), str)
            or annotation["annotation_sha256"] != _digest(annotation_content)
            or _DIGEST.fullmatch(str(annotation.get("qualified_result_sha256"))) is None):
        raise HSlowEventEligibilityError("research decision event annotation is invalid")
    return decision["decision_sha256"], annotation


def _utc(value: Any, label: str) -> datetime:
    if not isinstance(value, str):
        raise HSlowEventEligibilityError(f"{label} timestamp is invalid")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise HSlowEventEligibilityError(f"{label} timestamp is invalid") from exc
    if parsed.tzinfo is None:
        raise HSlowEventEligibilityError(f"{label} timestamp is invalid")
    return parsed.astimezone(UTC)


def _primary_context(primary_context: Mapping[str, Any], *, decision_at_utc: str) -> dict[str, Any]:
    """Validate a complete retained four-family report as of the decision."""
    report = _copy(primary_context, "primary event context")
    expected = {"schema_version", "context_state", "families", "execution_authority", "limitations", "context_sha256"}
    if set(report) != expected or report.get("schema_version") != "forex.primary-event-context.v1":
        raise HSlowEventEligibilityError("primary event context shape is invalid")
    body = {key: report[key] for key in expected - {"context_sha256"}}
    if (report.get("execution_authority") is not False or not isinstance(report.get("context_sha256"), str)
            or report["context_sha256"] != _digest(body)):
        raise HSlowEventEligibilityError("primary event context digest is invalid")
    if report.get("context_state") != "QUALIFIED_CONTEXT_ONLY":
        raise HSlowEventEligibilityError("primary event context is " + str(report.get("context_state", "UNAVAILABLE")))
    decision = _utc(decision_at_utc, "research decision")
    families = report.get("families")
    if not isinstance(families, list) or len(families) != len(_PRIMARY_SOURCES):
        raise HSlowEventEligibilityError("primary event context has incomplete family coverage")
    seen: set[str] = set()
    fields = {"family_id", "source_id", "state", "reason", "qualification_state", "limitation", "receipt"}
    for family in families:
        if not isinstance(family, dict) or set(family) != fields or family.get("family_id") not in _PRIMARY_SOURCES:
            raise HSlowEventEligibilityError("primary event context family shape is invalid")
        family_id = family["family_id"]
        source_id, source_url = _PRIMARY_SOURCES[family_id]
        receipt = family.get("receipt")
        if (family_id in seen or family.get("state") != "QUALIFIED_CONTEXT_ONLY"
                or family.get("source_id") != source_id or not isinstance(receipt, dict)
                or set(receipt) != {"source_url", "captured_at_utc", "source_sha256", "coverage_status"}
                or receipt.get("source_url") != source_url or receipt.get("coverage_status") != "COMPLETE"
                or _DIGEST.fullmatch(str(receipt.get("source_sha256"))) is None
                or _utc(receipt.get("captured_at_utc"), "primary event receipt") > decision):
            raise HSlowEventEligibilityError("primary event context receipt is incomplete, mismatched, or unavailable")
        seen.add(family_id)
    if seen != set(_PRIMARY_SOURCES):
        raise HSlowEventEligibilityError("primary event context has incomplete family coverage")
    return report


def build_h_slow_event_eligibility(
    research_decision: Mapping[str, Any], *, primary_context: Mapping[str, Any], entry_status: str,
    policy_version: str,
) -> dict[str, Any]:
    """Create a deterministic, still non-authorising eligibility record.

    The coverage/status values are preserved so the consumer can reject every
    non-clear result.  This helper does not qualify a source or decide a
    trading direction; Wave 2 must provide those facts separately.
    """
    decision_sha256, annotation = _attached_annotation(research_decision)
    primary = _primary_context(primary_context, decision_at_utc=research_decision["decision_at_utc"])
    content = {
        "schema_version": EVENT_ELIGIBILITY_SCHEMA_VERSION,
        "decision_sha256": decision_sha256,
        "annotation_sha256": annotation["annotation_sha256"],
        "qualified_result_sha256": annotation["qualified_result_sha256"],
        "primary_context_sha256": primary["context_sha256"],
        "entry_status": entry_status,
        "policy_version": policy_version,
        "execution_authority": False,
    }
    return {**content, "eligibility_sha256": _digest(content)}


def validate_h_slow_event_eligibility(
    event_eligibility: Mapping[str, Any] | None, *, research_decision: Mapping[str, Any] | None,
    primary_context: Mapping[str, Any] | None, decision_sha256: str,
) -> str:
    """Return ``ALLOW`` or a stable fail-closed refusal reason.

    Invalid/missing values return refusal reasons rather than throwing, so the
    order-preparation boundary has one deterministic no-entry outcome.  The
    result never grants order authority.
    """
    if research_decision is None or event_eligibility is None or primary_context is None:
        return "EVENT_CONTEXT_UNAVAILABLE"
    try:
        bound_decision_sha256, annotation = _attached_annotation(research_decision)
        primary = _primary_context(primary_context, decision_at_utc=research_decision["decision_at_utc"])
        record = _copy(event_eligibility, "event eligibility")
    except HSlowEventEligibilityError as exc:
        message = str(exc)
        if message.startswith("primary event context is "):
            return "EVENT_CONTEXT_" + message.removeprefix("primary event context is ")
        return "EVENT_CONTEXT_INVALID"
    if set(record) != _RECORD_FIELDS or record.get("schema_version") != EVENT_ELIGIBILITY_SCHEMA_VERSION:
        return "EVENT_CONTEXT_INVALID"
    content = {key: record[key] for key in _RECORD_FIELDS - {"eligibility_sha256"}}
    if (record.get("execution_authority") is not False
            or not isinstance(record.get("eligibility_sha256"), str)
            or record["eligibility_sha256"] != _digest(content)):
        return "EVENT_CONTEXT_INVALID"
    if (record.get("decision_sha256") != decision_sha256
            or bound_decision_sha256 != decision_sha256
            or record.get("annotation_sha256") != annotation["annotation_sha256"]
            or record.get("qualified_result_sha256") != annotation["qualified_result_sha256"]
            or record.get("primary_context_sha256") != primary["context_sha256"]):
        return "EVENT_CONTEXT_SOURCE_MISMATCH"
    if record.get("entry_status") not in _ENTRY_STATUSES:
        return "EVENT_CONTEXT_INVALID"
    if record["entry_status"] != "ALLOW":
        return "EVENT_NEW_ENTRY_NOT_ALLOWED"
    if not isinstance(record.get("policy_version"), str) or not record["policy_version"]:
        return "EVENT_CONTEXT_INVALID"
    return "ALLOW"
