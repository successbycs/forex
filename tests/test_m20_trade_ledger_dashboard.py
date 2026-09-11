import json
import subprocess
from datetime import date
from unittest import mock

from scripts.m20_trade_ledger_dashboard import render, trade_rows


def test_ledger_timeout_remains_refreshable():
    with mock.patch("scripts.m20_trade_ledger_dashboard.subprocess.run", side_effect=subprocess.TimeoutExpired("ledger", 8)):
        rows = trade_rows()
    assert "exceeded eight seconds" in rows[0]["error"]


def test_ledger_renders_monitoring_and_verified_sale_with_pnl():
    screen = render([
        {"attempt_id": "open", "submitted_at_utc": "2026-09-03T12:04:02Z", "action": "BUY", "lifecycle": "OPEN_MONITORING", "volume_lots": "0.01", "proposed_entry": 1.16153, "actual_entry_price": 1.16155, "stop_loss": 1.16110, "take_profit": 1.16217},
        {"submitted_at_utc": "2026-09-03T12:13:06Z", "action": "SELL", "lifecycle": "CLOSED_MATCHED", "volume_lots": "0.01", "proposed_entry": 1.16123, "stop_loss": 1.16172, "take_profit": 1.16049, "closed_at_utc": "2026-09-03T12:20:00Z", "exit_price": 1.16049, "close_reason": "TAKE_PROFIT", "gross_price_pnl_account": "12.34", "commission_account": "0", "swap_account": "0", "estimated_spread_cost_account": "0.20", "slippage_cost_account": "0.10", "estimated_total_cost_account": "0.30", "realized_pnl_account": "12.34", "account_currency": "AUD"},
    ], active_attempt_id="open", nz_day=date(2026, 9, 4))
    assert "MONITORING" in screen
    assert "SOLD / VERIFIED" in screen
    assert "+12.34 AUD" in screen
    assert "Gross     Fees      Net" in screen
    assert "Strategy" in screen
    assert "—" in screen  # Monitoring rows keep unavailable exit and P&L explicit.
    assert "1.16155" in screen
    assert "NZ day: 04/09/26" in screen
    assert "04/09 00:13:06" in screen
    assert "Closed 04/09 00:20:00 NZST at 1.16049; Take profit reached" in screen


def test_ledger_refuses_an_authoritatively_invalidated_outcome():
    screen = render([{"submitted_at_utc": "2026-09-03T12:20:00Z", "action": "BUY", "lifecycle": "CLOSED_MATCHED", "realized_pnl_account": "100000.18", "account_currency": "AUD", "reconciliation_status": "RECONCILIATION_ERROR", "reconciliation_disposition": "INVALIDATED", "closed_at_utc": "2026-09-03T12:21:00Z", "exit_price": 1.16032, "close_reason": "BROKER_SIDE_CLOSE"}], nz_day=date(2026, 9, 4), show_unverified=True)
    assert "RECONCILIATION ERROR" in screen
    assert "N/A — no countable trade" in screen
    assert "SOLD / VERIFIED" not in screen


def test_ledger_translates_a_broker_side_close_for_human_readability():
    screen = render([{
        "submitted_at_utc": "2026-09-03T12:20:00Z", "action": "BUY", "lifecycle": "CLOSED_MATCHED",
        "gross_price_pnl_account": "-0.24", "commission_account": "0", "swap_account": "0",
        "realized_pnl_account": "-0.24", "account_currency": "AUD",
        "closed_at_utc": "2026-09-03T12:21:00Z", "exit_price": 1.16032,
        "close_reason": "BROKER_SIDE_CLOSE",
    }], nz_day=date(2026, 9, 4))
    assert "Broker-side protective close" in screen


def test_ledger_uses_the_authoritative_reconciliation_error_disposition():
    screen = render([{
        "submitted_at_utc": "2026-09-03T12:20:00Z", "action": "BUY",
        "lifecycle": "CLOSED_RECONCILIATION_ERROR", "reconciliation_status": "RECONCILIATION_ERROR",
        "reconciliation_disposition": "INVALIDATED",
        "reconciliation_reason": "LEGACY_MIXED_RANGE_POSITION_HISTORY_QUERY",
        "closed_at_utc": "2026-09-03T12:21:00Z", "exit_price": 1.16032,
    }], nz_day=date(2026, 9, 4), show_rejections=True, show_unverified=True)
    assert "RECONCILIATION ERROR" in screen
    assert "LEGACY_MIXED_RANGE_POSITION_HISTORY_QUERY" in screen
    assert "SOLD / VERIFIED" not in screen


