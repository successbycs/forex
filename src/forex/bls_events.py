"""Pure parser for retained official BLS CPI and Employment Situation HTML.

The BLS schedule pages presently expose a three-column release table.  This
module parses only that declared shape and never fetches it.  It makes the
capture-completion timestamp the locally observed availability time; that is
not an assertion about BLS's historical first-publication availability.
"""
from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urlparse


PARSER_VERSION = "forex.bls-schedule-html.v1"
FAMILIES = {
    "CPI": {
        "path": "/schedule/news_release/cpi.htm",
        "source_id": "bls-cpi-release-schedule",
        "event_name": "US Consumer Price Index release",
        "event_prefix": "bls-cpi",
    },
    "EMPLOYMENT_SITUATION": {
        "path": "/schedule/news_release/empsit.htm",
        "source_id": "bls-employment-situation-release-schedule",
        "event_name": "US Employment Situation release",
        "event_prefix": "bls-employment-situation",
    },
}
_HEADERS = ("reference month", "release date", "release time")
_EASTERN_DECLARATION = re.compile(
    r"^(?:All release times|All times|Release times) are (?:in )?Eastern(?: Time)?$",
    re.IGNORECASE,
)


class BLSEventParseError(ValueError):
    """Invalid retained capture arguments, never a remote-fetch error."""


class _ScheduleTable(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tables: list[list[list[str]]] = []
        self._table: list[list[str]] | None = None
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "table":
            if self._table is None:
                self._table = []
        elif tag == "tr" and self._table is not None:
            self._row = []
        elif tag in {"th", "td"} and self._row is not None:
            self._cell = []

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"th", "td"} and self._cell is not None and self._row is not None:
            self._row.append(" ".join("".join(self._cell).split()))
            self._cell = None
        elif tag == "tr" and self._row is not None and self._table is not None:
            if self._row:
                self._table.append(self._row)
            self._row = None
        elif tag == "table" and self._table is not None:
            self.tables.append(self._table)
            self._table = None


