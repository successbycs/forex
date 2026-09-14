from __future__ import annotations

from dataclasses import dataclass

import pytest

from forex.h_slow_persistence import HSlowLifecycleStore, HSlowPersistenceError
from forex.stream_isolation import validate_stream_registry


def registry() -> dict:
    return {"schema_version": "forex.stream-isolation.v1", "streams": [
        {"stream_id": "M1", "server": "GOMarketsMU-Demo", "account_scope": "demo_scope_m1", "terminal_instance": "terminal_m1", "namespaces": {"state_namespace": "state_m1", "monitor_namespace": "monitor_m1", "lease_namespace": "lease_m1", "reservation_namespace": "reservation_m1", "outcome_namespace": "outcome_m1"}, "deployment_state": "RETAINED_EXISTING_OPERATION", "account_selection": "NOT_SELECTED", "execution_capability": "NOT_EXPOSED"},
        {"stream_id": "H_SLOW", "server": "GOMarketsMU-Demo", "account_scope": "demo_scope_hslow", "terminal_instance": "terminal_hslow", "namespaces": {"state_namespace": "state_hslow", "monitor_namespace": "monitor_hslow", "lease_namespace": "lease_hslow", "reservation_namespace": "reservation_hslow", "outcome_namespace": "outcome_hslow"}, "deployment_state": "NOT_DEPLOYED", "account_selection": "NOT_SELECTED", "execution_capability": "NOT_EXPOSED"},
    ]}


