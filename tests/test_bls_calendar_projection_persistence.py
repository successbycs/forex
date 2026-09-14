from __future__ import annotations

import pytest
import hashlib
import json

from forex.bls_calendar_projection_persistence import BLSProjectionPersistenceError, persist_bls_projection


def fact(identifier="cpi:one", revision=1, **changes):
    value = {"source_family": "CPI", "source_url": "https://www.bls.gov/schedule/news_release/cpi.htm", "capture_completed_at_utc": "2026-09-13T00:00:00Z", "raw_sha256": "sha256:" + "1" * 64, "receipt_sha256": "sha256:" + "2" * 64, "event_identifier": identifier, "scheduled_at_utc": "2026-10-01T12:00:00Z", "event_title": "CPI", "country_code": "US", "currency_code": "USD", "impact": "UNKNOWN", "qualification_state": "QUALIFIED", "qualification_reason": None, "source_revision": revision, "event_payload": {"record": identifier}}
    return {**value, **changes}


def projection(*facts):
    value = {"schema_version": "forex.bls-journal-calendar-facts.v1", "journal_sha256": "sha256:" + "a" * 64,
             "facts": list(facts), "execution_authority": False}
    return {**value, "projection_sha256": "sha256:" + hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()}


class Cursor:
    def __init__(self, db): self.db, self.row = db, None
    def __enter__(self): return self
    def __exit__(self, *args): return None
    def execute(self, query, params=()):
        self.db.queries.append((query, params)); self.row = None
        if query.startswith("INSERT INTO forex.economic_calendar_event_fact"):
            if self.db.fail_on_insert_number is not None and sum(1 for prior, _ in self.db.queries if prior.startswith("INSERT")) == self.db.fail_on_insert_number:
                raise RuntimeError("simulated database failure")
            if params[0] not in self.db.rows: self.db.rows.add(params[0]); self.row = (params[0],)
        elif query.startswith("SELECT fact_sha256 FROM forex.economic_calendar_event_fact"):
            self.row = (params[0],) if params[0] in self.db.rows else None
        else: raise AssertionError(query)
    def fetchone(self): return self.row


class Connection:
    def __init__(self, db, autocommit=False): self.db, self.autocommit = db, autocommit
    def __enter__(self): self.db.connections += 1; return self
    def __exit__(self, exc_type, *args):
        self.db.transactions += 1
        if exc_type is not None: self.db.rolled_back = True
    def cursor(self): return Cursor(self.db)


class Database:
    def __init__(self): self.rows, self.queries, self.connections, self.transactions = set(), [], 0, 0; self.rolled_back = False; self.fail_on_insert_number = None
    def connect(self): return Connection(self)


def test_all_facts_use_one_transaction_and_report_created_existing_counts():
    db = Database(); batch = projection(fact("one"), fact("two"))
    assert persist_bls_projection(batch, db.connect) == {"journal_sha256": batch["journal_sha256"], "created_count": 2, "existing_count": 0, "execution_authority": False}
    assert db.connections == db.transactions == 1
    repeat = persist_bls_projection(batch, db.connect)
    assert (repeat["created_count"], repeat["existing_count"]) == (0, 2)
    assert all("%s" in query for query, _ in db.queries if query.startswith("INSERT"))


def test_invalid_later_fact_refuses_before_connection_or_sql_write():
    db = Database()
    with pytest.raises(BLSProjectionPersistenceError, match="invalid canonical"):
        persist_bls_projection(projection(fact("good"), fact("bad", raw_sha256="sha256:bad")), db.connect)
    assert (db.connections, db.queries) == (0, [])


def test_substituted_fact_or_journal_under_an_old_projection_digest_refuses_before_io():
    db, batch = Database(), projection(fact("one"))
    batch["facts"][0]["event_title"] = "substituted"
    with pytest.raises(BLSProjectionPersistenceError, match="projection digest"):
        persist_bls_projection(batch, db.connect)
    assert (db.connections, db.queries) == (0, [])


@pytest.mark.parametrize("connection", [lambda db: Connection(db, autocommit=True), lambda db: type("NoAutocommit", (), {"__enter__": lambda self: self, "__exit__": lambda self, *args: None, "cursor": lambda self: None})()])
def test_autocommit_true_or_missing_refuses_before_cursor_or_sql(connection):
    db = Database()
    with pytest.raises(BLSProjectionPersistenceError, match="autocommit=False"):
        persist_bls_projection(projection(fact("one")), lambda: connection(db))
    assert db.queries == []


def test_mid_batch_database_failure_uses_connection_context_rollback_path():
    db = Database(); db.fail_on_insert_number = 2
    with pytest.raises(RuntimeError, match="simulated database failure"):
        persist_bls_projection(projection(fact("one"), fact("two")), db.connect)
    assert db.rolled_back is True


@pytest.mark.parametrize("bad", [
    {"schema_version": "wrong", "journal_sha256": "sha256:" + "a" * 64, "facts": [], "execution_authority": False, "projection_sha256": "sha256:" + "a" * 64},
    {"schema_version": "forex.bls-journal-calendar-facts.v1", "journal_sha256": "bad", "facts": [], "execution_authority": False, "projection_sha256": "sha256:" + "a" * 64},
    {"schema_version": "forex.bls-journal-calendar-facts.v1", "journal_sha256": "sha256:" + "a" * 64, "facts": [], "execution_authority": True, "projection_sha256": "sha256:" + "a" * 64},
])
def test_outer_projection_is_closed_and_non_authorising(bad):
    with pytest.raises(BLSProjectionPersistenceError):
        persist_bls_projection(bad, Database().connect)
