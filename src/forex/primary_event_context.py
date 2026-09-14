"""Read-only source coverage qualification for the EUR/USD primary event set.

It does not parse a publisher page or alter a decision.  It consumes only
already-retained source observations and makes missing, duplicate, or
coverage-unknown source state explicit before existing event annotations are
considered by research/reporting code.
"""
from __future__ import annotations

import json
import hashlib
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


SCHEMA = "forex.primary-event-context.v1"
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}")
_FAMILIES = {"US_CPI", "US_EMPLOYMENT_SITUATION", "FOMC_POLICY_DECISION", "ECB_POLICY_DECISION"}
_BLS_FAMILIES = {"US_CPI", "US_EMPLOYMENT_SITUATION"}
_POLICY_TIMING_FAMILIES = {"FOMC_POLICY_DECISION", "ECB_POLICY_DECISION"}
_BLS_URL = re.compile(r"https://www\.bls\.gov/schedule/20\d{2}/(0[1-9]|1[0-2])_sched_list\.htm\Z")
_CAPTURE = {"RETAINED", "UNAVAILABLE"}
_COVERAGE = {"UNKNOWN", "PARTIAL", "COMPLETE"}


class PrimaryEventContextError(ValueError):
    """A source contract or retained-observation claim is unsafe to use."""


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _utc(value: Any, *, label: str) -> str:
    if not isinstance(value, str):
        raise PrimaryEventContextError(f"{label} timestamp is invalid")
    try:
        instant = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise PrimaryEventContextError(f"{label} timestamp is invalid") from exc
    if instant.tzinfo is None:
        raise PrimaryEventContextError(f"{label} timestamp is invalid")
    return instant.astimezone(UTC).isoformat().replace("+00:00", "Z")


def load_contract(path: Path) -> dict[str, Any]:
    if not isinstance(path, Path) or path.is_symlink() or not path.is_file():
        raise PrimaryEventContextError("source contract must be a regular non-symlink file")
    try:
        value = json.loads(path.read_bytes())
    except (OSError, json.JSONDecodeError) as exc:
        raise PrimaryEventContextError("source contract is not valid JSON") from exc
    if not isinstance(value, dict) or set(value) != {"schema_version", "execution_authority", "purpose", "required_families"}:
        raise PrimaryEventContextError("source contract shape is invalid")
    rows = value.get("required_families")
    if value.get("schema_version") != SCHEMA or value.get("execution_authority") is not False or not isinstance(rows, list):
        raise PrimaryEventContextError("source contract identity is invalid")
    seen: set[str] = set()
    for row in rows:
        required = {"family_id", "source_id", "publisher", "source_url", "qualification_state", "timing_requirement", "limitation"}
        if (isinstance(row, dict) and (row.get("family_id") in _BLS_FAMILIES
                or (row.get("family_id") in _POLICY_TIMING_FAMILIES
                    and row.get("qualification_state") != "PENDING_RETAINED_CAPTURE"))):
            required.add("source_url_matching_policy")
        if (not isinstance(row, dict) or set(row) != required or not isinstance(row.get("family_id"), str)
                or row["family_id"] not in _FAMILIES or row["family_id"] in seen
                or not all(isinstance(row.get(field), str) and row[field] for field in required - {"family_id"})
                or not row["source_url"].startswith("https://")):
            raise PrimaryEventContextError("source contract family is invalid")
        if row["family_id"] in _BLS_FAMILIES and row.get("source_url_matching_policy") != "EXACT_BLS_MONTHLY_URL_TEMPLATE_ONLY":
            raise PrimaryEventContextError("BLS source URL matching policy is invalid")
        if (row["family_id"] in _POLICY_TIMING_FAMILIES and row.get("qualification_state") != "PENDING_RETAINED_CAPTURE"
                and row.get("source_url_matching_policy") != "EXACT_RETAINED_TIMING_MANIFEST_ONLY"):
            raise PrimaryEventContextError("policy timing source URL matching policy is invalid")
        seen.add(row["family_id"])
    if seen != _FAMILIES:
        raise PrimaryEventContextError("source contract must declare the complete EUR/USD primary family set")
    return value


