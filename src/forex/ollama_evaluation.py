"""Small, chronological M20 evaluation of bounded Ollama sentiment.

This module evaluates already-validated research sentiment against fixed
price-only and no-change comparators.  It is intentionally not a strategy or
an execution interface: all actions are labels used only to calculate a
historical, cost-sensitive comparison.
"""
from __future__ import annotations

from statistics import mean
from typing import Any


EVALUATION_VERSION = "forex.m20.ollama-historical-evaluation.v1"
FIXED_COST_BPS_PER_SIDE = 2.0
OLLAMA_MODEL = "qwen2.5:3b"
EXPERIMENT_SESSIONS = 3


def action_from_sentiment(response: dict[str, Any]) -> str:
    """Map a validated sentiment observation to an evaluation-only label."""
    if response.get("research_only") is not True or response.get("order_capability") is not False:
        raise ValueError("M20 accepts only research-only model responses")
    sentiment = response.get("sentiment")
    if response.get("abstain") is True or sentiment in {"ABSTAIN", "NEUTRAL"}:
        return "NO_TRADE"
    if sentiment == "POSITIVE":
        return "BUY"
    if sentiment == "NEGATIVE":
        return "SELL"
    raise ValueError("M20 received an invalid validated sentiment")


def _net_return(action: str, entry: float, exit_: float) -> float:
    if action == "NO_TRADE":
        return 0.0
    if action not in {"BUY", "SELL"}:
        raise ValueError("evaluation action must be BUY, SELL, or NO_TRADE")
    direction = 1.0 if action == "BUY" else -1.0
    return direction * (exit_ / entry - 1.0) - (2.0 * FIXED_COST_BPS_PER_SIDE / 10_000.0)


def _metrics(rows: list[dict[str, Any]], strategy: str) -> dict[str, Any]:
    acted = [item[strategy] for item in rows if item[strategy]["action"] != "NO_TRADE"]
    return {
        "sessions": len(rows),
        "actionable_sessions": len(acted),
        "directional_accuracy": round(mean(item["correct_direction"] for item in acted), 6) if acted else None,
        "mean_net_return": round(mean(item["net_return"] for item in acted), 10) if acted else 0.0,
        "total_net_return": round(sum(item["net_return"] for item in acted), 10),
        "cost_assumption_bps_per_side": FIXED_COST_BPS_PER_SIDE,
        "research_only": True,
    }


def evaluate(experiments: list[dict[str, Any]]) -> dict[str, Any]:
    """Evaluate pre-declared chronological experiment rows.

    Each input must contain an already-bounded Ollama response, a price-only
    label, and closed entry/exit prices.  Rows must be supplied chronologically
    and exactly three rows form the declared MVP evaluation set.
    """
    if len(experiments) != EXPERIMENT_SESSIONS:
        raise ValueError(f"M20 requires exactly {EXPERIMENT_SESSIONS} pre-declared sessions")
    decisions = [str(item["decision_at_utc"]) for item in experiments]
    if decisions != sorted(decisions) or len(set(decisions)) != len(decisions):
        raise ValueError("M20 sessions must be unique and chronological")
    rows: list[dict[str, Any]] = []
    for item in experiments:
        entry, exit_ = float(item["entry_close"]), float(item["exit_close"])
        if entry <= 0 or exit_ <= 0:
            raise ValueError("M20 requires positive closed prices")
        response = item["response"]
        ollama_action = action_from_sentiment(response)
        price_action = item["price_only_action"]
        if price_action not in {"BUY", "SELL"}:
            raise ValueError("M20 price-only baseline must be directional")
        realized = "BUY" if exit_ >= entry else "SELL"
        result: dict[str, Any] = {
            "decision_at_utc": item["decision_at_utc"],
            "entry_at_utc": item["entry_at_utc"],
            "exit_at_utc": item["exit_at_utc"],
            "context_bar_count": item["context_bar_count"],
            "model_output_sha256": item["model_output_sha256"],
        }
        for name, action in (("ollama_sentiment", ollama_action), ("price_only_return_2", price_action), ("no_change", "NO_TRADE")):
            result[name] = {
                "action": action,
                "net_return": _net_return(action, entry, exit_),
                "correct_direction": action == realized if action != "NO_TRADE" else None,
            }
        rows.append(result)
    return {
        "marker": "FOREX_M20_EVALUATION_OK",
        "evaluation_version": EVALUATION_VERSION,
        "model": OLLAMA_MODEL,
        "predeclared_controls": {
            "sessions": EXPERIMENT_SESSIONS,
            "chronological_only": True,
            "random_shuffling_used": False,
            "context_bars_per_session": 12,
            "price_only_baseline": "two_closed_bar_return_direction",
            "no_change_baseline": "NO_TRADE",
            "cost_bps_per_side": FIXED_COST_BPS_PER_SIDE,
        },
        "rows": rows,
        "comparison": {name: _metrics(rows, name) for name in ("ollama_sentiment", "price_only_return_2", "no_change")},
        "profitability_claim": False,
        "research_only": True,
        "order_capability": False,
        "live_trading_capability": False,
    }