def action_id(decision: str, kind: str, ticket: str | None) -> str:
    import hashlib, json
    return "sha256:" + hashlib.sha256(json.dumps({"decision_sha256": decision,
        "isolation_registry_fingerprint": validate_stream_registry(registry()).registry_fingerprint,
        "action": kind, "ticket_id": ticket}, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def plan(kind="OPEN", ticket=None) -> dict:
    decision = "sha256:" + "a" * 64
    from forex.stream_isolation import validate_stream_registry
    intent = {"action_id": action_id(decision, kind, ticket), "kind": kind, "ticket_id": ticket,
              "direction": "BUY" if kind == "OPEN" else None}
    return {"schema_version": "forex.h-slow.lifecycle-plan.v1", "stream_id": "H_SLOW", "decision_sha256": decision,
            "isolation_registry_fingerprint": validate_stream_registry(registry()).registry_fingerprint,
            "mandate_preflight_status": "NOT_PROVIDED", "lifecycle_state": "ENTRY_ELIGIBLE", "reason": "test",
            "next_action": kind, "intent": intent, "execution_authority": False}


def test_real_planner_output_is_accepted_by_persistence():
    from tests.test_h_slow_lifecycle import plan as lifecycle_plan
    db = Database()
    candidate = lifecycle_plan()
    stored = HSlowLifecycleStore(db.connect, stream_registry=registry()).persist_plan(candidate)
    assert stored.action_id == candidate["intent"]["action_id"]


@dataclass
class Row:
    action_id: str; kind: str; ticket: str | None; direction: str | None; scope: str; terminal_instance: str; fingerprint: str; decision: str; status: str = "PENDING"; terminal: str | None = None; valid_until: str | None = None; expired_at: str | None = None


class Cursor:
    def __init__(self, database): self.db, self.row, self.rowcount = database, None, 0
    def __enter__(self): return self
    def __exit__(self, *args): return None
    def execute(self, query, params=()):
        self.row, self.rowcount = None, 0
        if query == "SELECT %s::timestamptz > clock_timestamp()":
            self.row = (params[0] > self.db.now,)
        elif query.startswith("SELECT action_id FROM forex.h_slow_lifecycle_intent"):
            row = self.db.rows.get(params[0])
            if row and (row.scope, row.terminal_instance, row.fingerprint) == params[1:]:
                self.row = (row.action_id,)
        elif query.startswith("INSERT INTO forex.h_slow_lifecycle_intent"):
            key = params[0]
            if key not in self.db.rows:
                self.db.rows[key] = Row(key, params[5], params[6], params[7], params[1], params[2], params[3], params[4], valid_until=params[8]); row = self.db.rows[key]
                self.row, self.rowcount = (row.action_id, row.kind, row.ticket, row.direction, row.status, row.terminal, row.valid_until, row.expired_at), 1
        elif query.startswith("SELECT action_id,action_kind,ticket_id,direction,claim_status,terminal_status,") and "WHERE action_id=%s FOR UPDATE" in query:
            row = self.db.rows.get(params[0]); self.row = None if row is None else (row.action_id, row.kind, row.ticket, row.direction, row.status, row.terminal, row.valid_until, row.expired_at, row.scope, row.terminal_instance, row.fingerprint, row.decision)
        elif query.startswith("UPDATE forex.h_slow_lifecycle_intent SET claim_status='CLAIMED'"):
            row = self.db.rows.get(params[0])
            if row and row.status == "PENDING" and row.terminal is None and (row.valid_until is None or row.valid_until > self.db.now):
                row.status = "CLAIMED"; self.row, self.rowcount = (row.action_id, row.kind, row.ticket, row.direction, row.status, row.terminal, row.valid_until, row.expired_at), 1
        elif query.startswith("WITH expired AS ("):
            self.rows = []
            for row in self.db.rows.values():
                if (row.scope == params[0] and row.terminal_instance == params[1] and row.fingerprint == params[2]
                        and row.kind == "OPEN" and row.status == "PENDING" and row.valid_until is not None
                        and row.valid_until <= self.db.now):
                    row.status, row.terminal, row.expired_at = "EXPIRED_NOT_SUBMITTED", "NOT_SUBMITTED", self.db.now
                    self.db.expired.add(row.action_id)
                    self.rows.append((row.action_id, row.kind, row.ticket, row.direction, row.status, row.terminal, row.valid_until, row.expired_at))
        elif query.startswith("SELECT action_id,action_kind,ticket_id,direction,claim_status,terminal_status,valid_until_utc,expired_at_utc FROM forex.h_slow_lifecycle_intent"):
            assert params and len(params) == 1
            assert "terminal_instance=%s" not in query
            assert "isolation_registry_fingerprint=%s" not in query
            self.rows = [(row.action_id, row.kind, row.ticket, row.direction, row.status, row.terminal, row.valid_until, row.expired_at)
                         for row in self.db.rows.values()
                         if row.scope == params[0] and row.status in {"PENDING", "CLAIMED", "SUBMISSION_UNKNOWN"}]
        elif query.startswith("UPDATE forex.h_slow_lifecycle_intent SET claim_status='SUBMISSION_UNKNOWN'"):
            row = self.db.rows.get(params[0])
            if row and row.status == "CLAIMED":
                row.status = "SUBMISSION_UNKNOWN"; self.row, self.rowcount = (row.action_id, row.kind, row.ticket, row.direction, row.status, row.terminal, row.valid_until, row.expired_at), 1
        elif query.startswith("SELECT action_kind FROM forex.h_slow_lifecycle_intent"):
            row = self.db.rows.get(params[0]); self.row = None if row is None else (row.kind,)
        elif query.startswith("INSERT INTO forex.h_slow_lifecycle_reconciliation"):
            if params[0] not in self.db.reconciled: self.db.reconciled.add(params[0]); self.row = (params[0],)
        elif query.startswith("UPDATE forex.h_slow_lifecycle_intent SET claim_status='TERMINAL_RECONCILED'"):
            row = self.db.rows.get(params[3])
            if row and row.status in {"CLAIMED", "SUBMISSION_UNKNOWN"} and row.terminal is None:
                row.status, row.terminal = "TERMINAL_RECONCILED", params[0]; self.row = (row.action_id, row.kind, row.ticket, row.direction, row.status, row.terminal, row.valid_until, row.expired_at)
        else: raise AssertionError(query)
    def fetchone(self): return self.row
    def fetchall(self): return getattr(self, "rows", [])


class Connection:
    def __init__(self, database): self.database = database
    def __enter__(self): return self
    def __exit__(self, *args): return None
    def cursor(self): return Cursor(self.database)


class Database:
    def __init__(self): self.rows, self.reconciled, self.expired, self.now = {}, set(), set(), "2026-09-12T00:00:00Z"
    def connect(self): return Connection(self)


def test_persists_idempotently_and_claim_is_atomic_across_restart():
    db, first = Database(), plan()
    store = HSlowLifecycleStore(db.connect, stream_registry=registry())
    persisted = store.persist_plan(first)
    assert persisted.claim_status == "PENDING"
    restarted = HSlowLifecycleStore(db.connect, stream_registry=registry())
    assert restarted.persist_plan(first).claim_status == "PENDING"
    assert restarted.claim_intent(first["intent"]["action_id"]).claim_status == "CLAIMED"
    assert store.claim_intent(first["intent"]["action_id"]) is None


def test_ambiguous_submission_survives_restart_and_can_never_be_claimed_again():
    db, candidate = Database(), plan()
    store = HSlowLifecycleStore(db.connect, stream_registry=registry())
    store.persist_plan(candidate); store.claim_intent(candidate["intent"]["action_id"])
    assert store.mark_submission_unknown(candidate["intent"]["action_id"]).claim_status == "SUBMISSION_UNKNOWN"
    assert HSlowLifecycleStore(db.connect, stream_registry=registry()).claim_intent(candidate["intent"]["action_id"]) is None


def test_terminal_reconciliation_is_explicit_and_remains_non_retryable():
    db, candidate = Database(), plan("CLOSE", "ticket_hslow_1")
    store = HSlowLifecycleStore(db.connect, stream_registry=registry())
    store.persist_plan(candidate); store.claim_intent(candidate["intent"]["action_id"])
    result = store.reconcile_terminal(candidate["intent"]["action_id"], terminal_status="CLOSE_CONFIRMED", terminal_reference="broker_ticket_hslow_1", observed_at_utc="2026-09-12T00:00:00Z")
    assert result.claim_status == "TERMINAL_RECONCILED"
    assert store.claim_intent(candidate["intent"]["action_id"]) is None


def test_rejects_scope_fingerprint_drift_or_fabricated_authority():
    db, candidate = Database(), plan()
    candidate["isolation_registry_fingerprint"] = "sha256:" + "b" * 64
    with pytest.raises(HSlowPersistenceError, match="fingerprint"):
        HSlowLifecycleStore(db.connect, stream_registry=registry()).persist_plan(candidate)
    candidate = plan(); candidate["execution_authority"] = True
    with pytest.raises(HSlowPersistenceError, match="non-authorising"):
        HSlowLifecycleStore(db.connect, stream_registry=registry()).persist_plan(candidate)


def test_schema_has_isolated_scope_atomic_claim_and_non_retryable_unknown_state():
    source = open("sql/h_slow_lifecycle.sql", encoding="utf-8").read()
    assert "account_scope TEXT NOT NULL" in source
    assert "terminal_instance TEXT NOT NULL" in source
    assert "SUBMISSION_UNKNOWN" in source and "TERMINAL_RECONCILED" in source
    adapter = open("src/forex/h_slow_persistence.py", encoding="utf-8").read()
    assert "claim_status='PENDING'" in adapter
    assert "FOR UPDATE" in adapter


def test_unresolved_read_includes_pending_claimed_and_unknown_but_not_terminal():
    db, candidate = Database(), plan()
    store = HSlowLifecycleStore(db.connect, stream_registry=registry())
    store.persist_plan(candidate)
    assert [item.claim_status for item in store.unresolved_intents()] == ["PENDING"]
    store.claim_intent(candidate["intent"]["action_id"])
    assert [item.claim_status for item in store.unresolved_intents()] == ["CLAIMED"]
    store.mark_submission_unknown(candidate["intent"]["action_id"])
    assert [item.claim_status for item in store.unresolved_intents()] == ["SUBMISSION_UNKNOWN"]
    store.reconcile_terminal(candidate["intent"]["action_id"], terminal_status="OPEN_CONFIRMED", terminal_reference="ticket_hslow_1", observed_at_utc="2026-09-12T00:00:00Z")
    assert store.unresolved_intents() == ()


def test_open_deadline_is_utc_immutable_and_blocks_claim_after_database_deadline():
    db, candidate = Database(), plan()
    store = HSlowLifecycleStore(db.connect, stream_registry=registry())
    deadline = "2026-10-01T00:00:00Z"
    persisted = store.persist_plan(candidate, valid_until_utc=deadline)
    assert persisted.valid_until_utc == deadline
    assert store.persist_plan(candidate, valid_until_utc="2026-10-01T00:00:00+00:00").valid_until_utc == deadline
    with pytest.raises(HSlowPersistenceError, match="collision"):
        store.persist_plan(candidate, valid_until_utc="2026-11-01T00:00:00Z")
    db.now = deadline
    assert store.claim_intent(candidate["intent"]["action_id"]) is None


def test_deadline_rejects_non_utc_close_and_non_actionable_plans():
    store = HSlowLifecycleStore(Database().connect, stream_registry=registry())
    with pytest.raises(HSlowPersistenceError, match="UTC"):
        store.persist_plan(plan(), valid_until_utc="2026-10-01T00:00:00")
    with pytest.raises(HSlowPersistenceError, match="only OPEN"):
        store.persist_plan(plan("CLOSE", "ticket_hslow_1"), valid_until_utc="2026-10-01T00:00:00Z")
    no_intent = plan(); no_intent.update(next_action="HOLD", intent=None)
    with pytest.raises(HSlowPersistenceError, match="deadline"):
        store.persist_plan(no_intent, valid_until_utc="2026-10-01T00:00:00Z")


def test_expiry_is_idempotent_non_submission_without_broker_reconciliation():
    db, candidate = Database(), plan()
    store = HSlowLifecycleStore(db.connect, stream_registry=registry())
    store.persist_plan(candidate, valid_until_utc="2026-09-01T00:00:00Z")
    expired = store.expire_pending_intents()
    assert len(expired) == 1
    assert expired[0].claim_status == "EXPIRED_NOT_SUBMITTED"
    assert expired[0].terminal_status == "NOT_SUBMITTED"
    assert expired[0].expired_at_utc == db.now
    assert db.reconciled == set()
    assert db.expired == {candidate["intent"]["action_id"]}
    assert store.unresolved_intents() == ()
    assert store.expire_pending_intents() == ()
    assert store.claim_intent(candidate["intent"]["action_id"]) is None


def test_expiry_leaves_undated_claimed_unknown_and_close_intents_unmodified():
    db = Database()
    store = HSlowLifecycleStore(db.connect, stream_registry=registry())
    undated = plan()
    store.persist_plan(undated)
    claimed = plan("CLOSE", "ticket_hslow_1")
    store.persist_plan(claimed)
    store.claim_intent(claimed["intent"]["action_id"])
    assert store.expire_pending_intents() == ()
    assert db.rows[undated["intent"]["action_id"]].status == "PENDING"
    assert db.rows[claimed["intent"]["action_id"]].status == "CLAIMED"
    store.mark_submission_unknown(claimed["intent"]["action_id"])
    assert store.expire_pending_intents() == ()
    assert db.rows[claimed["intent"]["action_id"]].status == "SUBMISSION_UNKNOWN"


def test_schema_has_migration_deadline_db_clock_and_append_only_non_submission_expiry():
    source = open("sql/h_slow_lifecycle.sql", encoding="utf-8").read()
    assert "ADD COLUMN IF NOT EXISTS valid_until_utc TIMESTAMPTZ" in source
    assert "EXPIRED_NOT_SUBMITTED" in source
    assert "forex.h_slow_lifecycle_expiry" in source
    assert "reject_h_slow_expiry_mutation" in source
    adapter = open("src/forex/h_slow_persistence.py", encoding="utf-8").read()
    assert "valid_until_utc IS NULL OR valid_until_utc > clock_timestamp()" in adapter
    assert "valid_until_utc <= now()" in adapter
