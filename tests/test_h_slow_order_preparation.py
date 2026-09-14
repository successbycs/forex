from __future__ import annotations

import copy
import hashlib
import json

import pytest

from forex.h_slow_order_preparation import HSlowOrderPreparationError, prepare_h_slow_order
from forex.event_annotations import event_annotation
from forex.event_quality import qualify_events
from forex.h_slow_decision import attach_event_context
from forex.h_slow_event_eligibility import build_h_slow_event_eligibility
from forex.h_slow_lifecycle import plan_h_slow_lifecycle
from forex.h_slow_edge_sizing import derive_edge_sizing
from tests.test_h_slow_lifecycle import decision, observation, registry
from tests.test_h_slow_decision import DECISION


def primary_context(state="QUALIFIED_CONTEXT_ONLY"):
    sources = {
        "US_CPI": ("bls-monthly-release-calendar", "https://www.bls.gov/schedule/{year}/{month:02d}_sched_list.htm"),
        "US_EMPLOYMENT_SITUATION": ("bls-monthly-release-calendar", "https://www.bls.gov/schedule/{year}/{month:02d}_sched_list.htm"),
        "FOMC_POLICY_DECISION": ("federal-reserve-fomc-calendar", "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm"),
        "ECB_POLICY_DECISION": ("ecb-monetary-policy-calendar", "https://www.ecb.europa.eu/press/calendars/mgcgc/html/index.en.html"),
    }
    families = [{"family_id": family_id, "source_id": source_id, "state": "QUALIFIED_CONTEXT_ONLY",
                 "reason": "RETAINED_COMPLETE_SOURCE_COVERAGE", "qualification_state": "FUTURE_AMENDED_CONTRACT",
                 "limitation": "context only", "receipt": {"source_url": source_url,
                 "captured_at_utc": "2026-08-31T12:00:00Z", "source_sha256": "sha256:" + str(index) * 64,
                 "coverage_status": "COMPLETE"}}
                for index, (family_id, (source_id, source_url)) in enumerate(sources.items(), start=1)]
    body = {"schema_version": "forex.primary-event-context.v1", "context_state": state, "families": families,
            "execution_authority": False, "limitations": ["context only"]}
    return {**body, "context_sha256": "sha256:" + hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()}


def prepared_plan(action="BUY"):
    research_decision = attach_event_context(
        decision(action), event_annotation(
            qualify_events([], DECISION), decision_at_utc=DECISION,
            window_start_utc="2026-08-31T12:00:00Z", window_end_utc="2026-09-02T12:00:00Z",
        ),
    )
    eligibility = build_h_slow_event_eligibility(
        research_decision, primary_context=primary_context(), entry_status="ALLOW",
        policy_version="forex.event-risk.disabled.v1",
    )
    lifecycle_plan = plan_h_slow_lifecycle(
        research_decision=research_decision, reconciliation_observation=observation(), stream_registry=registry(),
    )
    return lifecycle_plan, eligibility, research_decision


def prepare(candidate=None, *, action="BUY", market_inputs=None, bounds=None,
            event_eligibility=None, research_decision=None, primary_event_context=None, edge_result=None):
    lifecycle_plan, default_eligibility, default_decision = prepared_plan(action)
    selected_limits = limits() if bounds is None else bounds
    selected_decision = default_decision if research_decision is None else research_decision
    if edge_result is None:
        try:
            edge_result = edge_sizing_result(
                decision_at_utc=selected_decision["decision_at_utc"],
                research_decision_sha256=lifecycle_plan["decision_sha256"],
                strategy_policy_version=selected_decision["policy_version"],
                hard_max_loss_aud=float(selected_limits["max_loss_aud"]),
            )
        except (TypeError, ValueError, OverflowError):
            edge_result = None
    return prepare_h_slow_order(
        lifecycle_plan if candidate is None else candidate,
        market_inputs=market() if market_inputs is None else market_inputs,
        limits=selected_limits,
        event_eligibility=default_eligibility if event_eligibility is None else event_eligibility,
        research_decision=selected_decision,
        primary_context=primary_context() if primary_event_context is None else primary_event_context,
        edge_sizing_result=edge_result,
    )


