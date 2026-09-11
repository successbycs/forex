"""Pure reconciliation of retained M20 broker outcome amounts.

This module classifies evidence only. It neither estimates missing broker fees nor
makes an execution or profitability decision.
"""
from __future__ import annotations

import math
from typing import Any

ACCOUNTING_VERSION = "forex.m20.broker-cost-accounting.v1"
ACTUAL_COST_FIELDS = ("commission_account", "fee_account", "swap_account")
ESTIMATED_COST_FIELDS = ("estimated_spread_cost_account", "slippage_cost_account", "estimated_total_cost_account")
ARITHMETIC_ABS_TOLERANCE_ACCOUNT = .005


class AccountingInputError(ValueError):
    pass


def _amount(value: Any, field: str) -> float:
    if isinstance(value, bool):
        raise AccountingInputError(f"{field} must be numeric")
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise AccountingInputError(f"{field} must be numeric") from exc
    if not math.isfinite(result):
        raise AccountingInputError(f"{field} must be finite")
    return result


def reconcile_broker_outcome(outcome: dict[str, Any]) -> dict[str, Any]:
    """Return a transparent cost-completeness classification for one outcome."""
    if not isinstance(outcome, dict) or outcome.get("reconciliation_status") != "MATCHED":
        raise AccountingInputError("a matched broker outcome is required")
    if outcome.get("account_currency") != "AUD":
        raise AccountingInputError("M20 outcome currency must be AUD")
    actual_missing = [field for field in ACTUAL_COST_FIELDS if outcome.get(field) is None]
    gross = _amount(outcome.get("gross_price_pnl_account"), "gross_price_pnl_account")
    realized = _amount(outcome.get("realized_pnl_account"), "realized_pnl_account")
    actual = {field: None if outcome.get(field) is None else _amount(outcome[field], field) for field in ACTUAL_COST_FIELDS}
    estimates_missing = [field for field in ESTIMATED_COST_FIELDS if outcome.get(field) is None]
    estimates = {field: None if outcome.get(field) is None else _amount(outcome[field], field) for field in ESTIMATED_COST_FIELDS}
    broker_net_from_components = None if actual_missing else gross + sum(actual.values())
    arithmetic_status = "UNVERIFIABLE" if actual_missing else ("MATCHED" if math.isclose(realized, broker_net_from_components, rel_tol=0.0, abs_tol=ARITHMETIC_ABS_TOLERANCE_ACCOUNT) else "MISMATCH")
    return {
        "accounting_version": ACCOUNTING_VERSION,
        "outcome_id": outcome.get("proposal_id"),
        "actual_cost_status": "INCOMPLETE" if actual_missing else "COMPLETE",
        "missing_actual_cost_fields": actual_missing,
        "actual_costs_account": actual,
        "actual_cost_total_account": None if actual_missing else sum(actual.values()),
        "gross_price_pnl_account": gross,
        "broker_net_from_components_account": broker_net_from_components,
        "broker_realized_pnl_account": realized,
        "broker_arithmetic_abs_tolerance_account": ARITHMETIC_ABS_TOLERANCE_ACCOUNT,
        "broker_arithmetic_status": arithmetic_status,
        "estimated_cost_status": "INCOMPLETE" if estimates_missing else "COMPLETE",
        "missing_estimated_cost_fields": estimates_missing,
        "estimated_execution_costs_account": estimates,
        "fee_observation": "UNKNOWN" if actual_missing else ("NONZERO" if any(actual[field] != 0 for field in ("commission_account", "fee_account")) else "ZERO"),
        "profitability_conclusion": "NOT_EVALUATED",
        "execution_authority": False,
    }


def summarize_broker_outcomes(outcomes: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate evidence coverage while preserving missing values as missing."""
    if not isinstance(outcomes, list):
        raise AccountingInputError("outcomes must be a list")
    results = [reconcile_broker_outcome(outcome) for outcome in outcomes]
    return {
        "accounting_version": ACCOUNTING_VERSION,
        "outcome_count": len(results),
        "complete_actual_cost_count": sum(item["actual_cost_status"] == "COMPLETE" for item in results),
        "nonzero_fee_observation_count": sum(item["fee_observation"] == "NONZERO" for item in results),
        "zero_fee_observation_count": sum(item["fee_observation"] == "ZERO" for item in results),
        "unknown_fee_observation_count": sum(item["fee_observation"] == "UNKNOWN" for item in results),
        "broker_arithmetic_mismatch_count": sum(item["broker_arithmetic_status"] == "MISMATCH" for item in results),
        "profitability_conclusion": "NOT_EVALUATED",
        "execution_authority": False,
        "records": results,
    }
