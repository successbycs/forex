#!/usr/bin/env python3
"""Fail-closed M20 Demo trading evidence bundle construction and verification.

This helper never contacts MT5, PostgreSQL, T480, or any broker.  Capture is
performed by the fixed no-argument adapter operation in the shell wrapper;
this module only validates and binds the retained result.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


class VerificationError(RuntimeError):
    """Raised when evidence is incomplete, inconsistent, or unsafe."""


SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")
HEX256 = re.compile(r"^[0-9a-f]{64}$")
MAX_SNAPSHOT_AGE = timedelta(seconds=30)
MAX_PROPOSAL_AGE = timedelta(minutes=5)
REQUIRED_ARTIFACTS = {
    "tests.txt",
    "governance.txt",
    "configuration.json",
    "demo-trading-operation.json",
    "lifecycle-summary.json",
    "listener-diagnostics.json",
    "listener-status.json",
    "session-audit.json",
    "revision.txt",
    "summary.txt",
}
M20_EVIDENCE_SURFACE = "continuous cap-constrained automated GOMarketsMU-Demo EUR/USD M1 trading session"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise VerificationError(message)


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise VerificationError(f"invalid JSON artifact: {path.name}") from error
    require(isinstance(value, dict), f"JSON artifact must be an object: {path.name}")
    return value


def utc(value: Any, field: str) -> datetime:
    require(isinstance(value, str) and value, f"{field} must be a non-empty UTC timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise VerificationError(f"{field} is not an ISO-8601 timestamp") from error
    require(parsed.tzinfo is not None, f"{field} must include a timezone")
    return parsed.astimezone(timezone.utc)


def string(value: Any, field: str) -> str:
    require(isinstance(value, str) and value.strip(), f"{field} must be a non-empty string")
    return value


def sha256(value: Any, field: str) -> str:
    result = string(value, field)
    require(SHA256.fullmatch(result) is not None, f"{field} must be a sha256 digest")
    return result


def object_field(value: dict[str, Any], name: str) -> dict[str, Any]:
    result = value.get(name)
    require(isinstance(result, dict), f"{name} must be an object")
    return result


def ensure_no_live_reference(value: Any) -> None:
    serialized = json.dumps(value, sort_keys=True, separators=(",", ":"))
    require("GOMarketsMU-Live" not in serialized, "M20 evidence must not contain a Live-server reference")


def parse_operation(wrapper: dict[str, Any], expected_fingerprint: str | None = None) -> dict[str, Any]:
    """Validate the fixed adapter wrapper and return its structured operation result."""
    ensure_no_live_reference(wrapper)
    require(wrapper.get("tool_id") == "forex_t480", "operation must be emitted by the Forex T480 adapter")
    require(wrapper.get("operation") == "m20_demo_trading_session", "operation is not the fixed M20 Demo session")
    require(wrapper.get("ok") is True, "adapter wrapper reports failure")
    result = object_field(wrapper, "result")
    require(result.get("ok") is True and result.get("exit_code") == 0, "fixed M20 operation did not exit successfully")
    stdout = string(result.get("stdout"), "operation result.stdout")
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError as error:
        raise VerificationError("operation stdout is not structured JSON") from error
    require(isinstance(payload, dict), "operation stdout must be a JSON object")
    ensure_no_live_reference(payload)
    require(payload.get("schema_version") == "forex.m20.demo-trading-operation.v1", "operation schema version mismatch")
    require(payload.get("marker") == "FOREX_M20_DEMO_TRADING_OPERATION_OK", "operation marker mismatch")
    require(payload.get("server") == "GOMarketsMU-Demo", "operation server is not GOMarketsMU-Demo")
    require(payload.get("symbol") == "EURUSD", "operation symbol is not EURUSD")
    utc(payload.get("captured_at_utc"), "operation.captured_at_utc")
    if expected_fingerprint is not None:
        require(wrapper.get("configuration_fingerprint") == expected_fingerprint, "adapter fingerprint does not match manifest")
        require(payload.get("configuration_fingerprint") == expected_fingerprint, "operation fingerprint does not match manifest")
    return payload


def validate_session(payload: dict[str, Any]) -> dict[str, Any]:
    session = object_field(payload, "session")
    string(session.get("session_id"), "session.session_id")
    require(session.get("server") == "GOMarketsMU-Demo", "session server is not Demo")
    require(session.get("instrument") == "EURUSD", "session instrument is not EURUSD")
    starts = utc(session.get("starts_at_utc"), "session.starts_at_utc")
    expires = utc(session.get("expires_at_utc"), "session.expires_at_utc")
    require(starts < expires, "session must have positive duration")
    max_trades = session.get("max_trades")
    require(max_trades is None or (isinstance(max_trades, int) and 1 <= max_trades <= 10), "session max_trades is invalid")
    for field, maximum in (("max_notional_per_trade_usd", 10000), ("max_cumulative_notional_usd", 100000)):
        value = session.get(field)
        require(isinstance(value, (int, float)) and 0 < value <= maximum, f"session {field} exceeds M20 cap")
    require(session.get("max_open_positions") == 1, "session must enforce one open position")
    loss_cap = session.get("maximum_loss_per_trade_aud")
    require(type(loss_cap) in (int, float) and math.isfinite(loss_cap) and 0 < loss_cap <= 100, "session AUD loss cap is invalid")
    require(session.get("status") in {"ACTIVE", "CLOSED", "EXPIRED"}, "session has an invalid audit status")
    return session


def validate_bars(bars: Any, timeframe: str, observed_at: datetime, *, allow_empty: bool = False) -> None:
    require(isinstance(bars, list) and (allow_empty or len(bars) >= 2), f"snapshot requires at least two closed {timeframe} bars")
    previous_close: datetime | None = None
    for index, bar in enumerate(bars):
        require(isinstance(bar, dict), f"{timeframe} bar {index} must be an object")
        require(bar.get("timeframe") == timeframe, f"{timeframe} bar {index} timeframe mismatch")
        opened = utc(bar.get("opened_at_utc"), f"{timeframe} bar {index}.opened_at_utc")
        closed = utc(bar.get("closed_at_utc"), f"{timeframe} bar {index}.closed_at_utc")
        require(opened < closed <= observed_at, f"{timeframe} bar {index} is unclosed or uses future data")
        require(previous_close is None or previous_close <= opened, f"{timeframe} bars are not ordered without overlap")
        previous_close = closed
        require(isinstance(bar.get("close"), (int, float)) and bar["close"] > 0, f"{timeframe} bar {index} close is invalid")


def validate_snapshot(payload: dict[str, Any], session: dict[str, Any]) -> dict[str, Any]:
    snapshot = object_field(payload, "decision_snapshot")
    string(snapshot.get("snapshot_id"), "decision_snapshot.snapshot_id")
    observed = utc(snapshot.get("observed_at_utc"), "decision_snapshot.observed_at_utc")
    captured = utc(snapshot.get("captured_at_utc"), "decision_snapshot.captured_at_utc")
    require(observed <= captured <= observed + MAX_SNAPSHOT_AGE, "market snapshot is stale")
    require(utc(session["starts_at_utc"], "session.starts_at_utc") <= observed <= utc(session["expires_at_utc"], "session.expires_at_utc"), "snapshot is outside its session")
    bid, ask, spread = snapshot.get("bid"), snapshot.get("ask"), snapshot.get("spread_points")
    require(isinstance(bid, (int, float)) and bid > 0, "snapshot bid is invalid")
    require(isinstance(ask, (int, float)) and ask >= bid, "snapshot ask is invalid")
    require(isinstance(spread, (int, float)) and spread >= 0, "snapshot spread is invalid")
    require(snapshot.get("freshness_seconds") == int((captured - observed).total_seconds()), "snapshot freshness_seconds is inconsistent")
    gates = snapshot.get("safety_gates")
    expected_gates = {"fresh_quote", "completed_m1", "normal_spread", "no_existing_position", "demo_lease_active", "news_blackout_inactive", "abnormal_volatility_inactive"}
    require(isinstance(gates, dict) and set(gates) == expected_gates and all(value is True or value is False for value in gates.values()), "snapshot safety gates are invalid")
    # A malformed or insufficient M1 response is retained as an explicit
    # non-actionable assessment with no invented candle rows.  It can never
    # authorize an order because completed_m1 is false.
    allow_empty_m1 = gates.get("completed_m1") is False and payload.get("proposal", {}).get("action") == "NO_TRADE"
    validate_bars(snapshot.get("m1_closed_bars"), "M1", observed, allow_empty=allow_empty_m1)
    m5_bars = snapshot.get("m5_closed_bars")
    require(isinstance(m5_bars, list), "M5 shadow-context candles must be a list")
    if m5_bars:
        validate_bars(m5_bars, "M5", observed)
    sha256(snapshot.get("payload_sha256"), "decision_snapshot.payload_sha256")
    return snapshot


def validate_strategy_selection(payload: dict[str, Any], snapshot: dict[str, Any], proposal: dict[str, Any]) -> None:
    selection = object_field(payload, "strategy_selection")
    signals = payload.get("strategy_assessments")
    ids = ["momentum_breakout", "compression_breakout", "trend_pullback", "range_reversion", "session_breakout"]
    require(selection.get("proposal_id") == proposal["proposal_id"], "strategy selection proposal mismatch")
    require(selection.get("trade_owner_id") == proposal["proposal_id"], "strategy owner must be proposal-bound")
    require(selection.get("market_regime") in {"UNSAFE_OR_UNTRADEABLE", "COMPRESSION_BREAKOUT", "TREND_PULLBACK", "RANGE_REVERSION", "LIQUID_SESSION_BREAKOUT", "MOMENTUM_BREAKOUT", "NO_CLEAR_REGIME"}, "market regime is invalid")
    require(selection.get("selection_status") in {"SELECTED_EXECUTABLE", "SELECTED_SHADOW", "NO_SELECTION"}, "strategy selection status is invalid")
    require(selection.get("cost_coverage_status") in {"FEASIBLE", "NOT_FEASIBLE", "NOT_APPLICABLE"}, "cost coverage status is invalid")
    if selection["selection_status"] == "SELECTED_EXECUTABLE":
        require(selection.get("selected_strategy_id") in ids, "executable strategy must be one of the fixed five")
        require(selection.get("trade_owner_strategy_id") == selection.get("selected_strategy_id"), "executable strategy ownership must match selection")
        require(proposal["action"] in {"BUY", "SELL"}, "executable strategy must have actionable proposal")
        require(selection["cost_coverage_status"] == "FEASIBLE", "executable proposal must cover projected costs")
    if proposal["action"] in {"BUY", "SELL"}:
        require(selection["selection_status"] == "SELECTED_EXECUTABLE", "actionable proposal lacks fixed strategy authority")
        require(all(snapshot["safety_gates"].values()), "actionable proposal has a failed safety gate")
    require(isinstance(signals, list) and [item.get("id") if isinstance(item, dict) else None for item in signals] == ids, "exactly five ordered strategy signals are required")
    require(all(item.get("eligible_for_execution") is True for item in signals), "all five fixed M20.11 strategies must be available for controlled selection")
    require(all(item.get("signal") in {"BUY", "SELL", "NO_TRADE"} and isinstance(item.get("reason"), str) and item["reason"] for item in signals), "strategy signal is invalid")


def validate_proposal(payload: dict[str, Any], session: dict[str, Any], snapshot: dict[str, Any]) -> dict[str, Any]:
    proposal = object_field(payload, "proposal")
    string(proposal.get("proposal_id"), "proposal.proposal_id")
    require(proposal.get("session_id") == session["session_id"], "proposal session does not match lease")
    require(proposal.get("snapshot_id") == snapshot["snapshot_id"], "proposal snapshot does not match decision snapshot")
    require(proposal.get("decision_snapshot_sha256") == snapshot["payload_sha256"], "proposal snapshot digest does not match")
    action = proposal.get("action")
    require(action in {"BUY", "SELL", "NO_TRADE"}, "proposal action is invalid")
    require(proposal.get("selected_timeframe") == "M1", "proposal selected timeframe is invalid")
    decision_at = utc(proposal.get("decision_at_utc"), "proposal.decision_at_utc")
    expires = utc(proposal.get("expires_at_utc"), "proposal.expires_at_utc")
    observed = utc(snapshot["observed_at_utc"], "decision_snapshot.observed_at_utc")
    require(decision_at == observed, "proposal decision time does not bind to the observed snapshot")
    require(decision_at <= expires <= decision_at + MAX_PROPOSAL_AGE, "proposal expiry exceeds M20 cap")
    require(expires <= utc(session["expires_at_utc"], "session.expires_at_utc"), "proposal expires after its session")
    string(proposal.get("rationale"), "proposal.rationale")
    confidence = proposal.get("confidence")
    require(isinstance(confidence, (int, float)) and 0 <= confidence <= 100, "proposal confidence is invalid")
    notional = proposal.get("notional_usd")
    if action == "NO_TRADE":
        require(notional is None, "NO_TRADE proposal must not contain notional")
    else:
        require(isinstance(notional, (int, float)) and 0 < notional <= session["max_notional_per_trade_usd"], "proposal notional exceeds lease")
        for field in ("proposed_entry", "stop_loss", "take_profit"):
            require(isinstance(proposal.get(field), (int, float)) and proposal[field] > 0, f"actionable proposal {field} is invalid")
    return proposal


def validate_execution_and_reconciliation(payload: dict[str, Any], session: dict[str, Any], snapshot: dict[str, Any], proposal: dict[str, Any]) -> None:
    execution = object_field(payload, "execution")
    reconciliation = object_field(payload, "reconciliation")
    audit = object_field(payload, "postgres_audit")
    action = proposal["action"]
    require(reconciliation.get("session_id") == session["session_id"], "reconciliation session mismatch")
    require(reconciliation.get("proposal_id") == proposal["proposal_id"], "reconciliation proposal mismatch")
    require(reconciliation.get("snapshot_id") == snapshot["snapshot_id"], "reconciliation snapshot mismatch")
    require(audit.get("session_id") == session["session_id"], "PostgreSQL audit session mismatch")
    require(audit.get("proposal_id") == proposal["proposal_id"], "PostgreSQL audit proposal mismatch")
    require(audit.get("snapshot_id") == snapshot["snapshot_id"], "PostgreSQL audit snapshot mismatch")
    sha256(audit.get("record_sha256"), "postgres_audit.record_sha256")
    if action == "NO_TRADE":
        require(execution.get("status") == "NOT_SUBMITTED", "NO_TRADE must not submit an order")
        require(execution.get("attempt_id") is None, "NO_TRADE must not have an execution attempt")
        require(reconciliation.get("status") == "NO_TRADE_RECONCILED", "NO_TRADE must be reconciled")
        require(audit.get("execution_attempt_id") is None, "NO_TRADE audit must not have an execution attempt")
        return
    require(execution.get("status") in {"ACCEPTED", "ACCEPTED_PARTIAL", "REJECTED", "FAILED", "NOT_SUBMITTED_AFTER_RESERVATION"}, "actionable execution must have a final bounded status")
    attempt_id = string(execution.get("attempt_id"), "execution.attempt_id")
    require(execution.get("session_id") == session["session_id"], "execution session mismatch")
    require(execution.get("proposal_id") == proposal["proposal_id"], "execution proposal mismatch")
    string(execution.get("idempotency_key"), "execution.idempotency_key")
    submitted = utc(execution.get("submitted_at_utc"), "execution.submitted_at_utc")
    require(utc(proposal["decision_at_utc"], "proposal.decision_at_utc") <= submitted <= utc(proposal["expires_at_utc"], "proposal.expires_at_utc"), "execution was not submitted during proposal validity")
    require(reconciliation.get("execution_attempt_id") == attempt_id, "reconciliation execution attempt mismatch")
    require(audit.get("execution_attempt_id") == attempt_id, "PostgreSQL audit execution attempt mismatch")
    if execution.get("status") == "NOT_SUBMITTED_AFTER_RESERVATION":
        require(reconciliation.get("status") == "NOT_SUBMITTED_RECONCILED", "stale actionable assessment must record terminal non-submission")
        require("outcome" not in reconciliation, "non-submission must not have a trade outcome")
        return
    require(execution.get("open_positions_before") == 0, "execution did not enforce one-position limit")
    cumulative = execution.get("cumulative_notional_before_usd")
    require(isinstance(cumulative, (int, float)) and 0 <= cumulative, "execution cumulative notional is invalid")
    require(cumulative + proposal["notional_usd"] <= session["max_cumulative_notional_usd"], "execution exceeds cumulative session cap")
    require(reconciliation.get("status") == "MATCHED", "actionable execution must be reconciled as MATCHED")
    if execution.get("status") == "REJECTED":
        require("outcome" not in reconciliation, "rejected execution must not have a trade outcome")
        return
    outcome = object_field(reconciliation, "outcome")
    require(outcome.get("proposal_id") == proposal["proposal_id"], "outcome proposal mismatch")
    utc(outcome.get("closed_at_utc"), "outcome.closed_at_utc")
    require(isinstance(outcome.get("exit_price"), (int, float)) and outcome["exit_price"] > 0, "outcome exit price is invalid")
    require(isinstance(outcome.get("realized_pnl_account"), (int, float)), "outcome realized P&L is invalid")
    require(outcome.get("account_currency") == "AUD", "outcome account currency is invalid")
    string(outcome.get("close_reason"), "outcome.close_reason")


def finite_number(value: Any, field: str, *, positive: bool = False) -> float:
    require(type(value) in (int, float, str), f"{field} must be numeric")
    try:
        number = float(value)
    except ValueError as error:
        raise VerificationError(f"{field} must be numeric") from error
    require(math.isfinite(number) and (not positive or number > 0), f"{field} is invalid")
    return number


def validate_closed_trade(row: dict[str, Any], session: dict[str, Any], captured: datetime) -> None:
    """Recompute a current lifecycle from retained, position-specific MT5 rows."""
    submitted = utc(row.get("submitted_at_utc"), "lifecycle.submitted_at_utc")
    closed = utc(row.get("closed_at_utc"), "lifecycle.closed_at_utc")
    decision = utc(row.get("decision_at_utc"), "lifecycle.decision_at_utc")
    snapshot_at = utc(row.get("snapshot_captured_at_utc"), "lifecycle.snapshot_captured_at_utc")
    expires = utc(row.get("proposal_expires_at_utc"), "lifecycle.proposal_expires_at_utc")
    require(captured - timedelta(hours=168) <= decision <= snapshot_at <= submitted <= closed <= captured,
            "lifecycle is stale, future-dated, or not proposal-first")
    require(submitted <= expires <= decision + MAX_PROPOSAL_AGE, "lifecycle submission exceeds proposal validity")
    require(utc(session["starts_at_utc"], "session.starts_at_utc") <= decision and closed <= utc(session["expires_at_utc"], "session.expires_at_utc"), "lifecycle exceeds its lease")
    string(row.get("proposal_id"), "lifecycle.proposal_id")
    string(row.get("attempt_id"), "lifecycle.attempt_id")
    string(row.get("snapshot_id"), "lifecycle.snapshot_id")
    require(sha256(row.get("decision_snapshot_sha256"), "lifecycle.decision_snapshot_sha256") == row.get("snapshot_payload_sha256"), "lifecycle snapshot digest mismatch")
    require(row.get("action") in {"BUY", "SELL"}, "lifecycle action is invalid")
    require(row.get("selected_strategy_id") in {"momentum_breakout", "compression_breakout", "trend_pullback", "range_reversion", "session_breakout"}
            and row.get("trade_owner_strategy_id") == row["selected_strategy_id"], "lifecycle strategy ownership mismatch")
    opening = object_field(row, "opening_context")
    closing = object_field(row, "closing_context")
    history = object_field(closing, "broker_history")
    require(history.get("server") == "GOMarketsMU-Demo" and history.get("symbol") == "EURUSD" and history.get("account_currency") == "AUD", "broker history surface mismatch")
    position = history.get("position_identifier")
    require(type(position) is int and position > 0 and opening.get("position_identifier") == position and closing.get("position_identifier") == position, "broker history position mismatch")
    deals = history.get("broker_deals")
    require(isinstance(deals, list) and len(deals) >= 2, "broker history requires opening and closing deals")
    digest = "sha256:" + hashlib.sha256(json.dumps(deals, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    require(history.get("broker_deals_sha256") == digest, "broker history digest mismatch")
    tickets: set[int] = set()
    entries, exits = [], []
    previous_time = None
    for deal in deals:
        require(isinstance(deal, dict) and deal.get("position_identifier") == position, "broker deal position mismatch")
        ticket = deal.get("ticket")
        require(type(ticket) is int and ticket > 0 and ticket not in tickets, "broker deal ticket is invalid or duplicated")
        tickets.add(ticket)
        at = utc(deal.get("time_utc"), "broker deal.time_utc")
        require(submitted <= at <= closed and (previous_time is None or previous_time <= at), "broker deal timestamp mismatch")
        previous_time = at
        for key in ("profit", "commission", "fee", "swap", "price", "volume"):
            require(type(deal.get(key)) in (int, float), f"broker deal.{key} must be a JSON number")
            finite_number(deal.get(key), f"broker deal.{key}")
        if deal["volume"] > 0:
            require(deal.get("symbol") == "EURUSD" and deal["price"] > 0 and deal.get("entry") in {0, 1, 3}, "broker market deal is invalid")
            is_open = deal["entry"] == 0
            require(deal.get("type") == ((0 if row["action"] == "BUY" else 1) if is_open else (1 if row["action"] == "BUY" else 0)), "broker deal side mismatch")
            (entries if is_open else exits).append(deal)
    require(bool(entries) and bool(exits), "broker history lacks opening or closing market deals")
    opened_volume = sum(d["volume"] for d in entries)
    closed_volume = sum(d["volume"] for d in exits)
    require(math.isclose(opened_volume, closed_volume, abs_tol=1e-9, rel_tol=0), "broker opening and closing volume mismatch")
    require(math.isclose(opened_volume, finite_number(opening.get("broker_filled_volume"), "opening volume", positive=True), abs_tol=1e-9, rel_tol=0), "broker fill volume mismatch")
    for field, rows in (("actual_entry_price", entries), ("exit_price", exits)):
        price = sum(d["price"] * d["volume"] for d in rows) / sum(d["volume"] for d in rows)
        require(math.isclose(price, finite_number(row.get(field), field, positive=True), rel_tol=0, abs_tol=1e-8), f"broker-derived {field} mismatch")
    totals = {}
    for source, field in (("profit", "gross_price_pnl_account"), ("commission", "commission_account"), ("fee", "fee_account"), ("swap", "swap_account")):
        totals[source] = sum(d[source] for d in deals)
        require(math.isclose(round(totals[source], 2), finite_number(row.get(field), field), rel_tol=0, abs_tol=1e-8), f"broker-derived {field} mismatch")
    require(row.get("account_currency") == "AUD" and math.isclose(round(sum(totals.values()), 2), finite_number(row.get("realized_pnl_account"), "realized P&L"), rel_tol=0, abs_tol=1e-8), "broker-derived AUD P&L mismatch")


def validate_broker_matched_lifecycle(wrapper: dict[str, Any], session: dict[str, Any], revision: str, fingerprint: str, captured: datetime) -> dict[str, Any]:
    """Require a fresh trade from this exact release, not an older lease trade."""
    ensure_no_live_reference(wrapper)
    require(wrapper.get("tool_id") == "forex_postgres_pgvector_t480", "lifecycle summary must use the PostgreSQL adapter")
    require(wrapper.get("operation") == "forex_m20_lifecycle_summary", "lifecycle summary operation mismatch")
    result = object_field(wrapper, "result")
    require(result.get("ok") is True and result.get("exit_code") == 0, "lifecycle summary failed")
    try:
        rows = json.loads(string(result.get("stdout"), "lifecycle summary stdout"))
    except json.JSONDecodeError as error:
        raise VerificationError("lifecycle summary stdout is not JSON") from error
    require(isinstance(rows, list), "lifecycle summary must be a list")
    for row in reversed(rows):
        if (not isinstance(row, dict) or row.get("session_id") != session["session_id"]
                or row.get("application_revision") != revision or row.get("configuration_fingerprint") != fingerprint):
            continue
        try:
            events = json.loads(row.get("events") or "[]")
        except (TypeError, json.JSONDecodeError):
            continue
        if (row.get("lifecycle") == "CLOSED_MATCHED" and row.get("reconciliation_status") == "MATCHED"
                and isinstance(events, list) and "OPENED" in events and "CLOSED" in events
                and events.index("OPENED") < events.index("CLOSED")):
            validate_closed_trade(row, session, captured)
            return row
    raise VerificationError("no broker-matched OPENED to CLOSED Demo trade exists for the captured lease, revision, and configuration")


def validate_payload(payload: dict[str, Any], expected_fingerprint: str | None = None) -> None:
    if expected_fingerprint is not None:
        require(payload.get("configuration_fingerprint") == expected_fingerprint, "operation fingerprint does not match manifest")
    session = validate_session(payload)
    snapshot = validate_snapshot(payload, session)
    proposal = validate_proposal(payload, session, snapshot)
    validate_strategy_selection(payload, snapshot, proposal)
    validate_execution_and_reconciliation(payload, session, snapshot, proposal)


def validate_listener(bundle: Path, root: Path, revision: str, fingerprint: str, session: dict[str, Any], captured: datetime) -> None:
    observations = {}
    for name, operation in (("listener-diagnostics.json", "m20_listener_diagnostics"), ("listener-status.json", "m20_listener_status")):
        wrapper = read_json(bundle / name)
        ensure_no_live_reference(wrapper)
        require(wrapper.get("tool_id") == "forex_t480" and wrapper.get("operation") == operation and wrapper.get("ok") is True, "listener adapter binding mismatch")
        require(wrapper.get("configuration_fingerprint") == fingerprint, "listener adapter configuration mismatch")
        result = object_field(wrapper, "result")
        require(result.get("ok") is True and result.get("exit_code") == 0, "listener observation failed")
        try:
            value = json.loads(string(result.get("stdout"), "listener stdout"))
        except json.JSONDecodeError as error:
            raise VerificationError("listener stdout is not JSON") from error
        require(isinstance(value, dict), "listener observation must be an object")
        observations[operation] = value
    diagnostics, status = observations["m20_listener_diagnostics"], observations["m20_listener_status"]
    require(diagnostics.get("task_state") == "Running" and diagnostics.get("logon_type") == "S4U" and diagnostics.get("maintenance_hold_present") is False, "permanent listener is not running unheld under S4U")
    require(status.get("running") is True and status.get("state") in {"RUNNING", "WAITING_FOR_FRESH_MT5_QUOTE"}, "listener is unhealthy")
    require(object_field(status, "monitor").get("state") in {"IDLE", "RUNNING"}, "listener monitoring is unhealthy")
    heartbeat = utc(status.get("heartbeat_at_utc"), "listener heartbeat")
    observed = utc(diagnostics.get("captured_at_utc"), "listener diagnostics timestamp")
    require(captured - timedelta(seconds=30) <= heartbeat <= captured and captured - timedelta(seconds=60) <= observed <= captured, "listener observation is stale or future-dated")
    binding = object_field(diagnostics, "deployment_binding")
    require(binding.get("observation") == "VALID" and binding.get("application_revision") == revision and binding.get("configuration_fingerprint") == fingerprint, "deployed revision/configuration mismatch")
    payload_hashes = object_field(binding, "payload_sha256")
    for name in ("m20_demo_listener_service", "m20_demo_trading_session", "m20_postgres_audit_bridge", "m20_discord_trade_notification"):
        expected = "sha256:" + hashlib.sha256((root / "t480" / f"{name}.py").read_bytes()).hexdigest()
        require(payload_hashes.get(f"{name}.payload") == expected, "deployed payload hash mismatch")
    lease = object_field(binding, "lease")
    require(lease.get("session_id") == session["session_id"] and lease.get("server") == "GOMarketsMU-Demo" and lease.get("symbol") == "EURUSD", "deployed lease surface mismatch")
    for key, expected in (("maximum_trades", None), ("maximum_duration_minutes", 0), ("maximum_open_positions", 1), ("maximum_notional_per_trade_usd", 10000), ("maximum_cumulative_notional_usd", 100000), ("maximum_loss_per_trade_aud", 100)):
        require(key in lease and lease[key] == expected, f"deployed lease {key} mismatch")


def project_fingerprint(root: Path) -> str:
    # Evidence recording runs the independent verifier while the governance
    # process holds its repository lock.  Forward this marker so the read-only
    # status invocation does not attempt to acquire that same non-reentrant
    # lock and deadlock the recording operation.
    environment = dict(os.environ)
    if environment.get("FOREX_GOVERNANCE_LOCK_HELD") == "1":
        environment["FOREX_GOVERNANCE_LOCK_HELD"] = "1"
    output = subprocess.check_output(
        [sys.executable, "scripts/forex_milestones.py", "status", "--json"],
        cwd=root,
        text=True,
        env=environment,
    )
    value = json.loads(output)
    return sha256(value.get("configuration_fingerprint"), "current configuration_fingerprint")


def artifact_list(bundle: Path) -> list[dict[str, str]]:
    return [
        {"path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        for path in sorted(bundle.iterdir())
        if path.is_file() and path.name != "manifest.json"
    ]


def capture(bundle: Path, root: Path) -> None:
    wrapper = read_json(bundle / "demo-trading-operation.json")
    fingerprint = project_fingerprint(root)
    payload = parse_operation(wrapper, fingerprint)
    validate_payload(payload, fingerprint)
    revision = (bundle / "revision.txt").read_text(encoding="utf-8").strip()
    captured = datetime.now(timezone.utc)
    lifecycle = validate_broker_matched_lifecycle(read_json(bundle / "lifecycle-summary.json"), payload["session"], revision, fingerprint, captured)
    validate_listener(bundle, root, revision, fingerprint, payload["session"], captured)
    session_audit = {
        "schema_version": "forex.m20.demo-trading-evidence.v1",
        "operation_marker": payload["marker"],
        "server": payload["server"],
        "symbol": payload["symbol"],
        "captured_at_utc": payload["captured_at_utc"],
        "configuration_fingerprint": fingerprint,
        "session": payload["session"],
        "decision_snapshot": payload["decision_snapshot"],
        "proposal": payload["proposal"],
        "execution": payload["execution"],
        "reconciliation": payload["reconciliation"],
        "postgres_audit": payload["postgres_audit"],
        "broker_matched_lifecycle": lifecycle,
    }
    (bundle / "session-audit.json").write_text(json.dumps(session_audit, indent=2) + "\n", encoding="utf-8")
    (bundle / "summary.txt").write_text("FOREX_M20_DEMO_TRADING_PROOF_OK\n", encoding="utf-8")
    revision = (bundle / "revision.txt").read_text(encoding="utf-8").strip()
    manifest = {
        "schema_version": "1.0.0",
        "milestone_id": "M20",
        "captured_at": captured.isoformat().replace("+00:00", "Z"),
        "git_revision": revision,
        "dirty_worktree": False,
        "configuration_fingerprint": fingerprint,
        "surface": M20_EVIDENCE_SURFACE,
        "operation": "fixed T480 m20_demo_trading_session operation",
        "expected_result": "fresh Demo EUR/USD data is assessed, recorded, bounded, and reconciled",
        "observed_result": "FOREX_M20_DEMO_TRADING_PROOF_OK",
        "exit_code": 0,
        "redactions": ["No credentials, account identifiers, or non-Demo broker data are retained."],
        "summary": "FOREX_M20_DEMO_TRADING_PROOF_OK",
        "artifacts": artifact_list(bundle),
    }
    (bundle / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def verify(bundle: Path, root: Path) -> None:
    evidence_root = (root / "runs" / "evidence" / "M20").resolve()
    require(bundle.is_relative_to(evidence_root), "evidence bundle is outside the M20 evidence root")
    manifest = read_json(bundle / "manifest.json")
    require(manifest.get("schema_version") == "1.0.0", "manifest schema version mismatch")
    require(manifest.get("milestone_id") == "M20", "manifest milestone is not M20")
    require(manifest.get("dirty_worktree") is False, "manifest records a dirty worktree")
    require(manifest.get("surface") == M20_EVIDENCE_SURFACE, "manifest surface mismatch")
    require(manifest.get("operation") == "fixed T480 m20_demo_trading_session operation", "manifest operation mismatch")
    require(manifest.get("observed_result") == "FOREX_M20_DEMO_TRADING_PROOF_OK", "manifest result marker mismatch")
    require(manifest.get("summary") == "FOREX_M20_DEMO_TRADING_PROOF_OK", "manifest summary marker mismatch")
    ensure_no_live_reference(manifest)
    require(manifest.get("git_revision") == subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip(), "manifest revision does not match HEAD")
    captured = utc(manifest.get("captured_at"), "manifest.captured_at")
    require(timedelta(0) <= datetime.now(timezone.utc) - captured < timedelta(hours=168), "evidence is stale or future-dated")
    fingerprint = project_fingerprint(root)
    require(manifest.get("configuration_fingerprint") == fingerprint, "manifest fingerprint does not match current configuration")
    artifacts = manifest.get("artifacts")
    require(isinstance(artifacts, list) and artifacts, "manifest artifacts are missing")
    artifact_names = {artifact.get("path") for artifact in artifacts if isinstance(artifact, dict)}
    require(artifact_names == REQUIRED_ARTIFACTS, "manifest must contain exactly the required M20 artifacts")
    for artifact in artifacts:
        require(isinstance(artifact, dict), "manifest artifact is invalid")
        name = string(artifact.get("path"), "artifact path")
        require("/" not in name and "\\" not in name and name not in {".", ".."}, "artifact path must be a bundle filename")
        digest = string(artifact.get("sha256"), "artifact sha256")
        require(HEX256.fullmatch(digest) is not None, "artifact sha256 is invalid")
        path = bundle / name
        require(path.is_file(), f"missing artifact: {name}")
        require(hashlib.sha256(path.read_bytes()).hexdigest() == digest, f"artifact digest mismatch: {name}")
    require("passed" in (bundle / "tests.txt").read_text(encoding="utf-8").lower(), "milestone tests did not pass")
    require("milestone governance valid" in (bundle / "governance.txt").read_text(encoding="utf-8"), "governance validation did not pass")
    configuration = read_json(bundle / "configuration.json")
    require(configuration.get("runtime_mode") == "DEMO_TRADING", "configuration is not in DEMO_TRADING mode")
    require(configuration.get("agent_authority_mode") == "DEMO_SESSION_BOUNDED", "configuration does not declare bounded Demo authority")
    require(configuration.get("live_trading_enabled") is False, "configuration enables live trading")
    require(configuration.get("permitted_mt5_server") == "GOMarketsMU-Demo", "configuration does not permit the Demo server")
    require(
        configuration.get("configuration_fingerprint") == fingerprint,
        "configuration artifact fingerprint does not match manifest binding",
    )
    wrapper = read_json(bundle / "demo-trading-operation.json")
    payload = parse_operation(wrapper, fingerprint)
    validate_payload(payload, fingerprint)
    lifecycle = validate_broker_matched_lifecycle(read_json(bundle / "lifecycle-summary.json"), payload["session"], manifest["git_revision"], fingerprint, captured)
    validate_listener(bundle, root, manifest["git_revision"], fingerprint, payload["session"], captured)
    audit = read_json(bundle / "session-audit.json")
    require(audit.get("schema_version") == "forex.m20.demo-trading-evidence.v1", "session audit schema mismatch")
    require(audit.get("configuration_fingerprint") == fingerprint, "session audit fingerprint mismatch")
    for field in ("server", "symbol", "session", "decision_snapshot", "proposal", "execution", "reconciliation", "postgres_audit"):
        require(audit.get(field) == payload.get(field), f"session audit {field} does not match operation")
    require(audit.get("broker_matched_lifecycle") == lifecycle, "session audit broker-matched lifecycle mismatch")
    require((bundle / "revision.txt").read_text(encoding="utf-8").strip() == manifest["git_revision"], "revision artifact mismatch")
    require((bundle / "summary.txt").read_text(encoding="utf-8").strip() == "FOREX_M20_DEMO_TRADING_PROOF_OK", "proof marker is missing")
    print("FOREX_M20_DEMO_TRADING_EVIDENCE_VERIFIED")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build or verify an M20 Demo trading evidence bundle.")
    parser.add_argument("command", choices=("capture", "verify"))
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--bundle", required=True, type=Path)
    args = parser.parse_args(argv)
    root, bundle = args.root.resolve(), args.bundle.resolve()
    if args.command == "capture":
        capture(bundle, root)
    else:
        verify(bundle, root)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except VerificationError as error:
        print(f"M20 evidence verification failed: {error}", file=sys.stderr)
        raise SystemExit(2) from error
