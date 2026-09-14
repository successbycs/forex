"""Read-only reporting over retained M20 snapshot/proposal/outcome records.

The input is one local JSON object with a ``records`` array.  Each record has
``snapshot`` and ``proposal`` mappings and can have a linked ``outcome``
mapping.  An optional top-level ``provenance`` mapping is echoed as declared
metadata, never treated as independently verified provenance.  This module
does not open a broker connection, mutate an input, or grant execution
authority.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from forex.m20_cost_accounting import AccountingInputError, summarize_broker_outcomes
from forex.m20_policy_kernel import KernelInputError, classify_retained_decision


REPORT_VERSION = "forex.m20.retained-replay-report.v1"
_SHA256 = re.compile(r"sha256:[0-9a-f]{64}")


class ReplayReportInputError(ValueError):
    """The enclosing retained-record document is not a reportable JSON input."""


def _canonical_sha256(value: Any) -> str:
    try:
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ReplayReportInputError("input must contain JSON-compatible finite values") from exc
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _source_sha256(value: Any) -> str:
    """Accept only the digest representation this reporter can actually bind.

    A merely prefixed string is not a SHA-256 value.  Keeping this strict is
    especially important for the fixed-export path, where the report carries
    the transport digest forward as provenance rather than recomputing it.
    """
    if not isinstance(value, str) or not _SHA256.fullmatch(value):
        raise ReplayReportInputError("source_sha256 must be a lowercase SHA-256 digest when supplied")
    return value


def _document(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ReplayReportInputError("input document must be a JSON object")
    records = value.get("records")
    if not isinstance(records, list):
        raise ReplayReportInputError("input document records must be a list")
    if "provenance" in value and not isinstance(value["provenance"], dict):
        raise ReplayReportInputError("input document provenance must be an object when present")
    return value


def _record_id(record: dict[str, Any], index: int) -> str:
    supplied = record.get("record_id")
    if supplied is None:
        return f"record-{index}"
    if not isinstance(supplied, str) or not supplied:
        raise ReplayReportInputError(f"record {index} record_id must be a non-empty string")
    return supplied


def build_replay_report(document: Any, *, source_sha256: str | None = None,
                        source_path: str | None = None) -> dict[str, Any]:
    """Classify retained records and cost coverage without counting duplicates.

    A duplicate snapshot ID, proposal ID, or linked outcome proposal ID is a
    data-quality error.  The first otherwise valid record is retained for
    aggregates; every later duplicate is explicitly excluded.  Missing outcome
    is reported as a limitation, not silently converted to a zero-cost result.
    """
    input_document = _document(document)
    if source_sha256 is not None:
        _source_sha256(source_sha256)
    seen_record_ids: set[str] = set()
    seen_snapshot_ids: set[str] = set()
    seen_proposal_ids: set[str] = set()
    seen_outcome_proposal_ids: set[str] = set()
    aggregate_outcomes: list[dict[str, Any]] = []
    report_records: list[dict[str, Any]] = []

    for index, value in enumerate(input_document["records"]):
        if not isinstance(value, dict):
            report_records.append({"index": index, "record_id": f"record-{index}", "status": "ERROR", "errors": ["record must be an object"], "included_in_aggregates": False})
            continue
        try:
            record_id = _record_id(value, index)
        except ReplayReportInputError as exc:
            report_records.append({"index": index, "record_id": f"record-{index}", "status": "ERROR", "errors": [str(exc)], "included_in_aggregates": False})
            continue
        entry: dict[str, Any] = {"index": index, "record_id": record_id, "status": "ERROR", "errors": [], "limitations": [], "included_in_aggregates": False}
        if record_id in seen_record_ids:
            entry["errors"].append("duplicate record_id")
        seen_record_ids.add(record_id)
        snapshot, proposal = value.get("snapshot"), value.get("proposal")
        if not isinstance(snapshot, dict):
            entry["errors"].append("snapshot must be an object")
        if not isinstance(proposal, dict):
            entry["errors"].append("proposal must be an object")
        if entry["errors"]:
            report_records.append(entry)
            continue
        entry["snapshot_sha256"] = _canonical_sha256(snapshot)
        entry["proposal_sha256"] = _canonical_sha256(proposal)
        snapshot_id, proposal_id = snapshot.get("snapshot_id"), proposal.get("proposal_id")
        if not isinstance(snapshot_id, str) or not snapshot_id:
            entry["errors"].append("snapshot_id is missing")
        elif snapshot_id in seen_snapshot_ids:
            entry["errors"].append("duplicate snapshot_id")
        else:
            seen_snapshot_ids.add(snapshot_id)
        if not isinstance(proposal_id, str) or not proposal_id:
            entry["errors"].append("proposal_id is missing")
        elif proposal_id in seen_proposal_ids:
            entry["errors"].append("duplicate proposal_id")
        else:
            seen_proposal_ids.add(proposal_id)
        if entry["errors"]:
            report_records.append(entry)
            continue
        try:
            entry["classification"] = classify_retained_decision(snapshot, proposal)
        except KernelInputError as exc:
            entry["errors"].append(f"classification: {exc}")
            report_records.append(entry)
            continue

        outcome = value.get("outcome")
        if outcome is None:
            entry["limitations"].append("linked broker outcome is absent")
        elif not isinstance(outcome, dict):
            entry["errors"].append("outcome must be an object when present")
        elif outcome.get("proposal_id") != proposal_id:
            entry["errors"].append("outcome proposal_id does not link to proposal_id")
        elif proposal_id in seen_outcome_proposal_ids:
            entry["errors"].append("duplicate linked outcome proposal_id")
        else:
            seen_outcome_proposal_ids.add(proposal_id)
            entry["outcome_sha256"] = _canonical_sha256(outcome)
            try:
                # Use the shared summary function even for a singleton so cost
                # semantics cannot drift from the established ledger reporter.
                entry["cost"] = summarize_broker_outcomes([outcome])["records"][0]
                aggregate_outcomes.append(outcome)
            except AccountingInputError as exc:
                entry["errors"].append(f"cost: {exc}")
        entry["status"] = "OK" if not entry["errors"] else "ERROR"
        entry["included_in_aggregates"] = entry["status"] == "OK"
        report_records.append(entry)

    aggregate = summarize_broker_outcomes(aggregate_outcomes)
    error_count = sum(record["status"] == "ERROR" for record in report_records)
    return {
        "report_version": REPORT_VERSION,
        "input_provenance": {
            "source_path": source_path,
            "source_sha256": source_sha256 or _canonical_sha256(input_document),
            "declared": input_document.get("provenance"),
            "declared_provenance_status": "NOT_INDEPENDENTLY_VERIFIED",
        },
        "record_count": len(report_records),
        "valid_record_count": sum(record["status"] == "OK" for record in report_records),
        "error_record_count": error_count,
        "records": report_records,
        "broker_outcome_coverage": aggregate,
        "profitability_conclusion": "NOT_EVALUATED",
        "execution_authority": False,
    }


def load_and_build_replay_report(path: str | Path) -> dict[str, Any]:
    """Read one local JSON document and return a report; never write input."""
    source = Path(path).expanduser().resolve(strict=True)
    try:
        raw = source.read_bytes()
        def unique_object(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise ReplayReportInputError(f"duplicate JSON field: {key}")
                result[key] = value
            return result

        def reject_constant(value):
            raise ReplayReportInputError(f"nonfinite JSON constant: {value}")

        document = json.loads(raw, object_pairs_hook=unique_object, parse_constant=reject_constant)
    except (OSError, json.JSONDecodeError) as exc:
        raise ReplayReportInputError(f"cannot read JSON input: {exc}") from exc
    return build_replay_report(document, source_sha256="sha256:" + hashlib.sha256(raw).hexdigest(), source_path=str(source))
