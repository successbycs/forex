from __future__ import annotations

from datetime import datetime, timedelta, timezone
import copy

import pytest

from forex.data_contracts import build_dataset_snapshot
from forex.h_slow_protection import HSlowProtectionError, derive_h_slow_stop


DECISION = "2026-09-01T12:00:00Z"
RULE = {"rule_id": "hslow-atr20x3-v1", "period": 20, "multiplier": 3}


def snapshot() -> dict:
    source = {"contract_version": "forex.historical-data.v1", "source_id": "fixture", "owner": "test", "license": "test", "cost_model": "none", "api_version": "1", "endpoint_allowlist": [], "rate_limit": "none", "retention_rule": "test", "historical_depth": "test", "revision_support": "none", "timezone_policy": "UTC", "outage_policy": "fail", "approval_status": "DEMO_ONLY", "secrets_reference": "NONE", "provenance_note": "test"}
    observation = {"contract_version": "forex.historical-data.v1", "observation_id": "obs", "source_id": "fixture", "source_revision": "1", "observed_at_utc": "2026-07-01T00:00:00Z", "available_at_utc": "2026-07-01T00:00:00Z", "retrieved_at_utc": "2026-07-01T00:00:00Z", "timezone": "UTC", "payload_sha256": "sha256:test", "payload_path": "test", "redacted": False}
    dates, current = [], datetime(2026, 7, 31, tzinfo=timezone.utc)
    while current <= datetime(2026, 8, 31, tzinfo=timezone.utc):
        if current.weekday() < 5:
            dates.append(current)
        current += timedelta(days=1)
    bars = []
    for index, opened in enumerate(dates):
        close = round(1.10 + index * .001, 5)
        bars.append({"time_utc": opened.isoformat().replace("+00:00", "Z"), "open": close, "high": round(close + .01, 5), "low": round(close - .01, 5), "close": round(close + .005, 5), "volume": 1, "raw_observation_id": "obs", "available_at_utc": (opened + timedelta(days=1)).isoformat().replace("+00:00", "Z")})
    return build_dataset_snapshot(snapshot_id="hslow-protection", instrument="EUR/USD", timeframe="D1", decision_cutoff_utc=DECISION, created_at_utc=DECISION, source_registry=[source], raw_observations=[observation], price_bars=bars)


def rebuild(value: dict) -> dict:
    return build_dataset_snapshot(snapshot_id=value["snapshot_id"], instrument=value["instrument"], timeframe=value["timeframe"], decision_cutoff_utc=value["decision_cutoff_utc"], created_at_utc=value["created_at_utc"], source_registry=value["source_registry"], raw_observations=value["raw_observations"], price_bars=value["price_bars"])


def test_derives_deterministic_atr20_times_three_buy_and_sell_stops():
    first = derive_h_slow_stop(snapshot(), decision_at_utc=DECISION, direction="BUY", entry_price="1.2", rule=RULE)
    second = derive_h_slow_stop(snapshot(), decision_at_utc=DECISION, direction="SELL", entry_price="1.2", rule=RULE)
    assert first["atr"] == "0.02"
    assert first["technical_stop_price"] == "1.14"
    assert second["technical_stop_price"] == "1.26"
    assert first["execution_authority"] is False
    assert first["input_sha256"].startswith("sha256:")


def test_rejects_missing_latest_weekday_and_internal_weekday_gap():
    stale = snapshot(); stale["price_bars"].pop()
    with pytest.raises(HSlowProtectionError, match="latest completed weekday"):
        derive_h_slow_stop(rebuild(stale), decision_at_utc=DECISION, direction="BUY", entry_price="1.2", rule=RULE)
    gap = snapshot(); del gap["price_bars"][12]
    with pytest.raises(HSlowProtectionError, match="weekday gap"):
        derive_h_slow_stop(rebuild(gap), decision_at_utc=DECISION, direction="BUY", entry_price="1.2", rule=RULE)


def test_rejects_lookahead_tamper_and_malformed_price():
    tampered = snapshot(); tampered["price_bars"][-1]["available_at_utc"] = "2026-09-02T00:00:00Z"
    with pytest.raises(HSlowProtectionError, match="invalid H_SLOW"):
        derive_h_slow_stop(rebuild(tampered), decision_at_utc=DECISION, direction="BUY", entry_price="1.2", rule=RULE)
    malformed = snapshot(); malformed["price_bars"][-1]["high"] = float("nan")
    with pytest.raises(HSlowProtectionError, match="finite positive"):
        derive_h_slow_stop(rebuild(malformed), decision_at_utc=DECISION, direction="BUY", entry_price="1.2", rule=RULE)


@pytest.mark.parametrize("rule", [{}, {"rule_id": "hslow-atr20x3-v1", "period": True, "multiplier": 3}, {"rule_id": "other", "period": 20, "multiplier": 3}, {"rule_id": "hslow-atr20x3-v1", "period": 20, "multiplier": 3.0}])
def test_rejects_any_rule_other_than_exact_proposed_definition(rule):
    with pytest.raises(HSlowProtectionError, match="rule"):
        derive_h_slow_stop(snapshot(), decision_at_utc=DECISION, direction="BUY", entry_price="1.2", rule=rule)


def test_rejects_wrong_direction_and_nonfinite_entry():
    with pytest.raises(HSlowProtectionError, match="direction"):
        derive_h_slow_stop(snapshot(), decision_at_utc=DECISION, direction="HOLD", entry_price="1.2", rule=RULE)
    with pytest.raises(HSlowProtectionError, match="finite"):
        derive_h_slow_stop(snapshot(), decision_at_utc=DECISION, direction="BUY", entry_price=float("inf"), rule=RULE)


def test_context_independence_and_full_input_binding():
    from decimal import localcontext
    expected = derive_h_slow_stop(snapshot(), decision_at_utc=DECISION, direction="BUY", entry_price="1.23456789012345678", rule=RULE)
    with localcontext() as context:
        context.prec = 6
        actual = derive_h_slow_stop(snapshot(), decision_at_utc=DECISION, direction="BUY", entry_price="1.23456789012345678", rule=RULE)
    assert actual == expected
    changed = derive_h_slow_stop(snapshot(), decision_at_utc=DECISION, direction="SELL", entry_price="1.23456789012345678", rule=RULE)
    assert changed["input_sha256"] != expected["input_sha256"]


@pytest.mark.parametrize("direction", ["BUY", "SELL"])
def test_precision_rounding_preserves_raw_stop_and_never_reduces_distance(direction):
    from decimal import Decimal
    result = derive_h_slow_stop(snapshot(), decision_at_utc=DECISION, direction=direction, entry_price="1.23456789012345678", rule=RULE)
    stop, raw = Decimal(result["technical_stop_price"]), Decimal(result["raw_technical_stop_price"])
    assert stop <= raw if direction == "BUY" else stop >= raw
    assert Decimal(str(float(stop))) == stop
    assert raw == Decimal("1.23456789012345678") + (Decimal("-.06") if direction == "BUY" else Decimal(".06"))


@pytest.mark.parametrize("entry", ["1e1000000", "1e-1000000", "1.1234567890123456789", True])
def test_rejects_unsupported_numeric_inputs(entry):
    with pytest.raises(HSlowProtectionError):
        derive_h_slow_stop(snapshot(), decision_at_utc=DECISION, direction="BUY", entry_price=entry, rule=RULE)
