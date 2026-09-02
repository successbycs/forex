"""Deterministic, chronological M16 historical evaluation.

This module is deliberately research-only.  It evaluates closed EUR/USD H1
history with frozen, chronological model windows; it neither connects to a
broker nor produces an executable trade instruction.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime
from statistics import mean
from typing import Any

from .daily_hypothesis import FEATURE_VERSION, MODEL_VERSION, advisory, features, train_baseline


EVALUATION_VERSION = "eurusd-walk-forward.v1"
DECISION_HOUR_UTC = 8
MANDATORY_EXIT_HOUR_UTC = 20
FIXED_COST_BPS = 2.0


def _time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("historical bar timestamp must include a timezone")
    return parsed


def _ordered_bars(bars: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if len(bars) < 12:
        raise ValueError("at least twelve closed bars are required")
    ordered = sorted(bars, key=lambda row: _time(str(row["time_utc"])))
    if [row["time_utc"] for row in ordered] != [row["time_utc"] for row in bars]:
        raise ValueError("bars must be supplied in strict chronological order")
    times = [_time(str(row["time_utc"])) for row in ordered]
    if len(set(times)) != len(times):
        raise ValueError("duplicate historical bar timestamps are not allowed")
    for row, timestamp in zip(ordered, times):
        available = _time(str(row["available_at_utc"]))
        if available < timestamp:
            raise ValueError("bar availability cannot precede its closed timestamp")
    return ordered


def _sessions(bars: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_day: dict[str, dict[int, tuple[int, dict[str, Any]]]] = {}
    for index, row in enumerate(bars):
        stamp = _time(str(row["time_utc"]))
        by_day.setdefault(stamp.date().isoformat(), {})[stamp.hour] = (index, row)
    sessions = []
    for day in sorted(by_day):
        slots = by_day[day]
        if DECISION_HOUR_UTC not in slots or MANDATORY_EXIT_HOUR_UTC not in slots:
            continue
        entry_index, entry = slots[DECISION_HOUR_UTC]
        _, exit_bar = slots[MANDATORY_EXIT_HOUR_UTC]
        decision = _time(str(entry["time_utc"]))
        if entry_index < 6 or _time(str(entry["available_at_utc"])) > decision or _time(str(exit_bar["available_at_utc"])) > _time(str(exit_bar["time_utc"])):
            continue
        sessions.append({"day_utc": day, "entry_index": entry_index, "entry": entry, "exit": exit_bar})
    if len(sessions) < 6:
        raise ValueError("historical data does not contain six complete UTC 08:00-to-20:00 sessions")
    return sessions


def _action_return(action: str, entry: float, exit_: float, cost_bps: float) -> float:
    if action == "NO_TRADE":
        return 0.0
    direction = 1.0 if action == "BUY" else -1.0
    return direction * (exit_ / entry - 1.0) - (2.0 * cost_bps / 10_000.0)


def _strategy_metrics(rows: list[dict[str, Any]], strategy: str) -> dict[str, Any]:
    selected = [row for row in rows if row[strategy]["action"] != "NO_TRADE"]
    returns = [row[strategy]["net_return"] for row in selected]
    correct = [row for row in selected if row[strategy]["correct_direction"]]
    return {
        "sessions": len(rows),
        "actionable_sessions": len(selected),
        "directional_accuracy": round(len(correct) / len(selected), 6) if selected else None,
        "mean_net_return": round(mean(returns), 10) if returns else 0.0,
        "total_net_return": round(sum(returns), 10),
        "cost_assumption_bps_per_side": FIXED_COST_BPS,
        "research_only": True,
    }


def _context_coverage(contexts: dict[str, list[dict[str, Any]]], sessions: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    start, end = sessions[0]["entry"]["time_utc"], sessions[-1]["exit"]["time_utc"]
    result: dict[str, dict[str, Any]] = {}
    for kind in ("macro", "calendar", "sentiment"):
        rows = contexts.get(kind, [])
        visible = [row for row in rows if row.get("available_at_utc") and row.get("time_utc") and row["available_at_utc"] <= end and row["time_utc"] <= end]
        aligned = [row for row in visible if start <= row["time_utc"] <= end]
        result[kind] = {
            "retained_records": len(rows),
            "visible_before_last_exit": len(visible),
            "aligned_records": len(aligned),
            "status": "EVALUATED_AS_UNAVAILABLE" if not aligned else "EXPERIMENTAL_CONTEXT_COVERAGE_ONLY",
            "used_as_model_feature": False,
        }
    return result


def evaluate_walk_forward(bars: list[dict[str, Any]], *, contexts: dict[str, list[dict[str, Any]]] | None = None) -> dict[str, Any]:
    """Evaluate frozen M15 models against fixed baselines without shuffling.

    Three sequential holdout windows are derived from complete UTC sessions.
    Each window trains once on bars preceding that window and then remains
    frozen throughout its test sessions.  Macro, calendar and sentiment rows
    are measured for available aligned coverage only; none become a model
    feature until a later, separately-qualified milestone.
    """
    bars = _ordered_bars(bars)
    sessions = _sessions(bars)
    test_size = max(1, len(sessions) // 6)
    starts = [len(sessions) // 2, len(sessions) // 2 + test_size, len(sessions) // 2 + 2 * test_size]
    rows: list[dict[str, Any]] = []
    windows: list[dict[str, Any]] = []
    for number, start in enumerate(starts, start=1):
        test_sessions = sessions[start:start + test_size]
        if not test_sessions:
            continue
        train_until = test_sessions[0]["entry_index"]
        decision = _time(str(test_sessions[0]["entry"]["time_utc"]))
        training = [bar for bar in bars[:train_until] if _time(str(bar["available_at_utc"])) <= decision]
        model = train_baseline(training)
        window_rows = []
        for session in test_sessions:
            entry, exit_ = session["entry"], session["exit"]
            decision = _time(str(entry["time_utc"]))
            visible = [bar for bar in bars[:session["entry_index"] + 1] if _time(str(bar["available_at_utc"])) <= decision]
            if len(visible) < 3:
                raise ValueError("insufficient point-in-time bars for a historical decision")
            sample = visible[-3:]
            ml_action = advisory(sample, model=model)["action"]
            deterministic = "BUY" if features(sample)["return_2"] >= 0 else "SELL"
            realized_direction = "BUY" if float(exit_["close"]) >= float(entry["close"]) else "SELL"
            item = {
                "day_utc": session["day_utc"],
                "entry_at_utc": entry["time_utc"], "exit_at_utc": exit_["time_utc"],
                "m15_ml": {"action": ml_action},
                "deterministic_return_2": {"action": deterministic},
                "no_change": {"action": "NO_TRADE"},
            }
            for strategy in ("m15_ml", "deterministic_return_2", "no_change"):
                action = item[strategy]["action"]
                item[strategy]["net_return"] = _action_return(action, float(entry["close"]), float(exit_["close"]), FIXED_COST_BPS)
                item[strategy]["correct_direction"] = action == realized_direction if action != "NO_TRADE" else None
            rows.append(item); window_rows.append(item)
        windows.append({"window": number, "train_bars": train_until, "test_sessions": len(window_rows), "first_test_day": window_rows[0]["day_utc"], "last_test_day": window_rows[-1]["day_utc"], "m15_ml": _strategy_metrics(window_rows, "m15_ml"), "deterministic_return_2": _strategy_metrics(window_rows, "deterministic_return_2"), "no_change": _strategy_metrics(window_rows, "no_change")})
    if len(windows) != 3:
        raise ValueError("three chronological test windows could not be created")
    model = train_baseline(bars[:sessions[starts[0]]["entry_index"]])
    contribution = {
        name: {
            "centroid_separation": abs(model["class_centroids"]["BUY"][name] - model["class_centroids"]["SELL"][name]),
            "mean_absolute_value": mean(abs(features(bars[session["entry_index"] - 2:session["entry_index"] + 1])[name]) for session in sessions),
        }
        for name in ("return_2", "mean_range")
    }
    return {
        "marker": "FOREX_M16_WALK_FORWARD_OK",
        "evaluation_version": EVALUATION_VERSION,
        "model_version": MODEL_VERSION,
        "feature_version": FEATURE_VERSION,
        "session_contract": {"decision_hour_utc": DECISION_HOUR_UTC, "mandatory_exit_hour_utc": MANDATORY_EXIT_HOUR_UTC, "cost_bps_per_side": FIXED_COST_BPS},
        "bars": len(bars), "sessions_available": len(sessions), "windows": windows,
        "overall": {name: _strategy_metrics(rows, name) for name in ("m15_ml", "deterministic_return_2", "no_change")},
        "feature_contribution_descriptive_only": contribution,
        "context_coverage": _context_coverage(contexts or {}, sessions),
        "chronological_only": True, "random_shuffling_used": False, "live_fitting_used": False,
        "profitability_claim": False, "research_only": True,
    }
