"""Opt-in destructive integration check for an explicitly disposable PostgreSQL DB.

Set ``FOREX_H_SLOW_TEST_DSN`` to a loopback DSN whose database name begins
``forex_hslow_`` and ``FOREX_H_SLOW_ALLOW_SCHEMA_RESET=YES``.  The test is
skipped otherwise; it never discovers a database or reads a production DSN.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest


DSN = os.environ.get("FOREX_H_SLOW_TEST_DSN")
if not DSN:
    pytestmark = pytest.mark.skip(reason="FOREX_H_SLOW_TEST_DSN is not set")


@pytest.fixture
def pg_connect():
    psycopg = pytest.importorskip("psycopg")
    if os.environ.get("FOREX_H_SLOW_ALLOW_SCHEMA_RESET") != "YES":
        pytest.skip("schema reset is not explicitly authorised")
    connection = psycopg.connect(DSN)
    try:
        if not connection.info.dbname.startswith("forex_hslow_"):
            pytest.skip("DSN database is not explicitly disposable")
        if connection.info.host not in {"127.0.0.1", "localhost", "::1"}:
            pytest.skip("DSN host is not loopback")
        with connection:
            connection.execute("DROP SCHEMA IF EXISTS forex CASCADE; CREATE SCHEMA forex;")
            connection.execute(Path("sql/h_slow_lifecycle.sql").read_text(encoding="utf-8"))
    finally:
        connection.close()

    return lambda: psycopg.connect(DSN)


def test_real_h_slow_store_lifecycle_on_disposable_postgres(pg_connect):
    import psycopg

    from forex.h_slow_persistence import HSlowLifecycleStore
    from tests.test_h_slow_lifecycle import plan, registry

    connect = pg_connect

    first = plan()
    store = HSlowLifecycleStore(connect, stream_registry=registry())
    assert store.persist_plan(first).claim_status == "PENDING"
    assert store.claim_intent(first["intent"]["action_id"]).claim_status == "CLAIMED"
    assert store.mark_submission_unknown(first["intent"]["action_id"]).claim_status == "SUBMISSION_UNKNOWN"
    assert HSlowLifecycleStore(connect, stream_registry=registry()).claim_intent(first["intent"]["action_id"]) is None

    close = plan("SELL", positions=[{"ticket_id": "ticket_hslow_1", "owner_stream_id": "H_SLOW", "direction": "BUY", "position_status": "OPEN"}])
    store.persist_plan(close)
    with pytest.raises(psycopg.errors.UniqueViolation):
        store.claim_intent(close["intent"]["action_id"])
    assert store.reconcile_terminal(first["intent"]["action_id"], terminal_status="OPEN_CONFIRMED", terminal_reference="local-observation-1", observed_at_utc="2026-09-12T00:00:00Z").claim_status == "TERMINAL_RECONCILED"
    assert store.claim_intent(close["intent"]["action_id"]).claim_status == "CLAIMED"
    assert store.reconcile_terminal(close["intent"]["action_id"], terminal_status="CLOSE_CONFIRMED", terminal_reference="local-observation-2", observed_at_utc="2026-09-12T00:01:00Z").claim_status == "TERMINAL_RECONCILED"


def test_real_expiry_prevents_claim_and_keeps_non_submission_audit(pg_connect):
    from datetime import timedelta
    from forex.h_slow_persistence import HSlowLifecycleStore, HSlowPersistenceError
    from tests.test_h_slow_lifecycle import plan, registry

    store = HSlowLifecycleStore(pg_connect, stream_registry=registry())
    with pg_connect() as connection:
        now = connection.execute("SELECT now()").fetchone()[0]
    expired_deadline = (now - timedelta(days=1)).isoformat().replace("+00:00", "Z")
    candidate = plan()
    action_id = candidate["intent"]["action_id"]
    store.persist_plan(candidate, valid_until_utc=expired_deadline)
    assert store.claim_intent(action_id) is None
    expired = store.expire_pending_intents()
    assert len(expired) == 1
    assert expired[0].claim_status == "EXPIRED_NOT_SUBMITTED"
    assert store.expire_pending_intents() == ()
    assert store.unresolved_intents() == ()
    assert store.claim_intent(action_id) is None
    assert store.persist_plan(candidate, valid_until_utc=expired_deadline).claim_status == "EXPIRED_NOT_SUBMITTED"
    with pytest.raises(HSlowPersistenceError):
        store.persist_plan(candidate, valid_until_utc=(now + timedelta(days=1)).isoformat())
    with pg_connect() as connection:
        # Expiry is not a broker response or a claimed execution attempt.
        assert connection.execute("SELECT count(*) FROM forex.h_slow_lifecycle_reconciliation").fetchone()[0] == 0
        assert connection.execute("SELECT claimed_at_utc FROM forex.h_slow_lifecycle_intent WHERE action_id=%s", (action_id,)).fetchone()[0] is None
        audit = connection.execute("SELECT expiry_reason,expired_at_utc FROM forex.h_slow_lifecycle_expiry WHERE action_id=%s", (action_id,)).fetchone()
        assert audit[0] == "OPEN_INTENT_EXPIRED_BEFORE_SUBMISSION"
        assert audit[1] >= now
    import psycopg
    with pytest.raises(psycopg.errors.CheckViolation):
        with pg_connect() as connection:
            connection.execute("UPDATE forex.h_slow_lifecycle_intent SET terminal_status=NULL WHERE action_id=%s", (action_id,))
    with pytest.raises(psycopg.errors.RaiseException):
        with pg_connect() as connection:
            connection.execute("DELETE FROM forex.h_slow_lifecycle_expiry WHERE action_id=%s", (action_id,))


def test_real_expiry_preserves_undated_close_and_unknown_work(pg_connect):
    from forex.h_slow_persistence import HSlowLifecycleStore
    from tests.test_h_slow_lifecycle import plan, registry
    store = HSlowLifecycleStore(pg_connect, stream_registry=registry())
    candidate = plan()
    action_id = candidate["intent"]["action_id"]
    store.persist_plan(candidate)
    assert store.expire_pending_intents() == ()
    store.claim_intent(action_id)
    store.mark_submission_unknown(action_id)
    close = plan("SELL", positions=[{"ticket_id": "owned_ticket", "owner_stream_id": "H_SLOW", "direction": "BUY", "position_status": "OPEN"}])
    store.persist_plan(close)
    assert store.expire_pending_intents() == ()
    assert {row.claim_status for row in store.unresolved_intents()} == {"PENDING", "SUBMISSION_UNKNOWN"}


def test_expiry_migration_preserves_legacy_undated_intent(pg_connect):
    from forex.h_slow_persistence import HSlowLifecycleStore
    from tests.test_h_slow_lifecycle import plan, registry
    store = HSlowLifecycleStore(pg_connect, stream_registry=registry())
    candidate = plan()
    store.persist_plan(candidate)
    with pg_connect() as connection:
        # Reproduce the old create-only schema's missing fields and restrictive
        # claim-state check on this explicitly disposable database only.
        connection.execute("ALTER TABLE forex.h_slow_lifecycle_intent DROP COLUMN valid_until_utc, DROP COLUMN expired_at_utc CASCADE")
        connection.execute("ALTER TABLE forex.h_slow_lifecycle_intent DROP CONSTRAINT h_slow_lifecycle_intent_claim_status_check")
        connection.execute("ALTER TABLE forex.h_slow_lifecycle_intent ADD CONSTRAINT h_slow_lifecycle_intent_claim_status_check CHECK (claim_status IN ('PENDING','CLAIMED','SUBMISSION_UNKNOWN','TERMINAL_RECONCILED'))")
        connection.execute("ALTER TABLE forex.h_slow_lifecycle_intent ADD CONSTRAINT owner_additional_rule CHECK (claim_status <> 'TERMINAL_RECONCILED' OR terminal_reference IS NOT NULL)")
        connection.execute(Path("sql/h_slow_lifecycle.sql").read_text())
        connection.execute(Path("sql/h_slow_lifecycle.sql").read_text())
        assert connection.execute("SELECT count(*) FROM pg_constraint WHERE conrelid='forex.h_slow_lifecycle_intent'::regclass AND conname='owner_additional_rule'").fetchone()[0] == 1
    assert store.expire_pending_intents() == ()
    retained = store.persist_plan(candidate)
    assert retained.valid_until_utc is None
    assert retained.claim_status == "PENDING"


def test_database_session_timezone_does_not_change_deadline(pg_connect):
    from forex.h_slow_persistence import HSlowLifecycleStore
    from tests.test_h_slow_lifecycle import plan, registry
    def local_zone():
        connection = pg_connect()
        connection.execute("SET TIME ZONE 'Pacific/Auckland'")
        return connection
    store = HSlowLifecycleStore(local_zone, stream_registry=registry())
    first = store.persist_plan(plan(), valid_until_utc="2099-10-01T00:00:00Z")
    assert first.valid_until_utc == "2099-10-01T00:00:00Z"
    assert store.persist_plan(plan(), valid_until_utc=first.valid_until_utc) == first


def test_claim_waiting_on_row_lock_cannot_outlive_entry_deadline(pg_connect):
    from concurrent.futures import ThreadPoolExecutor
    from datetime import timedelta
    from forex.h_slow_persistence import HSlowLifecycleStore
    from tests.test_h_slow_lifecycle import plan, registry
    store = HSlowLifecycleStore(pg_connect, stream_registry=registry())
    candidate = plan()
    with pg_connect() as connection:
        now = connection.execute("SELECT clock_timestamp()").fetchone()[0]
    deadline = (now + timedelta(seconds=1)).isoformat().replace("+00:00", "Z")
    store.persist_plan(candidate, valid_until_utc=deadline)
    locked = pg_connect()
    try:
        locked.execute("SELECT action_id FROM forex.h_slow_lifecycle_intent WHERE action_id=%s FOR UPDATE", (candidate["intent"]["action_id"],))
        with ThreadPoolExecutor(max_workers=1) as executor:
            attempt = executor.submit(store.claim_intent, candidate["intent"]["action_id"])
            locked.execute("SELECT pg_sleep(1.2)")
            locked.commit()
            assert attempt.result(timeout=5) is None
    finally:
        locked.close()
    assert len(store.expire_pending_intents()) == 1


def test_claim_waiting_on_account_index_rolls_back_after_deadline(pg_connect):
    from concurrent.futures import ThreadPoolExecutor
    from datetime import timedelta
    from forex.h_slow_persistence import HSlowLifecycleStore
    from tests.test_h_slow_lifecycle import plan, registry
    store = HSlowLifecycleStore(pg_connect, stream_registry=registry())
    prior, candidate = plan(), plan("SELL")
    store.persist_plan(prior)
    store.claim_intent(prior["intent"]["action_id"])
    with pg_connect() as connection:
        now = connection.execute("SELECT clock_timestamp()").fetchone()[0]
    store.persist_plan(candidate, valid_until_utc=(now + timedelta(seconds=1)).isoformat())
    locked = pg_connect()
    try:
        # Test-only terminal fixture holds the unique-index change uncommitted.
        locked.execute("UPDATE forex.h_slow_lifecycle_intent SET claim_status='TERMINAL_RECONCILED', terminal_status='NOT_SUBMITTED', reconciled_at_utc=now(), terminal_reference='test-only' WHERE action_id=%s", (prior["intent"]["action_id"],))
        with ThreadPoolExecutor(max_workers=1) as executor:
            attempt = executor.submit(store.claim_intent, candidate["intent"]["action_id"])
            locked.execute("SELECT pg_sleep(1.2)")
            locked.commit()
            assert attempt.result(timeout=5) is None
    finally:
        locked.close()
    with pg_connect() as connection:
        assert connection.execute("SELECT claim_status,claimed_at_utc FROM forex.h_slow_lifecycle_intent WHERE action_id=%s", (candidate["intent"]["action_id"],)).fetchone() == ("PENDING", None)
    assert len(store.expire_pending_intents()) == 1
