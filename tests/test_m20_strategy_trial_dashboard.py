from scripts.m20_strategy_trial_dashboard import render


def test_trial_dashboard_renders_all_trial_dimensions_without_claiming_zero_is_a_loss():
    screen = render([{
        "strategy_id": "compression_breakout", "strategy_label": "Compression",
        "signal_count": 5, "selected_count": 2, "attempt_count": 2,
        "opened_count": 2, "rejected_count": 0, "verified_closed_count": 2,
        "win_count": 1, "loss_count": 1, "net_realized_pnl_aud": -0.06,
    }])
    assert "Compression" in screen
    assert "5" in screen and "1/1" in screen and "-0.06 AUD" in screen
    assert "Not tried" in screen
    assert "TOTAL" in screen
    assert "zero means no verified sample yet" in screen
