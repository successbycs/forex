import pytest

from forex import m20_cost_accounting as accounting


def outcome(**overrides):
    base = {
        "proposal_id": "p-1", "reconciliation_status": "MATCHED", "account_currency": "AUD",
        "gross_price_pnl_account": 1.25, "commission_account": -0.10, "fee_account": -0.05,
        "swap_account": 0.0, "estimated_spread_cost_account": 0.08,
        "slippage_cost_account": 0.03, "estimated_total_cost_account": 0.11,
        "realized_pnl_account": 1.10,
    }
    return {**base, **overrides}


def test_complete_broker_costs_reconcile_without_double_counting_estimates():
    result = accounting.reconcile_broker_outcome(outcome())
    assert result["actual_cost_status"] == "COMPLETE"
    assert result["actual_cost_total_account"] == pytest.approx(-.15)
    assert result["broker_net_from_components_account"] == 1.10
    assert result["broker_arithmetic_status"] == "MATCHED"
    assert result["estimated_execution_costs_account"]["estimated_total_cost_account"] == .11
    assert result["profitability_conclusion"] == "NOT_EVALUATED"
    assert result["execution_authority"] is False


def test_missing_fee_remains_unknown_not_zero():
    result = accounting.reconcile_broker_outcome(outcome(commission_account=None, fee_account=None))
    assert result["actual_cost_status"] == "INCOMPLETE"
    assert result["fee_observation"] == "UNKNOWN"
    assert result["actual_costs_account"] == {"commission_account": None, "fee_account": None, "swap_account": 0.0}
    assert result["actual_cost_total_account"] is None
    assert result["broker_arithmetic_status"] == "UNVERIFIABLE"


def test_summary_counts_observations_without_making_a_profitability_claim():
    result = accounting.summarize_broker_outcomes([
        outcome(proposal_id="zero", commission_account=0, fee_account=0, realized_pnl_account=1.25),
        outcome(proposal_id="nonzero"), outcome(proposal_id="unknown", commission_account=None),
    ])
    assert result["outcome_count"] == 3
    assert result["zero_fee_observation_count"] == 1
    assert result["nonzero_fee_observation_count"] == 1
    assert result["unknown_fee_observation_count"] == 1
    assert result["profitability_conclusion"] == "NOT_EVALUATED"


def test_partial_cost_evidence_preserves_known_amounts_and_rejects_invalid_ones():
    partial = accounting.reconcile_broker_outcome(outcome(commission_account=-.1, fee_account=None, swap_account=-.02))
    assert partial["actual_costs_account"] == {"commission_account": -.1, "fee_account": None, "swap_account": -.02}
    assert partial["actual_cost_total_account"] is None
    with pytest.raises(accounting.AccountingInputError, match="fee_account"):
        accounting.reconcile_broker_outcome(outcome(fee_account=float("nan")))