def market(**changes) -> dict:
    value = {"server": "GOMarketsMU-Demo", "instrument": "EUR/USD", "observed_at_utc": "2026-09-01T12:00:00Z", "evaluated_at_utc": "2026-09-01T12:00:02Z", "maximum_quote_age_seconds": "5", "bid": "1.10000", "ask": "1.10020",
             "technical_stop_price": "1.09800", "tick_size": "0.0001", "point": "0.0001", "loss_per_tick_aud_per_lot": "10",
             "volume_min_lots": "0.01", "volume_max_lots": "2", "volume_step_lots": "0.01", "notional_usd_per_lot": "100000",
             "margin_aud_per_lot": "1000", "free_margin_aud": "200", "min_stop_distance_points": "10",
             "adverse_cost_allowance_aud_per_lot": "5"}
    value.update(changes)
    return value


def limits(**changes) -> dict:
    value = {"max_loss_aud": "100", "max_notional_usd": "1000", "lease_budget_usd": "1000", "maximum_volume_lots": "1"}
    value.update(changes)
    return value


def edge_sizing_result(*, decision_at_utc=DECISION, research_decision_sha256=None,
                       strategy_policy_version="forex.h-slow.tsmom-12m.v1", hard_max_loss_aud=100):
    def signed(value, field):
        value[field] = "sha256:" + hashlib.sha256(json.dumps(
            {key: item for key, item in value.items() if key != field},
            sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        return value
    policy = signed({"schema_version": "forex.h-slow.edge-sizing-policy.v1", "policy_id": "test-v1",
        "tiers": [{"tier": "BASE", "risk_multiplier": .25, "minimum_sample_count": 10,
                   "minimum_net_after_cost_return": .01, "maximum_drawdown": .2},
                  {"tier": "QUALIFIED", "risk_multiplier": .5, "minimum_sample_count": 20,
                   "minimum_net_after_cost_return": .02, "maximum_drawdown": .15},
                  {"tier": "STRONG", "risk_multiplier": 1.0, "minimum_sample_count": 40,
                   "minimum_net_after_cost_return": .04, "maximum_drawdown": .1}],
        "execution_authority": False}, "policy_sha256")
    evidence = signed({"schema_version": "forex.h-slow.edge-evidence.v1", "evidence_id": "test-oos",
        "decision_at_utc": decision_at_utc, "research_decision_sha256": research_decision_sha256 or "sha256:" + "b" * 64,
        "strategy_policy_version": strategy_policy_version,
        "forward_oos_metrics": {"retained_run_sha256": "sha256:" + "a" * 64,
        "sample_count": 40, "net_after_cost_return": .04, "max_drawdown": .1},
        "execution_authority": False}, "evidence_sha256")
    return derive_edge_sizing(policy, evidence, decision_at_utc=decision_at_utc,
                              research_decision_sha256=evidence["research_decision_sha256"],
                              strategy_policy_version=strategy_policy_version,
                              hard_max_loss_aud=hard_max_loss_aud)


def test_prepares_open_with_cost_once_and_rounds_down_across_caps():
    result = prepare()
    # Notional/lease cap: 1,000 USD / 100,000 USD per lot = 0.01 lot.
    assert result["outcome"] == "PREPARED_DISABLED"
    assert result["volume_lots"] == .01
    assert result["planned_stop_loss_aud"] == 2.2
    assert result["planned_adverse_cost_allowance_aud"] == .05
    assert result["planned_total_loss_aud"] == 2.25
    assert result["executable_stop_price"] == 1.098
    assert result["submission_status"] == "DISABLED_NOT_ROUTED"
    assert result["execution_authority"] is False
    assert result["preparation_input_sha256"].startswith("sha256:")


def test_future_or_other_decision_edge_evidence_cannot_prepare_open():
    lifecycle_plan, eligibility, research_decision = prepared_plan()
    future = edge_sizing_result(
        decision_at_utc="2099-01-01T00:00:00Z",
        research_decision_sha256=lifecycle_plan["decision_sha256"],
        strategy_policy_version=research_decision["policy_version"],
    )
    result = prepare(lifecycle_plan, event_eligibility=eligibility, research_decision=research_decision,
                     edge_result=future)
    assert result["reason"] == "EDGE_SIZING_EVIDENCE_INVALID"


def test_valid_fixed_initial_trial_prepares_without_edge_tiering_and_binds_cap():
    from forex.h_slow_initial_trial import load_initial_trial
    from pathlib import Path
    lifecycle_plan, eligibility, research_decision = prepared_plan()
    trial = load_initial_trial(Path(__file__).parents[1] / "config" / "h_slow_initial_trial.json")
    result = prepare_h_slow_order(lifecycle_plan, market_inputs=market(), limits=limits(max_loss_aud="2000",
        max_notional_usd="20000", lease_budget_usd="200000", maximum_volume_lots="1"),
        event_eligibility=eligibility, research_decision=research_decision, primary_context=primary_context(),
        initial_trial=trial)
    assert result["outcome"] == "PREPARED_DISABLED"
    assert result["edge_sizing_result_sha256"] is None
    assert result["initial_trial_sha256"].startswith("sha256:")
    assert result["planned_notional_usd"] <= 10000


def test_invalid_or_dynamic_fixed_trial_cannot_bypass_edge_requirement():
    lifecycle_plan, eligibility, research_decision = prepared_plan()
    bad = {"bad": True}
    result = prepare_h_slow_order(lifecycle_plan, market_inputs=market(), limits=limits(),
        event_eligibility=eligibility, research_decision=research_decision, primary_context=primary_context(),
        initial_trial=bad)
    assert result["reason"] == "INITIAL_TRIAL_INVALID"


def test_refuses_when_minimum_lot_exceeds_loss_margin_or_notional_capacity():
    result = prepare(market_inputs=market(free_margin_aud="5"))
    assert result["outcome"] == "REFUSED"
    assert result["reason"] == "MINIMUM_VOLUME_EXCEEDS_DECLARED_CAPACITY"


def test_margin_and_loss_caps_reduce_volume_and_step_rounds_down():
    result = prepare(market_inputs=market(notional_usd_per_lot="1000", free_margin_aud="39", margin_aud_per_lot="1000"), bounds=limits(max_notional_usd="1000", lease_budget_usd="1000", max_loss_aud="1000"))
    assert result["volume_lots"] == .03
    assert result["planned_margin_aud"] == 30.0


@pytest.mark.parametrize(("direction", "stop", "reason"), [("BUY", "1.10000", "TECHNICAL_STOP"), ("SELL", "1.10020", "TECHNICAL_STOP")])
def test_refuses_stop_on_wrong_executable_side(direction, stop, reason):
    candidate, eligibility, research_decision = prepared_plan(direction)
    result = prepare(candidate, market_inputs=market(technical_stop_price=stop), event_eligibility=eligibility, research_decision=research_decision)
    assert result["outcome"] == "REFUSED"
    assert reason in result["reason"]


def test_non_open_plan_never_prepares_entry():
    candidate, eligibility, research_decision = prepared_plan("NO_TRADE")
    result = prepare(candidate, event_eligibility=eligibility, research_decision=research_decision)
    assert result["outcome"] == "REFUSED"
    assert result["reason"] == "LIFECYCLE_PLAN_IS_NOT_OPEN"


def test_refuses_stale_quote_without_an_implicit_freshness_default():
    with pytest.raises(HSlowOrderPreparationError, match="stale"):
        prepare(market_inputs=market(observed_at_utc="2026-09-01T11:59:00Z"))


@pytest.mark.parametrize(("where", "key", "value"), [("market", "adverse_cost_allowance_aud_per_lot", "UNKNOWN"), ("market", "bid", True), ("market", "ask", float("nan")), ("limits", "max_loss_aud", "Infinity")])
def test_refuses_unknown_or_nonfinite_metadata(where, key, value):
    inputs, bounds = market(), limits()
    (inputs if where == "market" else bounds)[key] = value
    with pytest.raises(HSlowOrderPreparationError):
        prepare(market_inputs=inputs, bounds=bounds)


@pytest.mark.parametrize(("direction", "stop"), [("BUY", "1.09800"), ("SELL", "1.10220")])
def test_entry_spread_loss_prevents_minimum_lot_exceeding_budget(direction, stop):
    result = prepare(action=direction, market_inputs=market(technical_stop_price=stop), bounds=limits(max_loss_aud="2.1"))
    assert result["outcome"] == "REFUSED"


def test_refuses_live_source_and_mismatched_action_id():
    with pytest.raises(HSlowOrderPreparationError, match="GOMarketsMU-Demo"):
        prepare(market_inputs=market(server="GOMarketsMU-Live"))
    candidate, eligibility, research_decision = prepared_plan()
    candidate["intent"]["action_id"] = "sha256:" + "0" * 64
    with pytest.raises(HSlowOrderPreparationError, match="action ID"):
        prepare(candidate, event_eligibility=eligibility, research_decision=research_decision)


@pytest.mark.parametrize(("inputs", "bounds"), [
    (market(), limits(max_notional_usd="999.999999999999999999999999999")),
    (market(ask="1e1000000"), limits()),
    (market(volume_min_lots="1e-400", volume_step_lots="1e-400"), limits(maximum_volume_lots="1e-400")),
])
def test_unsupported_numeric_range_and_precision_refuse_cleanly(inputs, bounds):
    with pytest.raises(HSlowOrderPreparationError, match="supported numeric"):
        prepare(market_inputs=inputs, bounds=bounds)


def test_just_below_minimum_notional_cap_does_not_round_up():
    result = prepare(bounds=limits(max_notional_usd="999.999999999999999"))
    assert result["outcome"] == "REFUSED"


def test_output_rounding_cannot_exceed_volume_cap_or_leave_step_grid():
    value = "0.123456789012345678"
    with pytest.raises(HSlowOrderPreparationError, match="round-trip"):
        prepare(market_inputs=market(
            volume_step_lots=value, notional_usd_per_lot="1000", free_margin_aud="1000"),
            bounds=limits(maximum_volume_lots=value))


@pytest.mark.parametrize(("coverage", "reason"), [
    ("UNKNOWN", "EVENT_CONTEXT_UNKNOWN"), ("PARTIAL", "EVENT_CONTEXT_PARTIAL"),
    ("AMBIGUOUS", "EVENT_CONTEXT_AMBIGUOUS"), ("UNAVAILABLE", "EVENT_CONTEXT_UNAVAILABLE"),
])
def test_open_preparation_refuses_nonclear_event_context(coverage, reason):
    _, eligibility, research_decision = prepared_plan()
    assert prepare(event_eligibility=eligibility, research_decision=research_decision,
                   primary_event_context=primary_context(coverage))["reason"] == reason


def test_open_preparation_refuses_missing_nonclear_or_mismatched_event_binding():
    lifecycle_plan, eligibility, research_decision = prepared_plan()
    assert prepare_h_slow_order(lifecycle_plan, market_inputs=market(), limits=limits())["reason"] == "EVENT_CONTEXT_UNAVAILABLE"
    not_allowed = build_h_slow_event_eligibility(
        research_decision, primary_context=primary_context(), entry_status="NO_NEW_ENTRY",
        policy_version="forex.event-risk.disabled.v1",
    )
    assert prepare(event_eligibility=not_allowed, research_decision=research_decision)["reason"] == "EVENT_NEW_ENTRY_NOT_ALLOWED"
    invalid = dict(eligibility)
    invalid["eligibility_sha256"] = "sha256:" + "0" * 64
    assert prepare(event_eligibility=invalid, research_decision=research_decision)["reason"] == "EVENT_CONTEXT_INVALID"
    mismatched = dict(eligibility)
    mismatched["qualified_result_sha256"] = "sha256:" + "0" * 64
    content = {key: mismatched[key] for key in mismatched if key != "eligibility_sha256"}
    mismatched["eligibility_sha256"] = "sha256:" + hashlib.sha256(json.dumps(content, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    assert prepare(event_eligibility=mismatched, research_decision=research_decision)["reason"] == "EVENT_CONTEXT_SOURCE_MISMATCH"


def test_current_primary_context_unavailable_and_forged_coverage_label_cannot_prepare_open():
    from forex.primary_event_context import load_contract, qualify_context
    from pathlib import Path
    lifecycle_plan, eligibility, research_decision = prepared_plan()
    current = qualify_context(contract=load_contract(Path(__file__).resolve().parents[1] / "config/primary_event_context.json"), observations=[])
    assert current["context_state"] == "UNAVAILABLE"
    assert prepare(lifecycle_plan, event_eligibility=eligibility, research_decision=research_decision,
                   primary_event_context=current)["reason"] == "EVENT_CONTEXT_UNAVAILABLE"
    forged = dict(eligibility)
    forged["source_coverage_state"] = "QUALIFIED_COMPLETE"
    assert prepare(lifecycle_plan, event_eligibility=forged, research_decision=research_decision)["reason"] == "EVENT_CONTEXT_INVALID"
