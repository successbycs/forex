"""Deterministic append-only journal for locally retained event captures.

This is deliberately a value adapter, not persistence.  Callers keep the JSON
journal wherever their approved capture boundary permits.  A capture proves
only what was observed at its completion time; it never backfills a publisher's
historical availability or turns a later disappearance into cancellation.
"""
from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from forex.event_quality import qualify_events


JOURNAL_VERSION = "forex.event-revision-journal.v1"
_JOURNAL_FIELDS = {"schema_version", "captures", "records", "journal_sha256"}
_CAPTURE_FIELDS = {"capture_id", "capture_completed_at_utc", "payload_sha256", "content_sha256", "content", "source_family", "source_url", "parser_version", "observed_event_ids", "disappeared_event_ids"}
_SEMANTIC_FIELDS = ("event_id", "event_name", "source_id", "source_url", "license", "license_url", "status", "time_precision", "timezone", "scheduled_at_local", "local_fold", "reference_month", "release_date", "declared_release_time_local", "parser_time_limitation")


class EventRevisionError(ValueError):
    """A journal or parsed capture is malformed, conflicting, or tampered."""


def _copy(value: Any) -> Any:
    try:
        return json.loads(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False))
    except (TypeError, ValueError) as exc:
        raise EventRevisionError("value must be JSON-compatible with finite values") from exc


def _sha(value: Any) -> str:
    return "sha256:" + hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _utc(value: Any, label: str) -> tuple[datetime, str]:
    if not isinstance(value, str):
        raise EventRevisionError(f"{label} must be an ISO-8601 timestamp")
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise EventRevisionError(f"{label} is invalid") from exc
    if result.tzinfo is None:
        raise EventRevisionError(f"{label} must include an offset")
    result = result.astimezone(UTC)
    return result, result.isoformat().replace("+00:00", "Z")


