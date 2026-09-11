"""M22 deterministic offline risk evaluation with no execution surface."""
from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import yaml


class RiskPolicyError(ValueError):
    """A simulation policy or intent is not safe to evaluate."""


def _utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise RiskPolicyError("timestamp must include an offset")
    return parsed.astimezone(UTC)


def load_policy(root: Path) -> tuple[dict[str, Any], str]:
    """Load only the fixed M22 policy documents and bind their bytes."""
    paths = [root / "config/risk.yaml", root / "config/execution.yaml"]
    try:
        values = [yaml.safe_load(path.read_text()) for path in paths]
    except (OSError, yaml.YAMLError) as exc:
        raise RiskPolicyError("unable to load M22 policy") from exc
    if not all(isinstance(value, dict) for value in values):
        raise RiskPolicyError("M22 policies must be mappings")
    risk, execution = values
    required_risk = {"schema_version", "policy_version", "canonical_instrument", "maximum_open_positions", "maximum_planned_loss_aud", "maximum_spread_points", "event_blackout_minutes"}
    required_execution = {"schema_version", "mode", "mandatory_flat_by_hour_utc", "allow_order_submission"}
    if set(risk) != required_risk or set(execution) != required_execution:
        raise RiskPolicyError("M22 policy has missing or unknown fields")
    if (risk["schema_version"] != "forex.m22.risk.v1" or risk["canonical_instrument"] != "EUR/USD"
            or risk["maximum_open_positions"] != 1 or float(risk["maximum_planned_loss_aud"]) <= 0
            or float(risk["maximum_spread_points"]) <= 0 or int(risk["event_blackout_minutes"]) < 0):
        raise RiskPolicyError("M22 risk policy violates fixed safety bounds")
    if (execution["schema_version"] != "forex.m22.execution.v1" or execution["mode"] != "SIMULATION_ONLY"
            or execution["allow_order_submission"] is not False or not 0 <= int(execution["mandatory_flat_by_hour_utc"]) <= 23):
        raise RiskPolicyError("M22 execution policy must remain simulation-only")
    payload = {"risk": risk, "execution": execution}
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return payload, f"sha256:{digest}"


def evaluate(intent: dict[str, Any], *, policy: dict[str, Any], policy_sha256: str) -> dict[str, Any]:
    """Evaluate one non-executing intent and return all refusal reasons."""
    risk, execution = policy["risk"], policy["execution"]
    required = {"intent_id", "instrument", "decision_at_utc", "planned_exit_at_utc", "open_positions", "planned_loss_aud", "spread_points", "qualified_events"}
    missing = required - intent.keys()
    if missing:
        raise RiskPolicyError(f"intent missing required fields: {', '.join(sorted(missing))}")
    decision, exit_at = _utc(str(intent["decision_at_utc"])), _utc(str(intent["planned_exit_at_utc"]))
    reasons: list[str] = []
    if intent["instrument"] != risk["canonical_instrument"]:
        reasons.append("INSTRUMENT_NOT_ALLOWED")
    if not isinstance(intent["open_positions"], int) or intent["open_positions"] < 0:
        reasons.append("INVALID_POSITION_COUNT")
    elif intent["open_positions"] >= risk["maximum_open_positions"]:
        reasons.append("ONE_POSITION_LIMIT")
    if not isinstance(intent["planned_loss_aud"], (int, float)) or intent["planned_loss_aud"] < 0:
        reasons.append("INVALID_PLANNED_LOSS")
    elif float(intent["planned_loss_aud"]) > float(risk["maximum_planned_loss_aud"]):
        reasons.append("LOSS_LIMIT")
    if not isinstance(intent["spread_points"], (int, float)) or intent["spread_points"] < 0:
        reasons.append("INVALID_SPREAD")
    elif float(intent["spread_points"]) > float(risk["maximum_spread_points"]):
        reasons.append("SPREAD_LIMIT")
    flat_by = decision.replace(hour=int(execution["mandatory_flat_by_hour_utc"]), minute=0, second=0, microsecond=0)
    if exit_at >= flat_by or exit_at <= decision:
        reasons.append("MANDATORY_FLAT_BY_CUTOFF")
    blackout = timedelta(minutes=int(risk["event_blackout_minutes"]))
    for event in intent["qualified_events"]:
        try:
            scheduled = _utc(str(event["scheduled_at_utc"]))
            available = _utc(str(event["available_at_utc"]))
        except (KeyError, RiskPolicyError):
            reasons.append("UNQUALIFIED_EVENT_CONTEXT")
            break
        if available > decision:
            reasons.append("UNQUALIFIED_EVENT_CONTEXT")
            break
        if abs(scheduled - decision) <= blackout:
            reasons.append("SCHEDULED_EVENT_BLACKOUT")
            break
    return {
        "intent_id": str(intent["intent_id"]), "decision_at_utc": decision.isoformat().replace("+00:00", "Z"),
        "mode": execution["mode"], "policy_version": risk["policy_version"], "policy_sha256": policy_sha256,
        "outcome": "REFUSE" if reasons else "APPROVE_SIMULATION", "reasons": sorted(set(reasons)),
        "order_submission": "STRUCTURALLY_DISABLED",
    }


def drill(root: Path) -> dict[str, Any]:
    policy, digest = load_policy(root)
    base = {"instrument": "EUR/USD", "decision_at_utc": "2026-09-11T12:00:00Z", "planned_exit_at_utc": "2026-09-11T12:10:00Z", "open_positions": 0, "planned_loss_aud": 50.0, "spread_points": 8.0, "qualified_events": []}
    cases = [
        {"intent_id": "allowed", **base},
        {"intent_id": "position", **base, "open_positions": 1},
        {"intent_id": "loss", **base, "planned_loss_aud": 100.01},
        {"intent_id": "spread", **base, "spread_points": 12.1},
        {"intent_id": "cutoff", **base, "planned_exit_at_utc": "2026-09-11T18:00:00Z"},
        {"intent_id": "event", **base, "qualified_events": [{"scheduled_at_utc": "2026-09-11T12:20:00Z", "available_at_utc": "2026-09-11T11:00:00Z"}]},
    ]
    results = [evaluate(case, policy=policy, policy_sha256=digest) for case in cases]
    return {"marker": "FOREX_M22_RISK_DRILL_OK", "policy_sha256": digest, "results": results}
