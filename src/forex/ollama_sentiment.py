"""M18 validation boundary for local, research-only Ollama responses."""
from __future__ import annotations

from typing import Any

ALLOWED_SENTIMENTS = {"POSITIVE", "NEGATIVE", "NEUTRAL", "ABSTAIN"}
REQUIRED_FIELDS = {"sentiment", "confidence", "rationale", "abstain"}


def validate_response(value: dict[str, Any]) -> dict[str, Any]:
    """Validate a deliberately small research result; reject all command-like output."""
    if set(value) != REQUIRED_FIELDS:
        raise ValueError("response fields must exactly match the M18 contract")
    sentiment = value["sentiment"]
    confidence = value["confidence"]
    rationale = value["rationale"]
    abstain = value["abstain"]
    if sentiment not in ALLOWED_SENTIMENTS or not isinstance(confidence, int) or not 0 <= confidence <= 100:
        raise ValueError("invalid sentiment or confidence")
    if not isinstance(rationale, str) or not rationale.strip() or len(rationale) > 280:
        raise ValueError("invalid rationale")
    if not isinstance(abstain, bool) or abstain != (sentiment == "ABSTAIN"):
        raise ValueError("abstention must agree with sentiment")
    return {"sentiment": sentiment, "confidence": confidence, "rationale": rationale.strip(), "abstain": abstain, "research_only": True, "order_capability": False}
