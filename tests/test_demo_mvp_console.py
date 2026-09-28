from scripts import m33_mvp_console_web as console


def _models():
    return {
        "listener": {
            "state": "RUNNING", "heartbeat_at_utc": "2026-09-28T10:00:00Z", "release_id": "a" * 16,
            "runtime_binding": {"server": "GOMarketsMU-Demo", "symbol": "EURUSD"},
            "last_result": {"proposal": {"action": "BUY"}, "risk_policy": {"entry_allowed": True}, "captured_at_utc": "2026-09-28T10:00:00Z"},
        },
        "trace": {"observation": "TRACE_COMPLETE", "assessment_sequence": 12, "events": [{
            "sequence": 8, "event_type": "EXECUTION_RESULT", "occurred_at_utc": "2026-09-28T10:00:00Z",
            "facts": {"action": "BUY", "planned_entry": 1.2, "execution_status": "ACCEPTED"},
        }]},
        "pnl": {"schema_version": "forex.m33.5.system-pnl-summary.v1", "generated_at_utc": "2026-09-28T10:00:00Z", "unclosed_system_attempt_count": 1,
                "periods": [{"period": "today", "actual_net_pnl_account": 0.2, "account_currencies": ["AUD"], "matched_closed_count": 1, "excluded_closed_count": 2}],
                "journal": [{"closed_at_utc": "2026-09-28T10:00:00Z", "proposal_id": "p", "attempt_id": "a", "strategy_version": "v", "action": "BUY", "trade_owner_strategy_id": "compression_breakout", "reconciliation_status": "MATCHED", "proposed_entry": 1.2, "stop_loss": 1.1, "take_profit": 1.3, "actual_entry_price": 1.2, "exit_price": 1.3, "volume_lots": 0.01, "gross_price_pnl_account": 0.3, "commission_account": -0.1, "fee_account": 0, "swap_account": 0, "realized_pnl_account": 0.2, "account_currency": "AUD"}],
                "excluded_journal": [{"closed_at_utc": "2026-09-28T10:01:00Z", "proposal_id": "unmatched", "attempt_id": "attempt", "reconciliation_status": "RECONCILIATION_ERROR", "exclusion_reason": "UNRECONCILED", "realized_pnl_account": 99}]},
        "strategies": [{"strategy_id": "compression_breakout", "selected_count": 1, "attempt_count": 1, "verified_closed_count": 1, "win_count": 1, "loss_count": 0, "net_realized_pnl_aud": 0.2}],
    }


def test_console_renders_actual_read_models_without_any_control_surface():
    page = console.render_html(_models())
    assert "Forex Demo MVP Console" in page
    assert "GOMarketsMU-Demo" in page and "Broker-matched system journal" in page
    assert "Actual listener decision trace" in page and "compression_breakout" in page
    assert "Actual broker net P&amp;L only" in page
    assert "Current execution and reconciliation" in page
    assert "Excluded closed system outcomes" in page and "UNRECONCILED" in page
    assert "+99.00" not in page
    for forbidden in ("<form", "POST", "submit order", "maintenance hold control", "GOMarketsMU-Live"):
        assert forbidden not in page


def test_console_reads_all_fixed_panels_in_parallel(monkeypatch):
    calls = []
    monkeypatch.setattr(console, "_operation", lambda script, *args: calls.append((script, args)) or {"ok": True})
    assert set(console.fetch_console()) == {"listener", "trace", "pnl", "strategies"}
    assert len(calls) == 4


def test_console_escapes_listener_and_trace_values_and_marks_failed_read_visible():
    models = _models()
    models["listener"]["state"] = "<unsafe>"
    models["trace"]["events"][0]["facts"]["action"] = "<script>alert(1)</script>"
    models["pnl"] = {"_unavailable": "fixed reader failed"}
    page = console.render_html(models)
    assert "&lt;unsafe&gt;" in page and "&lt;script&gt;alert(1)&lt;/script&gt;" in page
    assert "JOURNAL / P&amp;L UNAVAILABLE" in page


def test_system_pnl_query_is_fixed_read_only_and_excludes_non_system_account_events():
    query = (console.ROOT / "sql" / "m33_mvp_system_pnl_summary.sql").read_text()
    for required in ("GOMarketsMU-Demo", "trade_owner_strategy_id IS NOT NULL", "MATCHED", "REPAIRED", "Pacific/Auckland", "excluded_closed_count", "excluded_journal", "LIMIT 50"):
        assert required in query
    for forbidden in ("INSERT", "UPDATE", "DELETE", "DROP", "demo_account_balance"):
        assert forbidden not in query
