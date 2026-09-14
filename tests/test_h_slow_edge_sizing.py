import hashlib
import json
from decimal import localcontext

import pytest

from forex.h_slow_edge_sizing import (
    EVIDENCE_SCHEMA,
    POLICY_SCHEMA,
    HSlowEdgeSizingError,
    derive_edge_sizing,
)


DECISION = "sha256:" + "b" * 64
POLICY_VERSION = "forex.h-slow.tsmom-12m.v1"
WHEN = "2026-10-01T00:00:00Z"


def sign(value, field):
    value[field] = "sha256:" + hashlib.sha256(json.dumps(
        {key: item for key, item in value.items() if key != field}, sort_keys=True, separators=(",", ":")
    ).encode()).hexdigest()
    return value


def policy():
    return sign({"schema_version": POLICY_SCHEMA, "policy_id": "v1", "tiers": [
        {"tier": "BASE", "risk_multiplier": .25, "minimum_sample_count": 10,
         "minimum_net_after_cost_return": .01, "maximum_drawdown": .2},
        {"tier": "QUALIFIED", "risk_multiplier": .5, "minimum_sample_count": 20,
         "minimum_net_after_cost_return": .02, "maximum_drawdown": .15},
        {"tier": "STRONG", "risk_multiplier": 1., "minimum_sample_count": 40,
         "minimum_net_after_cost_return": .04, "maximum_drawdown": .1},
    ], "execution_authority": False}, "policy_sha256")


def evidence(**changes):
    value = {"schema_version": EVIDENCE_SCHEMA, "evidence_id": "x", "decision_at_utc": WHEN,
             "research_decision_sha256": DECISION, "strategy_policy_version": POLICY_VERSION,
             "forward_oos_metrics": {"retained_run_sha256": "sha256:" + "a" * 64,
                 "sample_count": 40, "net_after_cost_return": .04, "max_drawdown": .1},
             "execution_authority": False}
    value.update(changes)
    return sign(value, "evidence_sha256")


def derive(item=None, **changes):
    return derive_edge_sizing(policy(), evidence() if item is None else item, decision_at_utc=WHEN,
                              research_decision_sha256=DECISION, strategy_policy_version=POLICY_VERSION,
                              hard_max_loss_aud=100, **changes)


def test_tiers_are_threshold_derived_and_hard_cap_wins():
    assert derive()["allowed_max_loss_aud"] == "100"


def test_edge_cap_uses_private_exact_decimal_context_and_never_exceeds_hard_cap():
    with localcontext() as hostile_context:
        hostile_context.prec = 1
        result = derive_edge_sizing(policy(), evidence(), decision_at_utc=WHEN,
                                    research_decision_sha256=DECISION,
                                    strategy_policy_version=POLICY_VERSION,
                                    hard_max_loss_aud=150)
    assert result["hard_max_loss_aud"] == "150"
    assert result["allowed_max_loss_aud"] == "150"


def test_false_strong_and_subjective_input_refuse():
    weak = evidence(forward_oos_metrics={"retained_run_sha256": "sha256:" + "a" * 64,
        "sample_count": 1, "net_after_cost_return": 0, "max_drawdown": .9})
    assert derive(weak)["tier"] == "REFUSE"
    invented = evidence()
    invented["llm_confidence"] = 1
    with pytest.raises(HSlowEdgeSizingError):
        derive(invented)


@pytest.mark.parametrize("metrics", [
    {"retained_run_sha256": "sha256:not-a-digest", "sample_count": 40, "net_after_cost_return": .04, "max_drawdown": .1},
    {"retained_run_sha256": "sha256:" + "a" * 64, "sample_count": 40, "net_after_cost_return": .04, "max_drawdown": -999},
])
def test_malformed_retention_or_impossible_drawdown_is_rejected(metrics):
    with pytest.raises(HSlowEdgeSizingError):
        derive(evidence(forward_oos_metrics=metrics))


def test_evidence_cannot_be_reused_for_a_different_research_decision_or_time():
    item = evidence(decision_at_utc="2099-01-01T00:00:00Z")
    with pytest.raises(HSlowEdgeSizingError):
        derive(item)


def test_decimal_metrics_cannot_round_up_across_a_tier_boundary():
    below_return = evidence(forward_oos_metrics={"retained_run_sha256": "sha256:" + "a" * 64,
        "sample_count": 40, "net_after_cost_return": "0.039999999999999999", "max_drawdown": ".1"})
    above_drawdown = evidence(forward_oos_metrics={"retained_run_sha256": "sha256:" + "a" * 64,
        "sample_count": 40, "net_after_cost_return": ".04", "max_drawdown": "0.100000000000000001"})
    assert derive(below_return)["tier"] == "QUALIFIED"
    assert derive(above_drawdown)["tier"] == "QUALIFIED"
    negative_underflow = evidence(forward_oos_metrics={"retained_run_sha256": "sha256:" + "a" * 64,
        "sample_count": 40, "net_after_cost_return": ".04", "max_drawdown": "-1e-999"})
    with pytest.raises(HSlowEdgeSizingError):
        derive(negative_underflow)
