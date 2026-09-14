from __future__ import annotations

import copy

import pytest

from forex.h_slow_lifecycle import HSlowLifecycleError, plan_h_slow_lifecycle
from forex.h_slow_decision import evaluate_h_slow_snapshot
from tests.test_h_slow_decision import monthly_snapshot, DECISION


def registry() -> dict:
    return {
        "schema_version": "forex.stream-isolation.v1",
        "streams": [
            {"stream_id": "M1", "server": "GOMarketsMU-Demo", "account_scope": "demo_scope_m1", "terminal_instance": "terminal_m1", "namespaces": {"state_namespace": "state_m1", "monitor_namespace": "monitor_m1", "lease_namespace": "lease_m1", "reservation_namespace": "reservation_m1", "outcome_namespace": "outcome_m1"}, "deployment_state": "RETAINED_EXISTING_OPERATION", "account_selection": "NOT_SELECTED", "execution_capability": "NOT_EXPOSED"},
            {"stream_id": "H_SLOW", "server": "GOMarketsMU-Demo", "account_scope": "demo_scope_hslow", "terminal_instance": "terminal_hslow", "namespaces": {"state_namespace": "state_hslow", "monitor_namespace": "monitor_hslow", "lease_namespace": "lease_hslow", "reservation_namespace": "reservation_hslow", "outcome_namespace": "outcome_hslow"}, "deployment_state": "NOT_DEPLOYED", "account_selection": "NOT_SELECTED", "execution_capability": "NOT_EXPOSED"},
        ],
    }


def observation(*, status="RECONCILED", positions=None, attempts=None) -> dict:
    return {"schema_version": "forex.h-slow.lifecycle-observation.v1", "stream_id": "H_SLOW",
            "account_scope": "demo_scope_hslow", "terminal_instance": "terminal_hslow",
            "reconciliation_status": status, "positions": positions or [], "pending_attempts": attempts or []}


