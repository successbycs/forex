from __future__ import annotations

import pytest

from forex.calendar_fact_persistence import CalendarFactPersistenceError, CalendarFactStore, canonical_fact


def fact(**changes):
    value = {"source_family": "FOMC_POLICY_DECISION", "source_url": "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm", "capture_completed_at_utc": "2026-09-13T00:00:00Z", "raw_sha256": "sha256:" + "1" * 64, "receipt_sha256": "sha256:" + "2" * 64, "event_identifier": "fomc:2026-01-28", "scheduled_at_utc": "2026-01-28T19:00:00Z", "event_title": "FOMC policy decision", "country_code": "US", "currency_code": "USD", "impact": "HIGH", "qualification_state": "QUALIFIED", "qualification_reason": None, "source_revision": 1, "event_payload": {"timezone": "America/New_York", "scheduled_at_local": "2026-01-28T14:00:00", "document_provenance": {"calendar": "retained"}}}
    return {**value, **changes}


class Cursor:
    def __init__(self, db): self.db, self.row, self.queries = db, None, []
    def __enter__(self): return self
    def __exit__(self, *args): return None
    def execute(self, query, params=()):
        self.queries.append((query, params)); self.row = None
        if query.startswith("INSERT INTO forex.economic_calendar_event_fact"):
            if params[0] not in self.db.rows: self.db.rows.add(params[0]); self.row = (params[0],)
        elif query.startswith("SELECT fact_sha256 FROM forex.economic_calendar_event_fact"):
            self.row = (params[0],) if params[0] in self.db.rows else None
        else: raise AssertionError(query)
    def fetchone(self): return self.row


class Connection:
    def __init__(self, db): self.db = db
    def __enter__(self): return self
    def __exit__(self, *args): return None
    def cursor(self):
        cursor = Cursor(self.db); self.db.cursors.append(cursor); return cursor


class Database:
    def __init__(self): self.rows, self.cursors = set(), []
    def connect(self): return Connection(self)


def test_persists_idempotently_with_fixed_parameterized_query():
    db = Database(); store = CalendarFactStore(db.connect)
    first, second = store.persist(fact()), store.persist(fact())
    assert (first["status"], second["status"]) == ("CREATED", "EXISTING")
    assert first["execution_authority"] is False
    inserts = [query for cursor in db.cursors for query, _ in cursor.queries if query.startswith("INSERT")]
    assert len(inserts) == 2 and all("%s::jsonb" in query and "raw_sha256" in query for query in inserts)
    payloads = [params[-1] for cursor in db.cursors for query, params in cursor.queries if query.startswith("INSERT")]
    assert payloads == ['{"document_provenance":{"calendar":"retained"},"scheduled_at_local":"2026-01-28T14:00:00","timezone":"America/New_York"}'] * 2


@pytest.mark.parametrize("changes", [{"source_url": "http://bad"}, {"raw_sha256": "no"}, {"scheduled_at_utc": "2026-01-28T19:00:00"}, {"country_code": "usa"}, {"qualification_state": "ALLOW_TRADE"}, {"source_revision": 0}, {"event_payload": []}, {"event_payload": {"bad": float("nan")}}])
def test_invalid_or_authorising_facts_refuse_before_database_io(changes):
    db = Database()
    with pytest.raises(CalendarFactPersistenceError): CalendarFactStore(db.connect).persist(fact(**changes))
    assert db.cursors == []


def test_canonical_hash_binds_provenance_and_event_content():
    baseline = canonical_fact(fact())
    assert baseline["fact_sha256"] != canonical_fact(fact(event_title="Changed title"))["fact_sha256"]
    assert baseline["fact_sha256"] != canonical_fact(fact(event_payload={"timezone": "UTC"}))["fact_sha256"]
    assert baseline["fact_sha256"] != canonical_fact(fact(qualification_state="QUARANTINED", qualification_reason="TIME_PRECISION_INSUFFICIENT"))["fact_sha256"]
    assert baseline["execution_authority"] is False


def test_manual_schema_declares_provenance_and_no_auto_apply_surface():
    source = open("sql/economic_calendar_facts.sql", encoding="utf-8").read()
    assert "economic_calendar_event_fact" in source and "raw_sha256" in source and "receipt_sha256" in source and "event_payload JSONB" in source
    assert "economic_calendar_event_fact_lookup_idx" in source
    adapter = open("src/forex/calendar_fact_persistence.py", encoding="utf-8").read()
    assert "CREATE TABLE" not in adapter and "execute(" in adapter
