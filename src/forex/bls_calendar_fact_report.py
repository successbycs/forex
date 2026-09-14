"""Validate a read-only PostgreSQL observation of stored BLS calendar facts.

The database transport is deliberately outside this module.  Callers supply
only the fixed query's decoded result.  This adapter neither writes, fetches,
parses retained bytes, nor makes an event or trading decision.
"""
from __future__ import annotations

import re
from typing import Any, Mapping

from forex.calendar_fact_persistence import CalendarFactPersistenceError, canonical_fact


class BLSCalendarFactReportError(ValueError):
    """The fixed database observation is not safe to represent as lineage."""


_OBSERVATION_FIELDS = {"schema_present", "rows"}
_ROW_FIELDS = {
    "fact_sha256", "source_family", "source_url", "capture_completed_at_utc", "raw_sha256",
    "receipt_sha256", "event_identifier", "scheduled_at_utc", "event_title", "country_code",
    "currency_code", "impact", "qualification_state", "qualification_reason", "source_revision",
    "event_payload",
}
_BLS_FAMILIES = {"CPI", "EMPLOYMENT_SITUATION", "BLS_MONTHLY"}
_BLS_URL_PREFIX = "https://www.bls.gov/schedule/"
_SHA256 = re.compile(r"sha256:[0-9a-f]{64}\Z")


def build_bls_calendar_fact_report(observation: Any) -> dict[str, Any]:
    """Return a closed non-authorising report from one fixed database read.

    A missing table is reported explicitly rather than inferred as empty.  A
    present table is accepted only when every returned BLS row recomputes to
    its stored canonical digest and carries capture-bound raw/receipt lineage.
    """
    if not isinstance(observation, Mapping) or set(observation) != _OBSERVATION_FIELDS:
        raise BLSCalendarFactReportError("database observation schema is invalid")
    if type(observation["schema_present"]) is not bool or not isinstance(observation["rows"], list):
        raise BLSCalendarFactReportError("database observation fields are invalid")
    if not observation["schema_present"]:
        if observation["rows"]:
            raise BLSCalendarFactReportError("absent calendar schema cannot contain rows")
        return {
            "schema_version": "forex.bls-calendar-fact-report.v1",
            "status": "CALENDAR_FACT_SCHEMA_UNAVAILABLE",
            "fact_count": 0,
            "facts": [],
            "execution_authority": False,
        }

    facts: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in observation["rows"]:
        if not isinstance(row, Mapping) or set(row) != _ROW_FIELDS:
            raise BLSCalendarFactReportError("stored calendar row schema is invalid")
        stored_digest = row["fact_sha256"]
        fact = {key: row[key] for key in _ROW_FIELDS - {"fact_sha256"}}
        try:
            checked = canonical_fact(fact)
        except CalendarFactPersistenceError as exc:
            raise BLSCalendarFactReportError("stored calendar row is not canonical") from exc
        if stored_digest != checked["fact_sha256"] or stored_digest in seen:
            raise BLSCalendarFactReportError("stored calendar fact digest is invalid or duplicated")
        if checked["source_family"] not in _BLS_FAMILIES or not checked["source_url"].startswith(_BLS_URL_PREFIX):
            raise BLSCalendarFactReportError("stored row is outside the fixed BLS source scope")
        payload = checked["event_payload"]
        provenance = payload.get("capture_provenance")
        if not isinstance(provenance, Mapping) or set(provenance) != {
            "capture_id", "capture_completed_at_utc", "payload_sha256", "content_sha256",
            "source_family", "source_url", "parser_version", "receipt_sha256",
        }:
            raise BLSCalendarFactReportError("stored BLS row lacks complete capture provenance")
        if (provenance["capture_completed_at_utc"] != checked["capture_completed_at_utc"]
                or provenance["payload_sha256"] != checked["raw_sha256"]
                or provenance["receipt_sha256"] != checked["receipt_sha256"]
                or provenance["source_family"] != checked["source_family"]
                or provenance["source_url"] != checked["source_url"]):
            raise BLSCalendarFactReportError("stored BLS row provenance does not bind indexed lineage")
        if (not isinstance(provenance["capture_id"], str) or not provenance["capture_id"]
                or not isinstance(provenance["parser_version"], str) or not provenance["parser_version"]
                or not isinstance(provenance["content_sha256"], str)
                or not _SHA256.fullmatch(provenance["content_sha256"])):
            raise BLSCalendarFactReportError("stored BLS capture provenance identity is invalid")
        revision = payload.get("event_revision")
        if not isinstance(revision, Mapping):
            raise BLSCalendarFactReportError("stored BLS row lacks an event revision")
        expected_revision = {
            "event_id": checked["event_identifier"],
            "event_name": checked["event_title"],
            "source_url": checked["source_url"],
            "payload_sha256": checked["raw_sha256"],
            "available_at_utc": checked["capture_completed_at_utc"],
            "origin_capture_id": provenance["capture_id"],
            "revision": checked["source_revision"],
        }
        if any(revision.get(field) != value for field, value in expected_revision.items()):
            raise BLSCalendarFactReportError("stored BLS event revision does not bind indexed lineage")
        seen.add(stored_digest)
        facts.append({
            "fact_sha256": stored_digest,
            "source_family": checked["source_family"],
            "source_url": checked["source_url"],
            "capture_completed_at_utc": checked["capture_completed_at_utc"],
            "raw_sha256": checked["raw_sha256"],
            "receipt_sha256": checked["receipt_sha256"],
            "event_identifier": checked["event_identifier"],
            "scheduled_at_utc": checked["scheduled_at_utc"],
            "event_title": checked["event_title"],
            "qualification_state": checked["qualification_state"],
            "qualification_reason": checked["qualification_reason"],
            "source_revision": checked["source_revision"],
        })
    facts.sort(key=lambda item: (item["capture_completed_at_utc"], item["event_identifier"], item["source_revision"], item["fact_sha256"]))
    return {
        "schema_version": "forex.bls-calendar-fact-report.v1",
        "status": "BLS_FACTS_RETRIEVED" if facts else "NO_STORED_BLS_FACTS",
        "fact_count": len(facts),
        "facts": facts,
        "execution_authority": False,
    }
