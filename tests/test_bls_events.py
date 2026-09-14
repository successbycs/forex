from forex.bls_events import BLSEventParseError, parse_bls_schedule_html
from forex.event_quality import qualify_events
import pytest


CPI_URL = "https://www.bls.gov/schedule/news_release/cpi.htm"
EMP_URL = "https://www.bls.gov/schedule/news_release/empsit.htm"


@pytest.mark.parametrize("declaration", [
    '<script>const example="Release times are Eastern";</script>',
    "Not all release times are Eastern Time.",
    "Release times are Eastern Standard Time (UTC-05:00).",
    "Not\nall release times are Eastern Time.",
    "Release times are Eastern\nStandard Time (UTC-05:00).",
])
def test_unsupported_timezone_declarations_remain_date_only(declaration):
    parsed = parse_bls_schedule_html(table(("June 2026", "Jul. 02, 2026", "08:30 AM"),
        eastern=declaration), capture_completed_at_utc="2026-01-01T00:00:00Z",
        source_url=CPI_URL, source_family="CPI")
    assert parsed["records"][0]["time_precision"] == "DATE_ONLY"


def table(*rows, eastern=""):
    content = "".join(f"<tr><td>{reference}</td><td>{date}</td><td>{time}</td></tr>" for reference, date, time in rows)
    return f"<html><body><p>{eastern}</p><table><tr><th>Reference Month</th><th>Release Date</th><th>Release Time</th></tr>{content}</table></body></html>"


def test_parses_observed_three_column_shape_but_does_not_assume_timezone():
    html = table(("November 2025", "Dec. 18, 2025", "08:30 AM"), ("December 2025", "Jan. 13, 2026", "08:30 AM"))
    parsed = parse_bls_schedule_html(html, capture_completed_at_utc="2026-09-12T01:02:03Z", source_url=CPI_URL, source_family="CPI")
    assert [item["reference_month"] for item in parsed["records"]] == ["2025-11", "2025-12"]
    assert parsed["records"][0]["time_precision"] == "DATE_ONLY"
    assert "timezone" not in parsed["records"][0]
    qualified = qualify_events(parsed["records"], "2026-09-12T02:00:00Z")
    assert qualified["accepted"] == []
    assert {item["reason"] for item in qualified["quarantined"]} == {"TIME_PRECISION_INSUFFICIENT"}


def test_eastern_declaration_enables_new_york_timing_and_dst_conversion():
    html = table(("February 2026", "Mar. 11, 2026", "08:30 AM"), ("October 2026", "Nov. 10, 2026", "08:30 AM"), eastern="All release times are Eastern Time.")
    parsed = parse_bls_schedule_html(html, capture_completed_at_utc="2026-01-01T00:00:00Z", source_url=EMP_URL, source_family="EMPLOYMENT_SITUATION")
    assert all(item["timezone"] == "America/New_York" for item in parsed["records"])
    qualified = qualify_events(parsed["records"], "2026-01-02T00:00:00Z")
    assert [item["scheduled_at_utc"] for item in qualified["accepted"]] == ["2026-03-11T12:30:00Z", "2026-11-10T13:30:00Z"]


def test_changed_schedule_is_taken_from_each_row_not_a_fixed_release_rule():
    html = table(("June 2026", "Jul. 02, 2026", "09:15 AM"), eastern="Release times are Eastern.")
    parsed = parse_bls_schedule_html(html, capture_completed_at_utc="2026-01-01T00:00:00Z", source_url=EMP_URL, source_family="EMPLOYMENT_SITUATION")
    assert parsed["records"][0]["scheduled_at_local"] == "2026-07-02T09:15:00"


def test_unknown_layout_and_malformed_rows_are_explicitly_quarantined():
    unknown = parse_bls_schedule_html("<html><body>temporarily unavailable</body></html>", capture_completed_at_utc="2026-01-01T00:00:00Z", source_url=CPI_URL, source_family="CPI")
    assert unknown["records"] == []
    assert unknown["quarantined"] == [{"reason": "UNKNOWN_BLS_SCHEDULE_LAYOUT"}]
    malformed = parse_bls_schedule_html(table(("not a month", "Jun. 10, 2026", "08:30 AM")), capture_completed_at_utc="2026-01-01T00:00:00Z", source_url=CPI_URL, source_family="CPI")
    assert malformed["records"] == []
    assert malformed["quarantined"][0]["reason"] == "MALFORMED_BLS_SCHEDULE_DATE_OR_TIME"


def test_rejects_wrong_family_url_and_missing_capture_offset():
    try:
        parse_bls_schedule_html(table(("May 2026", "Jun. 10, 2026", "08:30 AM")), capture_completed_at_utc="2026-01-01T00:00:00", source_url=CPI_URL, source_family="CPI")
    except BLSEventParseError as exc:
        assert "offset" in str(exc)
    else:
        raise AssertionError("naive capture timestamp was accepted")
    try:
        parse_bls_schedule_html(table(("May 2026", "Jun. 10, 2026", "08:30 AM")), capture_completed_at_utc="2026-01-01T00:00:00Z", source_url=EMP_URL, source_family="CPI")
    except BLSEventParseError as exc:
        assert "does not match" in str(exc)
    else:
        raise AssertionError("wrong BLS family URL was accepted")
