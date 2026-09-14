"""Closed, deterministic H_SLOW forward/OOS edge-sizing contract.

This is deliberately a *downward-only* sizing layer. It cannot grant trading
authority or enlarge a human-declared hard loss cap. Its evidence is bound to
the exact retained research decision and policy version being prepared.
"""
from __future__ import annotations

import hashlib
import json
import re
from decimal import Decimal, InvalidOperation, localcontext
from typing import Any

POLICY_SCHEMA = "forex.h-slow.edge-sizing-policy.v1"
EVIDENCE_SCHEMA = "forex.h-slow.edge-evidence.v1"
RESULT_SCHEMA = "forex.h-slow.edge-sizing-result.v1"
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}\Z")


class HSlowEdgeSizingError(ValueError):
    """The edge policy, retained evidence, or derived result is invalid."""


def _sha(value: Any) -> str:
    return "sha256:" + hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()


def _num(value: Any, label: str) -> Decimal:
    if isinstance(value, bool):
        raise HSlowEdgeSizingError(f"{label} must be finite numeric")
    try:
        # Decimal(str(...)) is intentional: tier boundaries are financial
        # contract values, so a value just below .04 must not round up to .04.
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise HSlowEdgeSizingError(f"{label} must be finite numeric") from exc
    if not number.is_finite():
        raise HSlowEdgeSizingError(f"{label} must be finite numeric")
    return number


def _digest(value: Any, label: str) -> str:
    if not isinstance(value, str) or not _DIGEST.fullmatch(value):
        raise HSlowEdgeSizingError(f"{label} must be a canonical SHA-256 digest")
    return value


def _nonempty_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise HSlowEdgeSizingError(f"{label} must be nonempty text")
    return value


def _decimal_text(value: Decimal) -> str:
    """Serialize an exact non-exponent Decimal for a hash-bound JSON record."""
    with localcontext() as serialization_context:
        serialization_context.prec = 50
        return format(value.normalize(), "f")


def _validate_policy(policy: dict[str, Any]) -> list[dict[str, Any]]:
    fields = {"schema_version", "policy_id", "policy_sha256", "tiers", "execution_authority"}
    if (not isinstance(policy, dict) or set(policy) != fields or policy.get("schema_version") != POLICY_SCHEMA
            or policy.get("execution_authority") is not False):
        raise HSlowEdgeSizingError("edge policy is invalid")
    _nonempty_text(policy.get("policy_id"), "policy_id")
    if policy.get("policy_sha256") != _sha({key: policy[key] for key in fields - {"policy_sha256"}}):
        raise HSlowEdgeSizingError("edge policy provenance is invalid")
    tiers = policy.get("tiers")
    expected = [("BASE", Decimal(".25")), ("QUALIFIED", Decimal(".5")), ("STRONG", Decimal("1"))]
    if not isinstance(tiers, list) or len(tiers) != len(expected):
        raise HSlowEdgeSizingError("edge policy tiers are invalid")
    previous_samples = 0
    previous_return, previous_drawdown = Decimal("-Infinity"), Decimal("Infinity")
    for row, (name, multiplier) in zip(tiers, expected):
        if (not isinstance(row, dict)
                or set(row) != {"tier", "risk_multiplier", "minimum_sample_count", "minimum_net_after_cost_return", "maximum_drawdown"}
                or row.get("tier") != name or _num(row.get("risk_multiplier"), "risk_multiplier") != multiplier
                or type(row.get("minimum_sample_count")) is not int or row["minimum_sample_count"] < 1):
            raise HSlowEdgeSizingError("edge tier is invalid")
        minimum_return = _num(row["minimum_net_after_cost_return"], "minimum_net_after_cost_return")
        maximum_drawdown = _num(row["maximum_drawdown"], "maximum_drawdown")
        if not Decimal(0) <= maximum_drawdown <= Decimal(1):
            raise HSlowEdgeSizingError("maximum_drawdown must be between zero and one")
        if (row["minimum_sample_count"] < previous_samples or minimum_return < previous_return
                or maximum_drawdown > previous_drawdown):
            raise HSlowEdgeSizingError("edge tiers must become no easier at higher risk")
        previous_samples, previous_return, previous_drawdown = row["minimum_sample_count"], minimum_return, maximum_drawdown
    return tiers


