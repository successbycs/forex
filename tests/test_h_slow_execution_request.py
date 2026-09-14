import copy
from decimal import localcontext
from pathlib import Path

import pytest

from forex.h_slow_execution_request import HSlowExecutionRequestError, build_execution_request
from forex.h_slow_initial_trial import load_initial_trial
from forex.h_slow_order_preparation import prepare_h_slow_order
from tests.test_h_slow_order_preparation import limits, market, prepared_plan, primary_context


TRIAL = load_initial_trial(Path(__file__).parents[1] / "config" / "h_slow_initial_trial.json")


def preparation():
    plan, eligibility, decision = prepared_plan()
    result = prepare_h_slow_order(
        plan, market_inputs=market(), limits=limits(max_loss_aud="2000", max_notional_usd="20000",
        lease_budget_usd="200000", maximum_volume_lots="1"), event_eligibility=eligibility,
        research_decision=decision, primary_context=primary_context(), initial_trial=TRIAL,
    )
    assert result["outcome"] == "PREPARED_DISABLED"
    return result


def broker_preflight(prepared: dict, *, open_positions: int = 0, offset: int = 0) -> dict:
    entry = prepared["entry_price"]
    bid, ask = (entry - .0002, entry) if prepared["direction"] == "BUY" else (entry, entry + .0002)
    return {
        "ok": True, "status": "PREFLIGHT_OK", "captured_at_utc": "2026-09-13T00:00:00Z",
        "account_label": "H1_demo", "account_scope_sha256": "sha256:" + "a" * 64,
        "server": "GOMarketsMU-Demo", "currency": "AUD", "symbol": "EURUSD",
        "bid": bid, "ask": ask, "tick_time_msc": 1789257600000 + offset * 1000,
        "broker_timestamp_offset_seconds": offset, "tick_age_seconds": 0,
        "open_positions": open_positions,
        "symbol_specification": {
            "name": "EURUSD", "point": .00001, "trade_tick_size": .00001,
            "trade_tick_value_loss": 1., "trade_contract_size": 100000.,
            "volume_min": .01, "volume_max": 1., "volume_step": .01,
            "trade_stops_level": 0, "trade_freeze_level": 0,
        },
    }


def build(prepared: dict, *, trial: dict = TRIAL, preflight: dict | None = None, offset: int = 0):
    return build_execution_request(
        initial_trial=trial, preparation=prepared,
        broker_preflight=broker_preflight(prepared) if preflight is None else preflight,
        expected_broker_timestamp_offset_seconds=offset,
    )


def test_real_fixed_trial_preparation_builds_disabled_bound_envelope():
    request = build(preparation())
    assert request["server"] == "GOMarketsMU-Demo"
    assert request["instrument"] == "EUR/USD"
    assert request["execution_authority"] is False
    assert request["submission_status"] == "DISABLED_NOT_ROUTED"
    assert request["request_sha256"].startswith("sha256:")
    assert request["broker_preflight_receipt_sha256"].startswith("sha256:")


@pytest.mark.parametrize("field,value", [
    ("edge_sizing_result_sha256", "sha256:" + "a" * 64),
    ("initial_trial_sha256", "sha256:" + "a" * 64),
    ("plan_sha256", "sha256:not-a-digest"),
    ("volume_lots", float("nan")),
    ("planned_notional_usd", 100001.0),
    ("schema_version", "wrong"),
    ("lifecycle_action_id", None),
    ("planned_adverse_cost_allowance_aud", -1.0),
    ("planned_total_loss_aud", .01),
])
def test_invalid_provenance_or_cap_cannot_build_request(field, value):
    candidate = copy.deepcopy(preparation())
    candidate[field] = value
    with pytest.raises(HSlowExecutionRequestError):
        build(candidate)


def test_directional_stop_and_total_loss_components_cannot_be_forged():
    candidate = preparation()
    candidate["executable_stop_price"] = 100.0
    with pytest.raises(HSlowExecutionRequestError, match="wrong executable side"):
        build(candidate)


def test_total_loss_check_uses_private_decimal_precision():
    candidate = preparation()
    candidate["planned_stop_loss_aud"] = .11
    candidate["planned_adverse_cost_allowance_aud"] = .01
    candidate["planned_total_loss_aud"] = .1
    with localcontext() as hostile_context:
        hostile_context.prec = 1
        with pytest.raises(HSlowExecutionRequestError, match="total loss"):
            build(candidate)


def test_unbounded_synthetic_numeric_values_are_rejected():
    candidate = preparation()
    candidate["planned_stop_loss_aud"] = 1e-60
    candidate["planned_adverse_cost_allowance_aud"] = 1e-60
    candidate["planned_total_loss_aud"] = 2e-60
    with pytest.raises(HSlowExecutionRequestError, match="precision or magnitude"):
        build(candidate)
    candidate = preparation()
    candidate["planned_total_loss_aud"] = candidate["planned_stop_loss_aud"]
    with pytest.raises(HSlowExecutionRequestError, match="total loss"):
        build(candidate)


def test_wrong_trial_and_nonprepared_or_extra_record_refuse():
    candidate = preparation()
    wrong_trial = {**TRIAL, "account_label": "other"}
    with pytest.raises(HSlowExecutionRequestError):
        build(candidate, trial=wrong_trial)
    candidate["outcome"] = "REFUSED"
    with pytest.raises(HSlowExecutionRequestError):
        build(candidate)
    candidate = preparation()
    candidate["edge_tier"] = "STRONG"
    with pytest.raises(HSlowExecutionRequestError):
        build(candidate)


def test_broker_preflight_must_be_flat_quote_matched_and_executable_volume():
    candidate = preparation()
    with pytest.raises(HSlowExecutionRequestError, match="not flat"):
        build(candidate, preflight=broker_preflight(candidate, open_positions=1))
    wrong_quote = broker_preflight(candidate)
    wrong_quote["ask"] += .00001
    with pytest.raises(HSlowExecutionRequestError, match="entry price"):
        build(candidate, preflight=wrong_quote)
    invalid_volume = broker_preflight(candidate)
    invalid_volume["symbol_specification"]["volume_min"] = .02
    with pytest.raises(HSlowExecutionRequestError):
        build(candidate, preflight=invalid_volume)
    shifted_offset = broker_preflight(candidate, offset=10800)
    with pytest.raises(HSlowExecutionRequestError, match="broker preflight"):
        build(candidate, preflight=shifted_offset)


def test_preflight_volume_lattice_uses_private_decimal_precision():
    with localcontext() as hostile_context:
        hostile_context.prec = 1
        assert build(preparation())["submission_status"] == "DISABLED_NOT_ROUTED"
