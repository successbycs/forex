"""Pure proposed ATR protection for the disabled H_SLOW research stream.

This is an engineering calculation, not a broker protection instruction.  It
uses only a point-in-time-qualified EUR/USD D1 snapshot and exposes no routing,
account, configuration, persistence, or order surface.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal, DecimalException, InvalidOperation, ROUND_CEILING, ROUND_FLOOR, localcontext
import hashlib
import json
from typing import Any, Mapping

from .h_slow_data import HSlowDataInputError, h_slow_daily_input


PROTECTION_SCHEMA_VERSION = "forex.h-slow.protection.v1"
_RULE = {"rule_id": "hslow-atr20x3-v1", "period": 20, "multiplier": 3}
_MAX_SIGNIFICANT_DIGITS = 18


class HSlowProtectionError(ValueError):
    """D1 data or a proposed ATR rule cannot support a technical stop."""


def _utc(value: Any, label: str) -> datetime:
    if not isinstance(value, str):
        raise HSlowProtectionError(f"{label} must be a UTC timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise HSlowProtectionError(f"{label} is invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise HSlowProtectionError(f"{label} must be UTC")
    return parsed.astimezone(timezone.utc)


def _decimal(value: Any, label: str) -> Decimal:
    if isinstance(value, bool):
        raise HSlowProtectionError(f"{label} must be a finite positive price")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise HSlowProtectionError(f"{label} must be a finite positive price") from exc
    if not number.is_finite() or number <= 0:
        raise HSlowProtectionError(f"{label} must be a finite positive price")
    digits = len(number.as_tuple().digits)
    if digits > _MAX_SIGNIFICANT_DIGITS:
        raise HSlowProtectionError(f"{label} exceeds supported decimal precision")
    if not Decimal("1e-12") <= number <= Decimal("1e12"):
        raise HSlowProtectionError(f"{label} exceeds supported price magnitude")
    return number


def _stamp(value: Decimal) -> str:
    return format(value.normalize(), "f")


def _conservative_precision(value: Decimal, *, upward: bool) -> Decimal:
    """Bound arithmetic output without reducing the protective distance."""
    # Fifteen digits also round-trip through the sizing API's JSON numbers.
    exponent = value.adjusted() - 14
    return value.quantize(Decimal(1).scaleb(exponent), rounding=ROUND_CEILING if upward else ROUND_FLOOR)


def _weekday_before(decision: datetime) -> datetime.date:
    candidate = (decision - timedelta(days=1)).date()
    while candidate.weekday() >= 5:
        candidate -= timedelta(days=1)
    return candidate


def _validated_rule(rule: Mapping[str, Any]) -> dict[str, Any]:
    if (not isinstance(rule, Mapping) or set(rule) != set(_RULE)
            or rule.get("rule_id") != _RULE["rule_id"]
            or type(rule.get("period")) is not int or rule["period"] != _RULE["period"]
            or type(rule.get("multiplier")) is not int or rule["multiplier"] != _RULE["multiplier"]):
        raise HSlowProtectionError("rule must equal the fixed hslow-atr20x3-v1 definition")
    return dict(_RULE)


def _last_twenty_one_ohlc(snapshot: Mapping[str, Any], *, decision_at_utc: str) -> tuple[list[tuple[datetime, Decimal, Decimal, Decimal]], dict[str, Any]]:
    """Reuse D1 point-in-time qualification then recover matching OHLC rows."""
    try:
        qualified = h_slow_daily_input(dict(snapshot), decision_at_utc=decision_at_utc)
    except HSlowDataInputError as exc:
        raise HSlowProtectionError(f"invalid H_SLOW D1 input: {exc}") from exc
    rows: list[tuple[datetime, Decimal, Decimal, Decimal]] = []
    source_rows = snapshot.get("price_bars")
    if not isinstance(source_rows, list) or len(source_rows) != len(qualified["daily_bars"]):
        raise HSlowProtectionError("snapshot OHLC rows do not match qualified D1 input")
    for daily, source in zip(qualified["daily_bars"], source_rows, strict=True):
        if not isinstance(source, dict) or _utc(source.get("time_utc"), "snapshot D1 time_utc") != _utc(daily["opened_at_utc"], "D1 opened_at_utc"):
            raise HSlowProtectionError("qualified D1 bar is absent from snapshot OHLC data")
        opened = _utc(daily["opened_at_utc"], "D1 opened_at_utc")
        high, low = _decimal(source.get("high"), "D1 high"), _decimal(source.get("low"), "D1 low")
        if not low <= _decimal(source.get("open"), "D1 open") <= high or not low <= _decimal(source.get("close"), "D1 close") <= high:
            raise HSlowProtectionError("D1 OHLC values are inconsistent")
        rows.append((opened, _decimal(source.get("high"), "D1 high"),
                     _decimal(source.get("low"), "D1 low"), _decimal(source.get("close"), "D1 close")))
    if len(rows) < 21:
        raise HSlowProtectionError("at least 21 qualified D1 OHLC bars are required")
    rows = rows[-21:]
    decision = _utc(decision_at_utc, "decision_at_utc")
    if rows[-1][0].date() != _weekday_before(decision):
        raise HSlowProtectionError("latest completed weekday preceding decision is missing")
    for previous, current in zip(rows, rows[1:]):
        if previous[0].weekday() >= 5 or current[0].weekday() >= 5:
            raise HSlowProtectionError("D1 ATR input must contain weekdays only")
        expected = previous[0] + timedelta(days=3 if previous[0].weekday() == 4 else 1)
        if current[0].date() != expected.date():
            raise HSlowProtectionError("qualified D1 ATR input has a weekday gap")
    return rows, qualified


def derive_h_slow_stop(snapshot: Mapping[str, Any], *, decision_at_utc: str, direction: str,
                        entry_price: Any, rule: Mapping[str, Any]) -> dict[str, Any]:
    """Derive a proposed 20-day ATR × 3 stop from qualified daily OHLC data."""
    try:
        with localcontext() as context:
            context.prec = 128
            return _derive(snapshot, decision_at_utc=decision_at_utc, direction=direction,
                           entry_price=entry_price, rule=rule)
    except DecimalException as exc:
        raise HSlowProtectionError("unsupported protective-stop decimal calculation") from exc


def _derive(snapshot, *, decision_at_utc, direction, entry_price, rule):
    checked_rule = _validated_rule(rule)
    if direction not in {"BUY", "SELL"}:
        raise HSlowProtectionError("direction must be BUY or SELL")
    entry = _decimal(entry_price, "entry_price")
    rows, qualified = _last_twenty_one_ohlc(snapshot, decision_at_utc=decision_at_utc)
    with localcontext() as context:
        context.prec = 128
        true_ranges: list[Decimal] = []
        for index in range(1, len(rows)):
            _, high, low, _ = rows[index]
            _, _, _, previous_close = rows[index - 1]
            if high < low:
                raise HSlowProtectionError("D1 high must not be below low")
            true_ranges.append(max(high - low, abs(high - previous_close), abs(low - previous_close)))
        atr = sum(true_ranges, Decimal("0")) / Decimal(checked_rule["period"])
        if atr <= 0:
            raise HSlowProtectionError("ATR must be positive")
        raw_stop = entry - Decimal(checked_rule["multiplier"]) * atr if direction == "BUY" else entry + Decimal(checked_rule["multiplier"]) * atr
    stop = _conservative_precision(raw_stop, upward=direction == "SELL")
    if stop <= 0 or not stop.is_finite():
        raise HSlowProtectionError("derived technical stop is not positive")
    binding = {"daily_input_sha256": qualified["input_sha256"], "direction": direction,
               "entry_price": _stamp(entry), "rule": checked_rule,
               "schema_version": PROTECTION_SCHEMA_VERSION}
    return {
        "schema_version": PROTECTION_SCHEMA_VERSION,
        "technical_stop_price": _stamp(stop),
        "raw_technical_stop_price": _stamp(raw_stop),
        "atr": _stamp(atr),
        "direction": direction,
        "entry_price": _stamp(entry),
        "snapshot_artifact_sha256": qualified["snapshot_artifact_sha256"],
        "input_sha256": "sha256:" + hashlib.sha256(json.dumps(binding, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
        "rule": checked_rule,
        "execution_authority": False,
    }
