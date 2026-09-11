"""M23 offline, deterministic sizing derived only from an M22 approval."""
from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from forex.simulated_risk import RiskPolicyError, drill, load_policy


def size_intent(intent: dict[str, Any], risk_result: dict[str, Any], *, policy: dict[str, Any], policy_sha256: str) -> dict[str, Any]:
    """Return a bounded simulated lot size or an explicit ``NO_TRADE`` result."""
    if risk_result.get("outcome") != "APPROVE_SIMULATION" or risk_result.get("policy_sha256") != policy_sha256:
        return {"intent_id": str(intent.get("intent_id", "unknown")), "outcome": "NO_TRADE", "reason": "RISK_NOT_APPROVED", "order_submission": "STRUCTURALLY_DISABLED"}
    required = {"intent_id", "stop_distance_points", "loss_per_point_aud_per_lot", "minimum_volume_lots", "maximum_volume_lots", "volume_step_lots"}
    missing = required - intent.keys()
    if missing:
        raise RiskPolicyError(f"sizing intent missing fields: {', '.join(sorted(missing))}")
    try:
        stop = float(intent["stop_distance_points"])
        point_value = float(intent["loss_per_point_aud_per_lot"])
        minimum = float(intent["minimum_volume_lots"])
        maximum = float(intent["maximum_volume_lots"])
        step = float(intent["volume_step_lots"])
    except (TypeError, ValueError) as exc:
        raise RiskPolicyError("sizing inputs must be numeric") from exc
    if not all(math.isfinite(value) and value > 0 for value in (stop, point_value, minimum, maximum, step)) or minimum > maximum:
        raise RiskPolicyError("invalid sizing bounds")
    risk_per_lot = stop * point_value
    risk_budget = float(policy["risk"]["maximum_planned_loss_aud"])
    raw_lots = risk_budget / risk_per_lot
    capped_lots = min(raw_lots, maximum)
    lots = math.floor((capped_lots + 1e-12) / step) * step
    if lots < minimum:
        return {"intent_id": str(intent["intent_id"]), "outcome": "NO_TRADE", "reason": "MINIMUM_VOLUME_EXCEEDS_RISK_BUDGET", "risk_budget_aud": risk_budget, "risk_per_lot_aud": risk_per_lot, "order_submission": "STRUCTURALLY_DISABLED"}
    planned_loss = lots * risk_per_lot
    return {"intent_id": str(intent["intent_id"]), "outcome": "SIZE_SIMULATION", "volume_lots": round(lots, 8), "risk_budget_aud": risk_budget, "risk_per_lot_aud": risk_per_lot, "planned_loss_aud": round(planned_loss, 8), "policy_sha256": policy_sha256, "order_submission": "STRUCTURALLY_DISABLED"}


def drill_sizing(root: Path) -> dict[str, Any]:
    policy, digest = load_policy(root)
    risks = {item["intent_id"]: item for item in drill(root)["results"]}
    base = {"stop_distance_points": 100.0, "loss_per_point_aud_per_lot": 10.0, "minimum_volume_lots": 0.01, "maximum_volume_lots": 1.0, "volume_step_lots": 0.01}
    return {"marker": "FOREX_M23_SIZING_DRILL_OK", "results": [
        size_intent({"intent_id": "sized", **base}, risks["allowed"], policy=policy, policy_sha256=digest),
        size_intent({"intent_id": "risk-refused", **base}, risks["loss"], policy=policy, policy_sha256=digest),
        size_intent({"intent_id": "too-small", **base, "minimum_volume_lots": 0.2}, risks["allowed"], policy=policy, policy_sha256=digest),
    ]}