def _semantic(record: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(record.get("event_id"), str) or not record["event_id"]:
        raise EventRevisionError("capture event_id is required")
    required = ("event_name", "source_id", "source_url", "license", "status", "time_precision")
    if not all(isinstance(record.get(field), str) and record[field] for field in required):
        raise EventRevisionError("capture event provenance or schedule fields are invalid")
    if record["time_precision"] == "EXACT_LOCAL_TIME" and (not isinstance(record.get("timezone"), str) or not isinstance(record.get("scheduled_at_local"), str)):
        raise EventRevisionError("exact local event lacks timezone or scheduled_at_local")
    return {field: _copy(record[field]) for field in _SEMANTIC_FIELDS if field in record}


def _validated_capture(capture_id: str, parsed: Any) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if not isinstance(capture_id, str) or not capture_id:
        raise EventRevisionError("capture_id must be non-empty")
    if not isinstance(parsed, dict):
        raise EventRevisionError("parsed capture must be an object")
    timestamp, captured = _utc(parsed.get("capture_completed_at_utc"), "capture_completed_at_utc")
    required = ("payload_sha256", "source_family", "source_url", "parser_version", "records")
    if any(field not in parsed for field in required) or not all(isinstance(parsed[field], str) and parsed[field] for field in required[:-1]):
        raise EventRevisionError("parsed capture lacks required provenance")
    if not str(parsed["payload_sha256"]).startswith("sha256:"):
        raise EventRevisionError("parsed capture payload_sha256 is invalid")
    records = parsed["records"]
    if not isinstance(records, list) or not all(isinstance(record, dict) for record in records):
        raise EventRevisionError("parsed capture records must be a list of objects")
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for record in records:
        if record.get("payload_sha256") != parsed["payload_sha256"] or record.get("available_at_utc") != captured:
            raise EventRevisionError("record payload hash or availability does not bind capture")
        semantic = _semantic(record)
        event_id = semantic["event_id"]
        if event_id in seen:
            raise EventRevisionError("conflicting event_id within one capture")
        seen.add(event_id)
        normalized.append(semantic)
    content = {"capture_completed_at_utc": captured, "payload_sha256": parsed["payload_sha256"],
               "source_family": parsed["source_family"], "source_url": parsed["source_url"],
               "parser_version": parsed["parser_version"], "records": normalized,
               "quarantined": _copy(parsed.get("quarantined", []))}
    metadata = {"capture_id": capture_id, "capture_completed_at_utc": captured,
                "payload_sha256": parsed["payload_sha256"], "content_sha256": _sha(content), "content": content,
                "source_family": parsed["source_family"], "source_url": parsed["source_url"],
                "parser_version": parsed["parser_version"]}
    return {"timestamp": timestamp, "metadata": metadata}, normalized


def _journal_payload(journal: dict[str, Any]) -> dict[str, Any]:
    return {key: journal[key] for key in ("schema_version", "captures", "records")}


def validate_journal(journal: Any) -> dict[str, Any]:
    """Verify a previously emitted journal and return an isolated copy."""
    copied = _copy(journal)
    if not isinstance(copied, dict) or set(copied) != _JOURNAL_FIELDS or copied.get("schema_version") != JOURNAL_VERSION:
        raise EventRevisionError("journal schema is invalid")
    if not isinstance(copied["captures"], list) or not isinstance(copied["records"], list):
        raise EventRevisionError("journal captures and records must be lists")
    if copied.get("journal_sha256") != _sha(_journal_payload(copied)):
        raise EventRevisionError("journal_sha256 does not bind journal content")
    rebuilt = empty_journal()
    previous: datetime | None = None
    capture_ids: set[str] = set()
    for capture in copied["captures"]:
        if not isinstance(capture, dict) or set(capture) != _CAPTURE_FIELDS:
            raise EventRevisionError("journal capture schema is invalid")
        timestamp, _ = _utc(capture.get("capture_completed_at_utc"), "journal capture completion")
        if previous is not None and timestamp <= previous:
            raise EventRevisionError("journal capture clocks are not strictly monotonic")
        previous = timestamp
        if not isinstance(capture.get("capture_id"), str) or capture["capture_id"] in capture_ids:
            raise EventRevisionError("journal capture_id is conflicting")
        capture_ids.add(capture["capture_id"])
        if not all(isinstance(capture.get(field), str) and capture[field] for field in _CAPTURE_FIELDS - {"observed_event_ids", "disappeared_event_ids", "content"}):
            raise EventRevisionError("journal capture provenance is invalid")
        content = capture["content"]
        if not isinstance(content, dict) or not isinstance(content.get("records"), list):
            raise EventRevisionError("journal retained capture content is invalid")
        if not all(isinstance(record, dict) for record in content["records"]):
            raise EventRevisionError("journal retained capture records are invalid")
        parsed = {**content, "records": [
            {**record, "payload_sha256": content.get("payload_sha256"),
             "available_at_utc": content.get("capture_completed_at_utc")}
            for record in content["records"]]}
        verified, observed = _validated_capture(capture["capture_id"], parsed)
        rebuilt = _extend_journal(rebuilt, verified["metadata"], observed)
        if rebuilt["captures"][-1] != capture:
            raise EventRevisionError("journal capture content or lineage mismatch")
    if rebuilt != copied:
        raise EventRevisionError("journal revision lineage does not bind retained captures")
    return copied


def empty_journal() -> dict[str, Any]:
    journal = {"schema_version": JOURNAL_VERSION, "captures": [], "records": []}
    return {**journal, "journal_sha256": _sha(journal)}


def append_parsed_capture(journal: Any, *, capture_id: str, parsed_capture: Any) -> dict[str, Any]:
    """Append one parsed capture without altering prior local observations."""
    checked = validate_journal(journal)
    capture, observed = _validated_capture(capture_id, parsed_capture)
    if any(item["capture_id"] == capture_id for item in checked["captures"]):
        raise EventRevisionError("conflicting capture_id")
    if checked["captures"]:
        last, _ = _utc(checked["captures"][-1]["capture_completed_at_utc"], "journal capture completion")
        if capture["timestamp"] <= last:
            raise EventRevisionError("capture clock must be later than prior journal capture")
    return _copy(_extend_journal(checked, capture["metadata"], observed))


def _extend_journal(checked: dict[str, Any], capture_metadata: dict[str, Any],
                    observed: list[dict[str, Any]]) -> dict[str, Any]:
    """Deterministically derive revisions from retained normalized captures."""
    current = {record["event_id"]: record for record in checked["records"]}
    for record in checked["records"]:
        if record["revision"] > current[record["event_id"]]["revision"]:
            current[record["event_id"]] = record
    observed_ids = {record["event_id"] for record in observed}
    new_records = list(checked["records"])
    for semantic in observed:
        prior = current.get(semantic["event_id"])
        if prior is not None and _semantic(prior) == semantic:
            continue
        revision = 1 if prior is None else prior["revision"] + 1
        new_records.append({**semantic, "revision": revision,
                            "available_at_utc": capture_metadata["capture_completed_at_utc"],
                            "origin_capture_id": capture_metadata["capture_id"],
                            "revision_semantics": "LOCAL_CAPTURE_INITIAL" if revision == 1 else "LOCAL_CAPTURE_SEMANTIC_CHANGE",
                            "publisher_historical_availability": "UNKNOWN"})
    previous_source_capture = next((item for item in reversed(checked["captures"])
                                    if item["source_family"] == capture_metadata["source_family"]
                                    and item["source_url"] == capture_metadata["source_url"]), None)
    prior_ids = set(previous_source_capture["observed_event_ids"]) if previous_source_capture else set()
    metadata = {**capture_metadata, "observed_event_ids": sorted(observed_ids),
                "disappeared_event_ids": sorted(prior_ids - observed_ids)}
    result = {"schema_version": JOURNAL_VERSION, "captures": [*checked["captures"], metadata], "records": new_records}
    result["journal_sha256"] = _sha(result)
    return result


def qualify_journal(journal: Any, *, decision_cutoff_utc: str) -> dict[str, Any]:
    """Feed retained journal versions through the existing event-quality gate."""
    checked = validate_journal(journal)
    return qualify_events(checked["records"], decision_cutoff_utc)
