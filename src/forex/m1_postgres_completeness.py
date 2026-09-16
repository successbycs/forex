"""Pure completeness report for retained M1 envelopes and captured DB summaries."""
from __future__ import annotations

import hashlib
import json
from typing import Any


SCHEMA = "forex.m1.completeness-report.v1"
SUMMARY_SCHEMA = "forex.m1.postgres-completeness-summary.v1"


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON field")
        result[key] = value
    return result


def build_report(envelopes: list[dict[str, Any]], *, postgres_raw: bytes | None,
                 postgres_reference: str | None = None) -> dict[str, Any]:
    """Build a deterministic, read-only report; ``None`` is an explicit unknown DB input."""
    if not isinstance(envelopes, list) or not all(isinstance(item, dict) for item in envelopes):
        raise ValueError("envelopes must be objects")
    decisions = [item for item in envelopes if item.get("terminal", {}).get("disposition") == "TERMINAL_DECISION"]
    refusals = [item for item in envelopes if item.get("terminal", {}).get("disposition") == "OPERATIONAL_REFUSAL"]
    source_hashes = [item.get("source", {}).get("sha256") for item in envelopes]
    duplicate_sources = sorted({digest for digest in source_hashes if isinstance(digest, str) and source_hashes.count(digest) > 1})
    provenance: dict[str, Any] = {"envelope_count": len(envelopes), "postgres": "UNKNOWN"}
    records: list[dict[str, Any]] = []
    limitations: list[str] = []
    if postgres_raw is None:
        limitations.append("POSTGRES_SUMMARY_UNAVAILABLE")
    else:
        if not isinstance(postgres_raw, bytes) or not isinstance(postgres_reference, str) or not postgres_reference:
            raise ValueError("postgres raw bytes and reference are required together")
        try:
            summary = json.loads(postgres_raw, object_pairs_hook=_pairs)
        except (ValueError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ValueError("postgres summary is not valid JSON") from exc
        if not isinstance(summary, dict) or summary.get("schema_version") != SUMMARY_SCHEMA or not isinstance(summary.get("records"), list):
            raise ValueError("postgres summary schema is unsupported")
        records = [item for item in summary["records"] if isinstance(item, dict)]
        if len(records) != len(summary["records"]):
            raise ValueError("postgres summary records are invalid")
        provenance["postgres"] = {"reference": postgres_reference,
                                  "sha256": "sha256:" + hashlib.sha256(postgres_raw).hexdigest(),
                                  "query_contract_version": summary.get("query_contract_version"),
                                  "query_sha256": summary.get("query_sha256"),
                                  "interval": summary.get("interval")}
    projected = {row.get("proposal_id"): row for row in records if isinstance(row.get("proposal_id"), str)}
    proposal_ids = [item.get("assessment", {}).get("proposal_id") for item in decisions]
    matched = sorted(identifier for identifier in proposal_ids if identifier in projected)
    backlog = sorted(identifier for identifier in proposal_ids if identifier not in projected)
    write_failures = [row for row in records if row.get("status") == "WRITE_FAILURE"]
    return {"schema_version": SCHEMA, "input_provenance": provenance,
            "counts": {"retained": len(envelopes), "terminal_decisions": len(decisions),
                       "operational_refusals": len(refusals), "duplicate_source_records": len(duplicate_sources),
                       "backlog": "UNKNOWN" if postgres_raw is None else len(backlog),
                       "write_failures": "UNKNOWN" if postgres_raw is None else len(write_failures)},
            "joins": {"raw_to_projection_matched": "UNKNOWN" if postgres_raw is None else len(matched),
                      "raw_to_projection_unmatched_proposal_ids": [] if postgres_raw is None else backlog},
            "operational_refusals": [{"source_sha256": item.get("source", {}).get("sha256"),
                                       "reason_code": item.get("terminal", {}).get("reason_code")} for item in refusals],
            "write_failures": "UNKNOWN" if postgres_raw is None else write_failures,
            "limitations": limitations + (["DUPLICATE_RETAINED_SOURCE"] if duplicate_sources else []),
            "execution_authority": False}
