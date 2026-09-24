from __future__ import annotations
from scripts.m33_daily_pnl_email import render_email
from scripts.m33_daily_pnl_report import render
from scripts.m33_daily_pnl_web import render_html


def _report():
    return {"date": "2026-09-23", "closed_outcome_count": 2, "applied_count": 1, "unavailable_count": 1, "rows": [
        {"closed_at_utc": "2026-09-23T12:00:00+12:00", "proposal_id": "applied", "actual_broker_net_aud": 0.27, "expected_round_trip_commission_aud": -0.06, "commission_adjusted_pnl_aud": 0.21, "coverage_status": "APPLIED", "unavailable_reason": None},
        {"closed_at_utc": "2026-09-23T12:01:00+12:00", "proposal_id": "unavailable", "actual_broker_net_aud": -0.10, "expected_round_trip_commission_aud": None, "commission_adjusted_pnl_aud": None, "coverage_status": "UNAVAILABLE", "unavailable_reason": "COST_COMPONENT_MISSING"},
    ]}


def test_daily_report_renders_applied_and_unavailable_rows_without_recalculation():
    output = render(_report())
    assert "Actual: +0.27 AUD" in output
    assert "Expected commission: -0.06 AUD | Adjusted: +0.21 AUD" in output
    assert "UNAVAILABLE (COST_COMPONENT_MISSING)" in output


def test_web_and_email_render_the_same_recorded_daily_facts():
    report = _report()
    page = render_html(report)
    text, email_html = render_email(report)
    for output in (page, text, email_html):
        assert "2026-09-23" in output
        assert "applied" in output
        assert "unavailable" in output
    assert "ASSUMED GO Plus+ AUD" in page
