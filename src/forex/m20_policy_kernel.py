"""Pure, non-executing representation of the deployed M20.11 policy.

This module intentionally has no MT5, database, environment, filesystem, or
network dependency.  It is for retained-record qualification and deterministic
policy replay; it cannot submit, amend, or close an order.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import math
import re
from typing import Any

KERNEL_VERSION = "forex.m20.11.pure-policy-kernel.v1"
STRATEGY_VERSION = "forex.m20.11.m1-five-strategy-trial.v2"
STRATEGY_IDS = (
    "momentum_breakout", "compression_breakout", "trend_pullback",
    "range_reversion", "session_breakout",
)
STRATEGY_REGIMES = (
    ("COMPRESSION_BREAKOUT", "compression_breakout"),
    ("TREND_PULLBACK", "trend_pullback"),
    ("RANGE_REVERSION", "range_reversion"),
    ("LIQUID_SESSION_BREAKOUT", "session_breakout"),
    ("MOMENTUM_BREAKOUT", "momentum_breakout"),
)
OWNER_MAX_HOLD_SECONDS = {
    "momentum_breakout": 10 * 60,
    "compression_breakout": 8 * 60,
    "trend_pullback": 10 * 60,
    "range_reversion": 6 * 60,
    "session_breakout": 10 * 60,
}
_M20_BASE_SNAPSHOT_BODY_FIELDS = frozenset({
    "observed_at_utc", "captured_at_utc", "bid", "ask", "spread_points",
    "freshness_seconds", "m1_closed_bars", "m5_closed_bars", "safety_gates",
    "market_context", "strategy_assessments",
})
_M20_FINANCING_SNAPSHOT_FIELDS = frozenset({"financing", "holding_review"})
_M20_EXTENDED_SNAPSHOT_BODY_FIELDS = _M20_BASE_SNAPSHOT_BODY_FIELDS | _M20_FINANCING_SNAPSHOT_FIELDS
_M20_CALENDAR_OVERLAY_SNAPSHOT_FIELDS = _M20_EXTENDED_SNAPSHOT_BODY_FIELDS | frozenset({"calendar_overlay"})
_SHA256 = re.compile(r"sha256:[0-9a-f]{64}\Z")


class KernelInputError(ValueError):
    """A retained input cannot support a deterministic policy conclusion."""


def _snapshot_body_sha256(snapshot_body: dict[str, Any]) -> str:
    """Return the deployed canonical digest for an exact M20 snapshot body."""
    encoded = json.dumps(snapshot_body, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def parse_utc(value: Any, label: str) -> datetime:
    if not isinstance(value, str):
        raise KernelInputError(f"{label} must be an ISO-8601 UTC timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise KernelInputError(f"{label} is invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise KernelInputError(f"{label} must be UTC")
    return parsed.astimezone(timezone.utc)


def _finite(value: Any, label: str, *, positive: bool = False) -> float:
    if isinstance(value, bool):
        raise KernelInputError(f"{label} must be numeric")
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise KernelInputError(f"{label} must be numeric") from exc
    if not math.isfinite(result) or (positive and result <= 0):
        raise KernelInputError(f"{label} is invalid")
    return result


def validate_closed_m1_window(*, rows: list[dict[str, Any]], cutoff_utc: str,
                               require_available_at: bool = True) -> list[dict[str, Any]]:
    """Validate a contiguous, closed, point-in-time M1 window.

    ``available_at_utc`` is deliberately mandatory for qualified historical
    replay.  The deployed M20 snapshot format predates this field; callers may
    set ``require_available_at=False`` solely to characterize that retained
    record, whose result remains availability-unqualified.
    """
    cutoff = parse_utc(cutoff_utc, "cutoff_utc")
    if not isinstance(rows, list) or len(rows) < 12:
        raise KernelInputError("at least twelve completed M1 candles are required")
    previous_close: datetime | None = None
    validated: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise KernelInputError(f"M1 row {index} is invalid")
        opened = parse_utc(row.get("opened_at_utc"), f"M1 row {index} opened_at_utc")
        closed = parse_utc(row.get("closed_at_utc"), f"M1 row {index} closed_at_utc")
        if (closed - opened).total_seconds() != 60 or closed > cutoff:
            raise KernelInputError(f"M1 row {index} is not a closed one-minute candle at cutoff")
        if previous_close is not None and opened != previous_close:
            raise KernelInputError(f"M1 row {index} is not contiguous")
        if require_available_at:
            available = parse_utc(row.get("available_at_utc"), f"M1 row {index} available_at_utc")
            if available < closed or available > cutoff:
                raise KernelInputError(f"M1 row {index} availability is outside its closed decision interval")
        ohlc = [_finite(row.get(key), f"M1 row {index} {key}", positive=True)
                for key in ("open", "high", "low", "close")]
        if ohlc[2] > min(ohlc[0], ohlc[3]) or ohlc[1] < max(ohlc[0], ohlc[3]):
            raise KernelInputError(f"M1 row {index} has invalid OHLC")
        previous_close = closed
        validated.append(dict(row))
    return validated


def strategy_assessments(*, m1: list[dict[str, Any]], tick: dict[str, Any],
                         active_action: str = "NO_TRADE") -> list[dict[str, Any]]:
    """Calculate the deployed five fixed M1 hypotheses from one snapshot."""
    point = 0.00001
    spread_points = _finite(tick.get("spread_points"), "spread_points")

    def record(identifier: str, label: str, signal: str, reason: str) -> dict[str, Any]:
        return {"id": identifier, "label": label, "signal": signal,
                "eligible_for_execution": True, "reason": reason}

    if len(m1) < 12:
        unavailable = "Needs twelve completed M1 candles."
        return [
            record("momentum_breakout", "Momentum breakout", active_action, "Closed-candle breakout assessment."),
            record("compression_breakout", "Compression breakout", "NO_TRADE", unavailable),
            record("trend_pullback", "Trend pullback", "NO_TRADE", unavailable),
            record("range_reversion", "Range reversion", "NO_TRADE", unavailable),
            record("session_breakout", "Session breakout", "NO_TRADE", unavailable),
        ]
    setup, previous = m1[-1], m1[-2]
    setup_open = _finite(setup.get("open", previous["close"]), "setup open", positive=True)
    previous_open = _finite(previous.get("open", m1[-3]["close"]), "previous open", positive=True)
    setup_close, previous_close = _finite(setup["close"], "setup close", positive=True), _finite(previous["close"], "previous close", positive=True)
    setup_move, previous_move = setup_close - setup_open, previous_close - previous_open
    direction = "BUY" if setup_move > 0 and previous_move > 0 else "SELL" if setup_move < 0 and previous_move < 0 else "NO_TRADE"
    momentum_points = abs(setup_move + previous_move) / point
    prior_five = m1[-6:-1]
    high = lambda rows: max(_finite(bar.get("high", bar["close"]), "bar high", positive=True) for bar in rows)
    low = lambda rows: min(_finite(bar.get("low", bar["close"]), "bar low", positive=True) for bar in rows)
    prior_high, prior_low = high(prior_five), low(prior_five)
    breakout = "BUY" if direction == "BUY" and setup_close > prior_high and momentum_points > spread_points else "SELL" if direction == "SELL" and setup_close < prior_low and momentum_points > spread_points else "NO_TRADE"
    compression = m1[-8:-3]
    compression_points = (high(compression) - low(compression)) / point
    compression_limit = max(12.0, spread_points * 3.0)
    compression_signal = breakout if compression_points <= compression_limit else "NO_TRADE"
    closes = [_finite(bar["close"], "bar close", positive=True) for bar in m1]
    rising = closes[-7] < closes[-6] < closes[-5] and closes[-4] < closes[-5] and setup_close > previous_close
    falling = closes[-7] > closes[-6] > closes[-5] and closes[-4] > closes[-5] and setup_close < previous_close
    pullback = "BUY" if rising and momentum_points > spread_points else "SELL" if falling and momentum_points > spread_points else "NO_TRADE"
    upper = _finite(setup.get("high", setup["close"]), "setup high", positive=True) >= prior_high and setup_close < setup_open
    lower = _finite(setup.get("low", setup["close"]), "setup low", positive=True) <= prior_low and setup_close > setup_open
    reversion = "SELL" if upper and abs(setup_move) / point > spread_points else "BUY" if lower and abs(setup_move) / point > spread_points else "NO_TRADE"
    hour = parse_utc(tick.get("observed_at_utc"), "observed_at_utc").hour
    liquid, normal_spread = 7 <= hour < 20, spread_points <= 12.0
    session = breakout if liquid and normal_spread else "NO_TRADE"
    return [
        record("momentum_breakout", "Momentum breakout", breakout, "Rule: two aligned candles, range break, and spread check."),
        record("compression_breakout", "Compression breakout", compression_signal, f"Prior five-candle range {compression_points:.1f} pts; limit {compression_limit:.1f} pts."),
        record("trend_pullback", "Trend pullback", pullback, "Trend, pullback, and resumption checks are " + ("aligned." if pullback != "NO_TRADE" else "not aligned.")),
        record("range_reversion", "Range reversion", reversion, "Range-edge rejection check is " + ("present." if reversion != "NO_TRADE" else "not present.")),
        record("session_breakout", "Session breakout", session, f"UTC hour {hour:02d}; liquid-session={liquid}, normal-spread={normal_spread}."),
    ]


def market_selection(*, tick: dict[str, Any], m1: list[dict[str, Any]],
                     assessments: list[dict[str, Any]], safety_gates: dict[str, bool]) -> dict[str, Any]:
    if (not all(safety_gates.values()) or int(_finite(tick.get("freshness_seconds"), "freshness_seconds")) > 30
            or _finite(tick.get("spread_points"), "spread_points") > 12 or len(m1) < 12):
        return {"market_regime": "UNSAFE_OR_UNTRADEABLE", "market_regime_reason": "Freshness, spread, or completed-candle safety gate is not satisfied.", "selected_strategy_id": None, "strategy_rule_version": None, "selection_status": "NO_SELECTION"}
    by_id = {item.get("id"): item for item in assessments}
    if set(by_id) != set(STRATEGY_IDS):
        raise KernelInputError("strategy assessments must contain exactly the deployed strategy IDs")
    for regime, strategy_id in STRATEGY_REGIMES:
        signal = by_id[strategy_id].get("signal")
        if signal in {"BUY", "SELL"}:
            return {"market_regime": regime, "market_regime_reason": f"{by_id[strategy_id]['label']} produced {signal} under deterministic regime precedence.", "selected_strategy_id": strategy_id, "strategy_rule_version": f"forex.m20.11.{strategy_id}.v2", "selection_status": "SELECTED_EXECUTABLE"}
    return {"market_regime": "NO_CLEAR_REGIME", "market_regime_reason": "No fixed M1 strategy produced an eligible market signal.", "selected_strategy_id": None, "strategy_rule_version": None, "selection_status": "NO_SELECTION"}


def normalized_technical_stop(*, action: str, entry: float, technical_stop: float, tick_size: float) -> float | None:
    if action not in {"BUY", "SELL"} or not all(math.isfinite(value) for value in (entry, technical_stop, tick_size)) or min(entry, tick_size) <= 0 or (action == "BUY" and not 0 < technical_stop < entry) or (action == "SELL" and not technical_stop > entry):
        return None
    return (math.floor(technical_stop / tick_size + 1e-9) if action == "BUY" else math.ceil(technical_stop / tick_size - 1e-9)) * tick_size


def planned_stop_loss(*, entry: float, stop: float, risk: dict[str, Any]) -> float:
    financing = risk.get("financing", {})
    distance = abs(entry - stop) + max(0.0, _finite(risk.get("observed_spread", 0), "observed_spread")) * .5
    return distance / _finite(risk["tick_size"], "tick_size", positive=True) * _finite(risk["tick_value_loss"], "tick_value_loss", positive=True) * _finite(risk["volume"], "volume", positive=True) + _finite(financing.get("adverse_financing_aud", 0), "adverse_financing_aud") + _finite(financing.get("commission_allowance_aud", 0), "commission_allowance_aud")


def strategy_trade_plan(*, strategy_id: str | None, signal: str, m1: list[dict[str, Any]], tick: dict[str, Any], session: dict[str, Any], risk: dict[str, Any]) -> tuple[str, float | None, float | None, float | None, float | None, str]:
    if strategy_id not in STRATEGY_IDS or signal not in {"BUY", "SELL"} or len(m1) < 12:
        return "NO_TRADE", None, None, None, None, "No selected actionable M1 strategy."
    if _finite(session["maximum_loss_per_trade_aud"], "maximum_loss_per_trade_aud") <= 0:
        return "NO_TRADE", None, None, None, None, "No remaining Option B loss headroom."
    action = signal
    entry = _finite(tick["ask"] if action == "BUY" else tick["bid"], "entry", positive=True)
    high = lambda rows: max(_finite(row.get("high", row["close"]), "bar high", positive=True) for row in rows)
    low = lambda rows: min(_finite(row.get("low", row["close"]), "bar low", positive=True) for row in rows)
    prior_five, compression = m1[-6:-1], m1[-8:-3]
    if strategy_id == "compression_breakout": technical_stop, reason = (low(compression) if action == "BUY" else high(compression)), "Compression range boundary supplies the technical stop; target is 1.5R."
    elif strategy_id == "trend_pullback": technical_stop, reason = (low(m1[-5:-1]) if action == "BUY" else high(m1[-5:-1])), "Pullback swing boundary supplies the technical stop; target is 1.5R."
    elif strategy_id == "range_reversion": technical_stop, reason = (high(prior_five) if action == "SELL" else low(prior_five)), "Rejected range edge supplies the protective stop; range midpoint is the initial target."
    elif strategy_id == "session_breakout": technical_stop, reason = (low(prior_five) if action == "BUY" else high(prior_five)), "Pre-breakout session boundary supplies the technical stop; target is 1.5R."
    else: technical_stop, reason = (low(prior_five) if action == "BUY" else high(prior_five)), "Prior five-candle range boundary supplies the technical stop; target is 1.5R."
    volume = _finite(risk["volume"], "volume", positive=True)
    stop = normalized_technical_stop(action=action, entry=entry, technical_stop=technical_stop, tick_size=_finite(risk["tick_size"], "tick_size", positive=True))
    if stop is None: return "NO_TRADE", None, None, None, None, "Selected strategy's technical stop is invalid at the current quote."
    if planned_stop_loss(entry=entry, stop=stop, risk=risk) > _finite(session["maximum_loss_per_trade_aud"], "maximum_loss_per_trade_aud"):
        return "NO_TRADE", None, None, None, None, "Minimum volume at the valid technical stop exceeds remaining capital headroom."
    take = (high(prior_five) + low(prior_five)) / 2 if strategy_id == "range_reversion" else entry + (1.5 * abs(entry - stop) if action == "BUY" else -1.5 * abs(entry - stop))
    point = _finite(risk["point"], "point", positive=True)
    take = round(take / point) * point
    if (action == "BUY" and take <= entry) or (action == "SELL" and take >= entry): return "NO_TRADE", None, None, None, None, "Selected strategy's target is not beyond the current executable quote."
    notional = volume * 100000 * entry
    if notional > _finite(session["max_notional_per_trade_usd"], "max_notional_per_trade_usd", positive=True):
        raise KernelInputError("M20 minimum EURUSD volume exceeds the Demo notional cap")
    return action, entry, stop, take, notional, reason


def owner_exit_contract(owner: str) -> dict[str, Any]:
    if owner not in OWNER_MAX_HOLD_SECONDS:
        raise KernelInputError("unknown selected strategy owner")
    return {"maximum_hold_seconds": OWNER_MAX_HOLD_SECONDS[owner], "invalidation": "M1_TWO_OPPOSITE_CLOSED_CANDLES", "broker_protection": "RETAIN_SL_TP"}


def classify_retained_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Classify retained M20 decision data without granting execution authority."""
    if not isinstance(snapshot, dict):
        raise KernelInputError("snapshot is invalid")
    observed_at = parse_utc(snapshot.get("observed_at_utc"), "observed_at_utc")
    # Newer M20 snapshots bind M1 bars to their fixed-read receipt and make a
    # proposal only after the complete capture.  Replay must therefore use
    # that decision cutoff, not the earlier broker tick timestamp.  Older
    # retained snapshots remain characterisable using their observation time.
    decision_value = snapshot.get("decision_at_utc", snapshot.get("observed_at_utc"))
    decision_at = parse_utc(decision_value, "decision_at_utc")
    if decision_at < observed_at:
        raise KernelInputError("decision_at_utc predates observed_at_utc")
    cutoff = decision_at.isoformat().replace("+00:00", "Z")
    rows = snapshot.get("m1_closed_bars")
    if not isinstance(rows, list):
        raise KernelInputError("snapshot M1 bars are absent")
    availability_qualified = all(isinstance(row, dict) and "available_at_utc" in row for row in rows)
    validate_closed_m1_window(rows=rows, cutoff_utc=cutoff, require_available_at=availability_qualified)
    assessments = strategy_assessments(m1=rows, tick=snapshot)
    required_gates = {"fresh_quote", "completed_m1", "normal_spread", "no_existing_position", "demo_lease_active", "news_blackout_inactive", "abnormal_volatility_inactive"}
    captured_gates = snapshot.get("safety_gates")
    gates_qualified = (isinstance(captured_gates, dict) and set(captured_gates) == required_gates
                       and all(isinstance(value, bool) for value in captured_gates.values()))
    gates = captured_gates if gates_qualified else {key: False for key in required_gates}
    selection = market_selection(tick=snapshot, m1=rows, assessments=assessments, safety_gates=gates)
    qualifications = []
    if not availability_qualified:
        qualifications.append("AVAILABILITY")
    if not gates_qualified:
        qualifications.append("SAFETY_GATES")
    return {"kernel_version": KERNEL_VERSION, "strategy_version": STRATEGY_VERSION,
            "observed_at_utc": observed_at.isoformat().replace("+00:00", "Z"),
            "decision_cutoff_utc": cutoff,
            "classification": "CLOCK_AND_GATES_CONSISTENT_PROVENANCE_UNVERIFIED" if not qualifications else "UNQUALIFIED_" + "_AND_".join(qualifications),
            "reason": "M1 clock consistency and the complete captured safety-gate set are valid, but source/provenance qualification is outside this retained-record classifier." if not qualifications else "Retained M20 parity is availability and/or gate unqualified; the result has no point-in-time or execution conclusion.",
            "assessments": assessments, "selection": selection, "execution_authority": False}


