from datetime import datetime, timedelta, timezone

import pytest

from forex.demo_trading import Candle, DemoSessionLedger, DemoSessionLease, DemoTradingError, MarketSnapshot, propose


NOW = datetime(2026, 9, 3, 1, 0, tzinfo=timezone.utc)


def snapshot(*, server: str = "GOMarketsMU-Demo", m1=(1.1, 1.101), m5=(1.1, 1.101)) -> MarketSnapshot:
    def bars(timeframe: str, values: tuple[float, float], minutes: int) -> tuple[Candle, Candle]:
        return tuple(Candle(timeframe, NOW - timedelta(minutes=minutes * (2 - index)), NOW - timedelta(minutes=minutes * (1 - index)), value) for index, value in enumerate(values))
    return MarketSnapshot(server, "EURUSD", NOW, NOW + timedelta(seconds=2), 1.1000, 1.1002, bars("M1", m1, 1), bars("M5", m5, 5))


def lease() -> DemoSessionLease:
    return DemoSessionLease("demo-session", NOW - timedelta(minutes=1), NOW + timedelta(minutes=59))


def test_m20_proposal_uses_only_closed_m1_and_m5_demo_data():
    result = propose(proposal_id="proposal-1", lease=lease(), snapshot=snapshot())
    assert result.action == "BUY"
    assert result.selected_timeframe == "M5"
    assert result.notional_usd == 10000
    assert result.snapshot_sha256.startswith("sha256:")


def test_m20_refuses_non_demo_or_stale_market_data():
    with pytest.raises(DemoTradingError, match="GOMarketsMU-Demo"):
        snapshot(server="GOMarketsMU-Live")
    with pytest.raises(DemoTradingError, match="stale"):
        MarketSnapshot("GOMarketsMU-Demo", "EURUSD", NOW, NOW + timedelta(seconds=31), 1.1, 1.1002, snapshot().m1_closed_bars, snapshot().m5_closed_bars)


def test_m20_ledger_enforces_one_position_and_idempotency():
    proposal = propose(proposal_id="proposal-1", lease=lease(), snapshot=snapshot())
    ledger = DemoSessionLedger(lease())
    request = ledger.request_execution(proposal, idempotency_key="request-1", now=NOW)
    assert request.action == "BUY"
    with pytest.raises(DemoTradingError, match="already used"):
        ledger.request_execution(proposal, idempotency_key="request-1", now=NOW)
    second = propose(proposal_id="proposal-2", lease=lease(), snapshot=snapshot())
    with pytest.raises(DemoTradingError, match="one-position"):
        ledger.request_execution(second, idempotency_key="request-2", now=NOW)


def test_m20_records_no_trade_when_timeframes_conflict():
    result = propose(proposal_id="proposal-1", lease=lease(), snapshot=snapshot(m1=(1.1, 1.101), m5=(1.101, 1.1)))
    assert result.action == "NO_TRADE"
    assert result.notional_usd is None
