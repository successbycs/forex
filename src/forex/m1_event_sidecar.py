"""Pure, context-only sidecars for retained full M1 assessment exports.

The sidecar deliberately does not amend a proposal, a decision snapshot, or a
broker/audit record.  It binds those already-retained values to one independently
supplied BLS event-context report for later observation or replay. The I/O
boundary must hash actual source bytes and build that report from a verified
capture store; this pure helper checks consistency, not source authenticity.
"""
from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import json
import re
from typing import Any

from forex.event_annotations import EventAnnotationInputError, event_annotation
from forex.m20_retained_export import RetainedExportInputError, adapt_retained_m20_export
from forex.m20_policy_kernel import (
    _M20_BASE_SNAPSHOT_BODY_FIELDS, _M20_EXTENDED_SNAPSHOT_BODY_FIELDS,
    _snapshot_body_sha256,
)


SIDECAR_SCHEMA = "forex.m1.event-context-sidecar.v1"
_DIGEST = "sha256:"


class M1EventSidecarError(ValueError):
    """A full retained assessment or event context cannot be bound safely."""


def _canonical(value: Any) -> bytes:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise M1EventSidecarError("sidecar input must contain finite JSON values") from exc


def _copy(value: Any) -> Any:
    return json.loads(_canonical(value))


def _sha(value: Any) -> str:
    return _DIGEST + hashlib.sha256(_canonical(value)).hexdigest()


def _digest(value: object, *, field: str) -> str:
    if not isinstance(value, str) or re.fullmatch(r"sha256:[0-9a-f]{64}", value) is None:
        raise M1EventSidecarError(f"{field} must be a SHA-256 digest")
    try:
        int(value[len(_DIGEST):], 16)
    except ValueError as exc:
        raise M1EventSidecarError(f"{field} must be a SHA-256 digest") from exc
    return value


