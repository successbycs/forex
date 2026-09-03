import subprocess
from unittest import mock

from scripts.m20_trade_ledger_dashboard import render, trade_rows


def test_ledger_timeout_remains_refreshable():
    with mock.patch("scripts.m20_trade_ledger_dashboard.subprocess.run", side_effect=subprocess.TimeoutExpired("ledger", 8)):
        rows = trade_rows()
    assert "exceeded eight seconds" in rows[0]["error"]


def test_ledger_renders_monitoring_and_verified_sale_with_pnl():
    screen = render([
        {"attempt_id": "open", "submitted_at_utc": "2026-09-03T12:04:02Z", "action": "BUY", "lifecycle": "OPEN_MONITORING", "volume_lots": "0.01", "proposed_entry": 1.16153, "stop_loss": 1.16110, "take_profit": 1.16217},
        {"submitted_at_utc": "2026-09-03T12:13:06Z", "action": "SELL", "lifecycle": "CLOSED_MATCHED", "volume_lots": "0.01", "proposed_entry": 1.16123, "stop_loss": 1.16172, "take_profit": 1.16049, "closed_at_utc": "2026-09-03T12:20:00Z", "exit_price": 1.16049, "close_reason": "TAKE_PROFIT", "realized_pnl_account": "12.34", "account_currency": "AUD"},
    ], active_attempt_id="open")
    assert "MONITORING" in screen
    assert "SOLD / VERIFIED" in screen
    assert "P&L: +12.34 AUD" in screen
    assert "Opened: 2026-09-03 12:13:06 UTC    Size: 0.01 lots" in screen
    assert "Proposed entry: 1.16123    Stop loss: 1.16172    Take profit: 1.16049" in screen
    assert "Closed: 2026-09-03 12:20:00 UTC    Exit price: 1.16049" in screen
    assert "Close reason: TAKE_PROFIT" in screen


def test_ledger_refuses_an_authoritatively_invalidated_outcome():
    screen = render([{"submitted_at_utc": "2026-09-03T12:20:00Z", "action": "BUY", "lifecycle": "CLOSED_MATCHED", "realized_pnl_account": "100000.18", "account_currency": "AUD", "reconciliation_status": "RECONCILIATION_ERROR", "reconciliation_disposition": "INVALIDATED", "closed_at_utc": "2026-09-03T12:21:00Z", "exit_price": 1.16032, "close_reason": "BROKER_SIDE_CLOSE"}])
    assert "RECONCILIATION ERROR" in screen
    assert "Not verified" in screen
    assert "SOLD / VERIFIED" not in screen


def test_ledger_uses_the_authoritative_reconciliation_error_disposition():
    screen = render([{
        "submitted_at_utc": "2026-09-03T12:20:00Z", "action": "BUY",
        "lifecycle": "CLOSED_RECONCILIATION_ERROR", "reconciliation_status": "RECONCILIATION_ERROR",
        "reconciliation_disposition": "INVALIDATED",
        "reconciliation_reason": "LEGACY_MIXED_RANGE_POSITION_HISTORY_QUERY",
        "closed_at_utc": "2026-09-03T12:21:00Z", "exit_price": 1.16032,
    }])
    assert "RECONCILIATION ERROR" in screen
    assert "LEGACY_MIXED_RANGE_POSITION_HISTORY_QUERY" in screen
    assert "SOLD / VERIFIED" not in screen


def test_ledger_shows_persisted_mt5_rejection_context_without_claiming_cause():
    screen = render([{
        "submitted_at_utc": "2026-09-03T12:20:00Z", "action": "BUY", "lifecycle": "TERMINAL_REJECTED",
        "rejection_context": {"retcode": "10016", "broker_comment": "Invalid stops", "requested_price": "1.16213",
        "observed_bid": "1.16205", "observed_ask": "1.16213", "spread_points": "8"},
    }])
    assert "Broker response: MT5 10016 — Invalid stops" in screen
    assert "Market then: bid 1.16205 / ask 1.16213" in screen


def test_ledger_cards_normalize_nzst_to_utc_and_keep_rejection_pnl_na():
    screen = render([{
        "submitted_at_utc": "2026-09-04T01:27:33+12:00", "action": "BUY", "lifecycle": "TERMINAL_REJECTED",
        "proposed_entry": "1.16213", "rejection_context": {"retcode": "10016"},
    }])
    assert "Opened: 2026-09-03 13:27:33 UTC" in screen
    assert "P&L: N/A — no order opened" in screen
    assert "Broker context: unavailable (legacy record)." in screen