def _validate_evidence(evidence: dict[str, Any], *, decision_at_utc: str,
                       research_decision_sha256: str, strategy_policy_version: str) -> dict[str, Any]:
    fields = {"schema_version", "evidence_id", "evidence_sha256", "decision_at_utc", "research_decision_sha256",
              "strategy_policy_version", "forward_oos_metrics", "execution_authority"}
    if (not isinstance(evidence, dict) or set(evidence) != fields or evidence.get("schema_version") != EVIDENCE_SCHEMA
            or evidence.get("execution_authority") is not False or evidence.get("decision_at_utc") != decision_at_utc):
        raise HSlowEdgeSizingError("edge evidence is invalid")
    _nonempty_text(evidence.get("evidence_id"), "evidence_id")
    if (evidence.get("research_decision_sha256") != _digest(research_decision_sha256, "research_decision_sha256")
            or evidence.get("strategy_policy_version") != _nonempty_text(strategy_policy_version, "strategy_policy_version")):
        raise HSlowEdgeSizingError("edge evidence is not bound to this research decision")
    if evidence.get("evidence_sha256") != _sha({key: evidence[key] for key in fields - {"evidence_sha256"}}):
        raise HSlowEdgeSizingError("edge evidence provenance is invalid")
    metrics = evidence.get("forward_oos_metrics")
    expected_metrics = {"retained_run_sha256", "sample_count", "net_after_cost_return", "max_drawdown"}
    if (not isinstance(metrics, dict) or set(metrics) != expected_metrics
            or type(metrics.get("sample_count")) is not int or metrics["sample_count"] < 1):
        raise HSlowEdgeSizingError("forward OOS metrics are invalid")
    _digest(metrics.get("retained_run_sha256"), "retained_run_sha256")
    drawdown = _num(metrics["max_drawdown"], "max_drawdown")
    _num(metrics["net_after_cost_return"], "net_after_cost_return")
    if not Decimal(0) <= drawdown <= Decimal(1):
        raise HSlowEdgeSizingError("max_drawdown must be between zero and one")
    return metrics


def derive_edge_sizing(policy: dict[str, Any], evidence: dict[str, Any], *, decision_at_utc: str,
                       research_decision_sha256: str, strategy_policy_version: str,
                       hard_max_loss_aud: float) -> dict[str, Any]:
    """Derive a risk tier from declared thresholds and bound retained evidence."""
    tiers = _validate_policy(policy)
    metrics = _validate_evidence(evidence, decision_at_utc=decision_at_utc,
                                 research_decision_sha256=research_decision_sha256,
                                 strategy_policy_version=strategy_policy_version)
    tier, multiplier = "REFUSE", Decimal(0)
    for row in tiers:
        if (metrics["sample_count"] >= row["minimum_sample_count"]
                and _num(metrics["net_after_cost_return"], "net_after_cost_return") >= _num(row["minimum_net_after_cost_return"], "minimum_net_after_cost_return")
                and _num(metrics["max_drawdown"], "max_drawdown") <= _num(row["maximum_drawdown"], "maximum_drawdown")):
            tier, multiplier = row["tier"], _num(row["risk_multiplier"], "risk_multiplier")
    hard_cap = _num(hard_max_loss_aud, "hard_max_loss_aud")
    if hard_cap <= 0:
        raise HSlowEdgeSizingError("hard_max_loss_aud must be positive")
    # Never inherit a caller's Decimal context: a low precision context can
    # round 150 * 1 upward to 200.  Preserve decimal text rather than a float
    # so serialization cannot reintroduce an upward rounding error.
    with localcontext() as calculation_context:
        calculation_context.prec = 50
        allowed_cap = hard_cap * multiplier
    if allowed_cap > hard_cap:
        raise HSlowEdgeSizingError("derived edge cap exceeds hard loss cap")
    content = {"policy": policy, "evidence": evidence, "decision_at_utc": decision_at_utc,
               "research_decision_sha256": research_decision_sha256, "strategy_policy_version": strategy_policy_version,
               "hard_max_loss_aud": _decimal_text(hard_cap), "tier": tier,
               "risk_multiplier": _decimal_text(multiplier), "allowed_max_loss_aud": _decimal_text(allowed_cap)}
    return {**content, "schema_version": RESULT_SCHEMA,
            "outcome": "REFUSED" if tier == "REFUSE" else "DOWNWARD_CAP_ONLY",
            "execution_authority": False, "result_sha256": _sha(content)}


def validate_edge_sizing_result(result: dict[str, Any], *, decision_at_utc: str,
                                research_decision_sha256: str, strategy_policy_version: str,
                                hard_max_loss_aud: float) -> dict[str, Any]:
    """Re-derive and bind a result to the decision actually being prepared."""
    if (not isinstance(result, dict) or result.get("schema_version") != RESULT_SCHEMA
            or result.get("execution_authority") is not False):
        raise HSlowEdgeSizingError("edge sizing result is invalid")
    derived = derive_edge_sizing(result.get("policy"), result.get("evidence"), decision_at_utc=decision_at_utc,
                                 research_decision_sha256=research_decision_sha256,
                                 strategy_policy_version=strategy_policy_version,
                                 hard_max_loss_aud=hard_max_loss_aud)
    if derived != result:
        raise HSlowEdgeSizingError("edge sizing result provenance is invalid")
    return derived
