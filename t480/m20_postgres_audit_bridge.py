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
    required = {"snapshot_id", "observed_at_utc", "captured_at_utc", "bid", "ask", "spread_points", "m1_closed_bars", "m5_closed_bars", "freshness_seconds", "payload_sha256"}
    if set(value) != required or value["snapshot_id"] != proposal["snapshot_id"] or value["payload_sha256"] != proposal["decision_snapshot_sha256"] or not isinstance(value["m1_closed_bars"], list) or not isinstance(value["m5_closed_bars"], list):
        raise SystemExit("M20 bridge snapshot does not bind its proposal")
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
        cursor.execute("SELECT 1 FROM forex.demo_trade_proposal p JOIN forex.demo_decision_snapshot s ON s.proposal_id=p.proposal_id WHERE p.proposal_id=%s AND p.session_id=%s AND p.action IN ('BUY','SELL') AND p.expires_at_utc >= now() FOR UPDATE", (proposal["proposal_id"], session["session_id"]))
        if cursor.fetchone() is None:
            raise SystemExit("M20 proposal is absent, unpersisted, expired, or non-actionable")
        cursor.execute("SELECT count(*) FROM forex.demo_execution_attempt WHERE session_id=%s", (session["session_id"],))
        if cursor.fetchone()[0] >= session["max_trades"]:
            raise SystemExit("M20 maximum trade count is reached")
        cursor.execute("SELECT COALESCE(sum(p.notional_usd),0) FROM forex.demo_execution_attempt a JOIN forex.demo_trade_proposal p ON p.proposal_id=a.proposal_id WHERE a.session_id=%s", (session["session_id"],))
        if float(cursor.fetchone()[0]) + float(proposal["notional_usd"]) > float(session["max_cumulative_notional_usd"]):
            raise SystemExit("M20 cumulative notional cap is reached")
        cursor.execute("SELECT count(*) FROM forex.demo_execution_attempt a LEFT JOIN forex.demo_trade_outcome o ON o.proposal_id=a.proposal_id WHERE a.session_id=%s AND o.proposal_id IS NULL AND NOT EXISTS (SELECT 1 FROM forex.demo_position_event e WHERE e.attempt_id=a.attempt_id AND e.event_type IN ('REJECTED','FAILED'))", (session["session_id"],))
        if cursor.fetchone()[0] != 0:
            raise SystemExit("M20 one-position limit is reached")
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
    with _connection() as conn, conn.cursor() as cursor:
        cursor.execute("SELECT 1 FROM forex.demo_execution_attempt WHERE attempt_id=%s FOR UPDATE", (result["attempt_id"],))
        if cursor.fetchone() is None:
            raise SystemExit("M20 result has no reserved execution attempt")
        cursor.execute("INSERT INTO forex.demo_position_event (event_id,attempt_id,event_type,observed_at_utc,payload_sha256,payload) VALUES (%s,%s,%s,%s,%s,%s::jsonb)", (result["event_id"], result["attempt_id"], result["event_type"], result["observed_at_utc"], result["payload_sha256"], json.dumps({"broker_order_reference": result["broker_order_reference"], **result["payload"]})))
    return {"ok": True, "recorded_event_id": result["event_id"]}


