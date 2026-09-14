from __future__ import annotations

import copy

import pytest

from forex.h_slow_execution_semantics import HSlowExecutionSemanticsError, validate_h_slow_execution_semantics


def proposal():
    return {
        "schema_version": "forex.h-slow.execution-semantics-proposal.v1", "state": "DRAFT_NOT_ACTIVE",
        "stream_id": "H_SLOW", "server": "GOMarketsMU-Demo", "instrument": "EUR/USD",
        "policy_version": "forex.h-slow.eurusd-tsmom-12m.v1",
        "decision_clock": {"cadence": "MONTHLY", "decision_at": "FIRST_UTC_DAY", "completed_data_only": True},
        "entry_lifecycle": {"flat_directional_target": "OPEN_ONCE_ONLY", "unchanged_target": "HOLD_NO_NEW_ORDER", "opposite_target": "CLOSE_FIRST_NEXT_MONTH_OPEN_ONLY"},
        "protection": {"initial_stop": "ATR20X3_BROKER_SIDE", "widening": "PROHIBITED", "trailing": "PROHIBITED", "take_profit": "NONE"},
        "holding": {"end_date": "NONE", "ongoing_hold_requires": "BROKER_PROTECTION_AND_RECONCILIATION_HEALTHY", "overnight_weekend": "OBSERVED_TERMS_AND_PRE_POST_RECONCILIATION", "unknown_terms": "NO_NEW_ENTRY"},
        "costs": {"unknown_terms": "NO_NEW_ENTRY", "zero_assumption": "PROHIBITED"},
        "event_context": {"mode": "ANNOTATION_ONLY", "direction_or_entry_authority": "PROHIBITED"},
        "risk_caps": {"max_open_positions": 1, "cap_expansion": "PROHIBITED"}, "execution_authority": False,
    }


def test_fixed_inactive_demo_proposal_returns_deterministic_non_authorising_report():
    first = validate_h_slow_execution_semantics(proposal())
    assert first == validate_h_slow_execution_semantics(proposal())
    assert first["validation_state"] == "VALID_DRAFT_NOT_ACTIVE"
    assert first["execution_authority"] is False
    assert first["proposal_sha256"].startswith("sha256:")


@pytest.mark.parametrize("mutate", [
    lambda value: value.update(state="ACTIVE"),
    lambda value: value.update(server="GOMarketsMU-Live"),
    lambda value: value.update(stream_id="M1"),
    lambda value: value.update(instrument="GBP/USD"),
    lambda value: value.update(policy_version="other"),
    lambda value: value["decision_clock"].update(decision_at="ANY_TIME"),
    lambda value: value["entry_lifecycle"].update(opposite_target="OPEN_IMMEDIATELY"),
    lambda value: value["protection"].update(widening="ALLOWED"),
    lambda value: value["protection"].update(take_profit="FIXED"),
    lambda value: value["holding"].update(unknown_terms="HOLD"),
    lambda value: value["costs"].update(zero_assumption="ALLOWED"),
    lambda value: value["event_context"].update(mode="ENTRY_GATE"),
    lambda value: value["risk_caps"].update(max_open_positions=2),
    lambda value: value.update(execution_authority=True),
    lambda value: value.update(route="generic-shell-command"),
])
def test_refuses_active_live_route_authority_or_any_fixed_rule_mutation(mutate):
    invalid = copy.deepcopy(proposal())
    mutate(invalid)
    with pytest.raises(HSlowExecutionSemanticsError):
        validate_h_slow_execution_semantics(invalid)


def test_refuses_missing_nested_rule_or_nonfinite_proposal():
    invalid = proposal()
    del invalid["holding"]["unknown_terms"]
    with pytest.raises(HSlowExecutionSemanticsError):
        validate_h_slow_execution_semantics(invalid)


@pytest.mark.parametrize("mutate", [
    lambda value: value.update(execution_authority=0),
    lambda value: value["risk_caps"].update(max_open_positions=True),
    lambda value: value["decision_clock"].update(completed_data_only=1),
])
def test_refuses_python_bool_integer_equality_bypasses(mutate):
    invalid = proposal()
    mutate(invalid)
    with pytest.raises(HSlowExecutionSemanticsError):
        validate_h_slow_execution_semantics(invalid)
    invalid = proposal()
    invalid["risk_caps"]["max_open_positions"] = float("nan")
    with pytest.raises(HSlowExecutionSemanticsError):
        validate_h_slow_execution_semantics(invalid)
