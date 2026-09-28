"""Atomic, redacted event records emitted by the fixed M20 listener.

This module has no MetaTrader, broker, database, subprocess or network path.
It only writes an append-only local explanation of work already completed by
the caller.  A failed write is reported to the caller and must never alter the
trading decision.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid5


SCHEMA_VERSION = "forex.m20.decision-trace-event.v1"
COMPLETE_SCHEMA_VERSION = "forex.m20.decision-trace-complete.v1"
EVENT_TYPES = {
    "QUOTE_READ", "INPUTS_VALIDATED", "STRATEGIES_ASSESSED",
    "OWNER_AND_GATES_RESOLVED", "PROPOSAL_PERSISTED", "EXECUTION_RESULT",
    "RECONCILIATION_RESULT", "ASSESSMENT_FAILED",
}
TRACE_FACT_FIELDS = {
    "server", "symbol", "bid", "ask", "spread_points", "freshness_seconds",
    "completed_m1_count", "m1_input_status", "safety_gates", "entry_allowed",
    "pause_reason", "strategies", "selected_strategy_id", "selection_status",
    "market_regime", "market_regime_reason", "cost_coverage_status", "action",
    "rationale", "planned_entry", "planned_stop_loss", "planned_take_profit",
    "planned_notional_usd", "execution_status", "attempt_id", "broker_retcode",
    "reconciliation_status", "reconciliation_reason",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _canonical(value: dict[str, Any]) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _safe_value(value: Any) -> bool:
    if value is None or isinstance(value, (str, int, float, bool)):
        return not isinstance(value, float) or value == value and abs(value) != float("inf")
    if isinstance(value, list):
        return all(_safe_value(item) for item in value)
    if isinstance(value, dict):
        return all(isinstance(key, str) and _safe_value(item) for key, item in value.items())
    return False


class DecisionTraceError(ValueError):
    """The caller supplied an unsafe or inconsistent trace record."""


class DecisionTraceWriter:
    """Publish one immutable redacted record for each completed listener phase."""

    def __init__(self, root: Path, *, run_id: str, listener_release_id: str,
                 configuration_fingerprint: str) -> None:
        if not all(isinstance(value, str) and value for value in (run_id, listener_release_id, configuration_fingerprint)):
            raise DecisionTraceError("trace identity is invalid")
        self.root = root / listener_release_id / run_id
        self.run_id = run_id
        self.listener_release_id = listener_release_id
        self.configuration_fingerprint = configuration_fingerprint
        self.sequence = 0
        self.event_hashes: list[str] = []

    def emit(self, event_type: str, facts: dict[str, Any], *, proposal_id: str | None = None,
             snapshot_id: str | None = None, decision_key: str | None = None,
             occurred_at_utc: str | None = None) -> dict[str, Any]:
        if event_type not in EVENT_TYPES or not isinstance(facts, dict):
            raise DecisionTraceError("trace event shape is invalid")
        if set(facts) - TRACE_FACT_FIELDS or not _safe_value(facts):
            raise DecisionTraceError("trace facts are not allowlisted or safe")
        if any(value is not None and (not isinstance(value, str) or not value) for value in (proposal_id, snapshot_id, decision_key)):
            raise DecisionTraceError("trace event identity is invalid")
        self.sequence += 1
        event_id = str(uuid5(NAMESPACE_URL, f"forex.m20.trace:{self.run_id}:{self.sequence}:{event_type}"))
        record = {
            "schema_version": SCHEMA_VERSION,
            "event_id": event_id,
            "sequence": self.sequence,
            "run_id": self.run_id,
            "listener_release_id": self.listener_release_id,
            "configuration_fingerprint": self.configuration_fingerprint,
            "occurred_at_utc": occurred_at_utc or _utc_now(),
            "event_type": event_type,
            "proposal_id": proposal_id,
            "snapshot_id": snapshot_id,
            "decision_key": decision_key,
            "facts": facts,
        }
        raw = _canonical(record)
        digest = "sha256:" + hashlib.sha256(raw).hexdigest()
        self._publish(f"{self.sequence:020d}.json", raw)
        self.event_hashes.append(digest)
        return {"event_id": event_id, "sequence": self.sequence, "event_sha256": digest}

    def complete(self, *, assessment_sequence: int, assessment_sha256: str | None,
                 proposal_id: str | None, snapshot_id: str | None, state: str) -> dict[str, Any]:
        if state not in {"TRACE_COMPLETE", "TRACE_INCOMPLETE"} or assessment_sequence <= 0:
            raise DecisionTraceError("trace completion state is invalid")
        if assessment_sha256 is not None and (not isinstance(assessment_sha256, str) or not assessment_sha256.startswith("sha256:")):
            raise DecisionTraceError("assessment hash is invalid")
        record = {
            "schema_version": COMPLETE_SCHEMA_VERSION,
            "run_id": self.run_id,
            "listener_release_id": self.listener_release_id,
            "configuration_fingerprint": self.configuration_fingerprint,
            "assessment_sequence": assessment_sequence,
            "assessment_sha256": assessment_sha256,
            "proposal_id": proposal_id,
            "snapshot_id": snapshot_id,
            "event_hashes": self.event_hashes,
            "state": state,
            "completed_at_utc": _utc_now(),
        }
        raw = _canonical(record)
        self._publish("complete.json", raw)
        return {"state": state, "run_id": self.run_id,
                "complete_sha256": "sha256:" + hashlib.sha256(raw).hexdigest()}

    def _publish(self, name: str, raw: bytes) -> None:
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        if not self.root.is_dir() or self.root.is_symlink():
            raise OSError("trace root is unsafe")
        target = self.root / name
        if target.exists() or target.is_symlink():
            if not target.is_file() or target.read_bytes() != raw:
                raise OSError("trace record conflicts with retained record")
            return
        staging = target.with_suffix(".pending")
        if staging.exists() or staging.is_symlink():
            raise OSError("trace staging record already exists")
        with staging.open("xb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(staging, target)
        finally:
            if staging.exists() and not staging.is_symlink():
                staging.unlink()


def bind_trace(root: Path, *, run_id: str, listener_release_id: str,
               configuration_fingerprint: str, last_sequence: int,
               assessment_sequence: int, assessment_sha256: str | None,
               proposal_id: str | None, snapshot_id: str | None) -> dict[str, Any]:
    """Atomically bind an emitted event set to one immutable assessment.

    This is called only after the listener has published its independent
    assessment-spool record.  It never recreates events or infers omissions;
    malformed, missing, or conflicting source records stay visibly incomplete.
    """
    if (not all(isinstance(value, str) and value for value in
                (run_id, listener_release_id, configuration_fingerprint))
            or not isinstance(last_sequence, int) or last_sequence < 1
            or not isinstance(assessment_sequence, int) or assessment_sequence < 1):
        return {"state": "TRACE_UNAVAILABLE", "reason": "INVALID_TRACE_REFERENCE"}
    writer = DecisionTraceWriter(root, run_id=run_id,
                                 listener_release_id=listener_release_id,
                                 configuration_fingerprint=configuration_fingerprint)
    hashes: list[str] = []
    state = "TRACE_COMPLETE"
    reason: str | None = None
    try:
        for sequence in range(1, last_sequence + 1):
            source = writer.root / f"{sequence:020d}.json"
            if (not source.is_file() or source.is_symlink()):
                state, reason = "TRACE_INCOMPLETE", "MISSING_EVENT"
                break
            raw = source.read_bytes()
            record = json.loads(raw)
            if (not isinstance(record, dict)
                    or record.get("schema_version") != SCHEMA_VERSION
                    or record.get("sequence") != sequence
                    or record.get("run_id") != run_id
                    or record.get("listener_release_id") != listener_release_id
                    or record.get("configuration_fingerprint") != configuration_fingerprint
                    or record.get("event_type") not in EVENT_TYPES
                    or not isinstance(record.get("facts"), dict)
                    or set(record["facts"]) - TRACE_FACT_FIELDS):
                state, reason = "TRACE_INCOMPLETE", "INVALID_EVENT"
                break
            if _canonical(record) != raw:
                state, reason = "TRACE_INCOMPLETE", "NONCANONICAL_EVENT"
                break
            hashes.append("sha256:" + hashlib.sha256(raw).hexdigest())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError):
        state, reason = "TRACE_INCOMPLETE", "UNREADABLE_EVENT"
    if assessment_sha256 is None:
        state, reason = "TRACE_INCOMPLETE", "ASSESSMENT_NOT_RETAINED"
    record = {
        "schema_version": COMPLETE_SCHEMA_VERSION,
        "run_id": run_id,
        "listener_release_id": listener_release_id,
        "configuration_fingerprint": configuration_fingerprint,
        "assessment_sequence": assessment_sequence,
        "assessment_sha256": assessment_sha256,
        "proposal_id": proposal_id,
        "snapshot_id": snapshot_id,
        "event_hashes": hashes,
        "state": state,
        "reason": reason,
        "completed_at_utc": _utc_now(),
    }
    try:
        raw = _canonical(record)
        writer._publish("complete.json", raw)
    except OSError:
        return {"state": "TRACE_UNAVAILABLE", "reason": "COMPLETION_WRITE_FAILED",
                "run_id": run_id}
    return {"state": state, "reason": reason, "run_id": run_id,
            "last_sequence": last_sequence,
            "complete_sha256": "sha256:" + hashlib.sha256(raw).hexdigest()}
