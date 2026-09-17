from scripts.m20_listener_evidence_view import render


def _latest(*, action="NO_TRADE"):
    return {
        "observation": "AVAILABLE", "listener_release_id": "a" * 16,
        "assessment_sequence": 42, "assessment_completed_at_utc": "2026-09-17T04:00:02Z",
        "assessment": {
            "proposal": {"proposal_id": "proposal-1", "action": action,
                         "decision_candle_closed_at_utc": "2026-09-17T04:00:00Z",
                         "rationale": "No selected actionable M1 strategy.",
                         "proposed_entry": None, "stop_loss": None, "take_profit": None},
            "execution": {"status": "NOT_SUBMITTED"},
            "reconciliation": {"status": "NO_TRADE_RECONCILED"},
            "strategy_selection": {"selected_strategy_id": None, "selection_status": "NO_SELECTION"},
            "strategy_assessments": [
                {"id": "momentum_breakout", "signal": "NO_TRADE", "reason": "No breakout."},
                {"id": "compression_breakout", "signal": "NO_TRADE", "reason": "No compression."},
                {"id": "trend_pullback", "signal": "NO_TRADE", "reason": "No pullback."},
                {"id": "range_reversion", "signal": "NO_TRADE", "reason": "No rejection."},
                {"id": "session_breakout", "signal": "NO_TRADE", "reason": "Outside session."},
            ],
        },
    }


def test_evidence_view_shows_full_terminal_no_trade_without_inventing_costs():
    screen = render(_latest(), [])
    assert "Closed M1 candle: 2026-09-17T04:00:00Z" in screen
    assert "Five strategy signals" in screen
    assert "- session_breakout: NO_TRADE — Outside session." in screen
    assert "Selected owner: UNKNOWN [NO_SELECTION]" in screen
    assert "Lifecycle join: NOT_APPLICABLE (terminal no-trade has no execution lifecycle)" in screen
    assert "Lifecycle: NO_TRADE_RECONCILED" in screen
    assert "Actual costs/outcome: N/A (no order)" in screen
    assert "Unresolved joins: NONE" in screen


def test_evidence_view_uses_only_exact_proposal_id_for_lifecycle_outcome_and_costs():
    latest = _latest(action="BUY")
    latest["assessment"]["execution"] = {"status": "SUBMITTED", "attempt_id": "attempt-1"}
    rows = [{"proposal_id": "other", "lifecycle": "CLOSED_MATCHED"}, {
        "proposal_id": "proposal-1", "attempt_id": "attempt-1", "lifecycle": "CLOSED_MATCHED",
        "closed_at_utc": "2026-09-17T04:04:00Z", "exit_price": "1.1002",
        "reconciliation_status": "MATCHED", "gross_price_pnl_account": "1.2",
        "commission_account": "0.1", "fee_account": "0", "swap_account": "0",
        "estimated_spread_cost_account": "0.2", "slippage_cost_account": "0.1",
        "estimated_total_cost_account": "0.4", "realized_pnl_account": "0.8", "account_currency": "AUD",
        "reconciliation_reason": None,
    }]
    screen = render(latest, rows)
    assert "Attempt: attempt-1 | execution SUBMITTED" in screen
    assert "Lifecycle join: MATCHED by exact proposal id" in screen
    assert "Lifecycle: CLOSED_MATCHED" in screen
    assert "gross 1.2" in screen and "realised 0.8 AUD" in screen
    assert "Unresolved joins: UNKNOWN" in screen


def test_evidence_view_keeps_lifecycle_failure_explicit():
    screen = render(_latest(action="BUY"), [{"error": "PostgreSQL lifecycle summary exceeded 15 seconds"}])
    assert "Lifecycle join: UNKNOWN (PostgreSQL lifecycle summary exceeded 15 seconds)" in screen
    assert "Actual costs/outcome: UNKNOWN" in screen


def test_evidence_view_reads_signals_and_owner_from_the_retained_snapshot_contract():
    latest = _latest()
    assessment = latest["assessment"]
    assessment["decision_snapshot"] = {
        "strategy_assessments": assessment.pop("strategy_assessments"),
        "market_context": {"selected_strategy_id": "range_reversion", "selection_status": "NO_SELECTION"},
    }
    assessment.pop("strategy_selection")
    screen = render(latest, [])
    assert "Selected owner: range_reversion [NO_SELECTION]" in screen
    assert "- momentum_breakout: NO_TRADE — No breakout." in screen


def test_evidence_view_does_not_invent_no_trade_reconciliation_when_it_is_absent():
    latest = _latest()
    latest["assessment"].pop("reconciliation")
    screen = render(latest, [])
    assert "reconciliation UNKNOWN" in screen
    assert "Actual costs/outcome: N/A (no order)" in screen