def qualify_context(*, contract: dict[str, Any], observations: list[dict[str, Any]]) -> dict[str, Any]:
    """Classify retained source coverage without accepting a silent omission.

    ``COMPLETE`` source coverage means only that the supplied observation says
    complete; it does not make a directional signal or an entry gate.
    """
    if not isinstance(contract, dict) or set(contract) != {"schema_version", "execution_authority", "purpose", "required_families"}:
        raise PrimaryEventContextError("source contract shape is invalid")
    if contract.get("schema_version") != SCHEMA or contract.get("execution_authority") is not False:
        raise PrimaryEventContextError("source contract identity is invalid")
    families = contract.get("required_families")
    if not isinstance(families, list):
        raise PrimaryEventContextError("source contract family is invalid")
    # Validate a direct value through a compact duplicate of the invariant,
    # keeping the public no-I/O function useful for deterministic tests.
    declared: dict[str, dict[str, Any]] = {}
    for row in families:
        required = {"family_id", "source_id", "publisher", "source_url", "qualification_state", "timing_requirement", "limitation"}
        if (isinstance(row, dict) and (row.get("family_id") in _BLS_FAMILIES
                or (row.get("family_id") in _POLICY_TIMING_FAMILIES
                    and row.get("qualification_state") != "PENDING_RETAINED_CAPTURE"))):
            required.add("source_url_matching_policy")
        if (not isinstance(row, dict) or set(row) != required or row.get("family_id") not in _FAMILIES
                or row["family_id"] in declared or not all(isinstance(row.get(field), str) and row[field] for field in required - {"family_id"})
                or not row["source_url"].startswith("https://")):
            raise PrimaryEventContextError("source contract family is invalid")
        if row["family_id"] in _BLS_FAMILIES and row.get("source_url_matching_policy") != "EXACT_BLS_MONTHLY_URL_TEMPLATE_ONLY":
            raise PrimaryEventContextError("BLS source URL matching policy is invalid")
        if (row["family_id"] in _POLICY_TIMING_FAMILIES and row.get("qualification_state") != "PENDING_RETAINED_CAPTURE"
                and row.get("source_url_matching_policy") != "EXACT_RETAINED_TIMING_MANIFEST_ONLY"):
            raise PrimaryEventContextError("policy timing source URL matching policy is invalid")
        declared[row["family_id"]] = row
    if set(declared) != _FAMILIES:
        raise PrimaryEventContextError("source contract must declare the complete EUR/USD primary family set")
    if not isinstance(observations, list) or not all(isinstance(row, dict) for row in observations):
        raise PrimaryEventContextError("source observations must be a list")
    by_source: dict[str, list[dict[str, Any]]] = {}
    for row in observations:
        if set(row) not in ({"source_id", "source_url", "capture_state", "coverage_status", "captured_at_utc", "source_sha256"},
                            {"family_id", "source_id", "source_url", "capture_state", "coverage_status", "captured_at_utc", "source_sha256"}):
            raise PrimaryEventContextError("source observation shape is invalid")
        if (not isinstance(row["source_id"], str) or row["capture_state"] not in _CAPTURE
                or not isinstance(row["source_url"], str) or not row["source_url"].startswith("https://")
                or row["coverage_status"] not in _COVERAGE or _DIGEST.fullmatch(str(row["source_sha256"])) is None):
            raise PrimaryEventContextError("source observation identity is invalid")
        _utc(row["captured_at_utc"], label="source observation")
        by_source.setdefault(row["source_id"], []).append(row)
    rows: list[dict[str, Any]] = []
    for family_id, source in sorted(declared.items()):
        observed = [item for item in by_source.get(source["source_id"], [])
                    if item.get("family_id") in (None, family_id)]
        if len(observed) != 1:
            state = "UNAVAILABLE" if not observed else "AMBIGUOUS"
            reason = "NO_RETAINED_SOURCE_OBSERVATION" if not observed else "MULTIPLE_SOURCE_OBSERVATIONS"
            receipt = None
        else:
            item = observed[0]
            receipt = {"source_url": item["source_url"],
                       "captured_at_utc": _utc(item["captured_at_utc"], label="source observation"),
                       "source_sha256": item["source_sha256"], "coverage_status": item["coverage_status"]}
            exact_template = source.get("source_url_matching_policy") == "EXACT_BLS_MONTHLY_URL_TEMPLATE_ONLY"
            url_matches = (_BLS_URL.fullmatch(item["source_url"]) is not None if exact_template
                           else item["source_url"] == source["source_url"])
            if not url_matches:
                state, reason = "AMBIGUOUS", "SOURCE_URL_DOES_NOT_MATCH_CONTRACT"
            elif source["qualification_state"] == "PENDING_RETAINED_CAPTURE":
                state, reason = "UNAVAILABLE", "SOURCE_CONTRACT_PENDING_CAPTURE"
            elif item["capture_state"] != "RETAINED":
                state, reason = "UNAVAILABLE", "SOURCE_CAPTURE_UNAVAILABLE"
            elif item["coverage_status"] != "COMPLETE":
                state, reason = "PARTIAL", "SOURCE_COVERAGE_NOT_COMPLETE"
            else:
                state, reason = "QUALIFIED_CONTEXT_ONLY", "RETAINED_COMPLETE_SOURCE_COVERAGE"
        rows.append({"family_id": family_id, "source_id": source["source_id"], "state": state, "reason": reason,
                     "qualification_state": source["qualification_state"], "limitation": source["limitation"], "receipt": receipt})
    states = {row["state"] for row in rows}
    overall = "AMBIGUOUS" if "AMBIGUOUS" in states else "UNAVAILABLE" if "UNAVAILABLE" in states else "PARTIAL" if "PARTIAL" in states else "QUALIFIED_CONTEXT_ONLY"
    result = {"schema_version": SCHEMA, "context_state": overall, "families": rows,
              "execution_authority": False,
              "limitations": ["This is source coverage/context qualification only; it cannot select direction or change entry eligibility.",
                              "Existing event annotations remain separately provenance- and decision-time-bound."]}
    return {**result, "context_sha256": "sha256:" + hashlib.sha256(_canonical(result)).hexdigest()}