def decision(action="BUY") -> dict:
    value = evaluate_h_slow_snapshot(monthly_snapshot(), decision_at_utc=DECISION)
    if action == "BUY":
        return value
    # Make a separately hash-verified fixture for the alternate directions.
    value["target"]["action"] = action
    import hashlib, json
    content = {key: value[key] for key in ("decision_schema_version", "policy_version", "snapshot_id", "snapshot_artifact_sha256", "policy_input_sha256", "decision_at_utc", "target", "event_annotation_status")}
    value["decision_sha256"] = "sha256:" + hashlib.sha256(json.dumps(content, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return value


def plan(action="BUY", **kwargs) -> dict:
    return plan_h_slow_lifecycle(research_decision=decision(action), reconciliation_observation=observation(**kwargs), stream_registry=registry())


def mandate() -> dict:
    return {
        "schema_version": "forex.h-slow.demo-trial-mandate.v1", "state": "PRE_ACTIVATION_REVIEWED",
        "server": "GOMarketsMU-Demo", "account_scope": "demo_scope_hslow", "terminal_instance": "terminal_hslow",
        "policy_version": "forex.h-slow.eurusd-tsmom-12m.v1", "operator_approval_reference": "approval_hslow_trial",
        "risk_resume_authority_reference": "risk_resume_hslow_operator",
        "limits": {"max_open_positions": 1, "max_loss_aud": 10.0, "max_notional_usd": 1000.0, "lease_budget_usd": 1000.0},
        "rule_references": {"sizing": "sizing_v1", "protection": "protection_v1", "holding_exit": "holding_exit_v1", "financing_cost": "financing_v1", "reconciliation": "reconciliation_v1"},
    }


def test_flat_verified_target_is_an_entry_plan_but_never_execution_authority():
    result = plan()
    assert result["lifecycle_state"] == "ENTRY_ELIGIBLE"
    assert result["next_action"] == "OPEN"
    assert result["intent"]["direction"] == "BUY"
    assert result["execution_authority"] is False


def test_planned_intent_identity_is_bound_to_account_isolation():
    original = plan()
    changed = registry()
    changed["streams"][1]["account_scope"] = "demo_scope_alternate"
    observed = observation()
    observed["account_scope"] = "demo_scope_alternate"
    alternate = plan_h_slow_lifecycle(research_decision=decision(),
        reconciliation_observation=observed, stream_registry=changed)
    assert original["intent"]["action_id"] != alternate["intent"]["action_id"]


def test_pre_activation_mandate_can_bind_planning_but_not_authorise_execution():
    result = plan_h_slow_lifecycle(
        research_decision=decision(), reconciliation_observation=observation(), stream_registry=registry(),
        trial_mandate=mandate(),
    )
    assert result["mandate_preflight_status"] == "PRE_ACTIVATION_MANDATE_VALIDATED"
    assert result["execution_authority"] is False


def test_same_direction_position_holds_without_reentry():
    result = plan(positions=[{"ticket_id": "ticket_hslow_1", "owner_stream_id": "H_SLOW", "direction": "BUY", "position_status": "OPEN"}])
    assert result["lifecycle_state"] == "HOLDING"
    assert result["next_action"] == "NONE"


def test_opposite_direction_is_close_first_then_open_only_after_confirmed_absence():
    position = {"ticket_id": "ticket_hslow_1", "owner_stream_id": "H_SLOW", "direction": "BUY", "position_status": "OPEN"}
    close = plan("SELL", positions=[position])
    assert close["lifecycle_state"] == "CLOSE_REQUIRED"
    assert close["next_action"] == "CLOSE"
    assert close["intent"]["ticket_id"] == "ticket_hslow_1"
    pending = plan("SELL", positions=[position], attempts=[{"attempt_id": "close_hslow_1", "kind": "CLOSE", "status": "PENDING", "ticket_id": "ticket_hslow_1"}])
    assert pending["lifecycle_state"] == "AWAITING_RECONCILIATION"
    reopened = plan("SELL")
    assert reopened["next_action"] == "OPEN"
    assert reopened["intent"]["direction"] == "SELL"


def test_no_trade_closes_existing_position_but_is_flat_when_reconciled_absent():
    position = {"ticket_id": "ticket_hslow_1", "owner_stream_id": "H_SLOW", "direction": "BUY", "position_status": "OPEN"}
    assert plan("NO_TRADE", positions=[position])["next_action"] == "CLOSE"
    assert plan("NO_TRADE")["lifecycle_state"] == "FLAT"


def test_restart_unknown_and_unresolved_attempts_fail_closed_and_prevent_duplicates():
    unknown = plan(status="UNKNOWN")
    assert unknown["lifecycle_state"] == "AWAITING_RECONCILIATION"
    pending = plan(attempts=[{"attempt_id": "open_hslow_1", "kind": "OPEN", "status": "UNKNOWN", "ticket_id": None}])
    assert pending["next_action"] == "WAIT"
    first = plan()
    assert first == plan()  # deterministic re-planning until intent is persisted/reconciled


def test_foreign_ticket_is_never_named_or_modified_by_hslow_plan():
    result = plan(positions=[{"ticket_id": "ticket_m1_1", "owner_stream_id": "M1", "direction": "BUY", "position_status": "OPEN"}])
    assert result["lifecycle_state"] == "FOREIGN_OWNERSHIP_BLOCKED"
    assert result["next_action"] == "WAIT"
    assert result["intent"] is None


def test_rejects_scope_drift_tampered_decision_and_duplicate_observed_ticket():
    bad = observation()
    bad["account_scope"] = "other_scope"
    with pytest.raises(HSlowLifecycleError, match="scope"):
        plan_h_slow_lifecycle(research_decision=decision(), reconciliation_observation=bad, stream_registry=registry())
    tampered = decision()
    tampered["target"]["action"] = "SELL"
    with pytest.raises(HSlowLifecycleError, match="verified"):
        plan_h_slow_lifecycle(research_decision=tampered, reconciliation_observation=observation(), stream_registry=registry())
    duplicate = {"ticket_id": "ticket_hslow_1", "owner_stream_id": "H_SLOW", "direction": "BUY", "position_status": "OPEN"}
    with pytest.raises(HSlowLifecycleError, match="duplicate position ticket"):
        plan(positions=[duplicate, copy.deepcopy(duplicate)])
