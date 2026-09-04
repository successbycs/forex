"""Fixed local PostgreSQL-audit bridge contract for the M20 T480 session.

This bridge is intentionally invoked only by the hash-bound M20 session
runner.  It accepts no database host, SQL, server, symbol, or transaction
argument.  Its deployment requires a machine-local ``FOREX_M20_POSTGRES_DSN``
and a Python environment with psycopg; absent prerequisites fail closed.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import timezone
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
    if (not isinstance(value["max_trades"], int) or not 1 <= value["max_trades"] <= 10
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


def persist_proposal(payload: dict[str, Any]) -> dict[str, Any]:
    """Persist immutable proposal and snapshot before any broker submission."""
    session, proposal = _session(payload), _proposal(payload)
    snapshot = _snapshot(payload, proposal)
    selection = _strategy_selection(payload, proposal)
    assessments = _strategy_assessments(payload)
    revision, fingerprint = _metadata(payload)
    with _connection() as conn, conn.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", (session["session_id"],))
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
    receipt = {"session_id": session["session_id"], "proposal_id": proposal["proposal_id"], "snapshot_id": snapshot["snapshot_id"]}
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
    required = {"attempt_id", "idempotency_key", "submitted_at_utc", "redacted_result", "broker_open_positions"}
    if set(reservation) != required or reservation["broker_open_positions"] != 0:
        raise SystemExit("M20 reservation must observe no open EURUSD position")
    with _connection() as conn, conn.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", (session["session_id"],))
        cursor.execute("SELECT status,expires_at_utc > now(),max_trades,max_notional_usd,max_cumulative_notional_usd,max_open_positions FROM forex.demo_trade_session WHERE session_id=%s AND starts_at_utc=%s AND expires_at_utc=%s FOR UPDATE", (session["session_id"], session["starts_at_utc"], session["expires_at_utc"]))
        row = cursor.fetchone()
        if row is None or row[0] != "ACTIVE" or row[1] is not True or tuple(row[2:]) != (session["max_trades"], session["max_notional_per_trade_usd"], session["max_cumulative_notional_usd"], 1):
            raise SystemExit("M20 session is inactive or differs from fixed limits")
        cursor.execute("SELECT 1 FROM forex.demo_trade_proposal p JOIN forex.demo_decision_snapshot s ON s.proposal_id=p.proposal_id JOIN forex.demo_strategy_selection selection ON selection.proposal_id=p.proposal_id WHERE p.proposal_id=%s AND p.session_id=%s AND p.action IN ('BUY','SELL') AND p.expires_at_utc >= now() AND selection.selection_status='SELECTED_EXECUTABLE' AND selection.selected_strategy_id IN ('momentum_breakout','compression_breakout','trend_pullback','range_reversion','session_breakout') AND selection.trade_owner_strategy_id=selection.selected_strategy_id AND selection.cost_coverage_status='FEASIBLE' FOR UPDATE", (proposal["proposal_id"], session["session_id"]))
        if cursor.fetchone() is None:
            raise SystemExit("M20 proposal is absent, unpersisted, expired, or non-actionable")
        cursor.execute("SELECT count(*) FROM forex.demo_execution_attempt WHERE session_id=%s", (session["session_id"],))
        if cursor.fetchone()[0] >= session["max_trades"]:
            raise SystemExit("M20 maximum trade count is reached")
        cursor.execute("SELECT COALESCE(sum(p.notional_usd),0) FROM forex.demo_execution_attempt a JOIN forex.demo_trade_proposal p ON p.proposal_id=a.proposal_id WHERE a.session_id=%s", (session["session_id"],))
        if float(cursor.fetchone()[0]) + float(proposal["notional_usd"]) > float(session["max_cumulative_notional_usd"]):
            raise SystemExit("M20 cumulative notional cap is reached")
        cursor.execute("SELECT count(*) FROM forex.demo_execution_attempt a LEFT JOIN forex.demo_trade_outcome o ON o.proposal_id=a.proposal_id WHERE o.proposal_id IS NULL AND NOT EXISTS (SELECT 1 FROM forex.demo_position_event e WHERE e.attempt_id=a.attempt_id AND e.event_type IN ('REJECTED','FAILED'))")
        if cursor.fetchone()[0] != 0:
            raise SystemExit("M20 global one-position limit is reached")
        cursor.execute("SELECT slot_number FROM forex.demo_trade_slot WHERE session_id=%s AND proposal_id IS NULL ORDER BY slot_number FOR UPDATE SKIP LOCKED LIMIT 1", (session["session_id"],))
        slot = cursor.fetchone()
        if slot is None:
            raise SystemExit("M20 no unclaimed execution slot remains")
        cursor.execute("UPDATE forex.demo_trade_slot SET proposal_id=%s,claimed_at_utc=%s WHERE session_id=%s AND slot_number=%s AND proposal_id IS NULL", (proposal["proposal_id"], reservation["submitted_at_utc"], session["session_id"], slot[0]))
        if cursor.rowcount != 1:
            raise SystemExit("M20 execution slot claim lost its atomic race")
        cursor.execute("INSERT INTO forex.demo_execution_attempt (attempt_id,proposal_id,session_id,slot_number,idempotency_key,submitted_at_utc,status,redacted_result) VALUES (%s,%s,%s,%s,%s,%s,'SUBMITTED',%s)", (reservation["attempt_id"], proposal["proposal_id"], session["session_id"], slot[0], reservation["idempotency_key"], reservation["submitted_at_utc"], reservation["redacted_result"]))
    receipt = {"session_id": session["session_id"], "proposal_id": proposal["proposal_id"], "snapshot_id": proposal["snapshot_id"], "execution_attempt_id": reservation["attempt_id"], "slot_number": slot[0]}
    return {"ok": True, "reservation": receipt, "postgres_audit": {**receipt, "record_sha256": _digest(receipt)}}


def record_result(payload: dict[str, Any]) -> dict[str, Any]:
    """Append an immutable broker result instead of mutating the attempt."""
    result = _object(payload, "result")
    required = {"event_id", "attempt_id", "event_type", "observed_at_utc", "broker_order_reference", "payload_sha256", "payload"}
    if set(result) != required or result["event_type"] not in {"OPENED", "REJECTED", "FAILED"} or not isinstance(result["payload"], dict):
        raise SystemExit("M20 broker result is invalid")
    if result["event_type"] == "REJECTED":
        diagnostic_fields = {
            "schema_version", "retcode", "broker_comment", "symbol", "action", "volume", "requested_price",
            "stop_loss", "take_profit", "deviation_points", "filling_mode", "time_mode", "magic",
            "observed_bid", "observed_ask", "spread_points", "tick_freshness_seconds", "symbol_point",
            "trade_tick_size", "stops_level_points", "freeze_level_points", "volume_min", "volume_max",
            "volume_step", "visible_positions_count", "lease_max_trades", "max_open_positions",
            "max_notional_per_trade_usd", "max_cumulative_notional_usd", "reservation_slot_number",
            "broker_order_reference", "broker_requested_price", "broker_requested_volume",
            "broker_requested_stop_loss", "broker_requested_take_profit", "position_ticket",
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
        cursor.execute("SELECT attempt.proposal_id FROM forex.demo_execution_attempt attempt JOIN forex.demo_strategy_selection selection ON selection.proposal_id=attempt.proposal_id WHERE attempt.attempt_id=%s AND selection.trade_owner_id=attempt.proposal_id AND selection.trade_owner_strategy_id IN ('momentum_breakout','compression_breakout','trend_pullback','range_reversion','session_breakout') AND selection.trade_owner_strategy_id=selection.selected_strategy_id AND selection.selection_status='SELECTED_EXECUTABLE' FOR UPDATE", (state["attempt_id"],))
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
    if (set(result) != result_required or result["event_type"] != "UPDATED" or not isinstance(result["payload"], dict)
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
    outcome_required = {"proposal_id", "closed_at_utc", "exit_price", "gross_price_pnl_account", "commission_account", "swap_account", "estimated_spread_cost_account", "slippage_cost_account", "estimated_total_cost_account", "realized_pnl_account", "account_currency", "close_reason", "reconciliation_status"}
    if (set(result) != result_required or result["event_type"] != "CLOSED" or not isinstance(result["payload"], dict)
            or set(outcome) != outcome_required or outcome["reconciliation_status"] != "MATCHED"
            or outcome["account_currency"] != "AUD"
            or not all(isinstance(outcome[field], (int, float)) for field in ("gross_price_pnl_account", "commission_account", "swap_account", "estimated_spread_cost_account", "slippage_cost_account", "estimated_total_cost_account", "realized_pnl_account"))
            or outcome["estimated_spread_cost_account"] < 0):
        raise SystemExit("M20 closed lifecycle outcome is invalid")
    with _connection() as conn, conn.cursor() as cursor:
        cursor.execute("SELECT proposal_id FROM forex.demo_execution_attempt WHERE attempt_id=%s FOR UPDATE", (result["attempt_id"],))
        attempt = cursor.fetchone()
        if attempt is None or attempt[0] != outcome["proposal_id"]:
            raise SystemExit("M20 closed outcome does not match its reserved attempt")
        cursor.execute("DELETE FROM forex.demo_open_position_state WHERE proposal_id=%s AND attempt_id=%s", (outcome["proposal_id"], result["attempt_id"]))
        cursor.execute("INSERT INTO forex.demo_position_event (event_id,attempt_id,event_type,observed_at_utc,payload_sha256,payload) VALUES (%s,%s,'CLOSED',%s,%s,%s::jsonb)", (result["event_id"], result["attempt_id"], result["observed_at_utc"], result["payload_sha256"], json.dumps({"broker_order_reference": result["broker_order_reference"], **result["payload"]})))
        cursor.execute("INSERT INTO forex.demo_trade_outcome (proposal_id,closed_at_utc,exit_price,gross_price_pnl_account,commission_account,swap_account,estimated_spread_cost_account,slippage_cost_account,estimated_total_cost_account,realized_pnl_account,account_currency,close_reason,reconciliation_status) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'MATCHED')", (outcome["proposal_id"], outcome["closed_at_utc"], outcome["exit_price"], outcome["gross_price_pnl_account"], outcome["commission_account"], outcome["swap_account"], outcome["estimated_spread_cost_account"], outcome["slippage_cost_account"], outcome["estimated_total_cost_account"], outcome["realized_pnl_account"], outcome["account_currency"], outcome["close_reason"]))
    return {"ok": True, "recorded_event_id": result["event_id"], "proposal_id": outcome["proposal_id"]}


def archive_history_unavailable_positions(payload: dict[str, Any]) -> dict[str, Any]:
    """Terminally retain old missing-history positions without inventing P&L.

    This is a deliberately narrow MVP recovery action.  It can be called only
    after the fixed MT5 runner has observed zero owned EURUSD positions and
    only for durable rows whose broker history has no priced market deal.  It
    appends a FAILED event containing that broker diagnostic, then removes the
    mutable *open* projection.  It never fabricates a close, fee, or outcome.
    """
    required = {"broker_open_position_count", "reason", "attempts"}
    if set(payload) != required or payload["broker_open_position_count"] != 0 or payload["reason"] != "BROKER_HISTORY_UNAVAILABLE":
        raise SystemExit("M20 history-unavailable archival payload is invalid")
    attempts = payload["attempts"]
    if not isinstance(attempts, list) or not attempts:
        raise SystemExit("M20 history-unavailable archival attempts are invalid")
    normalized: list[tuple[str, str]] = []
    for item in attempts:
        if not isinstance(item, dict) or set(item) != {"attempt_id", "history_diagnostic"}:
            raise SystemExit("M20 history-unavailable archival item is invalid")
        attempt_id, diagnostic = item["attempt_id"], item["history_diagnostic"]
        if not isinstance(attempt_id, str) or not attempt_id or not isinstance(diagnostic, str) or not diagnostic.startswith("M20 close deal history has no priced market deal"):
            raise SystemExit("M20 history-unavailable archival item is not broker-derived")
        normalized.append((attempt_id, diagnostic))
    if len({attempt_id for attempt_id, _ in normalized}) != len(normalized):
        raise SystemExit("M20 history-unavailable archival repeats an attempt")
    with _connection() as conn, conn.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(hashtextextended('forex.m20.history-unavailable', 0))")
        for attempt_id, diagnostic in normalized:
            cursor.execute(
                """SELECT state.proposal_id
                     FROM forex.demo_open_position_state state
                     JOIN forex.demo_execution_attempt attempt ON attempt.attempt_id=state.attempt_id
                     LEFT JOIN forex.demo_trade_outcome outcome ON outcome.proposal_id=state.proposal_id
                    WHERE state.attempt_id=%s AND outcome.proposal_id IS NULL
                      AND EXISTS (SELECT 1 FROM forex.demo_position_event opened WHERE opened.attempt_id=state.attempt_id AND opened.event_type='OPENED')
                      AND NOT EXISTS (SELECT 1 FROM forex.demo_position_event terminal WHERE terminal.attempt_id=state.attempt_id AND terminal.event_type IN ('CLOSED','REJECTED','FAILED'))
                    FOR UPDATE OF state""",
                (attempt_id,),
            )
            if cursor.fetchone() is None:
                raise SystemExit("M20 history-unavailable archival target is not a sole unresolved open position")
            event_payload = {
                "reason": "BROKER_HISTORY_UNAVAILABLE",
                "broker_open_position_count": 0,
                "history_diagnostic": diagnostic,
            }
            event_id = f"{attempt_id}:broker-history-unavailable"
            cursor.execute(
                """INSERT INTO forex.demo_position_event
                   (event_id,attempt_id,event_type,observed_at_utc,payload_sha256,payload)
                   VALUES (%s,%s,'FAILED',now(),%s,%s::jsonb)
                   ON CONFLICT (event_id) DO NOTHING""",
                (event_id, attempt_id, _digest(event_payload), json.dumps(event_payload)),
            )
            cursor.execute("DELETE FROM forex.demo_open_position_state WHERE attempt_id=%s", (attempt_id,))
            if cursor.rowcount != 1:
                raise SystemExit("M20 history-unavailable archival did not remove its mutable open projection")
    return {"ok": True, "archived_attempt_ids": [attempt_id for attempt_id, _ in normalized], "disposition": "HISTORY_UNAVAILABLE"}


def load_open_positions(payload: dict[str, Any]) -> dict[str, Any]:
    """Return only durable M20 monitor context; this is a fixed read surface."""
    if payload:
        raise SystemExit("M20 open-position recovery accepts no arguments")
    with _connection() as conn, conn.cursor() as cursor:
        cursor.execute(
            """SELECT state.proposal_id,p.action,p.proposed_entry,a.attempt_id,a.submitted_at_utc,
                      state.position_ticket,state.entry_price,state.stop_loss,state.take_profit,state.break_even_applied,
                      snapshot.ask-snapshot.bid,
                      COALESCE((SELECT event.payload->>'volume' FROM forex.demo_position_event event
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
            volume = float(row[11])
        except (TypeError, ValueError):
            volume = 0.0
        positions.append({
            "proposal_id": row[0], "action": row[1], "proposed_entry": float(row[2]),
            "attempt_id": row[3], "submitted_at_utc": row[4].astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
            "position_ticket": int(row[5]), "entry_price": float(row[6]),
            "stop_loss": float(row[7]), "take_profit": float(row[8]),
            "break_even_applied": bool(row[9]), "entry_spread": float(row[10]), "volume": volume,
            "trade_owner_strategy_id": row[12],
        })
    return {"ok": True, "open_positions": positions}


def reconcile(payload: dict[str, Any]) -> dict[str, Any]:
    """Read back the immutable lifecycle for one fixed persisted proposal."""
    proposal_id = payload.get("proposal_id")
    if not isinstance(proposal_id, str) or not proposal_id:
        raise SystemExit("M20 reconciliation proposal id is invalid")
    with _connection() as conn, conn.cursor() as cursor:
        cursor.execute("SELECT p.session_id,p.action,s.snapshot_id,a.attempt_id,COALESCE(array_agg(e.event_type) FILTER (WHERE e.event_id IS NOT NULL), ARRAY[]::text[]),o.closed_at_utc,o.exit_price,o.realized_pnl_account,o.account_currency,o.close_reason,o.reconciliation_status,o.gross_price_pnl_account,o.commission_account,o.swap_account,o.estimated_spread_cost_account,o.slippage_cost_account,o.estimated_total_cost_account,state.position_ticket,state.entry_price,state.stop_loss,state.take_profit,state.break_even_applied FROM forex.demo_trade_proposal p JOIN forex.demo_decision_snapshot s ON s.proposal_id=p.proposal_id LEFT JOIN forex.demo_execution_attempt a ON a.proposal_id=p.proposal_id LEFT JOIN forex.demo_position_event e ON e.attempt_id=a.attempt_id LEFT JOIN forex.demo_trade_outcome o ON o.proposal_id=p.proposal_id LEFT JOIN forex.demo_open_position_state state ON state.proposal_id=p.proposal_id WHERE p.proposal_id=%s GROUP BY p.session_id,p.action,s.snapshot_id,a.attempt_id,o.closed_at_utc,o.exit_price,o.realized_pnl_account,o.account_currency,o.close_reason,o.reconciliation_status,o.gross_price_pnl_account,o.commission_account,o.swap_account,o.estimated_spread_cost_account,o.slippage_cost_account,o.estimated_total_cost_account,state.position_ticket,state.entry_price,state.stop_loss,state.take_profit,state.break_even_applied", (proposal_id,))
        row = cursor.fetchone()
        if row is None:
            raise SystemExit("M20 reconciliation proposal is absent")
    closed_and_outcome = row[3] is not None and "CLOSED" in row[4] and row[5] is not None and row[10] == "MATCHED"
    terminal_rejection = row[3] is not None and ("REJECTED" in row[4] or "FAILED" in row[4])
    open_reconciled = row[3] is not None and "OPENED" in row[4] and row[17] is not None and not closed_and_outcome
    status = "NO_TRADE_RECONCILED" if row[1] == "NO_TRADE" and row[3] is None else ("MATCHED" if closed_and_outcome or terminal_rejection else ("OPEN_RECONCILED" if open_reconciled else "PENDING"))
    reconciliation = {"session_id": row[0], "proposal_id": proposal_id, "snapshot_id": row[2], "execution_attempt_id": row[3], "status": status}
    if closed_and_outcome:
        reconciliation["outcome"] = {"proposal_id": proposal_id, "closed_at_utc": row[5].astimezone(timezone.utc).isoformat().replace("+00:00", "Z"), "exit_price": float(row[6]), "realized_pnl_account": float(row[7]), "account_currency": row[8], "close_reason": row[9], "costs": {"gross_price_pnl_account": float(row[11]), "commission_account": float(row[12]), "swap_account": float(row[13]), "estimated_spread_cost_account": float(row[14]), "slippage_cost_account": float(row[15]), "estimated_total_cost_account": float(row[16])}}
    elif open_reconciled:
        reconciliation["position"] = {"position_ticket": int(row[17]), "entry_price": float(row[18]), "stop_loss": float(row[19]), "take_profit": float(row[20]), "break_even_applied": bool(row[21])}
    return {"ok": True, "reconciliation": reconciliation}


def main() -> int:
    command = sys.argv[1] if len(sys.argv) == 2 else ""
    actions = {"persist-proposal": persist_proposal, "reserve-execution": reserve_execution, "record-result": record_result, "record-open-position": record_open_position, "update-open-position": update_open_position, "record-closed-outcome": record_closed_outcome, "archive-history-unavailable-positions": archive_history_unavailable_positions, "load-open-positions": load_open_positions, "reconcile": reconcile}
    if command not in actions:
        raise SystemExit("M20 audit bridge command is not fixed")
    print(json.dumps(actions[command](_payload()), separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
