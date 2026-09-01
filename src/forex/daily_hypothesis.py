"""Small deterministic, research-only M15 hypothesis and advisory baseline."""
from __future__ import annotations

from typing import Any


MODEL_VERSION = "eurusd-linear-baseline.v1"
FEATURE_VERSION = "eurusd-h1-return-range.v1"


def features(bars: list[dict[str, Any]]) -> dict[str, float]:
    if len(bars) < 3:
        raise ValueError("at least three historical bars are required")
    closes = [float(item["close"]) for item in bars]
    ranges = [float(item["high"]) - float(item["low"]) for item in bars]
    return {
        "return_2": closes[-1] / closes[-3] - 1.0,
        "mean_range": sum(ranges[-3:]) / 3.0,
    }


def train_baseline(bars: list[dict[str, Any]]) -> dict[str, Any]:
    """Fit a tiny centroid classifier from closed historical bars only.

    Each training example uses bars ``i-2..i`` as features and the *next*
    closed bar direction as its label.  The returned parameters are plain JSON
    and deterministic; there is no online learning or external dependency.
    """
    if len(bars) < 6:
        raise ValueError("at least six closed bars are required for training")
    grouped: dict[str, list[dict[str, float]]] = {"BUY": [], "SELL": []}
    for index in range(2, len(bars) - 1):
        label = "BUY" if float(bars[index + 1]["close"]) >= float(bars[index]["close"]) else "SELL"
        grouped[label].append(features(bars[index - 2:index + 1]))
    if not grouped["BUY"] or not grouped["SELL"]:
        raise ValueError("training data must contain both next-bar directions")
    return {
        "model_version": MODEL_VERSION,
        "feature_version": FEATURE_VERSION,
        "training_examples": sum(map(len, grouped.values())),
        "class_centroids": {
            label: {name: sum(row[name] for row in rows) / len(rows) for name in ("return_2", "mean_range")}
            for label, rows in grouped.items()
        },
    }


def _distance(left: dict[str, float], right: dict[str, float]) -> float:
    return sum((left[name] - right[name]) ** 2 for name in ("return_2", "mean_range"))


def advisory(bars: list[dict[str, Any]], *, model: dict[str, Any] | None = None, event_window: str = "NO_SCHEDULED_EVENT_BLACKOUT") -> dict[str, Any]:
    """Return a reproducible BUY/SELL/NO_TRADE research advisory, never an order."""
    values = features(bars)
    model = model or train_baseline(bars)
    centroids = model["class_centroids"]
    buy_distance, sell_distance = _distance(values, centroids["BUY"]), _distance(values, centroids["SELL"])
    score = max(0, min(100, round(100 * sell_distance / (buy_distance + sell_distance))))
    if event_window == "EVENT_BLACKOUT":
        action, reason = "NO_TRADE", "scheduled-event blackout"
    elif score >= 55:
        action, reason = "BUY", "positive two-bar return"
    elif score <= 45:
        action, reason = "SELL", "negative two-bar return"
    else:
        action, reason = "NO_TRADE", "low-confidence range"
    return {
        "model_version": MODEL_VERSION,
        "feature_version": FEATURE_VERSION,
        "training_examples": model["training_examples"],
        "action": action,
        "advisory_score": score,
        "confidence": score if action == "BUY" else 100 - score if action == "SELL" else 0,
        "conflicting_signals": ["EVENT_BLACKOUT"] if event_window == "EVENT_BLACKOUT" else [],
        "invalidation_conditions": ["new historical input", "event blackout", "outside declared session"],
        "reason": reason,
        "research_only": True,
    }
