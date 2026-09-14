"""Typed PostgreSQL projection for already-retained economic-calendar facts.

This adapter neither reads files nor fetches sources. Raw publisher material
and receipts stay in their immutable provenance store; callers provide only
their hashes and an already-derived calendar fact.
"""
from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import json
import re
from typing import Any, Callable, Mapping, Protocol


class CalendarFactPersistenceError(ValueError):
    pass


class _Cursor(Protocol):
    def execute(self, query: str, params: tuple[Any, ...] = ...) -> Any: ...
    def fetchone(self) -> Any: ...
    def __enter__(self) -> "_Cursor": ...
    def __exit__(self, *args: Any) -> None: ...


class _Connection(Protocol):
    def cursor(self) -> _Cursor: ...
    def __enter__(self) -> "_Connection": ...
    def __exit__(self, *args: Any) -> None: ...


ConnectionFactory = Callable[[], _Connection]
_FIELDS = {"source_family", "source_url", "capture_completed_at_utc", "raw_sha256", "receipt_sha256",
           "event_identifier", "scheduled_at_utc", "event_title", "country_code", "currency_code",
           "impact", "qualification_state", "qualification_reason", "source_revision", "event_payload"}
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}\Z")
_QUALIFICATION = {"QUALIFIED", "QUARANTINED", "UNQUALIFIED", "UNKNOWN"}
_IMPACT = {"LOW", "MEDIUM", "HIGH", "UNKNOWN"}


def _utc(value: Any, field: str, *, nullable: bool = False) -> str | None:
    if value is None and nullable:
        return None
    if not isinstance(value, str):
        raise CalendarFactPersistenceError(f"{field} must be a UTC timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise CalendarFactPersistenceError(f"{field} must be a UTC timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != UTC.utcoffset(parsed):
        raise CalendarFactPersistenceError(f"{field} must use UTC")
    return parsed.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _text(value: Any, field: str, *, nullable: bool = False) -> str | None:
    if value is None and nullable:
        return None
    if not isinstance(value, str) or not value.strip():
        raise CalendarFactPersistenceError(f"{field} must be non-empty text")
    return value.strip()


def _object(value: Any, field: str) -> dict[str, Any]:
    """Freeze the complete normalized source record as finite JSON.

    Indexed columns are intentionally not the only calendar representation:
    the immutable provenance files remain source evidence, while this JSONB
    projection keeps every validated structured calendar attribute queryable.
    """
    if not isinstance(value, Mapping):
        raise CalendarFactPersistenceError(f"{field} must be a JSON object")
    try:
        decoded = json.loads(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False))
    except (TypeError, ValueError) as exc:
        raise CalendarFactPersistenceError(f"{field} must be finite JSON") from exc
    if not isinstance(decoded, dict):
        raise CalendarFactPersistenceError(f"{field} must be a JSON object")
    return decoded


def canonical_fact(fact: Mapping[str, Any]) -> dict[str, Any]:
    """Validate one closed, non-authorising fact payload and hash it."""
    if not isinstance(fact, Mapping) or set(fact) != _FIELDS:
        raise CalendarFactPersistenceError("calendar fact fields are invalid")
    result = {field: fact[field] for field in _FIELDS}
    for field in ("source_family", "source_url", "event_identifier", "event_title"):
        result[field] = _text(result[field], field)
    if not result["source_url"].startswith("https://"):
        raise CalendarFactPersistenceError("source_url must be HTTPS")
    for field in ("raw_sha256", "receipt_sha256"):
        if not isinstance(result[field], str) or not _DIGEST.fullmatch(result[field]):
            raise CalendarFactPersistenceError(f"{field} must be a sha256 digest")
    result["capture_completed_at_utc"] = _utc(result["capture_completed_at_utc"], "capture_completed_at_utc")
    result["scheduled_at_utc"] = _utc(result["scheduled_at_utc"], "scheduled_at_utc", nullable=True)
    for field, width in (("country_code", 2), ("currency_code", 3)):
        value = result[field]
        if value is not None and (not isinstance(value, str) or not re.fullmatch(rf"[A-Z]{{{width}}}", value)):
            raise CalendarFactPersistenceError(f"{field} is invalid")
    if result["impact"] is not None and result["impact"] not in _IMPACT:
        raise CalendarFactPersistenceError("impact is invalid")
    if result["qualification_state"] not in _QUALIFICATION:
        raise CalendarFactPersistenceError("qualification_state is invalid")
    result["qualification_reason"] = _text(result["qualification_reason"], "qualification_reason", nullable=True)
    if type(result["source_revision"]) is not int or result["source_revision"] < 1:
        raise CalendarFactPersistenceError("source_revision is invalid")
    result["event_payload"] = _object(result["event_payload"], "event_payload")
    encoded = json.dumps(result, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return {**result, "fact_sha256": "sha256:" + hashlib.sha256(encoded).hexdigest(), "execution_authority": False}


class CalendarFactStore:
    """Fixed-query, idempotent writer; it never applies the SQL migration."""
    def __init__(self, connection_factory: ConnectionFactory):
        self._connection_factory = connection_factory

    def persist(self, fact: Mapping[str, Any]) -> dict[str, Any]:
        row = canonical_fact(fact)
        fields = ("fact_sha256", "source_family", "source_url", "capture_completed_at_utc", "raw_sha256", "receipt_sha256", "event_identifier", "scheduled_at_utc", "event_title", "country_code", "currency_code", "impact", "qualification_state", "qualification_reason", "source_revision")
        # Do not rely on a particular PostgreSQL driver's implicit dict
        # adaptation. The explicit canonical JSON text and SQL JSONB cast work
        # for a normal psycopg connection and keep the fact hash reproducible.
        params = (*tuple(row[name] for name in fields), json.dumps(row["event_payload"], sort_keys=True, separators=(",", ":"), allow_nan=False))
        with self._connection_factory() as connection, connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO forex.economic_calendar_event_fact (fact_sha256,source_family,source_url,capture_completed_at_utc,raw_sha256,receipt_sha256,event_identifier,scheduled_at_utc,event_title,country_code,currency_code,impact,qualification_state,qualification_reason,source_revision,event_payload) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb) ON CONFLICT (fact_sha256) DO NOTHING RETURNING fact_sha256",
                params,
            )
            inserted = cursor.fetchone()
            if inserted is None:
                cursor.execute("SELECT fact_sha256 FROM forex.economic_calendar_event_fact WHERE fact_sha256=%s FOR UPDATE", (row["fact_sha256"],))
                if cursor.fetchone() is None:
                    raise CalendarFactPersistenceError("calendar fact disappeared after conflict")
        return {"fact_sha256": row["fact_sha256"], "status": "CREATED" if inserted else "EXISTING", "execution_authority": False}
