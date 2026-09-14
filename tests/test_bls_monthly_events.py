import pytest

from forex.bls_monthly_events import BLSMonthlyParseError, parse_bls_monthly_html
from forex.event_quality import qualify_events


URL = "https://www.bls.gov/schedule/2026/09_sched_list.htm"


def page(*rows, notice="NOTE: All times on calendar are Eastern Time."):
    body = "".join(f"<tr><td>{date}</td><td>{time}</td><td>{release}</td></tr>" for date, time, release in rows)
    return f"<html><body><p>{notice}</p><table><tr><th>Date</th><th>Time</th><th>Release</th></tr>{body}</table></body></html>"


def test_parses_observed_monthly_shape_with_stable_reference_month_ids():
    html = page(("Friday, September 4, 2026", "08:30 AM", "Employment Situation for August 2026"),
                ("Friday, September 11, 2026", "08:30 AM", "Consumer Price Index for August 2026"),
                ("Monday, September 7, 2026", "", "Labor Day"))
    parsed = parse_bls_monthly_html(html, capture_completed_at_utc="2026-01-01T00:00:00Z", source_url=URL)
    assert [item["event_id"] for item in parsed["records"]] == ["bls-employment-situation-2026-08", "bls-cpi-2026-08"]
    assert parsed["ignored_unrelated_row_count"] == 1
    assert all(item["timezone"] == "America/New_York" for item in parsed["records"])
    qualified = qualify_events(parsed["records"], "2026-01-02T00:00:00Z")
    assert [item["scheduled_at_utc"] for item in qualified["accepted"]] == ["2026-09-04T12:30:00Z", "2026-09-11T12:30:00Z"]


def test_dst_months_follow_new_york_rules_not_fixed_utc_offsets():
    march = parse_bls_monthly_html(page(("Friday, March 6, 2026", "08:30 AM", "Employment Situation for February 2026")), capture_completed_at_utc="2026-01-01T00:00:00Z", source_url="https://www.bls.gov/schedule/2026/03_sched_list.htm")
    november = parse_bls_monthly_html(page(("Friday, November 6, 2026", "08:30 AM", "Employment Situation for October 2026")), capture_completed_at_utc="2026-01-01T00:00:00Z", source_url="https://www.bls.gov/schedule/2026/11_sched_list.htm")
    assert qualify_events(march["records"], "2026-01-02T00:00:00Z")["accepted"][0]["scheduled_at_utc"] == "2026-03-06T13:30:00Z"
    assert qualify_events(november["records"], "2026-01-02T00:00:00Z")["accepted"][0]["scheduled_at_utc"] == "2026-11-06T13:30:00Z"


def test_missing_or_negated_notice_stays_date_only_and_quarantined():
    for notice in ("", "NOTE: All times on calendar are not Eastern Time.", "<script>NOTE: All times on calendar are Eastern Time.</script>"):
        parsed = parse_bls_monthly_html(page(("Friday, September 4, 2026", "08:30 AM", "Employment Situation for August 2026"), notice=notice), capture_completed_at_utc="2026-01-01T00:00:00Z", source_url=URL)
        assert parsed["records"][0]["time_precision"] == "DATE_ONLY"
        assert "timezone" not in parsed["records"][0]
        assert parsed["quarantined"][0]["reason"] == "BLS_MONTHLY_TIMEZONE_NOT_DECLARED_DATE_ONLY"


def test_malformed_targets_rows_and_url_are_refused_or_quarantined():
    malformed = parse_bls_monthly_html(page(("Friday, September 4, 2026", "08:30 AM", "Consumer Price Index for bad-month"),
                                             ("Friday, October 2, 2026", "08:30 AM", "Employment Situation for August 2026"),
                                             ("Friday, September 4, 2026", "", "Employment Situation for August 2026")),
                                       capture_completed_at_utc="2026-01-01T00:00:00Z", source_url=URL)
    assert {item["reason"] for item in malformed["quarantined"]} == {"MALFORMED_BLS_MONTHLY_TARGET", "BLS_MONTHLY_DATE_OUTSIDE_SOURCE_MONTH", "BLS_MONTHLY_TARGET_DATE_ONLY"}
    with pytest.raises(BLSMonthlyParseError):
        parse_bls_monthly_html(page(), capture_completed_at_utc="2026-01-01T00:00:00Z", source_url=URL + "?x=1")
    with pytest.raises(BLSMonthlyParseError):
        parse_bls_monthly_html(page(), capture_completed_at_utc="2026-01-01T00:00:00Z", source_url="https://www.bls.gov/schedule/2026/13_sched_list.htm")