def test_ledger_shows_persisted_mt5_rejection_context_without_claiming_cause():
    screen = render([{
        "submitted_at_utc": "2026-09-03T12:20:00Z", "action": "BUY", "lifecycle": "TERMINAL_REJECTED",
        "rejection_context": {"retcode": "10016", "broker_comment": "Invalid stops", "requested_price": "1.16213",
        "observed_bid": "1.16205", "observed_ask": "1.16213", "spread_points": "8"},
    }], nz_day=date(2026, 9, 4), show_rejections=True)
    assert "Rejected order attempts — not trades" in screen
    assert "MT5 10016: Invalid stops" in screen
    assert "bid/ask 1.16205/1.16213" in screen


def test_ledger_filters_to_current_nz_day_and_keeps_rejection_pnl_na():
    screen = render([{
        "submitted_at_utc": "2026-09-04T01:27:33+12:00", "action": "BUY", "lifecycle": "TERMINAL_REJECTED",
        "proposed_entry": "1.16213", "rejection_context": {"retcode": "10016"},
    }, {"submitted_at_utc": "2026-09-03T01:27:33+12:00", "action": "SELL", "lifecycle": "TERMINAL_REJECTED"}], nz_day=date(2026, 9, 4), show_rejections=True)
    assert "04/09 01:27:33" in screen
    assert "03/09 01:27:33" not in screen
    assert "Rejected order attempts today: 1" in screen
    assert "Broker context unavailable (legacy record)." in screen


def test_ledger_shows_every_opened_trade_for_the_selected_nz_day_not_only_ten():
    rows = [
        {"submitted_at_utc": f"2026-09-04T{hour:02}:00:00+12:00", "action": "BUY", "lifecycle": "OPEN_MONITORING"}
        for hour in range(12)
    ]
    screen = render(rows, nz_day=date(2026, 9, 4))
    assert "12 verified/open trades" in screen
    assert "04/09 00:00:00" in screen
    assert "04/09 11:00:00" in screen

def test_lifecycle_adapter_output_keeps_dashboard_trade_context(monkeypatch):
    from scripts import postgres_pgvector_adapter

    payload = '[{"session_id":"s","proposal_id":"p","attempt_id":"a","action":"BUY","status":"SUBMITTED","submitted_at_utc":"2026-09-11T06:00:00Z","proposed_entry":1.16,"stop_loss":1.159,"take_profit":1.161,"actual_entry_price":"1.16001","volume_lots":"0.01","selected_strategy_id":"compression_breakout","trade_owner_strategy_id":"compression_breakout","closed_at_utc":"2026-09-11T06:05:00Z","exit_price":1.16021,"gross_price_pnl_account":0.26,"commission_account":0.01,"fee_account":0.02,"swap_account":0.03,"estimated_spread_cost_account":0.08,"slippage_cost_account":0.02,"estimated_total_cost_account":0.10,"realized_pnl_account":0.20,"account_currency":"AUD","close_reason":"TAKE_PROFIT","reconciliation_status":"MATCHED","reconciliation_disposition":null,"reconciliation_reason":null,"rejection_context":null,"events":"[\\"OPENED\\",\\"CLOSED\\"]","lifecycle":"CLOSED_MATCHED"}]'
    monkeypatch.setattr(postgres_pgvector_adapter, "remote", lambda _: {"ok": True, "exit_code": 0, "stdout": payload, "stderr": ""})
    rows = json.loads(postgres_pgvector_adapter.m20_lifecycle_summary()["result"]["stdout"])
    screen = render(rows, nz_day=date(2026, 9, 11))
    assert "Compression" in screen
    assert "0.01" in screen
    assert "1.159" in screen and "1.161" in screen
    assert "+0.26" in screen and "+0.20 AUD" in screen


def test_lifecycle_adapter_output_preserves_evidence_validator_wire_format(monkeypatch):
    from scripts import postgres_pgvector_adapter
    from scripts.m20_demo_evidence_contract import validate_broker_matched_lifecycle

    payload = '[{"session_id":"lease","proposal_id":"p","attempt_id":"a","action":"BUY","submitted_at_utc":"2026-09-11T06:00:00Z","actual_entry_price":"1.16001","exit_price":1.16021,"realized_pnl_account":0.20,"account_currency":"AUD","reconciliation_status":"MATCHED","events":"[\\"OPENED\\",\\"CLOSED\\"]","lifecycle":"CLOSED_MATCHED"}]'
    monkeypatch.setattr(postgres_pgvector_adapter, "remote", lambda _: {"ok": True, "exit_code": 0, "stdout": payload, "stderr": ""})
    wrapper = postgres_pgvector_adapter.m20_lifecycle_summary()
    row = validate_broker_matched_lifecycle(wrapper, {"session_id": "lease"})
    assert row["attempt_id"] == "a"
