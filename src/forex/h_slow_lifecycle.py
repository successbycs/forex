"""Pure, fail-closed lifecycle planning for the disabled H_SLOW stream.

The module consumes retained research decisions and caller-supplied *read-only*
reconciliation observations.  It does not persist intent, contact a broker,
select a terminal/account, acquire a lease, or submit a close/open request.
Its output is an idempotent next-action plan for a future, separately
authorised adapter.  In particular, a reversal is always two reconciled
phases: close the owned ticket first, then (only in a later observation with
no owned exposure) consider an opening action.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Mapping

from .h_slow_policy import POLICY_VERSION
from .h_slow_trial_mandate import HSlowMandateError, validate_h_slow_trial_mandate
from .stream_isolation import StreamIsolationError, validate_stream_registry


LIFECYCLE_SCHEMA_VERSION = "forex.h-slow.lifecycle-plan.v1"
OBSERVATION_SCHEMA_VERSION = "forex.h-slow.lifecycle-observation.v1"
_OPAQUE = re.compile(r"^[a-z][a-z0-9_-]{2,127}$")
_ACTIONS = frozenset({"BUY", "SELL", "NO_TRADE"})


class HSlowLifecycleError(ValueError):
    """A lifecycle input is incomplete, unsafe, or implies authority."""


def _copy(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise HSlowLifecycleError(f"{label} must be a mapping")
    try:
        copied = json.loads(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False))
    except (TypeError, ValueError) as exc:
        raise HSlowLifecycleError(f"{label} must be JSON-safe") from exc
    if not isinstance(copied, dict):
        raise HSlowLifecycleError(f"{label} must be an object")
    return copied


def _digest(value: dict[str, Any]) -> str:
    return "sha256:" + hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()


def _opaque(value: Any, label: str) -> str:
    if not isinstance(value, str) or not _OPAQUE.fullmatch(value) or value.isdecimal():
        raise HSlowLifecycleError(f"{label} must be a non-secret opaque identifier")
    return value


def _verified_decision(value: Any) -> dict[str, Any]:
    """Verify the immutable research decision hash before planning from it."""
    decision = _copy(value, "research decision")
    base = {
        "decision_schema_version", "policy_version", "snapshot_id", "snapshot_artifact_sha256",
        "policy_input_sha256", "decision_at_utc", "target", "event_annotation_status",
    }
    expected = base | {"decision_sha256", "record_status", "execution_authority"}
    # Context attachment adds exactly one immutable annotation field.
    if decision.get("event_annotation_status") == "ATTACHED_CONTEXT_ONLY":
        expected |= {"event_annotation"}
    if set(decision) != expected:
        raise HSlowLifecycleError("research decision fields are invalid")
    content = {key: decision[key] for key in expected - {"decision_sha256", "record_status", "execution_authority"}}
    if (decision.get("decision_schema_version") != "forex.h-slow.research-decision.v1"
            or decision.get("policy_version") != POLICY_VERSION
            or decision.get("record_status") != "RESEARCH_TARGET_ONLY"
            or decision.get("execution_authority") is not False
            or decision.get("decision_sha256") != _digest(content)):
        raise HSlowLifecycleError("research decision is not a verified research-only record")
    target = decision.get("target")
    if not isinstance(target, dict) or target.get("policy_version") != POLICY_VERSION:
        raise HSlowLifecycleError("research decision target is invalid")
    if (target.get("instrument") != "EUR/USD" or target.get("action") not in _ACTIONS
            or target.get("research_only") is not True or target.get("execution_authority") is not False):
        raise HSlowLifecycleError("research decision target is not a disabled EUR/USD target")
    return decision


def _observation(value: Any, *, account_scope: str, terminal_instance: str) -> dict[str, Any]:
    observed = _copy(value, "reconciliation observation")
    expected = {
        "schema_version", "stream_id", "account_scope", "terminal_instance", "reconciliation_status",
        "positions", "pending_attempts",
    }
    if set(observed) != expected:
        raise HSlowLifecycleError("reconciliation observation fields are invalid")
    if observed["schema_version"] != OBSERVATION_SCHEMA_VERSION or observed["stream_id"] != "H_SLOW":
        raise HSlowLifecycleError("reconciliation observation is not H_SLOW v1")
    if observed["account_scope"] != account_scope or observed["terminal_instance"] != terminal_instance:
        raise HSlowLifecycleError("reconciliation observation scope does not match H_SLOW isolation")
    if observed["reconciliation_status"] not in {"RECONCILED", "UNKNOWN"}:
        raise HSlowLifecycleError("reconciliation status must be RECONCILED or UNKNOWN")
    if not isinstance(observed["positions"], list) or not isinstance(observed["pending_attempts"], list):
        raise HSlowLifecycleError("positions and pending_attempts must be lists")
    tickets: set[str] = set()
    for index, position in enumerate(observed["positions"]):
        if not isinstance(position, dict) or set(position) != {"ticket_id", "owner_stream_id", "direction", "position_status"}:
            raise HSlowLifecycleError(f"position {index} fields are invalid")
        ticket = _opaque(position["ticket_id"], f"position {index} ticket_id")
        if ticket in tickets:
            raise HSlowLifecycleError("duplicate position ticket")
        tickets.add(ticket)
        if position["owner_stream_id"] not in {"H_SLOW", "M1"}:
            raise HSlowLifecycleError(f"position {index} owner is unsupported")
        if position["direction"] not in {"BUY", "SELL"} or position["position_status"] != "OPEN":
            raise HSlowLifecycleError(f"position {index} is not an open directional position")
    attempts: set[str] = set()
    for index, attempt in enumerate(observed["pending_attempts"]):
        if not isinstance(attempt, dict) or set(attempt) != {"attempt_id", "kind", "status", "ticket_id"}:
            raise HSlowLifecycleError(f"pending attempt {index} fields are invalid")
        attempt_id = _opaque(attempt["attempt_id"], f"pending attempt {index} attempt_id")
        if attempt_id in attempts:
            raise HSlowLifecycleError("duplicate pending attempt")
        attempts.add(attempt_id)
        if attempt["kind"] not in {"OPEN", "CLOSE"} or attempt["status"] not in {"PENDING", "UNKNOWN"}:
            raise HSlowLifecycleError(f"pending attempt {index} is invalid")
        if attempt["ticket_id"] is not None:
            _opaque(attempt["ticket_id"], f"pending attempt {index} ticket_id")
        if attempt["kind"] == "CLOSE" and attempt["ticket_id"] is None:
            raise HSlowLifecycleError(f"pending close attempt {index} requires a ticket_id")
    return observed


def _result(*, decision: dict[str, Any], isolation_fingerprint: str, state: str, reason: str,
            next_action: str, ticket_id: str | None = None, preflight_status: str = "NOT_PROVIDED") -> dict[str, Any]:
    intent = None
    if next_action in {"OPEN", "CLOSE"}:
        intent = {
            "action_id": _digest({"decision_sha256": decision["decision_sha256"],
                                  "isolation_registry_fingerprint": isolation_fingerprint,
                                  "action": next_action, "ticket_id": ticket_id}),
            "kind": next_action,
            "ticket_id": ticket_id,
            "direction": decision["target"]["action"] if next_action == "OPEN" else None,
        }
    return {
        "schema_version": LIFECYCLE_SCHEMA_VERSION,
        "stream_id": "H_SLOW",
        "decision_sha256": decision["decision_sha256"],
        "isolation_registry_fingerprint": isolation_fingerprint,
        "mandate_preflight_status": preflight_status,
        "lifecycle_state": state,
        "reason": reason,
        "next_action": next_action,
        "intent": intent,
        # A plan is not mandate routing.  An executor must independently bind
        # a later approved routing/lease/protection implementation.
        "execution_authority": False,
    }


def plan_h_slow_lifecycle(*, research_decision: Mapping[str, Any], reconciliation_observation: Mapping[str, Any],
                          stream_registry: Mapping[str, Any], trial_mandate: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Return one deterministic, non-operational H_SLOW lifecycle next step.

    Unknown observations and outstanding attempts win over all targets.  An
    observed M1 ticket in the supplied account is never named in an intent;
    it blocks planning so a wrongly scoped deployment cannot close or offset
    foreign ownership.  A close is merely an intent until a subsequent
    ``RECONCILED`` observation confirms that its H_SLOW ticket is absent.
    """
    decision = _verified_decision(research_decision)
    try:
        isolation = validate_stream_registry(stream_registry)
    except StreamIsolationError as exc:
        raise HSlowLifecycleError(f"invalid stream isolation: {exc}") from exc
    hslow = next(item for item in stream_registry["streams"] if item["stream_id"] == "H_SLOW")
    observed = _observation(reconciliation_observation, account_scope=hslow["account_scope"], terminal_instance=hslow["terminal_instance"])
    preflight = "NOT_PROVIDED"
    if trial_mandate is not None:
        try:
            preflight = validate_h_slow_trial_mandate(trial_mandate, stream_registry=stream_registry)["preflight_status"]
        except HSlowMandateError as exc:
            raise HSlowLifecycleError(f"invalid trial mandate: {exc}") from exc
    if observed["reconciliation_status"] == "UNKNOWN":
        return _result(decision=decision, isolation_fingerprint=isolation.registry_fingerprint, preflight_status=preflight,
                       state="AWAITING_RECONCILIATION", reason="position observation is unknown", next_action="WAIT")
    if observed["pending_attempts"]:
        return _result(decision=decision, isolation_fingerprint=isolation.registry_fingerprint, preflight_status=preflight,
                       state="AWAITING_RECONCILIATION", reason="unresolved H_SLOW attempt prevents duplicate submission", next_action="WAIT")
    foreign = [item for item in observed["positions"] if item["owner_stream_id"] != "H_SLOW"]
    if foreign:
        return _result(decision=decision, isolation_fingerprint=isolation.registry_fingerprint, preflight_status=preflight,
                       state="FOREIGN_OWNERSHIP_BLOCKED", reason="foreign ticket observed; H_SLOW cannot modify it", next_action="WAIT")
    owned = observed["positions"]
    if len(owned) > 1:
        return _result(decision=decision, isolation_fingerprint=isolation.registry_fingerprint, preflight_status=preflight,
                       state="OWNERSHIP_ANOMALY", reason="multiple H_SLOW tickets require manual reconciliation", next_action="WAIT")
    target = decision["target"]["action"]
    if not owned:
        if target == "NO_TRADE":
            return _result(decision=decision, isolation_fingerprint=isolation.registry_fingerprint, preflight_status=preflight,
                           state="FLAT", reason="NO_TRADE target with no owned position", next_action="NONE")
        return _result(decision=decision, isolation_fingerprint=isolation.registry_fingerprint, preflight_status=preflight,
                       state="ENTRY_ELIGIBLE", reason="reconciled flat H_SLOW scope matches research target", next_action="OPEN")
    position = owned[0]
    if target == position["direction"]:
        return _result(decision=decision, isolation_fingerprint=isolation.registry_fingerprint, preflight_status=preflight,
                       state="HOLDING", reason="owned position already matches research target", next_action="NONE", ticket_id=position["ticket_id"])
    return _result(decision=decision, isolation_fingerprint=isolation.registry_fingerprint, preflight_status=preflight,
                   state="CLOSE_REQUIRED", reason="opposite or NO_TRADE target requires confirmed close before any entry", next_action="CLOSE", ticket_id=position["ticket_id"])
