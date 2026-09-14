"""Time-bound H_SLOW lifecycle evaluation for runtime integration.

Consumes an observation envelope from an adapter. Clocks are checked before
the pure lifecycle planner is called. This function does not certify broker
provenance or submit orders; freshness never substitutes for reconciliation.
"""
from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from typing import Any

from .h_slow_lifecycle import HSlowLifecycleError, plan_h_slow_lifecycle


def _utc(value: Any, field: str) -> datetime:
    if not isinstance(value, str):
        raise HSlowLifecycleError(f"{field} must be a UTC timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise HSlowLifecycleError(f"{field} is invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise HSlowLifecycleError(f"{field} must be UTC")
    return parsed


def evaluate_runtime_observation(*, research_decision: dict, envelope: dict,
                                 stream_registry: dict, evaluated_at_utc: str,
                                 maximum_observation_age_seconds: float,
                                 trial_mandate: dict | None = None) -> dict:
    """Check acquisition clocks and bind a lifecycle plan to retained input.

    The caller supplies the observation-age policy explicitly; there is no
    implicit new operational threshold. An expired monthly target cannot plan
    an entry or reversal in a later month. Position management requiring an
    independent protection rule remains the executor's responsibility.
    """
    expected = {"schema_version", "observed_at_utc", "received_at_utc", "observation"}
    if not isinstance(envelope, dict) or set(envelope) != expected:
        raise HSlowLifecycleError("observation envelope fields are invalid")
    if envelope["schema_version"] != "forex.h-slow.timed-observation.v1":
        raise HSlowLifecycleError("observation envelope version is invalid")
    if (isinstance(maximum_observation_age_seconds, bool)
            or not isinstance(maximum_observation_age_seconds, (int, float))
            or not math.isfinite(maximum_observation_age_seconds)
            or maximum_observation_age_seconds <= 0):
        raise HSlowLifecycleError("maximum observation age must be positive and finite")
    now = _utc(evaluated_at_utc, "evaluated_at_utc")
    observed = _utc(envelope["observed_at_utc"], "observed_at_utc")
    received = _utc(envelope["received_at_utc"], "received_at_utc")
    if not observed <= received <= now:
        raise HSlowLifecycleError("observation clocks must satisfy observed <= received <= evaluation")
    if (now - observed).total_seconds() > maximum_observation_age_seconds:
        raise HSlowLifecycleError("reconciliation observation is stale")
    if not isinstance(research_decision, dict):
        raise HSlowLifecycleError("research decision must be an object")
    decision_time = _utc(research_decision.get("decision_at_utc"), "decision_at_utc")
    if decision_time > observed:
        raise HSlowLifecycleError("reconciliation observation predates the research decision")
    if (decision_time.year, decision_time.month) != (now.year, now.month):
        raise HSlowLifecycleError("monthly target has expired; protection and reconciliation must continue")
    plan = plan_h_slow_lifecycle(research_decision=research_decision,
        reconciliation_observation=envelope["observation"], stream_registry=stream_registry,
        trial_mandate=trial_mandate)
    try:
        encoded = json.dumps(envelope, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    except (ValueError, TypeError) as exc:
        raise HSlowLifecycleError("observation envelope must be finite JSON") from exc
    return {
        "schema_version": "forex.h-slow.runtime-evaluation.v1",
        "evaluated_at_utc": now.isoformat().replace("+00:00", "Z"),
        "observation_sha256": "sha256:" + hashlib.sha256(encoded).hexdigest(),
        "observation_age_seconds": (now - observed).total_seconds(),
        "maximum_observation_age_seconds": maximum_observation_age_seconds,
        "plan": plan,
        "execution_authority": False,
    }
