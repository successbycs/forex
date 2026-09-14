"""Pure, submission-disabled preparation of a bounded H_SLOW OPEN intent.

Closed input schemas intentionally require caller-declared Demo EUR/USD market
metadata.  ``market_inputs`` has: ``server``, ``instrument``, ``observed_at_utc``,
``evaluated_at_utc``, ``maximum_quote_age_seconds``, ``bid``, ``ask``,
``technical_stop_price``, ``tick_size``, ``point``,
``loss_per_tick_aud_per_lot``, ``volume_min_lots``, ``volume_max_lots``,
``volume_step_lots``, ``notional_usd_per_lot``, ``margin_aud_per_lot``,
``free_margin_aud``, ``min_stop_distance_points``, and
``adverse_cost_allowance_aud_per_lot``.  The last field is the total labelled
financing, fee, and slippage allowance; unknown costs must not be encoded as
zero. ``limits`` has ``max_loss_aud``, ``max_notional_usd``,
``lease_budget_usd``, and ``maximum_volume_lots``.  Directional ``OPEN``
preparation also requires a retained H_SLOW research decision, a closed,
digest-bound event-eligibility record, and a hash-valid primary-event context
report. Missing, incomplete, ambiguous or non-ALLOW context returns a refusal;
this is not an event-policy implementation or an execution authority.

This module neither verifies a broker observation nor creates routing or order
authority.  It only performs deterministic arithmetic over declared values.
Inputs support at most 18 significant digits and nonzero values from 1e-12
through 1e12; calculations use a private 128-digit context and final cap checks.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, ROUND_CEILING, ROUND_DOWN, ROUND_FLOOR, InvalidOperation, DecimalException, localcontext
import hashlib
import json
from math import isfinite
from typing import Any, Mapping

from .h_slow_event_eligibility import validate_h_slow_event_eligibility
from .h_slow_edge_sizing import HSlowEdgeSizingError, validate_edge_sizing_result
from .h_slow_initial_trial import HSlowInitialTrialError, validate_initial_trial


ORDER_PREPARATION_SCHEMA_VERSION = "forex.h-slow.order-preparation.v1"
_MARKET_FIELDS = {
    "server", "instrument", "observed_at_utc", "evaluated_at_utc", "maximum_quote_age_seconds", "bid", "ask", "technical_stop_price", "tick_size", "point",
    "loss_per_tick_aud_per_lot", "volume_min_lots", "volume_max_lots", "volume_step_lots",
    "notional_usd_per_lot", "margin_aud_per_lot", "free_margin_aud", "min_stop_distance_points",
    "adverse_cost_allowance_aud_per_lot",
}
_LIMIT_FIELDS = {"max_loss_aud", "max_notional_usd", "lease_budget_usd", "maximum_volume_lots"}
_PLAN_FIELDS = {"schema_version", "stream_id", "decision_sha256", "isolation_registry_fingerprint",
                "mandate_preflight_status", "lifecycle_state", "reason", "next_action", "intent", "execution_authority"}


class HSlowOrderPreparationError(ValueError):
    """The requested preparation is malformed or carries invented authority."""


def _digest(value: Any) -> str:
    def encode_decimal(item: Any) -> str:
        if isinstance(item, Decimal):
            return format(item, "f")
        raise TypeError(f"unsupported digest value: {type(item).__name__}")
    return "sha256:" + hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False, default=encode_decimal).encode("utf-8")
    ).hexdigest()


def _copy(value: Mapping[str, Any], fields: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != fields:
        raise HSlowOrderPreparationError(f"{label} fields are invalid")
    try:
        return json.loads(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False))
    except (TypeError, ValueError) as exc:
        raise HSlowOrderPreparationError(f"{label} must be finite JSON") from exc


def _number(value: Any, label: str, *, positive: bool = True) -> Decimal:
    if isinstance(value, bool):
        raise HSlowOrderPreparationError(f"{label} must be numeric")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise HSlowOrderPreparationError(f"{label} must be numeric") from exc
    if not number.is_finite() or (number <= 0 if positive else number < 0):
        qualifier = "positive" if positive else "nonnegative"
        raise HSlowOrderPreparationError(f"{label} must be {qualifier} and finite")
    if len(number.as_tuple().digits) > 18 or (number != 0 and not Decimal("1e-12") <= number <= Decimal("1e12")):
        raise HSlowOrderPreparationError(f"{label} exceeds supported numeric precision or magnitude")
    return number


def _utc(value: Any, label: str) -> datetime:
    if not isinstance(value, str):
        raise HSlowOrderPreparationError(f"{label} must be a UTC timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise HSlowOrderPreparationError(f"{label} is invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise HSlowOrderPreparationError(f"{label} must be UTC")
    return parsed.astimezone(timezone.utc)


def _decimal_out(value: Decimal) -> float:
    result = float(value)
    if not isfinite(result) or (value != 0 and result == 0):
        raise HSlowOrderPreparationError("prepared value is not finite")
    if Decimal(str(result)) != value:
        raise HSlowOrderPreparationError("prepared value cannot round-trip exactly through JSON numeric output")
    return result


def _validate_plan(value: Mapping[str, Any]) -> dict[str, Any]:
    plan = _copy(value, _PLAN_FIELDS, "lifecycle plan")
    if (plan["schema_version"] != "forex.h-slow.lifecycle-plan.v1" or plan["stream_id"] != "H_SLOW"
            or plan["execution_authority"] is not False):
        raise HSlowOrderPreparationError("lifecycle plan is not a disabled H_SLOW plan")
    if plan["next_action"] == "OPEN":
        intent = plan["intent"]
        if (not isinstance(intent, dict) or set(intent) != {"action_id", "kind", "ticket_id", "direction"}
                or intent["kind"] != "OPEN" or intent["ticket_id"] is not None
                or intent["direction"] not in {"BUY", "SELL"}):
            raise HSlowOrderPreparationError("OPEN lifecycle intent is invalid")
        if intent["action_id"] != _digest({"decision_sha256": plan["decision_sha256"],
                "isolation_registry_fingerprint": plan["isolation_registry_fingerprint"],
                "action": "OPEN", "ticket_id": None}):
            raise HSlowOrderPreparationError("OPEN action ID does not bind lifecycle decision and isolation")
        if plan["lifecycle_state"] != "ENTRY_ELIGIBLE":
            raise HSlowOrderPreparationError("OPEN plan is not entry eligible")
    elif plan["next_action"] != "CLOSE" and plan["intent"] is not None:
        raise HSlowOrderPreparationError("non-OPEN lifecycle plan cannot carry an intent")
    return plan


def _validated_market(value: Mapping[str, Any]) -> dict[str, Any]:
    market = _copy(value, _MARKET_FIELDS, "market_inputs")
    if market["instrument"] != "EUR/USD" or market["server"] != "GOMarketsMU-Demo":
        raise HSlowOrderPreparationError("market_inputs must declare GOMarketsMU-Demo EUR/USD")
    observed = _utc(market["observed_at_utc"], "market_inputs.observed_at_utc")
    evaluated = _utc(market["evaluated_at_utc"], "market_inputs.evaluated_at_utc")
    maximum_age = _number(market["maximum_quote_age_seconds"], "market_inputs.maximum_quote_age_seconds")
    if observed > evaluated or Decimal(str((evaluated - observed).total_seconds())) > maximum_age:
        raise HSlowOrderPreparationError("market_inputs quote is stale or from the future")
    nonnegative = {"adverse_cost_allowance_aud_per_lot", "free_margin_aud", "min_stop_distance_points"}
    for field in _MARKET_FIELDS - {"server", "instrument", "observed_at_utc", "evaluated_at_utc", "maximum_quote_age_seconds"}:
        market[field] = _number(market[field], f"market_inputs.{field}", positive=field not in nonnegative)
    market["maximum_quote_age_seconds"] = maximum_age
    if market["ask"] < market["bid"] or market["volume_min_lots"] > market["volume_max_lots"]:
        raise HSlowOrderPreparationError("market_inputs quote or volume bounds are invalid")
    return market


def _validated_limits(value: Mapping[str, Any]) -> dict[str, Decimal]:
    limits = _copy(value, _LIMIT_FIELDS, "limits")
    return {field: _number(limits[field], f"limits.{field}") for field in _LIMIT_FIELDS}


def _edge_provenance(edge: Mapping[str, Any] | None) -> dict[str, Any]:
    if edge is None:
        return {"edge_sizing_result_sha256": None, "edge_policy_sha256": None,
                "edge_evidence_sha256": None}
    return {"edge_sizing_result_sha256": edge.get("result_sha256"),
            "edge_policy_sha256": edge.get("policy", {}).get("policy_sha256"),
            "edge_evidence_sha256": edge.get("evidence", {}).get("evidence_sha256")}


def _trial_provenance(trial: Mapping[str, Any] | None) -> dict[str, Any]:
    return {"initial_trial_sha256": None if trial is None else _digest(trial)}


def _refusal(plan: dict[str, Any], reason: str, *, market_inputs: Mapping[str, Any], limits: Mapping[str, Any],
             edge: Mapping[str, Any] | None = None, initial_trial: Mapping[str, Any] | None = None) -> dict[str, Any]:
    return {
        "schema_version": ORDER_PREPARATION_SCHEMA_VERSION,
        "outcome": "REFUSED",
        "reason": reason,
        "plan_sha256": _digest(plan),
        "market_inputs_sha256": _digest(market_inputs),
        "limits_sha256": _digest(limits),
        "preparation_input_sha256": _digest({"plan": plan, "market_inputs": market_inputs, "limits": limits,
                                               "edge": _edge_provenance(edge), "initial_trial": _trial_provenance(initial_trial)}),
        **_edge_provenance(edge),
        **_trial_provenance(initial_trial),
        "execution_authority": False,
        "submission_status": "DISABLED_NOT_ROUTED",
    }


def prepare_h_slow_order(lifecycle_plan: Mapping[str, Any], *, market_inputs: Mapping[str, Any],
                         limits: Mapping[str, Any], event_eligibility: Mapping[str, Any] | None = None,
                         research_decision: Mapping[str, Any] | None = None,
                         primary_context: Mapping[str, Any] | None = None,
                         edge_sizing_result: Mapping[str, Any] | None = None,
                         initial_trial: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Prepare using bounded inputs and a context independent of the caller."""
    try:
        with localcontext() as context:
            context.prec = 128
            return _prepare_h_slow_order(lifecycle_plan, market_inputs=market_inputs, limits=limits,
                                         event_eligibility=event_eligibility, research_decision=research_decision,
                                         primary_context=primary_context, edge_sizing_result=edge_sizing_result,
                                         initial_trial=initial_trial)
    except DecimalException as exc:
        raise HSlowOrderPreparationError("unsupported decimal preparation arithmetic") from exc


