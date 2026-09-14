"""Pure projection of a validated retained BLS journal into calendar facts.

This is intentionally not a parser, file reader, database writer, or trading
rule.  It derives fact-shaped values only after ``validate_journal`` has
rebuilt the immutable revision lineage.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from forex.calendar_fact_persistence import CalendarFactPersistenceError, canonical_fact
from forex.event_quality import qualify_events
from forex.event_revisions import EventRevisionError, validate_journal


class BLSJournalProjectionError(ValueError):
    pass


def _copy(value: Any) -> Any:
    try:
        return json.loads(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False))
    except (TypeError, ValueError) as exc:
        raise BLSJournalProjectionError("journal value is not finite JSON") from exc


def _qualification(record: dict[str, Any]) -> tuple[str, str | None, str | None]:
    """Use the existing deterministic quality rules, never a trade decision."""
    try:
        result = qualify_events([record], record["available_at_utc"])
    except (KeyError, TypeError, ValueError) as exc:
        raise BLSJournalProjectionError("validated revision cannot be qualified") from exc
    if result["accepted"]:
        return "QUALIFIED", None, result["accepted"][0]["scheduled_at_utc"]
    if not result["quarantined"]:
        raise BLSJournalProjectionError("revision produced no qualification outcome")
    return "QUARANTINED", result["quarantined"][0]["reason"], None


def project_bls_journal(journal: Any, *, capture_receipt_sha256_by_id: Any) -> dict[str, Any]:
    """Return one retained fact for every journal event revision.

    ``event_payload`` is the complete normalized journal revision; raw source
    bytes are never reread or copied here.  The per-fact receipt hash binds the
    receipt mapping is supplied by the already-verified immutable capture
    boundary; this pure adapter never invents or verifies receipt bytes.
    """
    try:
        checked = validate_journal(journal)
    except EventRevisionError as exc:
        raise BLSJournalProjectionError("immutable journal validation failed") from exc
    captures = {capture["capture_id"]: capture for capture in checked["captures"]}
    if not isinstance(capture_receipt_sha256_by_id, dict) or set(capture_receipt_sha256_by_id) != set(captures):
        raise BLSJournalProjectionError("receipt bindings must match retained capture IDs exactly")
    digest = re.compile(r"sha256:[0-9a-f]{64}\Z")
    if any(not isinstance(value, str) or not digest.fullmatch(value)
           for value in capture_receipt_sha256_by_id.values()):
        raise BLSJournalProjectionError("receipt binding is not a sha256 digest")
    facts: list[dict[str, Any]] = []
    for revision in checked["records"]:
        capture_id = revision.get("origin_capture_id")
        capture = captures.get(capture_id)
        if capture is None:
            raise BLSJournalProjectionError("revision capture lineage is missing")
        if revision.get("source_url") != capture["source_url"]:
            raise BLSJournalProjectionError("revision source URL does not bind origin capture")
        if revision.get("available_at_utc") != capture["capture_completed_at_utc"]:
            raise BLSJournalProjectionError("revision availability does not bind origin capture")
        if not isinstance(revision.get("revision"), int) or revision["revision"] < 1:
            raise BLSJournalProjectionError("revision number is invalid")
        state, reason, scheduled = _qualification(revision)
        event = _copy(revision)
        event_payload = {
            "event_revision": event,
            "capture_provenance": {
                "capture_id": capture_id,
                "capture_completed_at_utc": capture["capture_completed_at_utc"],
                "payload_sha256": capture["payload_sha256"],
                "content_sha256": capture["content_sha256"],
                "source_family": capture["source_family"],
                "source_url": capture["source_url"],
                "parser_version": capture["parser_version"],
                "receipt_sha256": capture_receipt_sha256_by_id[capture_id],
            },
        }
        fact = {
            "source_family": capture["source_family"],
            "source_url": capture["source_url"],
            "capture_completed_at_utc": capture["capture_completed_at_utc"],
            "raw_sha256": capture["payload_sha256"],
            "receipt_sha256": capture_receipt_sha256_by_id[capture_id],
            "event_identifier": revision["event_id"],
            "scheduled_at_utc": scheduled,
            "event_title": revision["event_name"],
            "country_code": "US",
            "currency_code": "USD",
            "impact": "UNKNOWN",
            "qualification_state": state,
            "qualification_reason": reason,
            "source_revision": revision["revision"],
            "event_payload": event_payload,
        }
        # ``validate_journal`` preserves older journal compatibility where a
        # payload hash has only a prefix check.  The canonical store contract
        # is stricter, so validate every assembled fact before it can leave
        # this adapter.  Do not return canonical_fact's derived hash/authority
        # fields: callers receive the exact closed input shape it accepted.
        try:
            canonical_fact(fact)
        except CalendarFactPersistenceError as exc:
            raise BLSJournalProjectionError("projected fact violates canonical persistence contract") from exc
        facts.append(fact)
    facts.sort(key=lambda fact: (fact["event_identifier"], fact["source_revision"]))
    result = {"schema_version": "forex.bls-journal-calendar-facts.v1", "journal_sha256": checked["journal_sha256"],
              "facts": facts, "execution_authority": False}
    result["projection_sha256"] = "sha256:" + hashlib.sha256(
        json.dumps(result, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()
    return result