def _capture_timestamp(value: str) -> str:
    if not isinstance(value, str):
        raise BLSEventParseError("capture_completed_at_utc must be an ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise BLSEventParseError("capture_completed_at_utc is invalid") from exc
    if parsed.tzinfo is None:
        raise BLSEventParseError("capture_completed_at_utc must include an offset")
    return parsed.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _source(family: str, source_url: str) -> dict[str, str]:
    if family not in FAMILIES:
        raise BLSEventParseError("source_family must be CPI or EMPLOYMENT_SITUATION")
    if not isinstance(source_url, str):
        raise BLSEventParseError("source_url must be an official BLS HTTPS URL")
    parsed = urlparse(source_url)
    if parsed.scheme != "https" or parsed.netloc.lower() != "www.bls.gov" or parsed.path != FAMILIES[family]["path"]:
        raise BLSEventParseError("source_url does not match the official BLS family schedule")
    return FAMILIES[family]


def _schedule_table(html: str) -> list[list[str]] | None:
    parser = _ScheduleTable()
    parser.feed(html)
    parser.close()
    matching = [table for table in parser.tables if table and tuple(cell.casefold() for cell in table[0]) == _HEADERS]
    return matching[0] if len(matching) == 1 else None


def _month(value: str, field: str) -> datetime:
    cleaned = value.replace(".", "")
    for form in ("%B %Y", "%b %Y") if field == "reference" else ("%B %d, %Y", "%b %d, %Y"):
        try:
            return datetime.strptime(cleaned, form)
        except ValueError:
            pass
    raise ValueError(field)


def _time(value: str) -> datetime:
    normalized = " ".join(value.upper().replace(".", "").split())
    return datetime.strptime(normalized, "%I:%M %p")


def parse_bls_schedule_html(html: str, *, capture_completed_at_utc: str,
                            source_url: str, source_family: str) -> dict[str, Any]:
    """Parse retained BLS HTML into records suitable for ``qualify_events``.

    Records get exact local timing only if this particular retained page states
    that its release times are Eastern.  Otherwise its date and displayed time
    are retained as descriptive fields and the standard event-quality layer
    quarantines the ``DATE_ONLY`` record.
    """
    if not isinstance(html, str) or not html.strip():
        raise BLSEventParseError("retained BLS HTML must be non-empty text")
    captured = _capture_timestamp(capture_completed_at_utc)
    family = _source(source_family, source_url)
    payload_sha256 = "sha256:" + hashlib.sha256(html.encode("utf-8")).hexdigest()
    table = _schedule_table(html)
    common = {
        "source_id": family["source_id"], "source_url": source_url,
        "license": "BLS copyright information; source-specific terms require qualification",
        "license_url": "https://www.bls.gov/opub/copyright-information.htm",
        "status": "SCHEDULED", "revision": 1,
        "revision_semantics": "LOCAL_CAPTURE_INITIAL",
        "publisher_historical_availability": "UNKNOWN",
        "available_at_utc": captured, "payload_sha256": payload_sha256,
        "parser_version": PARSER_VERSION,
    }
    if table is None:
        return {"parser_version": PARSER_VERSION, "source_family": source_family,
                "source_url": source_url, "payload_sha256": payload_sha256,
                "capture_completed_at_utc": captured, "records": [],
                "quarantined": [{"reason": "UNKNOWN_BLS_SCHEDULE_LAYOUT"}],
                "coverage_status": "UNKNOWN", "execution_authority": False}
    visible = "".join(HTMLParserText(html))
    eastern_declared = any(_EASTERN_DECLARATION.fullmatch(" ".join(sentence.split()))
                           for sentence in re.split(r"[.!?\n]", visible))
    records: list[dict[str, Any]] = []
    quarantined: list[dict[str, str]] = []
    for index, row in enumerate(table[1:], start=1):
        if len(row) != 3:
            quarantined.append({"row": str(index), "reason": "MALFORMED_BLS_SCHEDULE_ROW"})
            continue
        reference, release_date, release_time = row
        try:
            month = _month(reference, "reference")
            date = _month(release_date, "date")
            clock = _time(release_time)
        except ValueError:
            quarantined.append({"row": str(index), "reason": "MALFORMED_BLS_SCHEDULE_DATE_OR_TIME"})
            continue
        event = {**common, "event_id": f"{family['event_prefix']}-{month:%Y-%m}",
                 "event_name": family["event_name"], "reference_month": f"{month:%Y-%m}",
                 "release_date": f"{date:%Y-%m-%d}", "declared_release_time_local": clock.strftime("%H:%M"),
                 "time_precision": "EXACT_LOCAL_TIME" if eastern_declared else "DATE_ONLY"}
        if eastern_declared:
            event["timezone"] = "America/New_York"
            event["scheduled_at_local"] = f"{date:%Y-%m-%d}T{clock:%H:%M}:00"
        else:
            event["parser_time_limitation"] = "BLS schedule page did not declare Eastern time in this retained capture"
            quarantined.append({"row": str(index), "reason": "BLS_TIMEZONE_NOT_DECLARED_DATE_ONLY"})
        records.append(event)
    if not records and not quarantined:
        quarantined.append({"reason": "EMPTY_BLS_SCHEDULE_TABLE"})
    return {"parser_version": PARSER_VERSION, "source_family": source_family,
            "source_url": source_url, "payload_sha256": payload_sha256,
            "capture_completed_at_utc": captured, "records": records,
            "quarantined": quarantined, "coverage_status": "UNKNOWN",
            "execution_authority": False}


class HTMLParserText(HTMLParser):
    """Small text collector used only to verify a time-zone declaration."""
    def __init__(self, html: str) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.hidden = 0
        self.feed(html)
        self.close()

    def handle_data(self, data: str) -> None:
        if not self.hidden:
            # HTML source line wrapping is whitespace, not a sentence break.
            # Only explicit block tags below introduce line boundaries.
            self.parts.append(re.sub(r"\s+", " ", data))

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "template"}:
            self.hidden += 1
        elif not self.hidden and tag in {"p", "div", "br", "table", "tr", "li"}:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in {"script", "style", "template"}:
            self.hidden = max(0, self.hidden - 1)
        elif not self.hidden and tag in {"p", "div", "table", "tr", "li"}:
            self.parts.append("\n")

    def __iter__(self):
        return iter(self.parts)
