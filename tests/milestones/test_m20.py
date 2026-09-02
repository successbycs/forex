from forex.ollama_evaluation import EXPERIMENT_SESSIONS, action_from_sentiment, evaluate
from scripts import postgres_pgvector_adapter


def response(sentiment: str, abstain: bool = False) -> dict:
    return {"sentiment": sentiment, "abstain": abstain, "research_only": True, "order_capability": False}


def experiments() -> list[dict]:
    return [
        {
            "decision_at_utc": f"2026-07-{day:02d}T09:00:00+00:00", "entry_at_utc": f"2026-07-{day:02d}T08:00:00+00:00",
            "exit_at_utc": f"2026-07-{day:02d}T20:00:00+00:00", "entry_close": 1.10, "exit_close": 1.11 if day % 2 else 1.09,
            "context_bar_count": 12, "model_output_sha256": f"sha256:{day:064x}",
            "response": response("POSITIVE" if day % 2 else "NEGATIVE"), "price_only_action": "BUY",
        }
        for day in range(1, EXPERIMENT_SESSIONS + 1)
    ]


def test_m20_evaluation_is_fixed_chronological_and_research_only():
    result = evaluate(experiments())
    assert result["marker"] == "FOREX_M20_EVALUATION_OK"
    assert result["predeclared_controls"]["sessions"] == 6
    assert result["predeclared_controls"]["random_shuffling_used"] is False
    assert len(result["rows"]) == 6
    assert result["comparison"]["no_change"]["actionable_sessions"] == 0
    assert result["research_only"] is True and result["order_capability"] is False


def test_m20_abstention_is_evaluation_no_trade_and_rejects_order_surface():
    assert action_from_sentiment(response("ABSTAIN", True)) == "NO_TRADE"
    unsafe = response("POSITIVE")
    unsafe["order_capability"] = True
    try:
        action_from_sentiment(unsafe)
    except ValueError as exc:
        assert "research-only" in str(exc)
    else:
        raise AssertionError("M20 accepted an order-capable response")


def test_m20_adapter_exposes_one_fixed_read_only_probe():
    assert "forex-m20-ollama-evaluation-probe" in postgres_pgvector_adapter.READ_ONLY
    assert "m20_probe" in postgres_pgvector_adapter.ASSETS
    assert "forex-m20-ollama-evaluation-probe" not in postgres_pgvector_adapter.MUTATING
