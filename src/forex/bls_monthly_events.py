"""Parse retained BLS monthly schedule HTML for CPI and Employment Situation.

The monthly calendar is a second official BLS surface.  It is intentionally
limited to two named releases and emits event-quality compatible records only;
it makes no coverage, market-direction, or execution claim.
"""
from __future__ import annotations

import hashlib
import re
from datetime import datetime
from typing import Any
from urllib.parse import urlparse

from forex.bls_events import HTMLParserText, _ScheduleTable, _capture_timestamp


PARSER_VERSION = "forex.bls-monthly-schedule-html.v1"
SOURCE_FAMILY = "BLS_MONTHLY"
_URL = re.compile(r"^/schedule/(20\d\d)/(0[1-9]|1[0-2])_sched_list\.htm$")
_HEADERS = ("date", "time", "release")
_EASTERN_NOTICE = re.compile(r"^NOTE:\s*All times on calendar are Eastern Time$")
_TARGETS = (
    (re.compile(r"^Consumer Price Index for ([A-Z][a-z]+ \d{4})$"), "bls-cpi", "bls-cpi-release-schedule", "US Consumer Price Index release"),
    (re.compile(r"^Employment Situation for ([A-Z][a-z]+ \d{4})$"), "bls-employment-situation", "bls-employment-situation-release-schedule", "US Employment Situation release"),
)


class BLSMonthlyParseError(ValueError):
    """The retained input or official monthly-source identity is invalid."""


def _source_month(source_url: str) -> tuple[int, int]:
    if not isinstance(source_url, str):
        raise BLSMonthlyParseError("source_url must be an official BLS monthly schedule URL")
    parsed = urlparse(source_url)
    match = _URL.fullmatch(parsed.path)
    if (parsed.scheme, parsed.netloc.lower(), parsed.query, parsed.fragment, parsed.params) != ("https", "www.bls.gov", "", "", "") or match is None:
        raise BLSMonthlyParseError("source_url must be https://www.bls.gov/schedule/YYYY/MM_sched_list.htm without query or fragment")
    return int(match.group(1)), int(match.group(2))


def _table(html: str) -> list[list[str]] | None:
    parser = _ScheduleTable()
    parser.feed(html)
    parser.close()
    matching = [table for table in parser.tables if table and tuple(cell.casefold() for cell in table[0]) == _HEADERS]
    return matching[0] if len(matching) == 1 else None


def _eastern_declared(html: str) -> bool:
    visible = "".join(HTMLParserText(html))
    return any(_EASTERN_NOTICE.fullmatch(" ".join(sentence.split()))
               for sentence in re.split(r"[.!?\n]", visible))


def _date(value: str) -> datetime:
    for form in ("%A, %B %d, %Y", "%A, %b %d, %Y"):
        try:
            parsed = datetime.strptime(value.replace(".", ""), form)
            if value.split(",", 1)[0].casefold() != parsed.strftime("%A").casefold():
                raise ValueError("weekday does not match date")
            return parsed
        except ValueError:
            pass
    raise ValueError("date")


def _time(value: str) -> datetime:
    return datetime.strptime(" ".join(value.upper().replace(".", "").split()), "%I:%M %p")


def _target(value: str) -> tuple[datetime, str, str, str] | None:
    for pattern, prefix, source_id, event_name in _TARGETS:
        match = pattern.fullmatch(value)
        if match is None:
            label = "Consumer Price Index for " if prefix == "bls-cpi" else "Employment Situation for "
            if value.startswith(label):
                raise ValueError("reference month")
            continue
        try:
            reference = datetime.strptime(match.group(1), "%B %Y")
        except ValueError as exc:
            raise ValueError("reference month") from exc
        return reference, prefix, source_id, event_name
    return None