def record_closed_outcome(payload: dict[str, Any]) -> dict[str, Any]:
    """Append a CLOSED lifecycle event and its immutable realized outcome."""
    result = _object(payload, "result")
    outcome = _object(payload, "outcome")
    result_required = {"event_id", "attempt_id", "event_type", "observed_at_utc", "broker_order_reference", "payload_sha256", "payload"}
    outcome_required = {"proposal_id", "closed_at_utc", "exit_price", "realized_pnl_usd", "close_reason", "reconciliation_status"}
    if set(result) != result_required or result["event_type"] != "CLOSED" or not isinstance(result["payload"], dict) or set(outcome) != outcome_required or outcome["reconciliation_status"] != "MATCHED":
        raise SystemExit("M20 closed lifecycle outcome is invalid")
    with _connection() as conn, conn.cursor() as cursor:
        cursor.execute("SELECT proposal_id FROM forex.demo_execution_attempt WHERE attempt_id=%s FOR UPDATE", (result["attempt_id"],))
        attempt = cursor.fetchone()
        if attempt is None or attempt[0] != outcome["proposal_id"]:
            raise SystemExit("M20 closed outcome does not match its reserved attempt")
        cursor.execute("INSERT INTO forex.demo_position_event (event_id,attempt_id,event_type,observed_at_utc,payload_sha256,payload) VALUES (%s,%s,'CLOSED',%s,%s,%s::jsonb)", (result["event_id"], result["attempt_id"], result["observed_at_utc"], result["payload_sha256"], json.dumps({"broker_order_reference": result["broker_order_reference"], **result["payload"]})))
        cursor.execute("INSERT INTO forex.demo_trade_outcome (proposal_id,closed_at_utc,exit_price,realized_pnl_usd,close_reason,reconciliation_status) VALUES (%s,%s,%s,%s,%s,'MATCHED')", (outcome["proposal_id"], outcome["closed_at_utc"], outcome["exit_price"], outcome["realized_pnl_usd"], outcome["close_reason"]))
    return {"ok": True, "recorded_event_id": result["event_id"], "proposal_id": outcome["proposal_id"]}


def reconcile(payload: dict[str, Any]) -> dict[str, Any]:
    """Read back the immutable lifecycle for one fixed persisted proposal."""
    proposal_id = payload.get("proposal_id")
    if not isinstance(proposal_id, str) or not proposal_id:
        raise SystemExit("M20 reconciliation proposal id is invalid")
    with _connection() as conn, conn.cursor() as cursor:
        cursor.execute("SELECT p.session_id,p.action,s.snapshot_id,a.attempt_id,COALESCE(array_agg(e.event_type) FILTER (WHERE e.event_id IS NOT NULL), ARRAY[]::text[]),o.closed_at_utc,o.exit_price,o.realized_pnl_usd,o.close_reason,o.reconciliation_status FROM forex.demo_trade_proposal p JOIN forex.demo_decision_snapshot s ON s.proposal_id=p.proposal_id LEFT JOIN forex.demo_execution_attempt a ON a.proposal_id=p.proposal_id LEFT JOIN forex.demo_position_event e ON e.attempt_id=a.attempt_id LEFT JOIN forex.demo_trade_outcome o ON o.proposal_id=p.proposal_id WHERE p.proposal_id=%s GROUP BY p.session_id,p.action,s.snapshot_id,a.attempt_id,o.closed_at_utc,o.exit_price,o.realized_pnl_usd,o.close_reason,o.reconciliation_status", (proposal_id,))
        row = cursor.fetchone()
        if row is None:
            raise SystemExit("M20 reconciliation proposal is absent")
    closed_and_outcome = row[3] is not None and "CLOSED" in row[4] and row[5] is not None and row[9] == "MATCHED"
    status = "NO_TRADE_RECONCILED" if row[1] == "NO_TRADE" and row[3] is None else ("MATCHED" if closed_and_outcome else "PENDING")
    reconciliation = {"session_id": row[0], "proposal_id": proposal_id, "snapshot_id": row[2], "execution_attempt_id": row[3], "status": status}
    if closed_and_outcome:
        reconciliation["outcome"] = {"proposal_id": proposal_id, "closed_at_utc": row[5].astimezone(timezone.utc).isoformat().replace("+00:00", "Z"), "exit_price": float(row[6]), "realized_pnl_usd": float(row[7]), "close_reason": row[8]}
    return {"ok": True, "reconciliation": reconciliation}


def main() -> int:
    command = sys.argv[1] if len(sys.argv) == 2 else ""
    actions = {"persist-proposal": persist_proposal, "reserve-execution": reserve_execution, "record-result": record_result, "record-closed-outcome": record_closed_outcome, "reconcile": reconcile}
    if command not in actions:
        raise SystemExit("M20 audit bridge command is not fixed")
    print(json.dumps(actions[command](_payload()), separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