def classify_retained_decision(snapshot: dict[str, Any], proposal: dict[str, Any]) -> dict[str, Any]:
    """Classify a retained M20 snapshot with its bound proposal receipt time.

    M20 persists the decision time on the proposal after a complete M1 read.
    This offline adapter requires the proposal to identify and hash-bind the
    same snapshot before supplying that later cutoff to the pure classifier.
    It neither persists a result nor alters the deployed listener.
    """
    if not isinstance(snapshot, dict) or not isinstance(proposal, dict):
        raise KernelInputError("snapshot and proposal must be mappings")
    snapshot_id = snapshot.get("snapshot_id")
    payload_sha256 = snapshot.get("payload_sha256")
    body_fields = frozenset(snapshot) - {"snapshot_id", "payload_sha256"}
    if body_fields not in {_M20_BASE_SNAPSHOT_BODY_FIELDS, _M20_EXTENDED_SNAPSHOT_BODY_FIELDS, _M20_CALENDAR_OVERLAY_SNAPSHOT_FIELDS}:
        raise KernelInputError("retained snapshot body is not an exact deployed M20 schema variant")
    if body_fields in {_M20_EXTENDED_SNAPSHOT_BODY_FIELDS, _M20_CALENDAR_OVERLAY_SNAPSHOT_FIELDS} and not all(
            isinstance(snapshot[field], dict) for field in _M20_FINANCING_SNAPSHOT_FIELDS):
        raise KernelInputError("extended retained snapshot financing fields are invalid")
    if "calendar_overlay" in body_fields:
        try:
            from forex.m1_calendar_decision_overlay import M1CalendarOverlayError, apply_calendar_overlay
            overlay = snapshot["calendar_overlay"]
            if not isinstance(overlay, dict) or overlay != apply_calendar_overlay(
                    candidate=overlay.get("candidate"), gate_observation=overlay.get("gate_observation")):
                raise KernelInputError("retained snapshot calendar overlay is invalid")
        except (M1CalendarOverlayError, TypeError, AttributeError) as exc:
            raise KernelInputError("retained snapshot calendar overlay is invalid") from exc
    if not isinstance(snapshot_id, str) or not snapshot_id:
        raise KernelInputError("snapshot_id is required for proposal binding")
    if not isinstance(payload_sha256, str) or not _SHA256.fullmatch(payload_sha256):
        raise KernelInputError("snapshot payload_sha256 is not a canonical SHA-256 digest")
    snapshot_body = {key: snapshot[key] for key in body_fields}
    if _snapshot_body_sha256(snapshot_body) != payload_sha256:
        raise KernelInputError("snapshot payload_sha256 does not match the retained snapshot body")
    proposal_id = proposal.get("proposal_id")
    if not isinstance(proposal_id, str) or not proposal_id:
        raise KernelInputError("proposal_id is required for proposal binding")
    if "calendar_overlay" in body_fields:
        overlay = snapshot["calendar_overlay"]
        if (overlay["candidate"]["proposal_id"] != proposal_id
                or proposal.get("action") != overlay["final_action"]):
            raise KernelInputError("calendar overlay does not bind the retained proposal action")
    if proposal.get("snapshot_id") != snapshot_id:
        raise KernelInputError("proposal snapshot_id does not bind the retained snapshot")
    if proposal.get("decision_snapshot_sha256") != payload_sha256:
        raise KernelInputError("proposal decision snapshot hash does not bind the retained snapshot")
    decision_at = proposal.get("decision_at_utc")
    if not isinstance(decision_at, str):
        raise KernelInputError("proposal decision_at_utc is required")
    merged = {**snapshot, "decision_at_utc": decision_at}
    classified = classify_retained_snapshot(merged)
    return {**classified, "proposal_id": proposal_id, "proposal_bound": True}