def parse_bls_monthly_html(html: str, *, capture_completed_at_utc: str, source_url: str) -> dict[str, Any]:
    """Parse only CPI and Employment Situation rows from a retained month page."""
    if not isinstance(html, str) or not html.strip():
        raise BLSMonthlyParseError("retained BLS monthly HTML must be non-empty text")
    captured = _capture_timestamp(capture_completed_at_utc)
    source_year, source_month = _source_month(source_url)
    payload_sha = "sha256:" + hashlib.sha256(html.encode("utf-8")).hexdigest()
    table = _table(html)
    base = {"source_url": source_url,
            "license": "BLS copyright information; source-specific terms require qualification",
            "license_url": "https://www.bls.gov/opub/copyright-information.htm",
            "status": "SCHEDULED", "revision": 1, "revision_semantics": "LOCAL_CAPTURE_INITIAL",
            "publisher_historical_availability": "UNKNOWN", "available_at_utc": captured,
            "payload_sha256": payload_sha, "parser_version": PARSER_VERSION}
    if table is None:
        return {"parser_version": PARSER_VERSION, "source_family": SOURCE_FAMILY, "source_url": source_url,
                "payload_sha256": payload_sha, "capture_completed_at_utc": captured, "records": [],
                "quarantined": [{"reason": "UNKNOWN_BLS_MONTHLY_LAYOUT"}], "coverage_status": "UNKNOWN",
                "execution_authority": False}
    eastern = _eastern_declared(html)
    records: list[dict[str, Any]] = []
    quarantined: list[dict[str, str]] = []
    ignored = 0
    for index, row in enumerate(table[1:], start=1):
        if len(row) != 3:
            quarantined.append({"row": str(index), "reason": "MALFORMED_BLS_MONTHLY_ROW"})
            continue
        date_text, time_text, release = row
        try:
            target = _target(release)
        except ValueError:
            quarantined.append({"row": str(index), "reason": "MALFORMED_BLS_MONTHLY_TARGET"})
            continue
        if target is None:
            ignored += 1
            continue
        reference, prefix, source_id, event_name = target
        event = {**base, "event_id": f"{prefix}-{reference:%Y-%m}", "event_name": event_name,
                 "source_id": source_id, "reference_month": f"{reference:%Y-%m}",
                 "time_precision": "DATE_ONLY"}
        try:
            scheduled_date = _date(date_text)
        except ValueError:
            quarantined.append({"row": str(index), "reason": "MALFORMED_BLS_MONTHLY_DATE"})
            event["parser_time_limitation"] = f"MALFORMED_BLS_MONTHLY_DATE: {date_text}"
            records.append(event)
            continue
        if (scheduled_date.year, scheduled_date.month) != (source_year, source_month):
            quarantined.append({"row": str(index), "reason": "BLS_MONTHLY_DATE_OUTSIDE_SOURCE_MONTH"})
            event["parser_time_limitation"] = f"BLS_MONTHLY_DATE_OUTSIDE_SOURCE_MONTH: {date_text}"
            records.append(event)
            continue
        try:
            clock = _time(time_text)
        except ValueError:
            quarantined.append({"row": str(index), "reason": "BLS_MONTHLY_TARGET_DATE_ONLY"})
            clock = None
        event = {**event,
                 "release_date": f"{scheduled_date:%Y-%m-%d}",
                 "time_precision": "EXACT_LOCAL_TIME" if eastern and clock is not None else "DATE_ONLY"}
        if clock is not None:
            event["declared_release_time_local"] = clock.strftime("%H:%M")
        if eastern and clock is not None:
            event["timezone"] = "America/New_York"
            event["scheduled_at_local"] = f"{scheduled_date:%Y-%m-%d}T{clock:%H:%M}:00"
        elif not eastern:
            event["parser_time_limitation"] = "BLS monthly schedule did not declare Eastern time in visible page text"
            quarantined.append({"row": str(index), "reason": "BLS_MONTHLY_TIMEZONE_NOT_DECLARED_DATE_ONLY"})
        else:
            event["parser_time_limitation"] = "BLS monthly schedule has no valid release time for this target"
        records.append(event)
    if not records and not quarantined and ignored == 0:
        quarantined.append({"reason": "EMPTY_BLS_MONTHLY_TABLE"})
    return {"parser_version": PARSER_VERSION, "source_family": SOURCE_FAMILY, "source_url": source_url,
            "payload_sha256": payload_sha, "capture_completed_at_utc": captured, "records": records,
            "quarantined": quarantined, "ignored_unrelated_row_count": ignored, "coverage_status": "UNKNOWN",
            "execution_authority": False}
