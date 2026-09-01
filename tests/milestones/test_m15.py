from forex.daily_hypothesis import advisory, train_baseline


BARS = [
    {"close": 1.1000, "high": 1.1010, "low": 1.0990},
    {"close": 1.1010, "high": 1.1020, "low": 1.1000},
    {"close": 1.1030, "high": 1.1040, "low": 1.1020},
    {"close": 1.1010, "high": 1.1020, "low": 1.1000},
    {"close": 1.1040, "high": 1.1050, "low": 1.1030},
    {"close": 1.1020, "high": 1.1030, "low": 1.1010},
    {"close": 1.1050, "high": 1.1060, "low": 1.1040},
]


def test_m15_baseline_is_reproducible_and_advisory_only():
    model = train_baseline(BARS)
    result = advisory(BARS[-3:], model=model)
    assert result == advisory(BARS[-3:], model=model)
    assert result["action"] in {"BUY", "SELL", "NO_TRADE"}
    assert 0 <= result["advisory_score"] <= 100
    assert result["research_only"] is True


def test_m15_event_blackout_forces_no_trade():
    assert advisory(BARS[-3:], model=train_baseline(BARS), event_window="EVENT_BLACKOUT")["action"] == "NO_TRADE"


def test_m15_training_is_deterministic_and_uses_next_bar_labels():
    first, second = train_baseline(BARS), train_baseline(BARS)
    assert first == second
    assert first["training_examples"] == len(BARS) - 3
