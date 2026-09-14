"""Pure local H_SLOW readiness report with no persistence or broker surface.

This connects retained decision, reconciliation, isolation, event, market and
size inputs into one reproducible report.  It deliberately stops before the
durable worker: no schedule, database, terminal, account selection, route or
order capability is imported or exposed here.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from .h_slow_lifecycle import HSlowLifecycleError
from .h_slow_order_preparation import prepare_h_slow_order
from .h_slow_runtime import evaluate_runtime_observation
from .h_slow_initial_trial import HSlowInitialTrialError, validate_initial_trial


READINESS_INPUT_SCHEMA_VERSION = "forex.h-slow.readiness-input.v1"
READINESS_REPORT_SCHEMA_VERSION = "forex.h-slow.readiness-report.v1"
_REQUIRED = {
    "schema_version", "research_decision", "envelope", "stream_registry", "evaluated_at_utc",
    "maximum_observation_age_seconds", "market_inputs", "limits", "event_eligibility", "primary_context",
}
_OPTIONAL = {"trial_mandate", "initial_trial"}


class HSlowReadinessError(ValueError):
    """The local, submission-disabled readiness input is unsafe or incomplete."""


def _copy(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise HSlowReadinessError(f"{label} must be an object")
    try:
        copied = json.loads(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False))
    except (TypeError, ValueError) as exc:
        raise HSlowReadinessError(f"{label} must be finite JSON") from exc
    if not isinstance(copied, dict):
        raise HSlowReadinessError(f"{label} must be an object")
    return copied


def _digest(value: Mapping[str, Any]) -> str:
    return "sha256:" + hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()


def evaluate_h_slow_readiness(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Evaluate exactly one supplied H_SLOW snapshot without side effects."""
    supplied = _copy(payload, "readiness payload")
    if set(supplied) - _REQUIRED - _OPTIONAL or not _REQUIRED <= set(supplied):
        raise HSlowReadinessError("readiness payload fields are invalid")
    if supplied.get("schema_version") != READINESS_INPUT_SCHEMA_VERSION:
        raise HSlowReadinessError("unsupported readiness payload schema")
    runtime_input = {key: supplied[key] for key in (
        "research_decision", "envelope", "stream_registry", "evaluated_at_utc", "maximum_observation_age_seconds",
    )}
    if "trial_mandate" in supplied:
        runtime_input["trial_mandate"] = supplied["trial_mandate"]
    try:
        runtime = evaluate_runtime_observation(**runtime_input)
    except HSlowLifecycleError as exc:
        raise HSlowReadinessError(f"runtime readiness refused: {exc}") from exc
    initial_trial = None
    if "initial_trial" in supplied:
        try: initial_trial = validate_initial_trial(supplied["initial_trial"])
        except HSlowInitialTrialError as exc: raise HSlowReadinessError(f"initial trial refused: {exc}") from exc
    preparation = prepare_h_slow_order(
        runtime["plan"], market_inputs=supplied["market_inputs"], limits=supplied["limits"],
        event_eligibility=supplied["event_eligibility"], research_decision=supplied["research_decision"],
        primary_context=supplied["primary_context"], initial_trial=initial_trial,
    )
    if preparation.get("execution_authority") is not False or preparation.get("submission_status") != "DISABLED_NOT_ROUTED":
        raise HSlowReadinessError("order preparation returned unsafe authority")
    content = {
        "schema_version": READINESS_REPORT_SCHEMA_VERSION,
        "input_sha256": _digest(supplied),
        "runtime": runtime,
        "preparation": preparation,
        "readiness_state": ("PREPARED_DISABLED_NO_ROUTING" if preparation["outcome"] == "PREPARED_DISABLED"
                            else "NO_NEW_ENTRY"),
        "execution_authority": False,
        "submission_status": "DISABLED_NOT_ROUTED",
    }
    return {**content, "report_sha256": _digest(content)}
