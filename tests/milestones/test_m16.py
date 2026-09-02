from forex.walk_forward import evaluate_walk_forward


def _bars():
    rows = []
    value = 1.1
    for day in range(1, 19):
        for hour in range(24):
            value += 0.0002 if (day + hour) % 3 else -0.0001
            stamp = f"2026-08-{day:02d}T{hour:02d}:00:00Z"
            rows.append({"time_utc": stamp, "available_at_utc": stamp, "close": value, "high": value + 0.0003, "low": value - 0.0003})
    return rows


def test_m16_is_reproducible_chronological_and_research_only():
    result = evaluate_walk_forward(_bars(), contexts={"sentiment": [{"time_utc": "2026-08-10T08:00:00Z", "available_at_utc": "2026-08-10T08:00:00Z"}]})
    assert result == evaluate_walk_forward(_bars(), contexts={"sentiment": [{"time_utc": "2026-08-10T08:00:00Z", "available_at_utc": "2026-08-10T08:00:00Z"}]})
    assert result["marker"] == "FOREX_M16_WALK_FORWARD_OK"
    assert len(result["windows"]) == 3
    assert result["chronological_only"] and not result["random_shuffling_used"] and not result["live_fitting_used"]
    assert result["overall"]["no_change"]["actionable_sessions"] == 0
    assert result["context_coverage"]["macro"]["status"] == "EVALUATED_AS_UNAVAILABLE"
    assert result["research_only"] and not result["profitability_claim"]


def test_m16_rejects_non_chronological_data():
    bars = _bars(); bars[2], bars[3] = bars[3], bars[2]
    try:
        evaluate_walk_forward(bars)
    except ValueError as error:
        assert "chronological" in str(error)
    else:
        raise AssertionError("non-chronological input was accepted")
