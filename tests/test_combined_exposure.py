from __future__ import annotations

import pytest

from forex.combined_exposure import CombinedExposureError, combined_exposure_report
from tests.test_h_slow_lifecycle import registry


def observations(*, hslow_state="RECONCILED", m1_positions=None, hslow_positions=None):
    return [
        {"stream_id": "M1", "account_scope": "demo_scope_m1", "terminal_instance": "terminal_m1",
         "reconciliation_status": "RECONCILED", "positions": m1_positions or []},
        {"stream_id": "H_SLOW", "account_scope": "demo_scope_hslow", "terminal_instance": "terminal_hslow",
         "reconciliation_status": hslow_state, "positions": hslow_positions or []},
    ]


def position(ticket, owner, direction, notional=1000.0):
    return {"ticket_id": ticket, "owner_stream_id": owner, "direction": direction, "position_status": "OPEN",
            "notional_usd": notional, "margin_aud": 10.0, "maximum_loss_aud": 5.0}


def test_reports_gross_and_signed_exposure_only_for_two_reconciled_isolated_streams():
    result = combined_exposure_report(stream_registry=registry(), observations=observations(
        m1_positions=[position("ticket_m1", "M1", "BUY", 1000.0)],
        hslow_positions=[position("ticket_hslow", "H_SLOW", "SELL", 500.0)],
    ))
    assert result["report_state"] == "RECONCILED"
    assert (result["gross_notional_usd"], result["net_notional_usd"], result["margin_aud"], result["maximum_loss_aud"]) == (1500.0, 500.0, 20.0, 10.0)
    assert result["execution_authority"] is False
    assert result["report_sha256"].startswith("sha256:")


def test_unknown_stream_never_nets_or_invents_aggregate_exposure():
    result = combined_exposure_report(stream_registry=registry(), observations=observations(hslow_state="UNKNOWN"))
    assert result["report_state"] == "RECONCILIATION_REQUIRED"
    assert result["positions"] is None and result["gross_notional_usd"] is None


@pytest.mark.parametrize("mutate", [
    lambda rows: rows.pop(),
    lambda rows: rows[1].update(account_scope="demo_scope_m1"),
    lambda rows: rows[1].update(positions=[position("ticket_hslow", "M1", "BUY")]),
    lambda rows: rows[0].update(positions=[position("ticket_m1", "M1", "BUY", -1.0)]),
])
def test_refuses_missing_scope_cross_stream_ownership_or_invalid_amount(mutate):
    value = observations(); mutate(value)
    with pytest.raises(CombinedExposureError):
        combined_exposure_report(stream_registry=registry(), observations=value)
