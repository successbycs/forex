from __future__ import annotations

from datetime import datetime, timedelta, timezone
import importlib.util
import sys
import types

import pytest

from forex import m20_policy_kernel as kernel


def stamp(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def deployed_module(monkeypatch):
    fake_mt5 = types.SimpleNamespace(TIMEFRAME_M1=1, TIMEFRAME_M5=5, TIMEFRAME_H1=60)
    monkeypatch.setitem(sys.modules, "MetaTrader5", fake_mt5)
    spec = importlib.util.spec_from_file_location("m20_kernel_parity_runner", "t480/m20_demo_trading_session.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def bars(*, cutoff: datetime, include_availability: bool = True) -> list[dict]:
    rows = []
    for index in range(12):
        opened = cutoff - timedelta(minutes=12 - index)
        close = 1.10000 + index * .00002
        row = {
            "opened_at_utc": stamp(opened), "closed_at_utc": stamp(opened + timedelta(minutes=1)),
            "open": close - .00001, "high": close + .00003, "low": close - .00003,
            "close": close + .00001, "volume": 10,
        }
        if include_availability:
            row["available_at_utc"] = stamp(cutoff)
        rows.append(row)
    return rows


def tick(cutoff: datetime) -> dict:
    return {"observed_at_utc": stamp(cutoff), "freshness_seconds": 1,
            "spread_points": 2.0, "bid": 1.10020, "ask": 1.10022}


def gates() -> dict:
    return {key: True for key in ("fresh_quote", "completed_m1", "normal_spread", "no_existing_position", "demo_lease_active", "news_blackout_inactive", "abnormal_volatility_inactive")}


def test_strategy_assessments_and_selection_match_deployed_policy(monkeypatch):
    deployed = deployed_module(monkeypatch)
    cutoff = datetime(2026, 9, 11, 9, 0, tzinfo=timezone.utc)
    m1, current_tick = bars(cutoff=cutoff), tick(cutoff)
    assert kernel.strategy_assessments(m1=m1, tick=current_tick) == deployed._strategy_assessments(m1=m1, tick=current_tick)
    assessments = kernel.strategy_assessments(m1=m1, tick=current_tick)
    assert kernel.market_selection(tick=current_tick, m1=m1, assessments=assessments, safety_gates=gates()) == deployed._market_selection(tick=current_tick, m1=m1, assessments=assessments, safety_gates=gates())


@pytest.mark.parametrize("strategy_id", kernel.STRATEGY_IDS)
def test_protected_trade_plan_matches_deployed_policy(monkeypatch, strategy_id):
    deployed = deployed_module(monkeypatch)
    cutoff = datetime(2026, 9, 11, 9, 0, tzinfo=timezone.utc)
    m1, current_tick = bars(cutoff=cutoff), tick(cutoff)
    # The generated window has a viable BUY plan under each owner.
    inputs = dict(strategy_id=strategy_id, signal="BUY", m1=m1, tick=current_tick,
                  session={"maximum_loss_per_trade_aud": 100.0, "max_notional_per_trade_usd": 10_000.0},
                  risk={"volume": .01, "tick_size": .00001, "tick_value_loss": 1.395,
                        "point": .00001, "observed_spread": .00002,
                        "financing": {"adverse_financing_aud": 0.0, "commission_allowance_aud": 0.06}})
    assert kernel.strategy_trade_plan(**inputs) == deployed._strategy_trade_plan(**inputs)


def test_point_in_time_window_rejects_future_availability_and_gaps():
    cutoff = datetime(2026, 9, 11, 9, 0, tzinfo=timezone.utc)
    valid = bars(cutoff=cutoff)
    assert kernel.validate_closed_m1_window(rows=valid, cutoff_utc=stamp(cutoff)) == valid
    future = bars(cutoff=cutoff)
    future[-1]["available_at_utc"] = stamp(cutoff + timedelta(seconds=1))
    with pytest.raises(kernel.KernelInputError, match="availability"):
        kernel.validate_closed_m1_window(rows=future, cutoff_utc=stamp(cutoff))
    before_close = bars(cutoff=cutoff)
    before_close[-1]["available_at_utc"] = before_close[-1]["opened_at_utc"]
    with pytest.raises(kernel.KernelInputError, match="availability"):
        kernel.validate_closed_m1_window(rows=before_close, cutoff_utc=stamp(cutoff))
    gap = bars(cutoff=cutoff)
    gap[7]["opened_at_utc"] = stamp(cutoff - timedelta(minutes=4))
    gap[7]["closed_at_utc"] = stamp(cutoff - timedelta(minutes=3))
    with pytest.raises(kernel.KernelInputError, match="contiguous"):
        kernel.validate_closed_m1_window(rows=gap, cutoff_utc=stamp(cutoff))


def test_retained_snapshot_without_availability_is_characterized_but_not_qualified():
    cutoff = datetime(2026, 9, 11, 9, 0, tzinfo=timezone.utc)
    snapshot = {**tick(cutoff), "m1_closed_bars": bars(cutoff=cutoff, include_availability=False), "safety_gates": gates()}
    result = kernel.classify_retained_snapshot(snapshot)
    assert result["classification"] == "UNQUALIFIED_AVAILABILITY"
    assert result["execution_authority"] is False
    assert len(result["assessments"]) == 5


def test_owner_exit_contract_preserves_broker_protection_and_unknown_is_refused():
    assert kernel.owner_exit_contract("range_reversion") == {
        "maximum_hold_seconds": 360, "invalidation": "M1_TWO_OPPOSITE_CLOSED_CANDLES", "broker_protection": "RETAIN_SL_TP",
    }
    with pytest.raises(kernel.KernelInputError, match="unknown"):
        kernel.owner_exit_contract("not-a-strategy")


def test_retained_snapshot_with_missing_gates_is_not_allowed_to_select():
    cutoff = datetime(2026, 9, 11, 9, 0, tzinfo=timezone.utc)
    snapshot = {**tick(cutoff), "m1_closed_bars": bars(cutoff=cutoff)}
    result = kernel.classify_retained_snapshot(snapshot)
    assert result["classification"] == "UNQUALIFIED_SAFETY_GATES"
    assert result["selection"]["selection_status"] == "NO_SELECTION"


def test_successful_range_reversion_buy_and_sell_match_deployed_policy(monkeypatch):
    deployed = deployed_module(monkeypatch)
    cutoff = datetime(2026, 9, 11, 9, 0, tzinfo=timezone.utc)
    m1 = bars(cutoff=cutoff)
    for row in m1[-6:-1]:
        row.update(open=1.10010, high=1.10070, low=1.09950, close=1.10010)
    risk = {"volume": .01, "tick_size": .00001, "tick_value_loss": 1.395, "point": .00001,
            "observed_spread": .00002, "financing": {"adverse_financing_aud": 0.0, "commission_allowance_aud": 0.06}}
    session = {"maximum_loss_per_trade_aud": 100.0, "max_notional_per_trade_usd": 10_000.0}
    for action, quote in (("BUY", {"ask": 1.10000, "bid": 1.09998}), ("SELL", {"ask": 1.10042, "bid": 1.10040})):
        inputs = dict(strategy_id="range_reversion", signal=action, m1=m1, tick=quote, session=session, risk=risk)
        actual, expected = kernel.strategy_trade_plan(**inputs), deployed._strategy_trade_plan(**inputs)
        assert actual == expected
        assert actual[0] == action
        assert actual[-1] == "Rejected range edge supplies the protective stop; range midpoint is the initial target."


def test_precedence_and_owner_contracts_match_deployed_policy(monkeypatch):
    deployed = deployed_module(monkeypatch)
    cutoff = datetime(2026, 9, 11, 9, 0, tzinfo=timezone.utc)
    assessments = [
        {"id": strategy_id, "label": strategy_id, "signal": "BUY" if strategy_id in {"momentum_breakout", "compression_breakout"} else "NO_TRADE"}
        for strategy_id in kernel.STRATEGY_IDS
    ]
    current_tick, m1 = tick(cutoff), bars(cutoff=cutoff)
    assert kernel.market_selection(tick=current_tick, m1=m1, assessments=assessments, safety_gates=gates()) == deployed._market_selection(tick=current_tick, m1=m1, assessments=assessments, safety_gates=gates())
    for owner in kernel.STRATEGY_IDS:
        seconds, invalidation = deployed._owner_exit_contract(owner)
        assert kernel.owner_exit_contract(owner) == {"maximum_hold_seconds": seconds, "invalidation": invalidation, "broker_protection": "RETAIN_SL_TP"}


def test_consistent_snapshot_still_reports_provenance_unverified():
    cutoff = datetime(2026, 9, 11, 9, 0, tzinfo=timezone.utc)
    snapshot = {**tick(cutoff), "m1_closed_bars": bars(cutoff=cutoff), "safety_gates": gates()}
    result = kernel.classify_retained_snapshot(snapshot)
    assert result["classification"] == "CLOCK_AND_GATES_CONSISTENT_PROVENANCE_UNVERIFIED"
    assert result["execution_authority"] is False
