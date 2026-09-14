"""Adapt fixed, retained M20 exports into the offline replay-document shape.

Only a retained ``decision_snapshot`` plus its bound ``proposal`` is a replay
pair.  Lifecycle and lineage exports deliberately omit the snapshot body, so
this adapter preserves their identifiers and optional outcome fields as
coverage-only records instead of reconstructing or repairing a snapshot.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ADAPTER_VERSION = "forex.m20.retained-export-adapter.v1"


class RetainedExportInputError(ValueError):
    """A local retained export cannot be interpreted without guessing."""


def _decode_export(value: Any) -> tuple[Any, dict[str, Any]]:
    """Unwrap the fixed T480 envelope when its stdout is one JSON value."""
    if not isinstance(value, dict):
        return value, {"source_shape": "JSON_VALUE"}
    metadata = {"source_shape": "JSON_OBJECT"}
    for field in ("operation", "tool_id", "asset_sha256", "configuration_fingerprint"):
        if field in value:
            metadata[field] = value[field]
    result = value.get("result")
    if isinstance(result, dict) and isinstance(result.get("stdout"), str):
        try:
            decoded = _strict_json(result["stdout"])
        except RetainedExportInputError as exc:
            raise RetainedExportInputError("T480 result stdout is not JSON") from exc
        metadata["source_shape"] = "T480_RESULT_STDOUT_JSON"
        return decoded, metadata
    return value, metadata


def _coverage_row(row: dict[str, Any], *, limitation: str) -> dict[str, Any]:
    """Retain available linkage/cost fields without making a replay pair."""
    kept = {key: row.get(key) for key in (
        "proposal_id", "snapshot_id", "decision_snapshot_sha256",
        "snapshot_payload_sha256", "decision_at_utc", "reconciliation_status",
    ) if key in row}
    outcome = row.get("outcome")
    if isinstance(outcome, dict):
        kept["outcome"] = outcome
    elif any(key in row for key in ("gross_price_pnl_account", "commission_account", "fee_account", "swap_account", "realized_pnl_account")):
        # This is a literal field projection, not an inferred broker outcome.
        kept["outcome_fields_retained_without_replay_pair"] = {
            key: row.get(key) for key in (
                "proposal_id", "gross_price_pnl_account", "commission_account", "fee_account",
                "swap_account", "estimated_spread_cost_account", "slippage_cost_account",
                "estimated_total_cost_account", "realized_pnl_account", "account_currency",
                "reconciliation_status",
            ) if key in row
        }
    return {"identifiers": kept, "limitations": [limitation]}


def _duplicates(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, dict[str, int]] = {"proposal_id": {}, "snapshot_id": {}}
    for row in rows:
        for field, values in counts.items():
            value = row.get(field)
            if isinstance(value, str) and value:
                values[value] = values.get(value, 0) + 1
    return {f"duplicate_{field}_count": sum(count - 1 for count in values.values() if count > 1)
            for field, values in counts.items()}


def adapt_retained_m20_export(value: Any, *, source_sha256: str | None = None,
                              source_path: str | None = None) -> dict[str, Any]:
    """Return a replay document and explicit coverage limitations for one export.

    The function is pure: it neither reads a broker nor changes the source
    mapping.  It accepts exactly the discovered M20 operation envelope, fixed
    lifecycle-array export, and fixed lineage-object export.
    """
    payload, provenance = _decode_export(value)
    if source_sha256 is not None:
        provenance["source_sha256"] = source_sha256
    if source_path is not None:
        provenance["source_path"] = source_path
    provenance["adapter_version"] = ADAPTER_VERSION
    records: list[dict[str, Any]] = []
    unavailable: list[dict[str, Any]] = []
    source_rows: list[dict[str, Any]] = []

    # The permanent listener retains one complete assessment separately from
    # its compact heartbeat.  Its fixed export operation wraps the assessment
    # with transport provenance; unwrap only that exact observed shape rather
    # than treating a missing current record as a synthetic no-trade result.
    if isinstance(payload, dict) and "assessment" in payload:
        if payload.get("observation") != "AVAILABLE":
            raise RetainedExportInputError("latest listener assessment export is not available")
        if not isinstance(payload["assessment"], dict):
            raise RetainedExportInputError("latest listener assessment export has an invalid assessment body")
        for field in (
            "listener_release_id", "assessment_started_at_utc",
            "assessment_completed_at_utc", "raw_sha256",
        ):
            if field in payload:
                provenance[field] = payload[field]
        payload = payload["assessment"]
        provenance["source_shape"] = "M20_LISTENER_LATEST_ASSESSMENT"

    if isinstance(payload, dict) and isinstance(payload.get("decision_snapshot"), dict) and isinstance(payload.get("proposal"), dict):
        snapshot, proposal = payload["decision_snapshot"], payload["proposal"]
        source_rows.append({"proposal_id": proposal.get("proposal_id"), "snapshot_id": snapshot.get("snapshot_id")})
        record: dict[str, Any] = {"record_id": proposal.get("proposal_id") or snapshot.get("snapshot_id") or "operation-record",
                                  "snapshot": snapshot, "proposal": proposal}
        # An operation export normally contains reconciliation, not a complete
        # outcome.  Only preserve an already embedded outcome object.
        if isinstance(payload.get("outcome"), dict):
            record["outcome"] = payload["outcome"]
        else:
            record["source_limitations"] = ["operation export has no embedded broker outcome"]
        records.append(record)
    elif isinstance(payload, list) and all(isinstance(row, dict) for row in payload):
        source_rows = payload
        unavailable = [_coverage_row(row, limitation="lifecycle export omits retained decision snapshot body and proposal body") for row in payload]
        provenance["source_shape"] = "M20_LIFECYCLE_ARRAY"
    elif isinstance(payload, dict) and isinstance(payload.get("lineage"), list) and all(isinstance(row, dict) for row in payload["lineage"]):
        source_rows = payload["lineage"]
        unavailable = [_coverage_row(row, limitation="lineage export omits retained decision snapshot body and proposal digest") for row in source_rows]
        provenance["source_shape"] = "M20_LINEAGE_OBJECT"
    else:
        raise RetainedExportInputError("unsupported retained M20 export shape")

    duplicate_counts = _duplicates(source_rows)
    limitations: list[str] = []
    if unavailable:
        limitations.append("source rows retain lifecycle/cost coverage but cannot support policy parity without the original snapshot and proposal bodies")
    if any(duplicate_counts.values()):
        limitations.append("duplicate source identifiers are retained and counted; pass replayable pairs to the replay reporter for per-record exclusion")
    return {
        "schema_version": "forex.m20.retained-replay-document.v1",
        "provenance": provenance,
        "records": records,
        "retained_export_coverage": {
            "source_row_count": len(source_rows),
            "replayable_pair_count": len(records),
            "coverage_only_row_count": len(unavailable),
            **duplicate_counts,
            "limitations": limitations,
        },
        "coverage_only_records": unavailable,
        "execution_authority": False,
    }


def _strict_json(raw: bytes | str) -> Any:
    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise RetainedExportInputError(f"duplicate JSON field: {key}")
            result[key] = value
        return result

    def reject_constant(value: str) -> None:
        raise RetainedExportInputError(f"nonfinite JSON constant: {value}")

    try:
        return json.loads(raw, object_pairs_hook=unique_object, parse_constant=reject_constant)
    except json.JSONDecodeError as exc:
        raise RetainedExportInputError(f"cannot decode retained export JSON: {exc}") from exc


def load_and_adapt_retained_m20_export(path: str | Path) -> dict[str, Any]:
    """Read one local export without modifying it and adapt its observed shape."""
    source = Path(path).expanduser().resolve(strict=True)
    try:
        raw = source.read_bytes()
    except OSError as exc:
        raise RetainedExportInputError(f"cannot read retained export: {exc}") from exc
    return adapt_retained_m20_export(_strict_json(raw), source_sha256="sha256:" + hashlib.sha256(raw).hexdigest(), source_path=str(source))
