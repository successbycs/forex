"""One-pass, submission-disabled H_SLOW lifecycle worker.

The worker joins the time-checked runtime envelope, pure lifecycle planner,
and durable intent state.  It is deliberately not an execution worker: no
intent is claimed, no route is selected, and no broker call can occur here.
"""
from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any, Mapping

from .h_slow_persistence import HSlowLifecycleStore, HSlowPersistenceError, LifecycleIntent
from .h_slow_runtime import evaluate_runtime_observation


def _intent_dict(intent: LifecycleIntent | None) -> dict[str, Any] | None:
    return None if intent is None else asdict(intent)


def run_h_slow_worker_once(*, store: HSlowLifecycleStore, research_decision: Mapping[str, Any],
                           envelope: Mapping[str, Any], stream_registry: Mapping[str, Any],
                           evaluated_at_utc: str, maximum_observation_age_seconds: float,
                           trial_mandate: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Evaluate one observation and durably retain at most its valid intent.

    Clock and envelope validation occur before any persistence.  Durable
    unresolved state is read before a new plan is persisted, so a stale caller
    observation of a flat scope cannot hide a prior pending/claimed/unknown
    intent.  Submission remains structurally disabled even if a caller offers
    a pre-activation mandate.
    """
    runtime = evaluate_runtime_observation(
        research_decision=dict(research_decision), envelope=dict(envelope),
        stream_registry=dict(stream_registry), evaluated_at_utc=evaluated_at_utc,
        maximum_observation_age_seconds=maximum_observation_age_seconds,
        trial_mandate=None if trial_mandate is None else dict(trial_mandate),
    )
    plan = runtime["plan"]
    if store.registry_fingerprint != plan["isolation_registry_fingerprint"]:
        raise HSlowPersistenceError("worker/store isolation fingerprint mismatch")
    # Expiry applies only to never-claimed OPEN work; the store uses its own
    # database clock and retains an explicit non-submission audit transition.
    expired = store.expire_pending_intents()
    unresolved = store.unresolved_intents()
    plan_intent = plan["intent"]
    valid_until = None
    if plan_intent is not None and plan_intent["kind"] == "OPEN":
        decided = datetime.fromisoformat(research_decision["decision_at_utc"].replace("Z", "+00:00")).astimezone(UTC)
        valid_until = datetime(decided.year + (decided.month == 12),
                               1 if decided.month == 12 else decided.month + 1,
                               1, tzinfo=UTC).isoformat().replace("+00:00", "Z")
    same_intent = next((intent for intent in unresolved
                        if plan_intent is not None and intent.action_id == plan_intent["action_id"]), None)
    if unresolved:
        # Re-persist the same plan only to recover its durable state after a
        # restart.  A different decision must wait for reconciliation.
        persisted = store.persist_plan(plan, valid_until_utc=valid_until) if same_intent is not None else None
        return {
            "schema_version": "forex.h-slow.worker-result.v1",
            "observation_sha256": runtime["observation_sha256"],
            "runtime_evaluation": runtime,
            "worker_state": "DURABLE_RECONCILIATION_REQUIRED",
            "persisted_intent": _intent_dict(persisted),
            "unresolved_intents": [_intent_dict(intent) for intent in unresolved],
            "expired_intents": [_intent_dict(intent) for intent in expired],
            "submission_status": "DISABLED_NOT_ROUTED",
            "execution_authority": False,
        }
    persisted = store.persist_plan(plan, valid_until_utc=valid_until)
    return {
        "schema_version": "forex.h-slow.worker-result.v1",
        "observation_sha256": runtime["observation_sha256"],
        "runtime_evaluation": runtime,
        "worker_state": ("INTENT_EXPIRED_NOT_SUBMITTED" if persisted is not None
                         and persisted.claim_status == "EXPIRED_NOT_SUBMITTED"
                         else "INTENT_PERSISTED" if persisted is not None else "NO_ACTION"),
        "persisted_intent": _intent_dict(persisted),
        "unresolved_intents": [],
        "expired_intents": [_intent_dict(intent) for intent in expired],
        "submission_status": "DISABLED_NOT_ROUTED",
        "execution_authority": False,
    }
