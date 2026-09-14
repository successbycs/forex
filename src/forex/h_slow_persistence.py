"""PostgreSQL persistence for non-operational H_SLOW lifecycle intents.

This adapter deliberately accepts a connection factory rather than selecting a
database or reading environment settings.  It has no broker integration.  A
future authorised routing layer may claim an intent, but an ambiguous broker
result must be marked and reconciled; it can never be claimed again.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Callable, Mapping, Protocol

from .stream_isolation import StreamIsolationError, validate_stream_registry


class HSlowPersistenceError(ValueError):
    """A lifecycle plan or durable state transition is unsafe."""


class _ExpiredClaim(Exception):
    """Internal rollback signal when a database wait outlives a deadline."""


class _Cursor(Protocol):
    rowcount: int
    def execute(self, query: str, params: tuple[Any, ...] = ...) -> Any: ...
    def fetchone(self) -> Any: ...
    def fetchall(self) -> Any: ...
    def __enter__(self) -> "_Cursor": ...
    def __exit__(self, *args: Any) -> None: ...


class _Connection(Protocol):
    def cursor(self) -> _Cursor: ...
    def __enter__(self) -> "_Connection": ...
    def __exit__(self, *args: Any) -> None: ...


ConnectionFactory = Callable[[], _Connection]
_TERMINAL = frozenset({"OPEN_CONFIRMED", "OPEN_REJECTED", "CLOSE_CONFIRMED", "CLOSE_REJECTED", "NOT_SUBMITTED"})


@dataclass(frozen=True)
class LifecycleIntent:
    action_id: str
    action_kind: str
    ticket_id: str | None
    direction: str | None
    claim_status: str
    terminal_status: str | None
    valid_until_utc: str | None = None
    expired_at_utc: str | None = None


def _digest(value: dict[str, Any]) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _one(row: Any, message: str) -> tuple[Any, ...]:
    if row is None:
        raise HSlowPersistenceError(message)
    return tuple(row)


def _utc_timestamp(value: Any, *, field: str) -> str:
    """Return one canonical UTC timestamp, rejecting local/ambiguous input."""
    if not isinstance(value, str) or not value:
        raise HSlowPersistenceError(f"{field} must be a non-empty UTC timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise HSlowPersistenceError(f"{field} must be a valid UTC timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise HSlowPersistenceError(f"{field} must use UTC (+00:00 or Z)")
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _stored_utc_timestamp(value: Any, *, field: str) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise HSlowPersistenceError(f"stored {field} is not timezone-aware")
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    return _utc_timestamp(value, field=field)


def _intent(row: Any, message: str) -> LifecycleIntent:
    values = _one(row, message)
    if len(values) != 8:
        raise HSlowPersistenceError("lifecycle intent row shape is invalid")
    return LifecycleIntent(*values[:6], _stored_utc_timestamp(values[6], field="valid_until_utc"),
                           _stored_utc_timestamp(values[7], field="expired_at_utc"))


class HSlowLifecycleStore:
    """Durably persist and atomically claim H_SLOW plan intents.

    ``stream_registry`` is revalidated at construction.  No account identity
    is accepted from a caller: the only durable scope values are the opaque
    H_SLOW labels already bound to the isolation declaration.
    """

    def __init__(self, connection_factory: ConnectionFactory, *, stream_registry: Mapping[str, Any]):
        try:
            plan = validate_stream_registry(stream_registry)
        except StreamIsolationError as exc:
            raise HSlowPersistenceError(f"invalid stream isolation: {exc}") from exc
        self._connection_factory = connection_factory
        self._fingerprint = plan.registry_fingerprint
        hslow = next(row for row in stream_registry["streams"] if row["stream_id"] == "H_SLOW")
        self._account_scope = hslow["account_scope"]
        self._terminal_instance = hslow["terminal_instance"]

    @property
    def registry_fingerprint(self) -> str:
        """Immutable binding used to reject a mismatched runtime before I/O."""
        return self._fingerprint

    def persist_plan(self, lifecycle_plan: Mapping[str, Any], *, valid_until_utc: str | None = None) -> LifecycleIntent | None:
        """Insert an actionable plan once, returning its durable state.

        Replaying the same plan after a process restart retrieves the prior
        state.  A plan with no intent requires no durable execution record.
        """
        plan = self._validated_plan(lifecycle_plan)
        intent = plan["intent"]
        if intent is None:
            if valid_until_utc is not None:
                raise HSlowPersistenceError("a deadline requires an OPEN lifecycle intent")
            return None
        if valid_until_utc is not None and intent["kind"] != "OPEN":
            raise HSlowPersistenceError("only OPEN lifecycle intents can have a deadline")
        deadline = None if valid_until_utc is None else _utc_timestamp(valid_until_utc, field="valid_until_utc")
        with self._connection_factory() as connection, connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO forex.h_slow_lifecycle_intent "
                "(action_id,stream_id,account_scope,terminal_instance,isolation_registry_fingerprint,decision_sha256,action_kind,ticket_id,direction,valid_until_utc) "
                "VALUES (%s,'H_SLOW',%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (action_id) DO NOTHING "
                "RETURNING action_id,action_kind,ticket_id,direction,claim_status,terminal_status,valid_until_utc,expired_at_utc",
                (intent["action_id"], self._account_scope, self._terminal_instance, self._fingerprint,
                 plan["decision_sha256"], intent["kind"], intent["ticket_id"], intent["direction"], deadline),
            )
            row = cursor.fetchone()
            if row is None:
                cursor.execute(
                    "SELECT action_id,action_kind,ticket_id,direction,claim_status,terminal_status,valid_until_utc,expired_at_utc,"
                    "account_scope,terminal_instance,isolation_registry_fingerprint,decision_sha256 "
                    "FROM forex.h_slow_lifecycle_intent WHERE action_id=%s FOR UPDATE",
                    (intent["action_id"],),
                )
                existing = _one(cursor.fetchone(), "existing lifecycle intent disappeared")
                expected = (intent["action_id"], intent["kind"], intent["ticket_id"], intent["direction"],
                            deadline, self._account_scope, self._terminal_instance, self._fingerprint, plan["decision_sha256"])
                actual = (existing[0], existing[1], existing[2], existing[3], _stored_utc_timestamp(existing[6], field="valid_until_utc"),
                          existing[8], existing[9], existing[10], existing[11])
                if actual != expected:
                    raise HSlowPersistenceError("action ID collision has different isolation or decision binding")
                row = existing[:8]
        return _intent(row, "lifecycle intent insert failed")

    def claim_intent(self, action_id: str) -> LifecycleIntent | None:
        """Atomically change exactly one pending intent to CLAIMED.

        The conditional update is the concurrency control: a second runner,
        restart, ambiguous submission, or terminal reconciliation gets no row
        and must reconcile rather than retry the same intent.
        """
        try:
            return self._claim_intent(action_id)
        except _ExpiredClaim:
            return None

    def _claim_intent(self, action_id: str) -> LifecycleIntent | None:
        with self._connection_factory() as connection, connection.cursor() as cursor:
            # Acquire the row first, then check the wall clock in a second
            # statement. A predicate evaluated before a blocking row lock can
            # otherwise admit a target whose deadline passes during the wait.
            cursor.execute(
                "SELECT action_id FROM forex.h_slow_lifecycle_intent WHERE action_id=%s "
                "AND stream_id='H_SLOW' AND account_scope=%s AND terminal_instance=%s "
                "AND isolation_registry_fingerprint=%s FOR UPDATE",
                (action_id, self._account_scope, self._terminal_instance, self._fingerprint),
            )
            if cursor.fetchone() is None:
                return None
            cursor.execute(
                "UPDATE forex.h_slow_lifecycle_intent SET claim_status='CLAIMED',claimed_at_utc=clock_timestamp() "
                "WHERE action_id=%s AND stream_id='H_SLOW' AND account_scope=%s AND terminal_instance=%s "
                "AND isolation_registry_fingerprint=%s AND claim_status='PENDING' AND terminal_status IS NULL "
                "AND (valid_until_utc IS NULL OR valid_until_utc > clock_timestamp()) "
                "RETURNING action_id,action_kind,ticket_id,direction,claim_status,terminal_status,valid_until_utc,expired_at_utc",
                (action_id, self._account_scope, self._terminal_instance, self._fingerprint),
            )
            row = cursor.fetchone()
            if row is not None and row[6] is not None:
                # The UPDATE can additionally wait on the account-wide unique
                # index. Check again after all update-time waits and roll back
                # the entire transaction if the deadline passed meanwhile.
                cursor.execute("SELECT %s::timestamptz > clock_timestamp()", (row[6],))
                if _one(cursor.fetchone(), "claim deadline check failed")[0] is not True:
                    raise _ExpiredClaim()
        return None if row is None else _intent(row, "claimed lifecycle intent row is invalid")

    def expire_pending_intents(self) -> tuple[LifecycleIntent, ...]:
        """Terminally expire only unclaimed, dated OPEN intents in this exact scope.

        This uses PostgreSQL's clock rather than a caller clock.  Expiry is a
        non-submission conclusion, recorded separately from broker terminal
        reconciliation; it never changes CLAIMED, UNKNOWN, CLOSE, or legacy
        undated PENDING rows.
        """
        with self._connection_factory() as connection, connection.cursor() as cursor:
            cursor.execute(
                "WITH expired AS ("
                "UPDATE forex.h_slow_lifecycle_intent SET claim_status='EXPIRED_NOT_SUBMITTED',"
                "terminal_status='NOT_SUBMITTED',expired_at_utc=now() "
                "WHERE stream_id='H_SLOW' AND account_scope=%s AND terminal_instance=%s "
                "AND isolation_registry_fingerprint=%s AND action_kind='OPEN' AND claim_status='PENDING' "
                "AND valid_until_utc IS NOT NULL AND valid_until_utc <= now() "
                "RETURNING action_id,action_kind,ticket_id,direction,claim_status,terminal_status,valid_until_utc,expired_at_utc"
                "), audit AS ("
                "INSERT INTO forex.h_slow_lifecycle_expiry (action_id,expiry_reason,expired_at_utc) "
                "SELECT action_id,'OPEN_INTENT_EXPIRED_BEFORE_SUBMISSION',expired_at_utc FROM expired"
                ") SELECT action_id,action_kind,ticket_id,direction,claim_status,terminal_status,valid_until_utc,expired_at_utc "
                "FROM expired ORDER BY action_id",
                (self._account_scope, self._terminal_instance, self._fingerprint),
            )
            rows = cursor.fetchall()
        return tuple(_intent(row, "expired lifecycle intent row is invalid") for row in rows)

    def unresolved_intents(self) -> tuple[LifecycleIntent, ...]:
        """Return every entry-blocking H_SLOW intent on this account scope.

        ``PENDING`` is deliberately included: a persisted intent that has not
        been routed is still an unresolved intent, not permission to create a
        newer conflicting plan.  ``CLAIMED`` and ``SUBMISSION_UNKNOWN`` remain
        blocking across process restarts until explicit reconciliation. A
        terminal or configuration change cannot hide earlier account work;
        mutation methods still require the original exact registry binding.
        """
        with self._connection_factory() as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT action_id,action_kind,ticket_id,direction,claim_status,terminal_status,valid_until_utc,expired_at_utc "
                "FROM forex.h_slow_lifecycle_intent WHERE stream_id='H_SLOW' AND account_scope=%s "
                "AND claim_status IN ('PENDING','CLAIMED','SUBMISSION_UNKNOWN') ORDER BY created_at_utc,action_id",
                (self._account_scope,),
            )
            rows = cursor.fetchall()
        return tuple(_intent(row, "unresolved lifecycle intent row is invalid") for row in rows)

    def mark_submission_unknown(self, action_id: str) -> LifecycleIntent:
        """Persist ambiguity; this intentionally has no transition back to pending."""
        with self._connection_factory() as connection, connection.cursor() as cursor:
            cursor.execute(
                "UPDATE forex.h_slow_lifecycle_intent SET claim_status='SUBMISSION_UNKNOWN' "
                "WHERE action_id=%s AND stream_id='H_SLOW' AND account_scope=%s AND terminal_instance=%s "
                "AND isolation_registry_fingerprint=%s AND claim_status='CLAIMED' AND terminal_status IS NULL "
                "RETURNING action_id,action_kind,ticket_id,direction,claim_status,terminal_status,valid_until_utc,expired_at_utc",
                (action_id, self._account_scope, self._terminal_instance, self._fingerprint),
            )
            return _intent(cursor.fetchone(), "only a claimed unresolved intent can become submission-unknown")

    def reconcile_terminal(self, action_id: str, *, terminal_status: str, terminal_reference: str,
                           observed_at_utc: str) -> LifecycleIntent:
        """Append a terminal reconciliation and make the intent non-claimable."""
        if terminal_status not in _TERMINAL or not isinstance(terminal_reference, str) or not terminal_reference:
            raise HSlowPersistenceError("terminal reconciliation fields are invalid")
        if not isinstance(observed_at_utc, str) or not observed_at_utc.endswith("Z"):
            raise HSlowPersistenceError("observed_at_utc must be a UTC timestamp")
        with self._connection_factory() as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT action_kind FROM forex.h_slow_lifecycle_intent WHERE action_id=%s AND stream_id='H_SLOW' "
                "AND account_scope=%s AND terminal_instance=%s AND isolation_registry_fingerprint=%s FOR UPDATE",
                (action_id, self._account_scope, self._terminal_instance, self._fingerprint),
            )
            row = _one(cursor.fetchone(), "lifecycle intent is absent or outside this isolated scope")
            kind = row[0]
            if terminal_status != "NOT_SUBMITTED" and not terminal_status.startswith(kind):
                raise HSlowPersistenceError("terminal status does not match intent kind")
            cursor.execute(
                "INSERT INTO forex.h_slow_lifecycle_reconciliation "
                "(action_id,terminal_status,terminal_reference,observed_at_utc) VALUES (%s,%s,%s,%s) "
                "ON CONFLICT (action_id) DO NOTHING RETURNING action_id",
                (action_id, terminal_status, terminal_reference, observed_at_utc),
            )
            if cursor.fetchone() is None:
                raise HSlowPersistenceError("terminal reconciliation is already recorded")
            cursor.execute(
                "UPDATE forex.h_slow_lifecycle_intent SET claim_status='TERMINAL_RECONCILED',terminal_status=%s,"
                "terminal_reference=%s,reconciled_at_utc=%s WHERE action_id=%s AND claim_status IN ('CLAIMED','SUBMISSION_UNKNOWN') "
                "AND terminal_status IS NULL RETURNING action_id,action_kind,ticket_id,direction,claim_status,terminal_status,valid_until_utc,expired_at_utc",
                (terminal_status, terminal_reference, observed_at_utc, action_id),
            )
            return _intent(cursor.fetchone(), "terminal reconciliation requires a claimed or unknown intent")

    def _validated_plan(self, value: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(value, Mapping):
            raise HSlowPersistenceError("lifecycle plan must be a mapping")
        plan = dict(value)
        expected = {"schema_version", "stream_id", "decision_sha256", "isolation_registry_fingerprint",
                    "mandate_preflight_status", "lifecycle_state", "reason", "next_action", "intent", "execution_authority"}
        if set(plan) != expected or plan.get("schema_version") != "forex.h-slow.lifecycle-plan.v1":
            raise HSlowPersistenceError("lifecycle plan fields are invalid")
        if plan.get("stream_id") != "H_SLOW" or plan.get("execution_authority") is not False:
            raise HSlowPersistenceError("lifecycle plan is not a non-authorising H_SLOW plan")
        if plan.get("isolation_registry_fingerprint") != self._fingerprint:
            raise HSlowPersistenceError("lifecycle plan isolation fingerprint mismatch")
        intent = plan.get("intent")
        if plan.get("next_action") not in {"OPEN", "CLOSE"}:
            if intent is not None:
                raise HSlowPersistenceError("non-actionable lifecycle plan cannot contain intent")
            return plan
        if not isinstance(intent, dict) or set(intent) != {"action_id", "kind", "ticket_id", "direction"}:
            raise HSlowPersistenceError("actionable lifecycle plan intent is invalid")
        if intent["kind"] != plan["next_action"] or intent["kind"] not in {"OPEN", "CLOSE"}:
            raise HSlowPersistenceError("intent kind does not match lifecycle action")
        if intent["kind"] == "OPEN":
            if intent["ticket_id"] is not None or intent["direction"] not in {"BUY", "SELL"}:
                raise HSlowPersistenceError("open intent fields are invalid")
        elif intent["ticket_id"] is None or intent["direction"] is not None:
            raise HSlowPersistenceError("close intent fields are invalid")
        if intent["action_id"] != _digest({"decision_sha256": plan["decision_sha256"],
                                          "isolation_registry_fingerprint": self._fingerprint,
                                          "action": intent["kind"], "ticket_id": intent["ticket_id"]}):
            raise HSlowPersistenceError("intent action ID is not bound to this decision")
        return plan
