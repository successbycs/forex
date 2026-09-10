"""Fixed local PostgreSQL-audit bridge contract for the M20 T480 session.

This bridge is intentionally invoked only by the hash-bound M20 session
runner.  It accepts no database host, SQL, server, symbol, or transaction
argument.  Its deployment requires a machine-local ``FOREX_M20_POSTGRES_DSN``
and a Python environment with psycopg; absent prerequisites fail closed.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import sys
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_DOWN
from typing import Any


def _digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _payload() -> dict[str, Any]:
    try:
        value = json.load(sys.stdin)
    except json.JSONDecodeError as error:
        raise SystemExit("M20 audit bridge requires structured session payload") from error
    if not isinstance(value, dict):
        raise SystemExit("M20 audit bridge payload must be an object")
    return value


def _connection():
    dsn = os.environ.get("FOREX_M20_POSTGRES_DSN", "")
    if not dsn:
        raise SystemExit("M20 PostgreSQL bridge is not deployed with its local DSN")
    try:
        import psycopg  # type: ignore[import-not-found]
    except ImportError as error:
        raise SystemExit("M20 PostgreSQL bridge requires the deployed psycopg dependency") from error
    return psycopg.connect(dsn, connect_timeout=5)


def _object(payload: dict[str, Any], key: str) -> dict[str, Any]:
    value = payload.get(key)
    if not isinstance(value, dict):
        raise SystemExit(f"M20 bridge {key} is invalid")
    return value


def _session(payload: dict[str, Any]) -> dict[str, Any]:
    value = _object(payload, "session")
    required = {"session_id", "server", "instrument", "starts_at_utc", "expires_at_utc", "max_trades", "max_notional_per_trade_usd", "max_cumulative_notional_usd", "max_open_positions", "strategy_version", "operator_label"}
    if set(value) != required or value["server"] != "GOMarketsMU-Demo" or value["instrument"] != "EURUSD":
        raise SystemExit("M20 bridge accepts only the fixed Demo EURUSD session")
    if (value["max_trades"] is not None
            or value["max_open_positions"] != 1
            or not isinstance(value["max_notional_per_trade_usd"], (int, float)) or not 0 < value["max_notional_per_trade_usd"] <= 10000
            or not isinstance(value["max_cumulative_notional_usd"], (int, float)) or not 0 < value["max_cumulative_notional_usd"] <= 100000):
        raise SystemExit("M20 bridge session limits are invalid")
    return value


def _proposal(payload: dict[str, Any]) -> dict[str, Any]:
    value = _object(payload, "proposal")
    required = {"proposal_id", "session_id", "snapshot_id", "decision_at_utc", "expires_at_utc", "selected_timeframe", "action", "proposed_entry", "stop_loss", "take_profit", "notional_usd", "confidence", "rationale", "decision_snapshot_sha256", "strategy_version"}
    if set(value) != required or value.get("action") not in {"BUY", "SELL", "NO_TRADE"}:
        raise SystemExit("M20 bridge proposal is invalid")
    return value


def _snapshot(payload: dict[str, Any], proposal: dict[str, Any]) -> dict[str, Any]:
    value = _object(payload, "decision_snapshot")
    required = {"snapshot_id", "observed_at_utc", "captured_at_utc", "bid", "ask", "spread_points", "m1_closed_bars", "m5_closed_bars", "freshness_seconds", "safety_gates", "market_context", "strategy_assessments", "payload_sha256"}
    gates = value.get("safety_gates")
    expected_gates = {"fresh_quote", "completed_m1", "normal_spread", "no_existing_position", "demo_lease_active", "news_blackout_inactive", "abnormal_volatility_inactive"}
    if (set(value) != required or value["snapshot_id"] != proposal["snapshot_id"] or value["payload_sha256"] != proposal["decision_snapshot_sha256"] or not isinstance(value["m1_closed_bars"], list) or not isinstance(value["m5_closed_bars"], list)
            or not isinstance(gates, dict) or set(gates) != expected_gates or any(flag is not True and flag is not False for flag in gates.values())):
        raise SystemExit("M20 bridge snapshot does not bind its proposal")
    return value


def _strategy_selection(payload: dict[str, Any], proposal: dict[str, Any]) -> dict[str, Any]:
    value = _object(payload, "strategy_selection")
    required = {"proposal_id", "market_regime", "market_regime_reason", "selected_strategy_id", "strategy_rule_version", "selection_status", "trade_owner_id", "trade_owner_strategy_id", "entry_spread_cost_aud", "expected_exit_spread_cost_aud", "commission_allowance_aud", "slippage_allowance_aud", "expected_swap_aud", "projected_gross_profit_at_take_profit_aud", "estimated_round_trip_cost_aud", "minimum_net_profit_aud", "expected_net_profit_at_take_profit_aud", "cost_coverage_status"}
    regimes = {"UNSAFE_OR_UNTRADEABLE", "COMPRESSION_BREAKOUT", "TREND_PULLBACK", "RANGE_REVERSION", "LIQUID_SESSION_BREAKOUT", "MOMENTUM_BREAKOUT", "NO_CLEAR_REGIME"}
    strategies = {"momentum_breakout", "compression_breakout", "trend_pullback", "range_reversion", "session_breakout"}
    if (set(value) != required or value["proposal_id"] != proposal["proposal_id"] or value["trade_owner_id"] != proposal["proposal_id"]
            or value["market_regime"] not in regimes or value["selection_status"] not in {"SELECTED_EXECUTABLE", "SELECTED_SHADOW", "NO_SELECTION"}
            or value["cost_coverage_status"] not in {"FEASIBLE", "NOT_FEASIBLE", "NOT_APPLICABLE"}):
        raise SystemExit("M20 bridge strategy selection is invalid")
    selected = value["selected_strategy_id"]
    if selected is not None and selected not in strategies:
        raise SystemExit("M20 bridge strategy selection has an unknown strategy")
    if value["selection_status"] == "SELECTED_EXECUTABLE" and (selected not in strategies or value["trade_owner_strategy_id"] != selected):
        raise SystemExit("M20 bridge executable strategy selection is invalid")
    if value["selection_status"] == "NO_SELECTION" and any(value[field] is not None for field in ("selected_strategy_id", "strategy_rule_version", "trade_owner_strategy_id")):
        raise SystemExit("M20 bridge no-selection ownership is invalid")
    return value


def _strategy_assessments(payload: dict[str, Any]) -> list[dict[str, Any]]:
    value = payload.get("strategy_assessments")
    required = {"id", "label", "signal", "eligible_for_execution", "reason"}
    ids = ("momentum_breakout", "compression_breakout", "trend_pullback", "range_reversion", "session_breakout")
    if not isinstance(value, list) or len(value) != len(ids) or [item.get("id") if isinstance(item, dict) else None for item in value] != list(ids):
        raise SystemExit("M20 bridge requires exactly five ordered strategy assessments")
    if any(set(item) != required or item["signal"] not in {"BUY", "SELL", "NO_TRADE"} for item in value):
        raise SystemExit("M20 bridge strategy assessment is invalid")
    if any(item["eligible_for_execution"] is not True for item in value):
        raise SystemExit("M20 bridge strategy execution authority is invalid")
    return value


def _metadata(payload: dict[str, Any]) -> tuple[str, str]:
    revision, fingerprint = payload.get("application_revision"), payload.get("configuration_fingerprint")
    if not isinstance(revision, str) or len(revision) != 40 or not isinstance(fingerprint, str) or not fingerprint.startswith("sha256:"):
        raise SystemExit("M20 bridge provenance is invalid")
    return revision, fingerprint


def _parse_utc(value: Any, label: str) -> datetime:
    if not isinstance(value, str):
        raise SystemExit(f"M20.12 context {label} is not UTC text")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise SystemExit(f"M20.12 context {label} is not UTC text") from error
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise SystemExit(f"M20.12 context {label} is not UTC")
    return parsed


def _multi_timeframe_context(payload: dict[str, Any], proposal: dict[str, Any]) -> dict[str, Any]:
    """Validate the fixed observational M5/H1 context; it grants no authority."""
    value = _object(payload, "multi_timeframe_context")
    required = {"context_id", "proposal_id", "selected_m1_action", "overall_alignment", "context_disposition", "reason", "rule_version", "retrieved_at_utc", "source_inputs_sha256", "contexts"}
    rows_required = {"timeframe", "closed_at_utc", "data_age_seconds", "integrity_status", "market_state", "volatility_state", "liquidity_state", "alignment", "reason", "source_inputs"}
    alignments = {"ALIGNED", "NEUTRAL", "OPPOSED", "UNAVAILABLE", "NOT_APPLICABLE"}
    if (set(value) != required or value["proposal_id"] != proposal["proposal_id"]
            or value["selected_m1_action"] != proposal["action"]
            or value["overall_alignment"] not in alignments
            or value["context_disposition"] not in {"OBSERVE_ONLY", "NEUTRAL", "HARD_CONFLICT"}
            or not isinstance(value["context_id"], str) or not value["context_id"]
            or not isinstance(value["reason"], str) or not value["reason"]
            or not isinstance(value["rule_version"], str) or not value["rule_version"]
            or not isinstance(value["source_inputs_sha256"], str) or len(value["source_inputs_sha256"]) != 71
            or not value["source_inputs_sha256"].startswith("sha256:")
            or any(character not in "0123456789abcdef" for character in value["source_inputs_sha256"][7:])
            or not isinstance(value["contexts"], list) or [row.get("timeframe") if isinstance(row, dict) else None for row in value["contexts"]] != ["M5", "H1"]):
        raise SystemExit("M20.12 multi-timeframe context is invalid")
    _parse_utc(value["retrieved_at_utc"], "retrieved_at_utc")
    if value["context_disposition"] == "HARD_CONFLICT" and value["overall_alignment"] != "OPPOSED":
        raise SystemExit("M20.12 hard conflict must be opposed context")
    for row in value["contexts"]:
        if (set(row) != rows_required or row["integrity_status"] not in {"VALID", "STALE", "UNAVAILABLE", "INVALID"}
                or row["market_state"] not in {"BULLISH", "BEARISH", "RANGE", "MIXED", "UNKNOWN"}
                or row["volatility_state"] not in {"LOW", "NORMAL", "HIGH", "UNKNOWN"}
                or row["liquidity_state"] not in {"LIQUID", "THIN", "UNKNOWN"}
                or row["alignment"] not in alignments or not isinstance(row["reason"], str) or not row["reason"]
                or not isinstance(row["source_inputs"], dict)
                or not {"selected_m1_owner", "pre_context_m1_candidate", "final_m1_action"}.issubset(row["source_inputs"])):
            raise SystemExit("M20.12 context row is invalid")
        if row["source_inputs"]["final_m1_action"] != proposal["action"]:
            raise SystemExit("M20.12 context cannot alter the M1 proposal action")
        unavailable = row["integrity_status"] in {"UNAVAILABLE", "INVALID"}
        if unavailable and (row["closed_at_utc"] is not None or row["data_age_seconds"] is not None
                            or row["market_state"] != "UNKNOWN" or row["volatility_state"] != "UNKNOWN"
                            or row["liquidity_state"] != "UNKNOWN" or row["alignment"] != "UNAVAILABLE"):
            raise SystemExit("M20.12 unavailable context must remain visibly neutral")
        if not unavailable:
            closed_at = _parse_utc(row["closed_at_utc"], f"{row['timeframe']} closed_at_utc")
            if (not isinstance(row["data_age_seconds"], int) or row["data_age_seconds"] < 0
                    or closed_at > _parse_utc(value["retrieved_at_utc"], "retrieved_at_utc")):
                raise SystemExit("M20.12 closed context data is invalid")
    return value


def persist_proposal(payload: dict[str, Any]) -> dict[str, Any]:
    """Persist immutable proposal and snapshot before any broker submission."""
    session, proposal = _session(payload), _proposal(payload)
    snapshot = _snapshot(payload, proposal)
    selection = _strategy_selection(payload, proposal)
    assessments = _strategy_assessments(payload)
    context = _multi_timeframe_context(payload, proposal)
    revision, fingerprint = _metadata(payload)
    with _connection() as conn, conn.cursor() as cursor:
        # All leases share one Demo risk/entry writer. A per-session lock did
        # not serialize the global unresolved-exposure check across leases.
        cursor.execute("SELECT pg_advisory_xact_lock(hashtextextended('forex.m20.conservative-risk.v1', 0))")
        cursor.execute("SELECT pause_reasons,cash_flow_review_approved FROM forex.demo_risk_policy_state WHERE policy_version='forex.m20.conservative-risk.v1' FOR UPDATE")
        risk_state = cursor.fetchone()
        if risk_state is None or risk_state[0] or risk_state[1]:
            raise SystemExit("M20 reservation requires checked, unpaused persistent risk state")
        cursor.execute(
            """INSERT INTO forex.demo_trade_session
               (session_id,operator_label,server,instrument,starts_at_utc,expires_at_utc,max_trades,max_notional_usd,max_cumulative_notional_usd,max_open_positions,status,strategy_version,application_revision,configuration_fingerprint)
               VALUES (%s,%s,'GOMarketsMU-Demo','EURUSD',%s,%s,%s,%s,%s,1,'ACTIVE',%s,%s,%s)
               ON CONFLICT (session_id) DO NOTHING""",
            (session["session_id"], session["operator_label"], session["starts_at_utc"], session["expires_at_utc"], session["max_trades"], session["max_notional_per_trade_usd"], session["max_cumulative_notional_usd"], session["strategy_version"], revision, fingerprint),
        )
        cursor.execute(
            "SELECT status,max_trades,max_notional_usd,max_cumulative_notional_usd,max_open_positions FROM forex.demo_trade_session WHERE session_id=%s AND starts_at_utc=%s AND expires_at_utc=%s FOR UPDATE",
            (session["session_id"], session["starts_at_utc"], session["expires_at_utc"]),
        )
        row = cursor.fetchone()
        if row is None or row[0] != "ACTIVE" or tuple(row[1:]) != (session["max_trades"], session["max_notional_per_trade_usd"], session["max_cumulative_notional_usd"], 1):
            raise SystemExit("M20 PostgreSQL session is missing, inactive, or differs from the local lease")
        if session["max_trades"] is not None:
            cursor.execute("INSERT INTO forex.demo_trade_slot (session_id,slot_number) SELECT %s, generate_series(1,%s) ON CONFLICT DO NOTHING", (session["session_id"], session["max_trades"]))
        cursor.execute(
            "INSERT INTO forex.demo_trade_proposal (proposal_id,session_id,decision_at_utc,expires_at_utc,selected_timeframe,action,proposed_entry,stop_loss,take_profit,notional_usd,confidence,rationale,decision_snapshot_sha256,strategy_version,application_revision,configuration_fingerprint) VALUES (%(proposal_id)s,%(session_id)s,%(decision_at_utc)s,%(expires_at_utc)s,%(selected_timeframe)s,%(action)s,%(proposed_entry)s,%(stop_loss)s,%(take_profit)s,%(notional_usd)s,%(confidence)s,%(rationale)s,%(decision_snapshot_sha256)s,%(strategy_version)s,%(application_revision)s,%(configuration_fingerprint)s)",
            {**proposal, "application_revision": revision, "configuration_fingerprint": fingerprint},
        )
        cursor.execute(
            "INSERT INTO forex.demo_decision_snapshot (snapshot_id,proposal_id,observed_at_utc,captured_at_utc,bid,ask,spread_points,m1_closed_bars,m5_closed_bars,freshness_seconds,payload_sha256) VALUES (%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s)",
            (snapshot["snapshot_id"], proposal["proposal_id"], snapshot["observed_at_utc"], snapshot["captured_at_utc"], snapshot["bid"], snapshot["ask"], snapshot["spread_points"], json.dumps(snapshot["m1_closed_bars"]), json.dumps(snapshot["m5_closed_bars"]), snapshot["freshness_seconds"], snapshot["payload_sha256"]),
        )
        cursor.execute(
            """INSERT INTO forex.demo_strategy_selection
               (proposal_id,market_regime,market_regime_reason,selected_strategy_id,strategy_rule_version,selection_status,trade_owner_id,trade_owner_strategy_id,entry_spread_cost_aud,expected_exit_spread_cost_aud,commission_allowance_aud,slippage_allowance_aud,expected_swap_aud,projected_gross_profit_at_take_profit_aud,estimated_round_trip_cost_aud,minimum_net_profit_aud,expected_net_profit_at_take_profit_aud,cost_coverage_status)
               VALUES (%(proposal_id)s,%(market_regime)s,%(market_regime_reason)s,%(selected_strategy_id)s,%(strategy_rule_version)s,%(selection_status)s,%(trade_owner_id)s,%(trade_owner_strategy_id)s,%(entry_spread_cost_aud)s,%(expected_exit_spread_cost_aud)s,%(commission_allowance_aud)s,%(slippage_allowance_aud)s,%(expected_swap_aud)s,%(projected_gross_profit_at_take_profit_aud)s,%(estimated_round_trip_cost_aud)s,%(minimum_net_profit_aud)s,%(expected_net_profit_at_take_profit_aud)s,%(cost_coverage_status)s)""",
            selection,
        )
        for assessment in assessments:
            cursor.execute(
                "INSERT INTO forex.demo_strategy_signal (proposal_id,strategy_id,signal,eligible_for_execution,reason,observed_at_utc) VALUES (%s,%s,%s,%s,%s,%s)",
                (proposal["proposal_id"], assessment["id"], assessment["signal"], assessment["eligible_for_execution"], assessment["reason"], snapshot["observed_at_utc"]),
            )
        cursor.execute(
            "INSERT INTO forex.demo_multi_timeframe_context (context_id,proposal_id,selected_m1_action,overall_alignment,context_disposition,reason,rule_version,retrieved_at_utc,source_inputs_sha256) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            tuple(context[key] for key in ("context_id", "proposal_id", "selected_m1_action", "overall_alignment", "context_disposition", "reason", "rule_version", "retrieved_at_utc", "source_inputs_sha256")),
        )
        for row in context["contexts"]:
            cursor.execute(
                "INSERT INTO forex.demo_multi_timeframe_context_bar (context_id,timeframe,closed_at_utc,data_age_seconds,integrity_status,market_state,volatility_state,liquidity_state,alignment,reason,source_inputs) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)",
                (context["context_id"], row["timeframe"], row["closed_at_utc"], row["data_age_seconds"], row["integrity_status"], row["market_state"], row["volatility_state"], row["liquidity_state"], row["alignment"], row["reason"], json.dumps(row["source_inputs"])),
            )
    receipt = {"session_id": session["session_id"], "proposal_id": proposal["proposal_id"], "snapshot_id": snapshot["snapshot_id"], "multi_timeframe_context_id": context["context_id"]}
    return {"ok": True, "postgres_audit": {**receipt, "execution_attempt_id": None, "record_sha256": _digest({**receipt, "execution_attempt_id": None})}}


def reserve_execution(payload: dict[str, Any]) -> dict[str, Any]:
    """Atomically claim a session slot before MT5 can be called.

    This is deliberately the only state transition that authorizes the fixed
    runner to submit an order.  It verifies the persisted proposal/snapshot,
    caps, idempotency, and both database and observed broker position limits.
    """
    session, proposal = _session(payload), _proposal(payload)
    _snapshot(payload, proposal)
    selection = _strategy_selection(payload, proposal)
    _strategy_assessments(payload)
    if proposal["action"] not in {"BUY", "SELL"}:
        raise SystemExit("NO_TRADE proposals cannot reserve an execution slot")
    reservation = _object(payload, "reservation")
    required = {"attempt_id", "idempotency_key", "submitted_at_utc", "redacted_result", "broker_open_positions", "account_scope_sha256", "planned_loss_aud"}
    if set(reservation) != required or reservation["broker_open_positions"] != 0:
        raise SystemExit("M20 reservation must observe no open EURUSD position")
    with _connection() as conn, conn.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(hashtextextended('forex.m20.conservative-risk.v1', 0))")
        cursor.execute("SELECT pause_reasons,cash_flow_review_approved,account_scope_sha256,last_observed_equity,peak_adjusted_equity,daily_anchor_equity,weekly_anchor_equity,risk_observed_at_utc >= clock_timestamp() - interval '10 seconds' FROM forex.demo_risk_policy_state WHERE policy_version='forex.m20.conservative-risk.v1' FOR UPDATE")
        risk_state = cursor.fetchone()
        if (risk_state is None or risk_state[0] or risk_state[1]
                or risk_state[2] is None or risk_state[2] != reservation["account_scope_sha256"]
                or risk_state[7] is not True):
            raise SystemExit("M20 reservation requires fresh, unpaused, account-bound risk state")
        planned_loss = reservation["planned_loss_aud"]
        available = _risk_response(*(float(value) for value in risk_state[3:7]), set())["risk"]["maximum_loss_aud"]
        if type(planned_loss) not in (int, float) or not math.isfinite(planned_loss) or not 0 < planned_loss <= available:
            raise SystemExit("M20 planned loss exceeds remaining capital headroom")
        cursor.execute("SELECT status,expires_at_utc > now(),max_trades,max_notional_usd,max_cumulative_notional_usd,max_open_positions FROM forex.demo_trade_session WHERE session_id=%s AND starts_at_utc=%s AND expires_at_utc=%s FOR UPDATE", (session["session_id"], session["starts_at_utc"], session["expires_at_utc"]))
        row = cursor.fetchone()
        if row is None or row[0] != "ACTIVE" or row[1] is not True or tuple(row[2:]) != (session["max_trades"], session["max_notional_per_trade_usd"], session["max_cumulative_notional_usd"], 1):
            raise SystemExit("M20 session is inactive or differs from fixed limits")
        cursor.execute("SELECT 1 FROM forex.demo_trade_proposal p JOIN forex.demo_decision_snapshot s ON s.proposal_id=p.proposal_id JOIN forex.demo_strategy_selection selection ON selection.proposal_id=p.proposal_id WHERE p.proposal_id=%s AND p.session_id=%s AND p.action IN ('BUY','SELL') AND p.expires_at_utc >= now() AND selection.selection_status='SELECTED_EXECUTABLE' AND selection.selected_strategy_id IN ('momentum_breakout','compression_breakout','trend_pullback','range_reversion','session_breakout') AND selection.trade_owner_strategy_id=selection.selected_strategy_id AND selection.cost_coverage_status='FEASIBLE' FOR UPDATE", (proposal["proposal_id"], session["session_id"]))
        if cursor.fetchone() is None:
            raise SystemExit("M20 proposal is absent, unpersisted, expired, or non-actionable")
        cursor.execute("SELECT count(*) FROM forex.demo_execution_attempt WHERE session_id=%s", (session["session_id"],))
        if session["max_trades"] is not None and cursor.fetchone()[0] >= session["max_trades"]:
            raise SystemExit("M20 maximum trade count is reached")
        cursor.execute("SELECT COALESCE(sum(p.notional_usd),0) FROM forex.demo_execution_attempt a JOIN forex.demo_trade_proposal p ON p.proposal_id=a.proposal_id WHERE a.session_id=%s", (session["session_id"],))
        if float(cursor.fetchone()[0]) + float(proposal["notional_usd"]) > float(session["max_cumulative_notional_usd"]):
            raise SystemExit("M20 cumulative notional cap is reached")
        cursor.execute("SELECT count(*) FROM forex.demo_execution_attempt a LEFT JOIN forex.demo_trade_outcome o ON o.proposal_id=a.proposal_id WHERE o.proposal_id IS NULL AND NOT EXISTS (SELECT 1 FROM forex.demo_position_event e WHERE e.attempt_id=a.attempt_id AND e.event_type='REJECTED')")
        if cursor.fetchone()[0] != 0:
            raise SystemExit("M20 global one-position limit is reached")
        slot_number = None
        if session["max_trades"] is not None:
            cursor.execute("SELECT slot_number FROM forex.demo_trade_slot WHERE session_id=%s AND proposal_id IS NULL ORDER BY slot_number FOR UPDATE SKIP LOCKED LIMIT 1", (session["session_id"],))
            slot = cursor.fetchone()
            if slot is None:
                raise SystemExit("M20 no unclaimed execution slot remains")
            slot_number = slot[0]
            cursor.execute("UPDATE forex.demo_trade_slot SET proposal_id=%s,claimed_at_utc=%s WHERE session_id=%s AND slot_number=%s AND proposal_id IS NULL", (proposal["proposal_id"], reservation["submitted_at_utc"], session["session_id"], slot_number))
            if cursor.rowcount != 1:
                raise SystemExit("M20 execution slot claim lost its atomic race")
        cursor.execute("INSERT INTO forex.demo_execution_attempt (attempt_id,proposal_id,session_id,slot_number,idempotency_key,submitted_at_utc,status,redacted_result) VALUES (%s,%s,%s,%s,%s,%s,'SUBMITTED',%s)", (reservation["attempt_id"], proposal["proposal_id"], session["session_id"], slot_number, reservation["idempotency_key"], reservation["submitted_at_utc"], reservation["redacted_result"]))
    receipt = {"session_id": session["session_id"], "proposal_id": proposal["proposal_id"], "snapshot_id": proposal["snapshot_id"], "execution_attempt_id": reservation["attempt_id"], "slot_number": slot_number}
    return {"ok": True, "reservation": receipt, "postgres_audit": {**receipt, "record_sha256": _digest(receipt)}}


RISK_PAUSE_ORDER = ("EXTERNAL_CASH_FLOW", "UNKNOWN_ACCOUNT_STATE", "PEAK_DRAWDOWN", "WEEKLY_LOSS", "DAILY_LOSS")


def _ordered_risk_pauses(reasons: set[str]) -> list[str]:
    if not reasons.issubset(RISK_PAUSE_ORDER):
        raise SystemExit("M20 persisted risk pause is invalid")
    return [reason for reason in RISK_PAUSE_ORDER if reason in reasons]


def _risk_response(equity: float, peak: float, daily: float, weekly: float, reasons: set[str]) -> dict[str, Any]:
    """Cash headroom before another trade, rounded down rather than above a cap."""
    e, p, d, w = (Decimal(str(value)) for value in (equity, peak, daily, weekly))
    headroom = min(Decimal("100"), e * Decimal("0.001"),
                   e - d * Decimal("0.995"), e - w * Decimal("0.99"),
                   e - p * Decimal("0.98"))
    allowance = max(Decimal("0"), headroom).quantize(Decimal("0.01"), rounding=ROUND_DOWN)
    ordered = _ordered_risk_pauses(reasons)
    return {"ok": True, "risk": {"entry_allowed": not ordered and allowance > 0,
            "pause_reason": ordered[0] if ordered else None, "pause_reasons": ordered,
            "policy_equity": equity, "maximum_loss_aud": float(allowance)}}


def enforce_risk_policy(payload: dict[str, Any]) -> dict[str, Any]:
    """Persist and enforce the fixed conservative risk budget before entry."""
    policy = _object(payload, "policy")
    account = _object(payload, "account")
    policy_required = {"policy_version", "reporting_currency", "maximum_risk_per_trade_percent", "maximum_risk_per_trade_aud", "daily_loss_limit_percent", "weekly_loss_limit_percent", "peak_equity_drawdown_limit_percent", "loss_budget_timezone", "daily_pause_reset", "manual_resume_reasons", "require_known_external_cashflow"}
    account_required = {"balance", "equity", "auckland_date", "auckland_week_start", "account_scope_sha256"}
    if (set(policy) != policy_required or policy["policy_version"] != "forex.m20.conservative-risk.v1"
            or policy["reporting_currency"] != "AUD" or policy["maximum_risk_per_trade_percent"] != .10
            or policy["maximum_risk_per_trade_aud"] != 100.0 or policy["daily_loss_limit_percent"] != .50
            or policy["weekly_loss_limit_percent"] != 1.0 or policy["peak_equity_drawdown_limit_percent"] != 2.0
            or policy["loss_budget_timezone"] != "Pacific/Auckland" or policy["daily_pause_reset"] != "NEXT_AUCKLAND_DAY"
            or policy["manual_resume_reasons"] != ["WEEKLY_LOSS", "PEAK_DRAWDOWN", "EXTERNAL_CASH_FLOW", "UNKNOWN_ACCOUNT_STATE"]
            or policy["require_known_external_cashflow"] is not True or set(account) != account_required
            or not all(type(account[key]) in (int, float) and math.isfinite(account[key]) and account[key] > 0 for key in ("balance", "equity"))
            or not all(isinstance(account[key], str) and len(account[key]) == 10 for key in ("auckland_date", "auckland_week_start"))):
        raise SystemExit("M20 persistent risk policy payload is invalid")
    balance, equity = float(account["balance"]), float(account["equity"])
    scope = account["account_scope_sha256"]
    if not isinstance(scope, str) or len(scope) != 64 or any(c not in "0123456789abcdef" for c in scope):
        raise SystemExit("M20 risk account identity binding is invalid")
    try:
        observed_day = date.fromisoformat(account["auckland_date"])
        if account["auckland_week_start"] != (observed_day - timedelta(days=observed_day.weekday())).isoformat():
            raise ValueError("week anchor differs")
    except ValueError as error:
        raise SystemExit("M20 risk observation date is invalid") from error
    with _connection() as conn, conn.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", (policy["policy_version"],))
        cursor.execute("SELECT expected_balance,peak_adjusted_equity,daily_anchor_equity,daily_anchor_date::text,weekly_anchor_equity,weekly_anchor_date::text,pause_reason,pause_until_date::text,cash_flow_review_approved,pause_reasons,account_scope_sha256 FROM forex.demo_risk_policy_state WHERE policy_version=%s FOR UPDATE", (policy["policy_version"],))
        state = cursor.fetchone()
        if state is None:
            cursor.execute("INSERT INTO forex.demo_risk_policy_state (policy_version,account_currency,baseline_balance,expected_balance,peak_adjusted_equity,daily_anchor_equity,daily_anchor_date,weekly_anchor_equity,weekly_anchor_date,account_scope_sha256,last_observed_equity,risk_observed_at_utc) VALUES (%s,'AUD',%s,%s,%s,%s,%s,%s,%s,%s,%s,now())", (policy["policy_version"], balance, balance, equity, equity, account["auckland_date"], equity, account["auckland_week_start"], scope, equity))
            return _risk_response(equity, equity, equity, equity, set())
        expected_balance, peak, daily_anchor, daily_date, weekly_anchor, weekly_date, pause_reason, pause_until, cash_flow_review_approved, pause_reasons, bound_scope = state
        if bound_scope is not None and bound_scope != scope:
            raise SystemExit("M20 observed account differs from the bound risk account")
        expected_balance = float(expected_balance)
        peak, daily_anchor, weekly_anchor = float(peak), float(daily_anchor), float(weekly_anchor)
        reasons = set(pause_reasons)
        if pause_reason is not None:
            reasons.add(pause_reason)
        _ordered_risk_pauses(reasons)
        if daily_date > account["auckland_date"] or weekly_date > account["auckland_week_start"]:
            raise SystemExit("M20 risk observation predates durable anchors")
        cash_flow_delta = balance - expected_balance
        if abs(cash_flow_delta) > .02:
            if cash_flow_review_approved:
                # The fixed operator action explicitly acknowledges this cash
                # movement. Shift every raw-equity anchor by the same amount
                # so adjusted-equity drawdown remains continuous.
                expected_balance = balance
                peak += cash_flow_delta
                daily_anchor += cash_flow_delta
                weekly_anchor += cash_flow_delta
                cash_flow_review_approved = False
            else:
                reasons.add("EXTERNAL_CASH_FLOW")
        else:
            cash_flow_review_approved = False
        if daily_date != account["auckland_date"]:
            daily_anchor, daily_date = equity, account["auckland_date"]
            reasons.discard("DAILY_LOSS")
            pause_until = None
        if weekly_date != account["auckland_week_start"]:
            weekly_anchor, weekly_date = equity, account["auckland_week_start"]
        peak = max(peak, equity)
        if equity <= float(daily_anchor) * .995:
            reasons.add("DAILY_LOSS")
        if equity <= float(weekly_anchor) * .99:
            reasons.add("WEEKLY_LOSS")
        if equity <= peak * .98:
            reasons.add("PEAK_DRAWDOWN")
        ordered = _ordered_risk_pauses(reasons)
        cursor.execute("UPDATE forex.demo_risk_policy_state SET expected_balance=%s,peak_adjusted_equity=%s,daily_anchor_equity=%s,daily_anchor_date=%s,weekly_anchor_equity=%s,weekly_anchor_date=%s,pause_reason=%s,pause_until_date=%s,cash_flow_review_approved=%s,pause_reasons=%s,account_scope_sha256=%s,last_observed_equity=%s,risk_observed_at_utc=now(),updated_at_utc=now() WHERE policy_version=%s", (expected_balance, peak, daily_anchor, daily_date, weekly_anchor, weekly_date, ordered[0] if ordered else None, (observed_day + timedelta(days=1)).isoformat() if "DAILY_LOSS" in reasons else None, cash_flow_review_approved, ordered, scope, equity, policy["policy_version"]))
    return _risk_response(equity, peak, daily_anchor, weekly_anchor, reasons)


def pause_unknown_account_state(payload: dict[str, Any]) -> dict[str, Any]:
    """Latch unavailable account state without inventing equity or anchors."""
    if payload:
        raise SystemExit("M20 unknown-account pause accepts no caller-controlled fields")
    with _connection() as conn, conn.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(hashtextextended('forex.m20.conservative-risk.v1', 0))")
        cursor.execute("SELECT pause_reasons FROM forex.demo_risk_policy_state WHERE policy_version='forex.m20.conservative-risk.v1' FOR UPDATE")
        row = cursor.fetchone()
        if row is None:
            raise SystemExit("M20 cannot initialise risk anchors from unknown account state")
        reasons = _ordered_risk_pauses(set(row[0]) | {"UNKNOWN_ACCOUNT_STATE"})
        cursor.execute("UPDATE forex.demo_risk_policy_state SET pause_reason=%s,pause_reasons=%s,risk_observed_at_utc=NULL,updated_at_utc=now() WHERE policy_version='forex.m20.conservative-risk.v1'", (reasons[0], reasons))
    return {"ok": True, "entry_allowed": False, "pause_reasons": reasons}


def resume_risk_policy(payload: dict[str, Any]) -> dict[str, Any]:
    """Record a fixed operator resume request without overriding a current limit."""
    if payload:
        raise SystemExit("M20 risk-policy resume accepts no caller-controlled fields")
    manual_reasons = {"WEEKLY_LOSS", "PEAK_DRAWDOWN", "EXTERNAL_CASH_FLOW", "UNKNOWN_ACCOUNT_STATE"}
    with _connection() as conn, conn.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(hashtextextended('forex.m20.conservative-risk.v1', 0))")
        cursor.execute("SELECT pause_reasons,cash_flow_review_approved FROM forex.demo_risk_policy_state WHERE policy_version='forex.m20.conservative-risk.v1' FOR UPDATE")
        row = cursor.fetchone()
        reasons = set(row[0]) if row else set()
        ordered = _ordered_risk_pauses(reasons)
        reviewable = [reason for reason in ordered if reason in manual_reasons]
        if not reviewable:
            raise SystemExit("M20 risk-policy resume requires a current manual-review pause")
        previous_reason = reviewable[0]
        resume_id = str(uuid.uuid4())
        cursor.execute("INSERT INTO forex.demo_risk_policy_resume (resume_id,policy_version,previous_pause_reason,operator_action) VALUES (%s,'forex.m20.conservative-risk.v1',%s,'m20_listener_resume_risk_policy')", (resume_id, previous_reason))
        reasons.remove(previous_reason)
        remaining = _ordered_risk_pauses(reasons)
        cursor.execute("UPDATE forex.demo_risk_policy_state SET pause_reason=%s,pause_reasons=%s,cash_flow_review_approved=%s,risk_observed_at_utc=NULL,updated_at_utc=now() WHERE policy_version='forex.m20.conservative-risk.v1'", (remaining[0] if remaining else None, remaining, bool(row[1]) or previous_reason == 'EXTERNAL_CASH_FLOW'))
    return {"ok": True, "risk_resume": {"resume_id": resume_id, "previous_pause_reason": previous_reason, "remaining_pause_reasons": remaining, "next_account_check_required": True}}


def record_result(payload: dict[str, Any]) -> dict[str, Any]:
    """Append an immutable broker result instead of mutating the attempt."""
    result = _object(payload, "result")
    required = {"event_id", "attempt_id", "event_type", "observed_at_utc", "broker_order_reference", "payload_sha256", "payload"}
    if (set(result) != required or result["event_type"] not in {"OPENED", "REJECTED", "FAILED", "UNKNOWN"}
            or not isinstance(result["payload"], dict) or result["payload_sha256"] != _digest(result["payload"])):
        raise SystemExit("M20 broker result is invalid")
    if result["event_type"] in {"REJECTED", "UNKNOWN"}:
        diagnostic_fields = {
            "schema_version", "retcode", "broker_comment", "symbol", "action", "volume", "requested_price",
            "stop_loss", "take_profit", "deviation_points", "filling_mode", "time_mode", "magic",
            "observed_bid", "observed_ask", "spread_points", "tick_freshness_seconds", "symbol_point",
            "trade_tick_size", "stops_level_points", "freeze_level_points", "volume_min", "volume_max",
            "volume_step", "visible_positions_count", "lease_max_trades", "max_open_positions",
            "max_notional_per_trade_usd", "max_cumulative_notional_usd", "reservation_slot_number",
            "broker_order_reference", "broker_requested_price", "broker_requested_volume",
            "broker_requested_stop_loss", "broker_requested_take_profit", "position_ticket",
            "position_identifier", "fill_status", "broker_filled_volume", "position_observation_error",
        }
        if set(result["payload"]) != diagnostic_fields or result["payload"].get("schema_version") != "forex.m20.mt5-result-context.v1":
            raise SystemExit("M20 rejected broker result lacks fixed diagnostic context")
    with _connection() as conn, conn.cursor() as cursor:
        cursor.execute("SELECT 1 FROM forex.demo_execution_attempt WHERE attempt_id=%s FOR UPDATE", (result["attempt_id"],))
        if cursor.fetchone() is None:
            raise SystemExit("M20 result has no reserved execution attempt")
        cursor.execute("INSERT INTO forex.demo_position_event (event_id,attempt_id,event_type,observed_at_utc,payload_sha256,payload) VALUES (%s,%s,%s,%s,%s,%s::jsonb)", (result["event_id"], result["attempt_id"], result["event_type"], result["observed_at_utc"], result["payload_sha256"], json.dumps({"broker_order_reference": result["broker_order_reference"], **result["payload"]})))
    return {"ok": True, "recorded_event_id": result["event_id"]}


def record_open_position(payload: dict[str, Any]) -> dict[str, Any]:
    """Persist the one observed broker position for restart-safe monitoring."""
    state = _object(payload, "state")
    required = {"proposal_id", "attempt_id", "position_ticket", "action", "opened_at_utc", "observed_at_utc", "entry_price", "stop_loss", "take_profit"}
    if (set(state) != required or state["action"] not in {"BUY", "SELL"}
            or not isinstance(state["position_ticket"], int) or state["position_ticket"] <= 0
            or not all(isinstance(state[field], (int, float)) and state[field] > 0 for field in ("entry_price", "stop_loss", "take_profit"))):
        raise SystemExit("M20 open position state is invalid")
    with _connection() as conn, conn.cursor() as cursor:
        cursor.execute("SELECT attempt.proposal_id FROM forex.demo_execution_attempt attempt JOIN forex.demo_strategy_selection selection ON selection.proposal_id=attempt.proposal_id WHERE attempt.attempt_id=%s AND selection.trade_owner_id=attempt.proposal_id AND selection.trade_owner_strategy_id IN ('momentum_breakout','compression_breakout','trend_pullback','range_reversion','session_breakout') AND selection.trade_owner_strategy_id=selection.selected_strategy_id AND selection.selection_status='SELECTED_EXECUTABLE' AND EXISTS (SELECT 1 FROM forex.demo_position_event event WHERE event.attempt_id=attempt.attempt_id AND event.event_type='OPENED' AND NULLIF(event.payload->>'position_ticket','')::bigint=%s) FOR UPDATE", (state["attempt_id"], state["position_ticket"]))
        attempt = cursor.fetchone()
        if attempt is None or attempt[0] != state["proposal_id"]:
            raise SystemExit("M20 open position state does not match its reserved attempt")
        cursor.execute("INSERT INTO forex.demo_open_position_state (proposal_id,attempt_id,position_ticket,action,opened_at_utc,observed_at_utc,entry_price,stop_loss,take_profit,status) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,'OPEN')", tuple(state[field] for field in ("proposal_id", "attempt_id", "position_ticket", "action", "opened_at_utc", "observed_at_utc", "entry_price", "stop_loss", "take_profit")))
    return {"ok": True, "proposal_id": state["proposal_id"], "position_ticket": state["position_ticket"]}


def update_open_position(payload: dict[str, Any]) -> dict[str, Any]:
    """Record a broker-side SL/TP modification and refresh current state."""
    result = _object(payload, "result")
    state = _object(payload, "state")
    result_required = {"event_id", "attempt_id", "event_type", "observed_at_utc", "broker_order_reference", "payload_sha256", "payload"}
    state_required = {"proposal_id", "position_ticket", "observed_at_utc", "stop_loss", "take_profit", "break_even_applied"}
    if (set(result) != result_required or result["event_type"] != "UPDATED" or not isinstance(result["payload"], dict) or result["payload_sha256"] != _digest(result["payload"])
            or set(state) != state_required or not isinstance(state["position_ticket"], int) or state["position_ticket"] <= 0
            or not isinstance(state["break_even_applied"], bool)
            or not all(isinstance(state[field], (int, float)) and state[field] > 0 for field in ("stop_loss", "take_profit"))):
        raise SystemExit("M20 open position update is invalid")
    with _connection() as conn, conn.cursor() as cursor:
        cursor.execute("UPDATE forex.demo_open_position_state SET observed_at_utc=%s,stop_loss=%s,take_profit=%s,break_even_applied=%s,status='MONITORING',updated_at_utc=now() WHERE proposal_id=%s AND attempt_id=%s AND position_ticket=%s", (state["observed_at_utc"], state["stop_loss"], state["take_profit"], state["break_even_applied"], state["proposal_id"], result["attempt_id"], state["position_ticket"]))
        if cursor.rowcount != 1:
            raise SystemExit("M20 open position update does not match durable state")
        cursor.execute("INSERT INTO forex.demo_position_event (event_id,attempt_id,event_type,observed_at_utc,payload_sha256,payload) VALUES (%s,%s,'UPDATED',%s,%s,%s::jsonb)", (result["event_id"], result["attempt_id"], result["observed_at_utc"], result["payload_sha256"], json.dumps({"broker_order_reference": result["broker_order_reference"], **result["payload"]})))
    return {"ok": True, "recorded_event_id": result["event_id"]}


def record_closed_outcome(payload: dict[str, Any]) -> dict[str, Any]:
    """Append a CLOSED lifecycle event and its immutable realized outcome."""
    result = _object(payload, "result")
    outcome = _object(payload, "outcome")
    result_required = {"event_id", "attempt_id", "event_type", "observed_at_utc", "broker_order_reference", "payload_sha256", "payload"}
    outcome_required = {"proposal_id", "closed_at_utc", "exit_price", "gross_price_pnl_account", "commission_account", "fee_account", "swap_account", "estimated_spread_cost_account", "slippage_cost_account", "estimated_total_cost_account", "realized_pnl_account", "account_currency", "close_reason", "reconciliation_status"}
    if (set(result) != result_required or result["event_type"] != "CLOSED" or not isinstance(result["payload"], dict) or result["payload_sha256"] != _digest(result["payload"])
            or set(outcome) != outcome_required or outcome["reconciliation_status"] != "MATCHED"
            or outcome["account_currency"] != "AUD"
            or not all(isinstance(outcome[field], (int, float)) for field in ("gross_price_pnl_account", "commission_account", "fee_account", "swap_account", "estimated_spread_cost_account", "slippage_cost_account", "estimated_total_cost_account", "realized_pnl_account"))
            or outcome["estimated_spread_cost_account"] < 0 or not isinstance(outcome["exit_price"], (int, float)) or outcome["exit_price"] <= 0):
        raise SystemExit("M20 closed lifecycle outcome is invalid")
    with _connection() as conn, conn.cursor() as cursor:
        cursor.execute("SELECT proposal_id FROM forex.demo_execution_attempt WHERE attempt_id=%s FOR UPDATE", (result["attempt_id"],))
        attempt = cursor.fetchone()
        if attempt is None or attempt[0] != outcome["proposal_id"]:
            raise SystemExit("M20 closed outcome does not match its reserved attempt")
        cursor.execute("DELETE FROM forex.demo_open_position_state WHERE proposal_id=%s AND attempt_id=%s RETURNING position_ticket", (outcome["proposal_id"], result["attempt_id"]))
        if cursor.fetchone() is None:
            raise SystemExit("M20 closed outcome has no durable open position")
        cursor.execute("INSERT INTO forex.demo_position_event (event_id,attempt_id,event_type,observed_at_utc,payload_sha256,payload) VALUES (%s,%s,'CLOSED',%s,%s,%s::jsonb)", (result["event_id"], result["attempt_id"], result["observed_at_utc"], result["payload_sha256"], json.dumps({"broker_order_reference": result["broker_order_reference"], **result["payload"]})))
        cursor.execute("INSERT INTO forex.demo_trade_outcome (proposal_id,closed_at_utc,exit_price,gross_price_pnl_account,commission_account,fee_account,swap_account,estimated_spread_cost_account,slippage_cost_account,estimated_total_cost_account,realized_pnl_account,account_currency,close_reason,reconciliation_status) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'MATCHED')", (outcome["proposal_id"], outcome["closed_at_utc"], outcome["exit_price"], outcome["gross_price_pnl_account"], outcome["commission_account"], outcome["fee_account"], outcome["swap_account"], outcome["estimated_spread_cost_account"], outcome["slippage_cost_account"], outcome["estimated_total_cost_account"], outcome["realized_pnl_account"], outcome["account_currency"], outcome["close_reason"]))
        cursor.execute("UPDATE forex.demo_risk_policy_state SET expected_balance=expected_balance+%s,updated_at_utc=now() WHERE policy_version='forex.m20.conservative-risk.v1'", (outcome["realized_pnl_account"],))
    return {"ok": True, "recorded_event_id": result["event_id"], "proposal_id": outcome["proposal_id"]}



# This recovery is deliberately not a generic audit-repair API.  It can append
# only the four exact, retained broker-history mappings captured before the
# listener was released with durable open-position state.  Each source event
# remains immutable and risk accounting starts after this historic interval.
_HISTORICAL_RECOVERIES = {
    "feffc714-c88f-5d34-bdca-705040a28565": ("3f40a116-bc15-5897-9062-c743b9ee5199", "SELL", 41488649, "2026-09-03T09:18:05Z", "2026-09-03T09:28:07Z", 0.18),
    "e0dac54c-6b56-5a84-9022-126c3c21e00b": ("ee9f449b-dca7-549b-81de-5efcdabcb579", "BUY", 41495536, "2026-09-03T11:18:08Z", "2026-09-03T11:21:00Z", 0.01),
    "15dffa0b-0446-500c-af09-ddce686e11f9": ("b3259891-acb5-54d8-a183-86b076dcbec1", "BUY", 41499398, "2026-09-03T12:04:03Z", "2026-09-03T12:13:02Z", -0.56),
    "c66d1af4-3d00-56a8-83e2-881f1eec416b": ("a802ff2c-2c91-57aa-a364-030a4faeb8a7", "SELL", 41499981, "2026-09-03T12:13:07Z", "2026-09-03T12:15:01Z", -0.21),
}


def record_historical_reconciliation(payload: dict[str, Any]) -> dict[str, Any]:
    """Append only validated retained MT5 history for four legacy attempts.

    It cannot close a current position and deliberately leaves the conservative
    risk policy state untouched: its baseline was initialized after these
    historic broker closes, so applying their P&L now would mimic cash flow.
    """
    recoveries = payload.get("recoveries")
    if not isinstance(recoveries, list) or len(recoveries) != len(_HISTORICAL_RECOVERIES):
        raise SystemExit("M20 historical reconciliation must contain the exact retained attempt set")
    observed_ids = [item.get("attempt_id") if isinstance(item, dict) else None for item in recoveries]
    if set(observed_ids) != set(_HISTORICAL_RECOVERIES) or len(set(observed_ids)) != len(observed_ids):
        raise SystemExit("M20 historical reconciliation attempt set is not fixed")
    required = {"attempt_id", "proposal_id", "action", "position_identifier", "closed_at_utc", "exit_price", "gross_price_pnl_account", "commission_account", "fee_account", "swap_account", "realized_pnl_account", "account_currency", "broker_order_reference", "broker_deals", "broker_deals_sha256"}
    normalized: list[dict[str, Any]] = []
    for item in recoveries:
        if not isinstance(item, dict) or set(item) != required:
            raise SystemExit("M20 historical reconciliation row is invalid")
        expected = _HISTORICAL_RECOVERIES[item["attempt_id"]]
        proposal_id, action, position_id, opened_at, closed_at, expected_net = expected
        if (item["proposal_id"], item["action"], item["position_identifier"]) != (proposal_id, action, position_id):
            raise SystemExit("M20 historical reconciliation mapping differs from retained broker attribution")
        if (item["account_currency"] != "AUD" or not isinstance(item["broker_order_reference"], str)
                or not isinstance(item["broker_deals"], list) or len(item["broker_deals"]) != 2
                or item["broker_deals_sha256"] != _digest(item["broker_deals"])
                or not isinstance(item["exit_price"], (int, float)) or item["exit_price"] <= 0
                or not all(isinstance(item[field], (int, float)) for field in ("gross_price_pnl_account", "commission_account", "fee_account", "swap_account", "realized_pnl_account"))):
            raise SystemExit("M20 historical reconciliation broker result is invalid")
        deals = item["broker_deals"]
        opening, closing = deals
        expected_open_type, expected_close_type = (1, 0) if action == "SELL" else (0, 1)
        expected_deal_fields = {"ticket", "order", "position_identifier", "broker_time_utc", "time_utc", "entry", "type", "volume", "price", "profit", "commission", "swap", "fee", "reason", "symbol"}
        if (any(not isinstance(deal, dict) or set(deal) != expected_deal_fields for deal in deals)
                or opening["position_identifier"] != position_id or closing["position_identifier"] != position_id
                or opening["symbol"] != "EURUSD" or closing["symbol"] != "EURUSD"
                or opening["time_utc"] != opened_at or closing["time_utc"] != closed_at or item["closed_at_utc"] != closed_at
                or opening["entry"] != 0 or closing["entry"] != 1
                or opening["type"] != expected_open_type or closing["type"] != expected_close_type
                or not all(isinstance(deal[field], (int, float)) and deal[field] > 0 for deal in deals for field in ("ticket", "order", "volume", "price"))
                or not all(abs(float(deal["volume"]) - 0.01) <= 1e-9 for deal in deals)
                or any(float(deal[field]) != 0.0 for deal in deals for field in ("commission", "fee", "swap"))):
            raise SystemExit("M20 historical reconciliation deal set differs from retained broker attribution")
        if (round(item["gross_price_pnl_account"] + item["commission_account"] + item["fee_account"] + item["swap_account"], 2) != round(item["realized_pnl_account"], 2)
                or round(item["realized_pnl_account"], 2) != expected_net):
            raise SystemExit("M20 historical reconciliation net P&L does not reconcile")
        normalized.append(item)
    with _connection() as conn, conn.cursor() as cursor:
        for item in normalized:
            cursor.execute(
                "SELECT p.action, EXISTS(SELECT 1 FROM forex.demo_trade_outcome o WHERE o.proposal_id=a.proposal_id), EXISTS(SELECT 1 FROM forex.demo_position_event e WHERE e.attempt_id=a.attempt_id AND e.event_type='CLOSED'), EXISTS(SELECT 1 FROM forex.demo_position_event e WHERE e.attempt_id=a.attempt_id AND e.event_type='OPENED'), EXISTS(SELECT 1 FROM forex.demo_position_event e WHERE e.attempt_id=a.attempt_id AND e.event_type='FAILED') FROM forex.demo_execution_attempt a JOIN forex.demo_trade_proposal p ON p.proposal_id=a.proposal_id WHERE a.attempt_id=%s AND a.proposal_id=%s FOR UPDATE",
                (item["attempt_id"], item["proposal_id"]),
            )
            state = cursor.fetchone()
            if state is None or state != (item["action"], False, False, True, True):
                raise SystemExit("M20 historical reconciliation source lifecycle is not the fixed legacy state")
            event_payload = {
                "schema_version": "forex.m20.historical-reconciliation.v1",
                "reason": "RETAINED_BROKER_HISTORY_EXACT_POSITION_MATCH",
                "position_identifier": item["position_identifier"],
                "closed_volume": 0.01,
                "broker_deals": item["broker_deals"],
                "broker_deals_sha256": item["broker_deals_sha256"],
            }
            event_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{item['attempt_id']}:historical-retained-close:v1"))
            cursor.execute("INSERT INTO forex.demo_position_event (event_id,attempt_id,event_type,observed_at_utc,payload_sha256,payload) VALUES (%s,%s,'CLOSED',now(),%s,%s::jsonb)", (event_id, item["attempt_id"], _digest(event_payload), json.dumps({"broker_order_reference": item["broker_order_reference"], **event_payload})))
            cursor.execute("INSERT INTO forex.demo_trade_outcome (proposal_id,closed_at_utc,exit_price,gross_price_pnl_account,commission_account,fee_account,swap_account,estimated_spread_cost_account,slippage_cost_account,estimated_total_cost_account,realized_pnl_account,account_currency,close_reason,reconciliation_status) VALUES (%s,%s,%s,%s,%s,%s,%s,NULL,NULL,NULL,%s,'AUD','RETAINED_BROKER_HISTORY_EXACT_POSITION_MATCH','MATCHED')", (item["proposal_id"], item["closed_at_utc"], item["exit_price"], item["gross_price_pnl_account"], item["commission_account"], item["fee_account"], item["swap_account"], item["realized_pnl_account"]))
            revision_id = "historical-retained-broker-reconciliation:" + item["attempt_id"]
            original = {"legacy_attempt_without_outcome": True, "legacy_events": ["OPENED", "FAILED"]}
            cursor.execute("INSERT INTO forex.demo_outcome_reconciliation_revision (revision_id,proposal_id,disposition,observed_at_utc,reason_code,original_outcome,broker_position_id,broker_deals,broker_deals_sha256,repaired_closed_at_utc,repaired_exit_price,repaired_gross_price_pnl_account,repaired_commission_account,repaired_swap_account,repaired_realized_pnl_account,repaired_account_currency) VALUES (%s,%s,'REPAIRED',now(),'RETAINED_BROKER_HISTORY_EXACT_POSITION_MATCH',%s::jsonb,%s,%s::jsonb,%s,%s,%s,%s,%s,%s,%s,'AUD')", (revision_id, item["proposal_id"], json.dumps(original), item["position_identifier"], json.dumps(item["broker_deals"]), item["broker_deals_sha256"], item["closed_at_utc"], item["exit_price"], item["gross_price_pnl_account"], item["commission_account"], item["swap_account"], item["realized_pnl_account"]))
    return {"ok": True, "marker": "FOREX_M20_HISTORICAL_RECONCILIATION_APPENDED", "attempt_ids": observed_ids, "risk_policy_state_changed": False}

def load_open_positions(payload: dict[str, Any]) -> dict[str, Any]:
    """Return only durable M20 monitor context; this is a fixed read surface."""
    if payload:
        raise SystemExit("M20 open-position recovery accepts no arguments")
    with _connection() as conn, conn.cursor() as cursor:
        cursor.execute(
            """SELECT state.proposal_id,p.action,p.proposed_entry,p.stop_loss,a.attempt_id,a.submitted_at_utc,
                      state.position_ticket,state.entry_price,state.stop_loss,state.take_profit,state.break_even_applied,
                      snapshot.ask-snapshot.bid,
                      COALESCE((SELECT COALESCE(event.payload->>'broker_filled_volume',event.payload->>'volume') FROM forex.demo_position_event event
                                WHERE event.attempt_id=a.attempt_id AND event.event_type='OPENED'
                                ORDER BY event.observed_at_utc DESC LIMIT 1),''),
                      COALESCE((SELECT event.payload->>'position_identifier' FROM forex.demo_position_event event
                                WHERE event.attempt_id=a.attempt_id AND event.event_type='OPENED'
                                ORDER BY event.observed_at_utc DESC LIMIT 1),''),selection.trade_owner_strategy_id
                 FROM forex.demo_open_position_state state
                 JOIN forex.demo_trade_proposal p ON p.proposal_id=state.proposal_id
                 JOIN forex.demo_execution_attempt a ON a.attempt_id=state.attempt_id
                 JOIN forex.demo_decision_snapshot snapshot ON snapshot.proposal_id=p.proposal_id
                 JOIN forex.demo_strategy_selection selection ON selection.proposal_id=p.proposal_id
                ORDER BY state.opened_at_utc"""
        )
        rows = cursor.fetchall()
    positions = []
    for row in rows:
        try:
            # Column 11 is the decision snapshot's entry spread.  The
            # broker-recorded OPENED-event volume follows it at column 12.
            # Treating the spread as lots makes restart recovery refuse a
            # perfectly valid open position as having no measurable volume.
            volume = float(row[12])
        except (TypeError, ValueError):
            volume = 0.0
        positions.append({
            "proposal_id": row[0], "action": row[1], "proposed_entry": float(row[2]),
            "initial_stop_loss": float(row[3]), "attempt_id": row[4], "submitted_at_utc": row[5].astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
            "position_ticket": int(row[6]), "entry_price": float(row[7]),
            "stop_loss": float(row[8]), "take_profit": float(row[9]),
            "break_even_applied": bool(row[10]), "entry_spread": float(row[11]), "volume": volume,
            "position_identifier": int(row[13]) if row[13] else int(row[6]),
            "trade_owner_strategy_id": row[14],
        })
    return {"ok": True, "open_positions": positions}


def reconcile(payload: dict[str, Any]) -> dict[str, Any]:
    """Read back the immutable lifecycle for one fixed persisted proposal."""
    proposal_id = payload.get("proposal_id")
    if not isinstance(proposal_id, str) or not proposal_id:
        raise SystemExit("M20 reconciliation proposal id is invalid")
    with _connection() as conn, conn.cursor() as cursor:
        cursor.execute("SELECT p.session_id,p.action,s.snapshot_id,a.attempt_id,COALESCE(array_agg(e.event_type) FILTER (WHERE e.event_id IS NOT NULL), ARRAY[]::text[]),o.closed_at_utc,o.exit_price,o.realized_pnl_account,o.account_currency,o.close_reason,o.reconciliation_status,o.gross_price_pnl_account,o.commission_account,o.fee_account,o.swap_account,o.estimated_spread_cost_account,o.slippage_cost_account,o.estimated_total_cost_account,state.position_ticket,state.entry_price,state.stop_loss,state.take_profit,state.break_even_applied FROM forex.demo_trade_proposal p JOIN forex.demo_decision_snapshot s ON s.proposal_id=p.proposal_id LEFT JOIN forex.demo_execution_attempt a ON a.proposal_id=p.proposal_id LEFT JOIN forex.demo_position_event e ON e.attempt_id=a.attempt_id LEFT JOIN forex.demo_trade_outcome o ON o.proposal_id=p.proposal_id LEFT JOIN forex.demo_open_position_state state ON state.proposal_id=p.proposal_id WHERE p.proposal_id=%s GROUP BY p.session_id,p.action,s.snapshot_id,a.attempt_id,o.closed_at_utc,o.exit_price,o.realized_pnl_account,o.account_currency,o.close_reason,o.reconciliation_status,o.gross_price_pnl_account,o.commission_account,o.fee_account,o.swap_account,o.estimated_spread_cost_account,o.slippage_cost_account,o.estimated_total_cost_account,state.position_ticket,state.entry_price,state.stop_loss,state.take_profit,state.break_even_applied", (proposal_id,))
        row = cursor.fetchone()
        if row is None:
            raise SystemExit("M20 reconciliation proposal is absent")
    closed_and_outcome = row[3] is not None and "CLOSED" in row[4] and row[5] is not None and row[10] == "MATCHED"
    terminal_rejection = row[3] is not None and "REJECTED" in row[4]
    open_reconciled = row[3] is not None and "OPENED" in row[4] and row[18] is not None and not closed_and_outcome
    status = "NO_TRADE_RECONCILED" if row[1] == "NO_TRADE" and row[3] is None else ("MATCHED" if closed_and_outcome or terminal_rejection else ("OPEN_RECONCILED" if open_reconciled else "PENDING"))
    reconciliation = {"session_id": row[0], "proposal_id": proposal_id, "snapshot_id": row[2], "execution_attempt_id": row[3], "status": status}
    if closed_and_outcome:
        reconciliation["outcome"] = {"proposal_id": proposal_id, "closed_at_utc": row[5].astimezone(timezone.utc).isoformat().replace("+00:00", "Z"), "exit_price": float(row[6]), "realized_pnl_account": float(row[7]), "account_currency": row[8], "close_reason": row[9], "costs": {"gross_price_pnl_account": float(row[11]), "commission_account": float(row[12]), "fee_account": float(row[13]), "swap_account": float(row[14]), "estimated_spread_cost_account": float(row[15]), "slippage_cost_account": float(row[16]), "estimated_total_cost_account": float(row[17])}}
    elif open_reconciled:
        reconciliation["position"] = {"position_ticket": int(row[18]), "entry_price": float(row[19]), "stop_loss": float(row[20]), "take_profit": float(row[21]), "break_even_applied": bool(row[22])}
    return {"ok": True, "reconciliation": reconciliation}


def main() -> int:
    command = sys.argv[1] if len(sys.argv) == 2 else ""
    actions = {"persist-proposal": persist_proposal, "reserve-execution": reserve_execution, "enforce-risk-policy": enforce_risk_policy, "resume-risk-policy": resume_risk_policy, "pause-unknown-account-state": pause_unknown_account_state, "record-result": record_result, "record-open-position": record_open_position, "update-open-position": update_open_position, "record-closed-outcome": record_closed_outcome, "record-historical-reconciliation": record_historical_reconciliation, "load-open-positions": load_open_positions, "reconcile": reconcile}
    if command not in actions:
        raise SystemExit("M20 audit bridge command is not fixed")
    print(json.dumps(actions[command](_payload()), separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
