import pytest
from forex.ollama_sentiment import validate_response


def test_m18_accepts_only_research_sentiment_or_abstain():
    result = validate_response({"sentiment":"ABSTAIN", "confidence":0, "rationale":"Insufficient permitted context.", "abstain":True})
    assert result["research_only"] and not result["order_capability"]


@pytest.mark.parametrize("value", [
    {"sentiment":"BUY", "confidence":90, "rationale":"x", "abstain":False},
    {"sentiment":"NEUTRAL", "confidence":50, "rationale":"x", "abstain":False, "order":"BUY"},
    {"sentiment":"ABSTAIN", "confidence":0, "rationale":"x", "abstain":False},
])
def test_m18_rejects_trade_like_or_invalid_output(value):
    with pytest.raises(ValueError): validate_response(value)
