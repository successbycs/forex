"""M18's bounded, research-only Ollama sentiment contract.

This module deliberately builds a fixed request and validates the entire model
response.  It has no account, network, MT5, shell, or order surface.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any


ALLOWED_SENTIMENTS = {"POSITIVE", "NEGATIVE", "NEUTRAL", "ABSTAIN"}
REQUIRED_FIELDS = {"sentiment", "confidence", "rationale", "abstain"}
PROMPT_TEMPLATE_VERSION = "forex.m18.sentiment.v1"
RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["sentiment", "confidence", "rationale", "abstain"],
    "properties": {
        "sentiment": {"type": "string", "enum": sorted(ALLOWED_SENTIMENTS)},
        "confidence": {"type": "integer", "minimum": 0, "maximum": 100},
        "rationale": {"type": "string", "minLength": 1, "maxLength": 280},
        "abstain": {"type": "boolean"},
    },
}


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256(value: Any) -> str:
    """Return a stable, explicit provenance hash for JSON-compatible data."""
    return f"sha256:{hashlib.sha256(_canonical(value).encode()).hexdigest()}"


def build_request(context: dict[str, Any]) -> dict[str, Any]:
    """Build the only M18 prompt from the already-bounded M17 context."""
    forbidden = {"account", "credentials", "mt5_control", "order", "execution", "future_bars"}
    if context.get("schema_version") != "forex.agent-context.v1":
        raise ValueError("M18 requires the M17 context contract")
    if context.get("agent_authority") != "NONE" or context.get("order_capability") is not False:
        raise ValueError("M18 accepts only non-executing context")
    if forbidden & set(context):
        raise ValueError("M18 context contains a forbidden field")
    permitted = {
        "cutoff_utc": context.get("cutoff_utc"),
        "price_bars": context.get("price_bars"),
        "research_features": context.get("research_features"),
    }
    if not isinstance(permitted["price_bars"], list) or not permitted["price_bars"]:
        raise ValueError("M18 requires at least one permitted historical bar")
    prompt = (
        "You are a research-only EUR/USD historical-context assistant. "
        "Do not give a trading instruction, order, position size, or execution advice. "
        "Assess only the supplied closed historical context. If the context is insufficient, "
        "return ABSTAIN with confidence 0. Return JSON only matching the supplied schema.\n"
        f"Context: {_canonical(permitted)}"
    )
    return {
        "schema_version": "forex.m18.ollama-request.v1",
        "prompt_template_version": PROMPT_TEMPLATE_VERSION,
        "prompt": prompt,
        "input_context_sha256": sha256(permitted),
        "response_schema": RESPONSE_SCHEMA,
    }


def validate_response(value: dict[str, Any]) -> dict[str, Any]:
    """Validate a deliberately small research result; reject all command-like output."""
    if set(value) != REQUIRED_FIELDS:
        raise ValueError("response fields must exactly match the M18 contract")
    sentiment = value["sentiment"]
    confidence = value["confidence"]
    rationale = value["rationale"]
    abstain = value["abstain"]
    if sentiment not in ALLOWED_SENTIMENTS or isinstance(confidence, bool) or not isinstance(confidence, int) or not 0 <= confidence <= 100:
        raise ValueError("invalid sentiment or confidence")
    if not isinstance(rationale, str) or not rationale.strip() or len(rationale) > 280:
        raise ValueError("invalid rationale")
    if not isinstance(abstain, bool) or abstain != (sentiment == "ABSTAIN"):
        raise ValueError("abstention must agree with sentiment")
    if abstain and confidence != 0:
        raise ValueError("an abstention must have zero confidence")
    return {
        "sentiment": sentiment,
        "confidence": confidence,
        "rationale": rationale.strip(),
        "abstain": abstain,
        "research_only": True,
        "order_capability": False,
    }
