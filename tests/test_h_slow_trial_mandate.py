from __future__ import annotations

import copy

import pytest

from forex.h_slow_trial_mandate import HSlowMandateError, validate_h_slow_trial_mandate


def registry() -> dict:
    return {
        "schema_version": "forex.stream-isolation.v1",
        "streams": [
            {"stream_id": "M1", "server": "GOMarketsMU-Demo", "account_scope": "demo_scope_m1", "terminal_instance": "terminal_m1", "namespaces": {"state_namespace": "state_m1", "monitor_namespace": "monitor_m1", "lease_namespace": "lease_m1", "reservation_namespace": "reservation_m1", "outcome_namespace": "outcome_m1"}, "deployment_state": "RETAINED_EXISTING_OPERATION", "account_selection": "NOT_SELECTED", "execution_capability": "NOT_EXPOSED"},
            {"stream_id": "H_SLOW", "server": "GOMarketsMU-Demo", "account_scope": "demo_scope_hslow", "terminal_instance": "terminal_hslow", "namespaces": {"state_namespace": "state_hslow", "monitor_namespace": "monitor_hslow", "lease_namespace": "lease_hslow", "reservation_namespace": "reservation_hslow", "outcome_namespace": "outcome_hslow"}, "deployment_state": "NOT_DEPLOYED", "account_selection": "NOT_SELECTED", "execution_capability": "NOT_EXPOSED"},
        ],
    }


def mandate() -> dict:
    return {
        "schema_version": "forex.h-slow.demo-trial-mandate.v1", "state": "PRE_ACTIVATION_REVIEWED",
        "server": "GOMarketsMU-Demo", "account_scope": "demo_scope_hslow", "terminal_instance": "terminal_hslow",
        "policy_version": "forex.h-slow.eurusd-tsmom-12m.v1", "operator_approval_reference": "approval_hslow_trial",
        "risk_resume_authority_reference": "risk_resume_hslow_operator",
        "limits": {"max_open_positions": 1, "max_loss_aud": 10.0, "max_notional_usd": 1000.0, "lease_budget_usd": 1000.0},
        "rule_references": {"sizing": "sizing_v1", "protection": "protection_v1", "holding_exit": "holding_exit_v1", "financing_cost": "financing_v1", "reconciliation": "reconciliation_v1"},
    }


def test_validates_completed_mandate_without_execution_authority():
    result = validate_h_slow_trial_mandate(mandate(), stream_registry=registry())
    assert result["preflight_status"] == "PRE_ACTIVATION_MANDATE_VALIDATED"
    assert result["mandate_sha256"].startswith("sha256:")
    assert result["execution_authority"] is False


@pytest.mark.parametrize(("path", "value", "message"), [
    (("state",), "ACTIVE", "PRE_ACTIVATION_REVIEWED"),
    (("server",), "GOMarketsMU-Live", "GOMarketsMU-Demo"),
    (("limits", "max_open_positions"), 2, "one position"),
    (("limits", "max_open_positions"), True, "one position"),
    (("limits", "max_open_positions"), 1.0, "one position"),
    (("account_scope",), "other_demo_scope", "does not match"),
    (("risk_resume_authority_reference",), "99", "opaque identifier"),
])
def test_rejects_activation_live_risk_expansion_and_scope_drift(path, value, message):
    candidate = mandate()
    target = candidate
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    with pytest.raises(HSlowMandateError, match=message):
        validate_h_slow_trial_mandate(candidate, stream_registry=registry())


def test_mandate_hash_changes_when_human_owned_terms_change():
    first = validate_h_slow_trial_mandate(mandate(), stream_registry=registry())
    changed = mandate()
    changed["limits"]["max_loss_aud"] = 11.0
    second = validate_h_slow_trial_mandate(changed, stream_registry=registry())
    assert first["mandate_sha256"] != second["mandate_sha256"]


def test_rejects_injected_account_or_order_authority_field():
    candidate = mandate()
    candidate["mt5_login"] = "not-an-authority"
    with pytest.raises(HSlowMandateError, match="fields are invalid"):
        validate_h_slow_trial_mandate(candidate, stream_registry=registry())