def _prepare_h_slow_order(lifecycle_plan: Mapping[str, Any], *, market_inputs: Mapping[str, Any],
                          limits: Mapping[str, Any], event_eligibility: Mapping[str, Any] | None,
                          research_decision: Mapping[str, Any] | None,
                          primary_context: Mapping[str, Any] | None, edge_sizing_result: Mapping[str, Any] | None,
                          initial_trial: Mapping[str, Any] | None) -> dict[str, Any]:
    """Prepare an offline H_SLOW OPEN size or return a bounded refusal.

    Volume is the minimum of explicit loss, broker volume, configured maximum,
    notional, lease-budget, and free-margin caps, then rounded down to the
    declared volume step.  Adverse costs are added once per lot to stop loss.
    """
    plan = _validate_plan(lifecycle_plan)
    market = _validated_market(market_inputs)
    checked_limits = _validated_limits(limits)
    trial: dict[str, Any] | None = None
    if initial_trial is not None:
        try:
            trial = validate_initial_trial(dict(initial_trial))
        except (HSlowInitialTrialError, TypeError, ValueError):
            return _refusal(plan, "INITIAL_TRIAL_INVALID", market_inputs=market, limits=checked_limits)
        checked_limits = {
            **checked_limits,
            "max_loss_aud": min(checked_limits["max_loss_aud"], _number(trial["max_loss_aud"], "initial_trial.max_loss_aud")),
            "max_notional_usd": min(checked_limits["max_notional_usd"], _number(trial["max_notional_usd"], "initial_trial.max_notional_usd")),
            "lease_budget_usd": min(checked_limits["lease_budget_usd"], _number(trial["lease_budget_usd"], "initial_trial.lease_budget_usd")),
            "maximum_volume_lots": min(checked_limits["maximum_volume_lots"], _number(trial["maximum_volume_lots"], "initial_trial.maximum_volume_lots")),
        }
    if plan["next_action"] != "OPEN":
        return _refusal(plan, "LIFECYCLE_PLAN_IS_NOT_OPEN", market_inputs=market, limits=checked_limits)
    event_status = validate_h_slow_event_eligibility(
        event_eligibility, research_decision=research_decision, primary_context=primary_context,
        decision_sha256=plan["decision_sha256"])
    if event_status != "ALLOW":
        return _refusal(plan, event_status, market_inputs=market, limits=checked_limits)
    direction = plan["intent"]["direction"]
    entry = market["ask"] if direction == "BUY" else market["bid"]
    technical_stop = market["technical_stop_price"]
    stop = ((technical_stop / market["tick_size"]).to_integral_value(rounding=ROUND_FLOOR)
            if direction == "BUY" else
            (technical_stop / market["tick_size"]).to_integral_value(rounding=ROUND_CEILING)) * market["tick_size"]
    minimum_distance = market["min_stop_distance_points"] * market["point"]
    distance = (market["bid"] - stop) if direction == "BUY" else (stop - market["ask"])
    if stop <= 0 or distance <= 0 or distance < minimum_distance:
        return _refusal(plan, "TECHNICAL_STOP_VIOLATES_EXECUTABLE_SIDE_OR_MINIMUM", market_inputs=market, limits=checked_limits)

    if trial is not None and edge_sizing_result is not None:
        return _refusal(plan, "INITIAL_TRIAL_REJECTS_DYNAMIC_EDGE_SIZING", market_inputs=market,
                        limits=checked_limits, initial_trial=trial)
    if trial is None and edge_sizing_result is None:
        return _refusal(plan, "EDGE_SIZING_EVIDENCE_MISSING", market_inputs=market, limits=checked_limits)
    edge = None
    if trial is None:
     try:
        # Event eligibility above has already verified this retained research
        # record. Bind the sizing result to that exact decision rather than to
        # a timestamp supplied by the sizing result itself.
        if not isinstance(research_decision, Mapping):
            raise HSlowEdgeSizingError("research decision is unavailable")
        edge = validate_edge_sizing_result(
            dict(edge_sizing_result),
            decision_at_utc=research_decision.get("decision_at_utc"),
            research_decision_sha256=plan["decision_sha256"],
            strategy_policy_version=research_decision.get("policy_version"),
            hard_max_loss_aud=float(checked_limits["max_loss_aud"]),
        )
     except (HSlowEdgeSizingError, TypeError, ValueError):
        return _refusal(plan, "EDGE_SIZING_EVIDENCE_INVALID", market_inputs=market, limits=checked_limits)
     if edge["outcome"] == "REFUSED":
        return _refusal(plan, "EDGE_SIZING_EVIDENCE_REFUSED", market_inputs=market, limits=checked_limits, edge=edge)
     checked_limits = {**checked_limits, "max_loss_aud": min(checked_limits["max_loss_aud"], Decimal(str(edge["allowed_max_loss_aud"]))) }

    # Broker minimum distance uses the closing side of the quote, but loss
    # starts at the actual entry side. The latter includes the entry spread.
    stop_loss_per_lot = abs(entry - stop) / market["tick_size"] * market["loss_per_tick_aud_per_lot"]
    risk_per_lot = stop_loss_per_lot + market["adverse_cost_allowance_aud_per_lot"]
    caps = (
        checked_limits["max_loss_aud"] / risk_per_lot,
        market["volume_max_lots"],
        checked_limits["maximum_volume_lots"],
        checked_limits["max_notional_usd"] / market["notional_usd_per_lot"],
        checked_limits["lease_budget_usd"] / market["notional_usd_per_lot"],
        market["free_margin_aud"] / market["margin_aud_per_lot"],
    )
    raw_volume = min(caps)
    volume = (raw_volume / market["volume_step_lots"]).to_integral_value(rounding=ROUND_DOWN) * market["volume_step_lots"]
    if volume < market["volume_min_lots"]:
        return _refusal(plan, "MINIMUM_VOLUME_EXCEEDS_DECLARED_CAPACITY", market_inputs=market, limits=checked_limits, edge=edge, initial_trial=trial)
    planned_stop_loss = volume * stop_loss_per_lot
    planned_cost_allowance = volume * market["adverse_cost_allowance_aud_per_lot"]
    if (planned_stop_loss + planned_cost_allowance > checked_limits["max_loss_aud"]
            or volume > min(market["volume_max_lots"], checked_limits["maximum_volume_lots"])
            or volume * market["notional_usd_per_lot"] > min(checked_limits["max_notional_usd"], checked_limits["lease_budget_usd"])
            or volume * market["margin_aud_per_lot"] > market["free_margin_aud"]):
        return _refusal(plan, "QUANTIZED_SIZE_EXCEEDS_CAPACITY", market_inputs=market, limits=checked_limits, edge=edge, initial_trial=trial)
    content = {
        "plan": plan, "market_inputs": market, "limits": checked_limits,
        "edge": _edge_provenance(edge),
        "initial_trial": _trial_provenance(trial),
        "direction": direction, "entry_price": entry, "technical_stop_price": technical_stop, "executable_stop_price": stop, "volume_lots": volume,
        "planned_stop_loss_aud": planned_stop_loss, "planned_adverse_cost_allowance_aud": planned_cost_allowance,
        "planned_total_loss_aud": planned_stop_loss + planned_cost_allowance,
        "planned_notional_usd": volume * market["notional_usd_per_lot"], "planned_margin_aud": volume * market["margin_aud_per_lot"],
    }
    return {
        "schema_version": ORDER_PREPARATION_SCHEMA_VERSION,
        "outcome": "PREPARED_DISABLED",
        "reason": "DECLARED_INPUTS_WITHIN_BOUNDED_CAPACITY",
        "lifecycle_action_id": plan["intent"]["action_id"],
        "direction": direction,
        "entry_price": _decimal_out(entry),
        "technical_stop_price": _decimal_out(technical_stop),
        "executable_stop_price": _decimal_out(stop),
        "volume_lots": _decimal_out(volume),
        "planned_stop_loss_aud": _decimal_out(planned_stop_loss),
        "planned_adverse_cost_allowance_aud": _decimal_out(planned_cost_allowance),
        "planned_total_loss_aud": _decimal_out(planned_stop_loss + planned_cost_allowance),
        "planned_notional_usd": _decimal_out(content["planned_notional_usd"]),
        "planned_margin_aud": _decimal_out(content["planned_margin_aud"]),
        "plan_sha256": _digest(plan), "market_inputs_sha256": _digest(market), "limits_sha256": _digest(checked_limits),
        **_edge_provenance(edge),
        **_trial_provenance(trial),
        "preparation_input_sha256": _digest(content),
        "execution_authority": False,
        "submission_status": "DISABLED_NOT_ROUTED",
    }
