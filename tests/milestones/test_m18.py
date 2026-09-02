import pytest
from forex.ollama_sentiment import PROMPT_TEMPLATE_VERSION, build_request, validate_response


def test_m18_accepts_only_research_sentiment_or_abstain():
    result = validate_response({"sentiment":"ABSTAIN", "confidence":0, "rationale":"Insufficient permitted context.", "abstain":True})
    assert result["research_only"] and not result["order_capability"]


def test_m18_fixed_request_accepts_only_bounded_m17_context():
    request = build_request({
        "schema_version": "forex.agent-context.v1", "agent_authority": "NONE",
        "order_capability": False, "cutoff_utc": "2026-08-28T22:00:00Z",
        "price_bars": [{"time_utc": "2026-08-28T21:00:00Z", "close": "1.15"}],
        "research_features": {"source": "DEMO_ONLY_HISTORICAL"},
    })
    assert request["prompt_template_version"] == PROMPT_TEMPLATE_VERSION
    assert request["input_context_sha256"].startswith("sha256:")
    assert "order" not in request["prompt"].lower().split("context:")[1]


def test_m18_rejects_context_with_execution_capability():
    with pytest.raises(ValueError):
        build_request({"schema_version": "forex.agent-context.v1", "agent_authority": "NONE", "order_capability": True, "price_bars": [{}]})


@pytest.mark.parametrize("value", [
    {"sentiment":"BUY", "confidence":90, "rationale":"x", "abstain":False},
    {"sentiment":"NEUTRAL", "confidence":50, "rationale":"x", "abstain":False, "order":"BUY"},
    {"sentiment":"ABSTAIN", "confidence":0, "rationale":"x", "abstain":False},
    {"sentiment":"ABSTAIN", "confidence":10, "rationale":"x", "abstain":True},
])
def test_m18_rejects_trade_like_or_invalid_output(value):
    with pytest.raises(ValueError): validate_response(value)
