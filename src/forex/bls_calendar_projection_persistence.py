"""Atomic persistence of one already-verified BLS calendar projection.

This module accepts no store paths, credentials, SQL strings, source material,
or execution instructions.  It validates the closed projection value before
opening the supplied database connection.
"""
from __future__ import annotations

import json
import hashlib
import re
from typing import Any, Callable, Protocol

from forex.calendar_fact_persistence import CalendarFactPersistenceError, canonical_fact


class BLSProjectionPersistenceError(ValueError):
    pass


class _Cursor(Protocol):
    def execute(self, query: str, params: tuple[Any, ...] = ...) -> Any: ...
    def fetchone(self) -> Any: ...
    def __enter__(self) -> "_Cursor": ...
    def __exit__(self, *args: Any) -> None: ...


class _Connection(Protocol):
    autocommit: bool
    def cursor(self) -> _Cursor: ...
    def __enter__(self) -> "_Connection": ...
    def __exit__(self, *args: Any) -> None: ...


ConnectionFactory = Callable[[], _Connection]
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}\Z")
_PROJECTION_FIELDS = {"schema_version", "journal_sha256", "facts", "execution_authority", "projection_sha256"}
_FIELDS = ("fact_sha256", "source_family", "source_url", "capture_completed_at_utc", "raw_sha256", "receipt_sha256",
           "event_identifier", "scheduled_at_utc", "event_title", "country_code", "currency_code", "impact",
           "qualification_state", "qualification_reason", "source_revision")
_INSERT = (
    "INSERT INTO forex.economic_calendar_event_fact "
    "(fact_sha256,source_family,source_url,capture_completed_at_utc,raw_sha256,receipt_sha256,event_identifier,scheduled_at_utc,event_title,country_code,currency_code,impact,qualification_state,qualification_reason,source_revision,event_payload) "
    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb) ON CONFLICT (fact_sha256) DO NOTHING RETURNING fact_sha256"
)


def _validated_projection(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, dict) or set(value) != _PROJECTION_FIELDS:
        raise BLSProjectionPersistenceError("projection schema is invalid")
    if value.get("schema_version") != "forex.bls-journal-calendar-facts.v1":
        raise BLSProjectionPersistenceError("projection schema is invalid")
    if not isinstance(value.get("journal_sha256"), str) or not _DIGEST.fullmatch(value["journal_sha256"]):
        raise BLSProjectionPersistenceError("projection journal digest is invalid")
    if value.get("execution_authority") is not False or not isinstance(value.get("facts"), list):
        raise BLSProjectionPersistenceError("projection is not a non-authorising fact list")
    payload = {key: value[key] for key in _PROJECTION_FIELDS - {"projection_sha256"}}
    expected = "sha256:" + hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()
    if value.get("projection_sha256") != expected:
        raise BLSProjectionPersistenceError("projection digest does not bind journal and facts")
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for fact in value["facts"]:
        try:
            row = canonical_fact(fact)
        except CalendarFactPersistenceError as exc:
            raise BLSProjectionPersistenceError("projection contains an invalid canonical fact") from exc
        if row["fact_sha256"] in seen:
            raise BLSProjectionPersistenceError("projection contains duplicate canonical facts")
        seen.add(row["fact_sha256"])
        rows.append(row)
    return rows


def persist_bls_projection(projection: Any, connection_factory: ConnectionFactory) -> dict[str, Any]:
    """Persist all closed facts in one connection/cursor transaction scope."""
    if not callable(connection_factory):
        raise BLSProjectionPersistenceError("connection_factory must be callable")
    rows = _validated_projection(projection)
    created = existing = 0
    with connection_factory() as connection:
        # A caller-controlled autocommit connection would defeat batch
        # atomicity before the context manager can roll back a later failure.
        if getattr(connection, "autocommit", None) is not False:
            raise BLSProjectionPersistenceError("connection must expose autocommit=False for atomic persistence")
        with connection.cursor() as cursor:
            for row in rows:
                params = (*tuple(row[field] for field in _FIELDS),
                          json.dumps(row["event_payload"], sort_keys=True, separators=(",", ":"), allow_nan=False))
                cursor.execute(_INSERT, params)
                if cursor.fetchone() is None:
                    cursor.execute("SELECT fact_sha256 FROM forex.economic_calendar_event_fact WHERE fact_sha256=%s FOR UPDATE",
                                   (row["fact_sha256"],))
                    if cursor.fetchone() is None:
                        raise BLSProjectionPersistenceError("canonical fact disappeared after conflict")
                    existing += 1
                else:
                    created += 1
    return {"journal_sha256": projection["journal_sha256"], "created_count": created,
            "existing_count": existing, "execution_authority": False}
