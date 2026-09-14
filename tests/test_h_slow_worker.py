from __future__ import annotations

import pytest

from forex.h_slow_lifecycle import HSlowLifecycleError
from forex.h_slow_persistence import HSlowLifecycleStore, HSlowPersistenceError
from forex.h_slow_worker import run_h_slow_worker_once
from tests.test_h_slow_lifecycle import decision, observation, registry
from tests.test_h_slow_persistence import Database


def envelope(*, observed_at="2026-09-01T12:00:00Z", received_at="2026-09-01T12:00:01Z") -> dict:
    return {"schema_version": "forex.h-slow.timed-observation.v1", "observed_at_utc": observed_at,
            "received_at_utc": received_at, "observation": observation()}


def run(store, *, target="BUY", current_envelope=None) -> dict:
    return run_h_slow_worker_once(
        store=store, research_decision=decision(target), envelope=current_envelope or envelope(),
        stream_registry=registry(), evaluated_at_utc="2026-09-01T12:00:02Z",
        maximum_observation_age_seconds=10.0,
    )


def test_worker_persists_actual_runtime_plan_but_submission_is_structurally_disabled():
    database = Database()
    result = run(HSlowLifecycleStore(database.connect, stream_registry=registry()))
    assert result["worker_state"] == "INTENT_PERSISTED"
    assert result["persisted_intent"]["claim_status"] == "PENDING"
    assert result["submission_status"] == "DISABLED_NOT_ROUTED"
    assert result["execution_authority"] is False
    assert result["observation_sha256"].startswith("sha256:")
    assert len(database.rows) == 1


def test_restart_unknown_is_read_from_store_and_cannot_be_bypassed_by_flat_observation():
    database = Database()
    first_store = HSlowLifecycleStore(database.connect, stream_registry=registry())
    first = run(first_store)
    action_id = first["persisted_intent"]["action_id"]
    first_store.claim_intent(action_id)
    first_store.mark_submission_unknown(action_id)
    restarted = run(HSlowLifecycleStore(database.connect, stream_registry=registry()))
    assert restarted["worker_state"] == "DURABLE_RECONCILIATION_REQUIRED"
    assert restarted["unresolved_intents"][0]["claim_status"] == "SUBMISSION_UNKNOWN"
    assert restarted["persisted_intent"]["claim_status"] == "SUBMISSION_UNKNOWN"
    assert len(database.rows) == 1


def test_new_decision_does_not_write_when_previous_intent_is_durably_unresolved():
    database = Database()
    store = HSlowLifecycleStore(database.connect, stream_registry=registry())
    initial = run(store)
    store.claim_intent(initial["persisted_intent"]["action_id"])
    store.mark_submission_unknown(initial["persisted_intent"]["action_id"])
    blocked = run(HSlowLifecycleStore(database.connect, stream_registry=registry()), target="SELL")
    assert blocked["worker_state"] == "DURABLE_RECONCILIATION_REQUIRED"
    assert blocked["persisted_intent"] is None
    assert len(database.rows) == 1


def test_stale_observation_fails_before_any_durable_read_or_write():
    database = Database()
    store = HSlowLifecycleStore(database.connect, stream_registry=registry())
    with pytest.raises(HSlowLifecycleError, match="stale"):
        run(store, current_envelope=envelope(observed_at="2026-09-01T11:59:00Z"))
    assert database.rows == {}


def test_mismatched_store_refused_before_database_access():
    different = registry()
    different["streams"][1]["terminal_instance"] = "replacement_terminal"
    def forbidden_connect():
        raise AssertionError("mismatched store must not access the database")
    store = HSlowLifecycleStore(forbidden_connect, stream_registry=different)
    with pytest.raises(HSlowPersistenceError, match="worker/store isolation"):
        run(store)


def test_changed_terminal_cannot_hide_prior_account_intent():
    database = Database()
    first = run(HSlowLifecycleStore(database.connect, stream_registry=registry()))
    changed = registry()
    changed["streams"][1]["terminal_instance"] = "replacement_terminal"
    changed_envelope = envelope()
    changed_envelope["observation"]["terminal_instance"] = "replacement_terminal"
    result = run_h_slow_worker_once(
        store=HSlowLifecycleStore(database.connect, stream_registry=changed),
        research_decision=decision("SELL"), envelope=changed_envelope, stream_registry=changed,
        evaluated_at_utc="2026-09-01T12:00:02Z", maximum_observation_age_seconds=10,
    )
    assert result["worker_state"] == "DURABLE_RECONCILIATION_REQUIRED"
    assert result["persisted_intent"] is None
    assert result["unresolved_intents"][0]["action_id"] == first["persisted_intent"]["action_id"]
    assert len(database.rows) == 1


def test_worker_binds_month_end_deadline_and_expires_before_reading(monkeypatch):
    database = Database()
    store = HSlowLifecycleStore(database.connect, stream_registry=registry())
    calls = []
    persist = store.persist_plan
    unresolved = store.unresolved_intents
    def expire():
        calls.append("expire")
        return ()
    def read():
        calls.append("read")
        return unresolved()
    def retain(plan, *, valid_until_utc=None):
        calls.append(valid_until_utc)
        return persist(plan, valid_until_utc=valid_until_utc)
    monkeypatch.setattr(store, "expire_pending_intents", expire)
    monkeypatch.setattr(store, "unresolved_intents", read)
    monkeypatch.setattr(store, "persist_plan", retain)
    result = run(store)
    assert calls == ["expire", "read", "2026-10-01T00:00:00Z"]
    assert result["expired_intents"] == []


def test_close_plan_never_gets_monthly_entry_expiry(monkeypatch):
    database = Database()
    store = HSlowLifecycleStore(database.connect, stream_registry=registry())
    received = []
    persist = store.persist_plan
    def retain(plan, *, valid_until_utc=None):
        received.append((plan["next_action"], valid_until_utc))
        return persist(plan, valid_until_utc=valid_until_utc)
    monkeypatch.setattr(store, "persist_plan", retain)
    current = envelope()
    current["observation"] = observation(positions=[{"ticket_id": "owned_ticket", "owner_stream_id": "H_SLOW", "direction": "BUY", "position_status": "OPEN"}])
    run(store, target="SELL", current_envelope=current)
    assert received == [("CLOSE", None)]


def test_expired_replay_is_reported_without_resurrection():
    database = Database()
    store = HSlowLifecycleStore(database.connect, stream_registry=registry())
    initial = run(store)
    database.now = "2026-10-01T00:00:00Z"
    result = run(store)
    assert result["worker_state"] == "INTENT_EXPIRED_NOT_SUBMITTED"
    assert result["expired_intents"][0]["action_id"] == initial["persisted_intent"]["action_id"]
    assert result["persisted_intent"]["claim_status"] == "EXPIRED_NOT_SUBMITTED"
    assert len(database.rows) == 1
    assert store.claim_intent(initial["persisted_intent"]["action_id"]) is None