def _utc(value: object, *, field: str) -> tuple[datetime, str]:
    if not isinstance(value, str):
        raise M1EventSidecarError(f"{field} must be a timezone-aware timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise M1EventSidecarError(f"{field} must be a timezone-aware timestamp") from exc
    if parsed.tzinfo is None:
        raise M1EventSidecarError(f"{field} must be a timezone-aware timestamp")
    parsed = parsed.astimezone(UTC)
    return parsed, parsed.isoformat().replace("+00:00", "Z")


def _identity(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise M1EventSidecarError(f"{field} must be a non-empty string")
    return value


def _full_assessment(retained_assessment: Any, source_raw_sha256: str) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Adapt only the existing full-assessment retained-export shape."""
    _digest(source_raw_sha256, field="source_raw_sha256")
    try:
        adapted = adapt_retained_m20_export(retained_assessment, source_sha256=source_raw_sha256)
    except RetainedExportInputError as exc:
        raise M1EventSidecarError(f"retained assessment is unsupported: {exc}") from exc
    coverage = adapted["retained_export_coverage"]
    records = adapted["records"]
    if (coverage.get("replayable_pair_count") != 1 or coverage.get("coverage_only_row_count") != 0
            or len(records) != 1):
        raise M1EventSidecarError("retained lifecycle or lineage coverage cannot supply a full M1 assessment")
    record = records[0]
    snapshot, proposal = record.get("snapshot"), record.get("proposal")
    if not isinstance(snapshot, dict) or not isinstance(proposal, dict):
        raise M1EventSidecarError("retained full assessment lacks snapshot or proposal")
    return _copy(snapshot), _copy(proposal), _copy(adapted["provenance"])


def _verified_context(event_context: Any, *, decision_at_utc: str,
                      window_start_utc: str, window_end_utc: str) -> tuple[dict[str, Any], str]:
    """Check supplied report consistency by recomputing its annotation.

    The journal digest is a caller-provided binding. Only the I/O integration
    can establish that qualification was built from that retained journal.
    """
    if not isinstance(event_context, dict):
        raise M1EventSidecarError("a verified event-context report is required; unavailable context is not synthesized")
    required = {"schema_version", "journal_sha256", "qualification", "annotation", "execution_authority"}
    if not required <= set(event_context):
        raise M1EventSidecarError("event context report has no supported verified annotation schema")
    if event_context.get("schema_version") != "forex.event-store-context-report.v1":
        raise M1EventSidecarError("event context must be the verified retained-store report")
    if event_context.get("execution_authority") is not False:
        raise M1EventSidecarError("event context must not grant execution authority")
    journal_sha = _digest(event_context.get("journal_sha256"), field="event_context.journal_sha256")
    qualification, supplied = event_context.get("qualification"), event_context.get("annotation")
    if not isinstance(qualification, dict) or not isinstance(supplied, dict):
        raise M1EventSidecarError("event context report has no supported verified annotation schema")
    try:
        expected = event_annotation(qualification, decision_at_utc=decision_at_utc,
                                    window_start_utc=window_start_utc, window_end_utc=window_end_utc)
    except (EventAnnotationInputError, ValueError, TypeError) as exc:
        raise M1EventSidecarError(f"event context cannot be verified: {exc}") from exc
    if _canonical(supplied) != _canonical(expected):
        raise M1EventSidecarError("event context annotation does not bind its qualification, decision, and window")
    return _copy(expected), journal_sha


def build_m1_event_context_sidecar(retained_assessment: Any, *, source_raw_sha256: str,
                                   event_context: Any, window_start_utc: str,
                                   window_end_utc: str) -> dict[str, Any]:
    """Bind one retained full assessment to a verified observational annotation.

    ``window_start_utc`` and ``window_end_utc`` are mandatory caller-declared
    review bounds.  This function does not supply a blackout default and does
    not alter the source assessment mapping.
    """
    snapshot, proposal, provenance = _full_assessment(retained_assessment, source_raw_sha256)
    snapshot_id = _identity(snapshot.get("snapshot_id"), field="snapshot.snapshot_id")
    proposal_id = _identity(proposal.get("proposal_id"), field="proposal.proposal_id")
    if proposal.get("snapshot_id") != snapshot_id:
        raise M1EventSidecarError("proposal snapshot_id does not bind retained snapshot")
    snapshot_hash = _digest(snapshot.get("payload_sha256"), field="snapshot.payload_sha256")
    body = {key: value for key, value in snapshot.items() if key not in {"snapshot_id", "payload_sha256"}}
    if frozenset(body) not in {_M20_BASE_SNAPSHOT_BODY_FIELDS, _M20_EXTENDED_SNAPSHOT_BODY_FIELDS}:
        raise M1EventSidecarError("snapshot body is not a deployed M20 schema variant")
    if _snapshot_body_sha256(body) != snapshot_hash:
        raise M1EventSidecarError("snapshot payload_sha256 does not match retained body")
    if proposal.get("decision_snapshot_sha256") != snapshot_hash:
        raise M1EventSidecarError("proposal decision_snapshot_sha256 does not bind retained snapshot payload")
    observed_at, observed = _utc(snapshot.get("observed_at_utc"), field="snapshot.observed_at_utc")
    captured_at, captured = _utc(snapshot.get("captured_at_utc"), field="snapshot.captured_at_utc")
    decision_at, decision = _utc(proposal.get("decision_at_utc"), field="proposal.decision_at_utc")
    _, window_start = _utc(window_start_utc, field="window_start_utc")
    _, window_end = _utc(window_end_utc, field="window_end_utc")
    if captured_at < observed_at or decision_at < captured_at:
        raise M1EventSidecarError("proposal/snapshot timestamps are not chronological")
    annotation, journal_sha = _verified_context(event_context, decision_at_utc=decision,
                                                 window_start_utc=window_start,
                                                 window_end_utc=window_end)
    content = {
        "schema_version": SIDECAR_SCHEMA,
        "annotation_type": "EVENT_CONTEXT_ONLY",
        "annotation_status": "ATTACHED_CONTEXT_ONLY",
        "source_raw_sha256": source_raw_sha256,
        "source_shape": provenance.get("source_shape"),
        "source_adapter_version": provenance.get("adapter_version"),
        "proposal_id": proposal_id,
        "proposal_sha256": _sha(proposal),
        "snapshot_id": snapshot_id,
        "snapshot_payload_sha256": snapshot_hash,
        "snapshot_sha256": _sha(snapshot),
        "snapshot_observed_at_utc": observed,
        "snapshot_captured_at_utc": captured,
        "decision_at_utc": decision,
        "event_context_journal_sha256": journal_sha,
        "event_qualification_sha256": annotation["qualified_result_sha256"],
        "event_annotation_sha256": annotation["annotation_sha256"],
        "event_annotation": annotation,
        "execution_authority": False,
    }
    return {**content, "sidecar_sha256": _sha(content)}
