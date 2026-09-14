"""Prepared, disabled-by-default event-risk gate for new M1 entries only.

This pure module is intentionally not imported by the listener, M20 policy
kernel, or execution path.  It can evaluate only a hash-bound event sidecar
and hash-bound primary-source context report supplied by a future approved
integration.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from typing import Any


SCHEMA = "forex.m1-event-risk-gate.v1"
POLICY_SCHEMA = "forex.m1-event-risk-gate-policy.v1"
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}")
_PRIMARY_SOURCES = {
    "US_CPI": ("bls-monthly-release-calendar", "https://www.bls.gov/schedule/{year}/{month:02d}_sched_list.htm"),
    "US_EMPLOYMENT_SITUATION": ("bls-monthly-release-calendar", "https://www.bls.gov/schedule/{year}/{month:02d}_sched_list.htm"),
    "FOMC_POLICY_DECISION": ("federal-reserve-fomc-calendar", "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm"),
    "ECB_POLICY_DECISION": ("ecb-monetary-policy-calendar", "https://www.ecb.europa.eu/press/calendars/mgcgc/html/index.en.html"),
}


class EventRiskGateError(ValueError):
    """A prepared policy or claimed validated context is unsafe."""


def _canonical(value: Any) -> bytes:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise EventRiskGateError("context is not finite JSON") from exc


def _digest(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or _DIGEST.fullmatch(value) is None:
        raise EventRiskGateError(f"{field} is not a SHA-256 digest")
    return value


def _utc(value: Any, *, field: str) -> datetime:
    if not isinstance(value, str):
        raise EventRiskGateError(f"{field} timestamp is invalid")
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise EventRiskGateError(f"{field} timestamp is invalid") from exc
    if result.tzinfo is None:
        raise EventRiskGateError(f"{field} timestamp is invalid")
    return result.astimezone(UTC)


def validate_policy(policy: Any) -> dict[str, Any]:
    required = {"schema_version", "enabled", "scope", "required_context_state", "blackout_before_seconds",
                "blackout_after_seconds", "execution_authority", "activation_requirement"}
    if not isinstance(policy, dict) or set(policy) != required or policy.get("schema_version") != POLICY_SCHEMA:
        raise EventRiskGateError("event-risk policy shape is invalid")
    if (not isinstance(policy["enabled"], bool) or policy["scope"] != "NEW_ENTRY_ONLY"
            or policy["required_context_state"] != "QUALIFIED_CONTEXT_ONLY"
            or type(policy["blackout_before_seconds"]) is not int or policy["blackout_before_seconds"] < 0
            or type(policy["blackout_after_seconds"]) is not int or policy["blackout_after_seconds"] < 0
            or policy["execution_authority"] is not False or not isinstance(policy["activation_requirement"], str)
            or not policy["activation_requirement"]):
        raise EventRiskGateError("event-risk policy is invalid")
    return policy


def _verified_sidecar(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or value.get("schema_version") != "forex.m1.event-context-sidecar.v1":
        raise EventRiskGateError("event sidecar is unavailable")
    supplied = _digest(value.get("sidecar_sha256"), field="sidecar_sha256")
    body = {key: item for key, item in value.items() if key != "sidecar_sha256"}
    if supplied != "sha256:" + hashlib.sha256(_canonical(body)).hexdigest():
        raise EventRiskGateError("event sidecar digest does not bind context")
    if value.get("execution_authority") is not False or value.get("annotation_type") != "EVENT_CONTEXT_ONLY":
        raise EventRiskGateError("event sidecar has unsafe authority")
    for field in ("source_raw_sha256", "event_context_journal_sha256", "event_qualification_sha256", "event_annotation_sha256"):
        _digest(value.get(field), field=field)
    annotation = value.get("event_annotation")
    if not isinstance(annotation, dict) or annotation.get("annotation_type") != "EVENT_CONTEXT_ONLY":
        raise EventRiskGateError("event sidecar annotation is unavailable")
    annotation_digest = annotation.get("annotation_sha256")
    if (annotation_digest != value["event_annotation_sha256"]
            or annotation_digest != "sha256:" + hashlib.sha256(_canonical({k: v for k, v in annotation.items() if k != "annotation_sha256"})).hexdigest()):
        raise EventRiskGateError("event sidecar annotation digest does not bind context")
    decision = _utc(value.get("decision_at_utc"), field="sidecar.decision_at_utc")
    if annotation.get("decision_at_utc") != decision.isoformat().replace("+00:00", "Z"):
        raise EventRiskGateError("event sidecar decision time does not bind annotation")
    events = annotation.get("events")
    if not isinstance(events, list):
        raise EventRiskGateError("event sidecar events are unavailable")
    for item in events:
        if not isinstance(item, dict) or type(item.get("seconds_from_decision")) is not int:
            raise EventRiskGateError("event sidecar event timing is invalid")
    return {"decision_at_utc": decision, "events": events}


def _verified_primary_context(value: Any, *, decision_at_utc: datetime) -> dict[str, Any]:
    if not isinstance(value, dict) or value.get("schema_version") != "forex.primary-event-context.v1":
        raise EventRiskGateError("primary event context is unavailable")
    supplied = _digest(value.get("context_sha256"), field="primary_context.context_sha256")
    body = {key: item for key, item in value.items() if key != "context_sha256"}
    if supplied != "sha256:" + hashlib.sha256(_canonical(body)).hexdigest():
        raise EventRiskGateError("primary event context digest does not bind coverage")
    if value.get("execution_authority") is not False:
        raise EventRiskGateError("primary event context has unsafe authority")
    families = value.get("families")
    if not isinstance(families, list) or len(families) != len(_PRIMARY_SOURCES):
        raise EventRiskGateError("primary event context has incomplete family coverage")
    observed: set[str] = set()
    required = {"family_id", "source_id", "state", "reason", "qualification_state", "limitation", "receipt"}
    for family in families:
        if not isinstance(family, dict) or set(family) != required or family.get("family_id") not in _PRIMARY_SOURCES:
            raise EventRiskGateError("primary event context family shape is invalid")
        family_id = family["family_id"]
        if family_id in observed or family.get("state") != "QUALIFIED_CONTEXT_ONLY":
            raise EventRiskGateError("primary event context family is not qualified")
        expected_source_id, expected_url = _PRIMARY_SOURCES[family_id]
        receipt = family.get("receipt")
        if (family.get("source_id") != expected_source_id or not isinstance(receipt, dict)
                or set(receipt) != {"source_url", "captured_at_utc", "source_sha256", "coverage_status"}
                or receipt.get("source_url") != expected_url or receipt.get("coverage_status") != "COMPLETE"):
            raise EventRiskGateError("primary event context family receipt does not bind the source contract")
        _digest(receipt.get("source_sha256"), field="primary event receipt source_sha256")
        if _utc(receipt.get("captured_at_utc"), field="primary event receipt") > decision_at_utc:
            raise EventRiskGateError("primary event receipt is unavailable at decision time")
        observed.add(family_id)
    if observed != set(_PRIMARY_SOURCES):
        raise EventRiskGateError("primary event context has incomplete family coverage")
    return value


def evaluate_new_entry(*, policy: Any, sidecar: Any = None, primary_context: Any = None) -> dict[str, Any]:
    """Return a prepared gate observation; disabled policy leaves execution unchanged."""
    chosen = validate_policy(policy)
    base = {"schema_version": SCHEMA, "execution_authority": False, "scope": "NEW_ENTRY_ONLY"}
    if not chosen["enabled"]:
        return {**base, "state": "ANNOTATION_ONLY_DISABLED", "new_entry_permitted": None,
                "reason": "SHIPPED_POLICY_DISABLED_NO_EXECUTION_BEHAVIOR_CHANGE"}
    try:
        context = _verified_sidecar(sidecar)
        coverage = _verified_primary_context(primary_context, decision_at_utc=context["decision_at_utc"])
    except EventRiskGateError as exc:
        return {**base, "state": "FAIL_SAFE_CONTEXT_UNAVAILABLE", "new_entry_permitted": False, "reason": str(exc)}
    if coverage.get("context_state") != chosen["required_context_state"]:
        return {**base, "state": "FAIL_SAFE_CONTEXT_" + str(coverage.get("context_state", "UNAVAILABLE")),
                "new_entry_permitted": False, "reason": "PRIMARY_EVENT_CONTEXT_NOT_QUALIFIED"}
    before, after = chosen["blackout_before_seconds"], chosen["blackout_after_seconds"]
    nearby = [item for item in context["events"] if -after <= item["seconds_from_decision"] <= before]
    if nearby:
        return {**base, "state": "NEW_ENTRY_REFUSED_EVENT_WINDOW", "new_entry_permitted": False,
                "reason": "QUALIFIED_EVENT_WITHIN_CONFIGURED_WINDOW", "event_count": len(nearby)}
    return {**base, "state": "NEW_ENTRY_PERMITTED", "new_entry_permitted": True,
            "reason": "QUALIFIED_CONTEXT_HAS_NO_EVENT_IN_CONFIGURED_WINDOW", "event_count": 0}
