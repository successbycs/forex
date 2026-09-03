"""Bounded, Demo-only M20 decision and execution-session contracts.

This module is intentionally broker-independent.  The MT5 adapter may submit
only an ``ExecutionRequest`` produced here after it has captured and persisted
the matching market snapshot and proposal.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import hashlib
import json
from typing import Literal


Action = Literal["BUY", "SELL", "NO_TRADE"]


class DemoTradingError(ValueError):
    """A Demo-only session, market snapshot, or execution request is unsafe."""


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise DemoTradingError("timestamps must include a timezone")
    return value.astimezone(timezone.utc)


@dataclass(frozen=True)
class Candle:
    timeframe: Literal["M1", "M5"]
    opened_at_utc: datetime
    closed_at_utc: datetime
    close: float

    def __post_init__(self) -> None:
        if self.close <= 0 or _utc(self.closed_at_utc) <= _utc(self.opened_at_utc):
            raise DemoTradingError("a candle must have a positive close and a closed interval")


@dataclass(frozen=True)
class MarketSnapshot:
    server: str
    symbol: str
    observed_at_utc: datetime
    captured_at_utc: datetime
    bid: float
    ask: float
    m1_closed_bars: tuple[Candle, ...]
    m5_closed_bars: tuple[Candle, ...]

    def __post_init__(self) -> None:
        observed = _utc(self.observed_at_utc)
        captured = _utc(self.captured_at_utc)
        if self.server != "GOMarketsMU-Demo" or self.symbol != "EURUSD":
            raise DemoTradingError("M20 permits only GOMarketsMU-Demo EURUSD snapshots")
        if self.bid <= 0 or self.ask < self.bid:
            raise DemoTradingError("bid/ask values are invalid")
        if captured < observed or captured - observed > timedelta(seconds=30):
            raise DemoTradingError("market snapshot is stale")
        for timeframe, bars in (("M1", self.m1_closed_bars), ("M5", self.m5_closed_bars)):
            if len(bars) < 2 or any(bar.timeframe != timeframe for bar in bars):
                raise DemoTradingError(f"snapshot requires at least two closed {timeframe} candles")
            if any(_utc(bar.closed_at_utc) > observed for bar in bars):
                raise DemoTradingError("an unclosed or future candle was supplied")

    @property
    def payload_sha256(self) -> str:
        payload = {
            "server": self.server,
            "symbol": self.symbol,
            "observed_at_utc": _utc(self.observed_at_utc).isoformat(),
            "captured_at_utc": _utc(self.captured_at_utc).isoformat(),
            "bid": self.bid,
            "ask": self.ask,
            "m1_closed_bars": [(bar.opened_at_utc.isoformat(), bar.closed_at_utc.isoformat(), bar.close) for bar in self.m1_closed_bars],
            "m5_closed_bars": [(bar.opened_at_utc.isoformat(), bar.closed_at_utc.isoformat(), bar.close) for bar in self.m5_closed_bars],
        }
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        return "sha256:" + hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True)
class DemoSessionLease:
    session_id: str
    starts_at_utc: datetime
    expires_at_utc: datetime
    max_trades: int = 10
    max_notional_per_trade_usd: int = 10000
    max_cumulative_notional_usd: int = 100000
    max_open_positions: int = 1

    def __post_init__(self) -> None:
        if not self.session_id.strip() or _utc(self.expires_at_utc) <= _utc(self.starts_at_utc):
            raise DemoTradingError("a Demo session needs an identifier and positive duration")
        if _utc(self.expires_at_utc) - _utc(self.starts_at_utc) > timedelta(minutes=60):
            raise DemoTradingError("a Demo session cannot exceed 60 minutes")
        if not 1 <= self.max_trades <= 10 or self.max_open_positions != 1:
            raise DemoTradingError("M20 permits at most 10 trades and one open position")
        if not 0 < self.max_notional_per_trade_usd <= 10000 or not 0 < self.max_cumulative_notional_usd <= 100000:
            raise DemoTradingError("M20 notional limits are invalid")


@dataclass(frozen=True)
class TradeProposal:
    proposal_id: str
    session_id: str
    action: Action
    selected_timeframe: Literal["M1", "M5"]
    decision_at_utc: datetime
    expires_at_utc: datetime
    entry: float | None
    stop_loss: float | None
    take_profit: float | None
    notional_usd: int | None
    confidence: int
    rationale: str
    snapshot_sha256: str


@dataclass(frozen=True)
class ExecutionRequest:
    proposal_id: str
    session_id: str
    idempotency_key: str
    action: Literal["BUY", "SELL"]
    notional_usd: int


def propose(*, proposal_id: str, lease: DemoSessionLease, snapshot: MarketSnapshot) -> TradeProposal:
    """Create a deterministic M1/M5 proposal from data available at decision time."""
    decision_at = _utc(snapshot.observed_at_utc)
    if not _utc(lease.starts_at_utc) <= decision_at <= _utc(lease.expires_at_utc):
        raise DemoTradingError("the session is inactive at the decision time")
    m1_up = snapshot.m1_closed_bars[-1].close > snapshot.m1_closed_bars[-2].close
    m5_up = snapshot.m5_closed_bars[-1].close > snapshot.m5_closed_bars[-2].close
    m1_down = snapshot.m1_closed_bars[-1].close < snapshot.m1_closed_bars[-2].close
    m5_down = snapshot.m5_closed_bars[-1].close < snapshot.m5_closed_bars[-2].close
    if m1_up and m5_up:
        action: Action = "BUY"
        entry, stop, target = snapshot.ask, snapshot.bid * 0.9995, snapshot.ask * 1.001
        rationale = "M1 and M5 closed-candle momentum agree upward."
    elif m1_down and m5_down:
        action = "SELL"
        entry, stop, target = snapshot.bid, snapshot.ask * 1.0005, snapshot.bid * 0.999
        rationale = "M1 and M5 closed-candle momentum agree downward."
    else:
        action = "NO_TRADE"
        entry = stop = target = None
        rationale = "M1 and M5 closed-candle momentum conflict; abstaining."
    return TradeProposal(
        proposal_id=proposal_id,
        session_id=lease.session_id,
        action=action,
        selected_timeframe="M5",
        decision_at_utc=decision_at,
        expires_at_utc=min(_utc(lease.expires_at_utc), decision_at + timedelta(minutes=5)),
        entry=entry,
        stop_loss=stop,
        take_profit=target,
        notional_usd=lease.max_notional_per_trade_usd if action != "NO_TRADE" else None,
        confidence=60 if action != "NO_TRADE" else 100,
        rationale=rationale,
        snapshot_sha256=snapshot.payload_sha256,
    )


@dataclass
class DemoSessionLedger:
    lease: DemoSessionLease
    claimed_proposals: set[str] = field(default_factory=set)
    idempotency_keys: set[str] = field(default_factory=set)
    cumulative_notional_usd: int = 0
    open_positions: int = 0

    def request_execution(self, proposal: TradeProposal, *, idempotency_key: str, now: datetime) -> ExecutionRequest:
        now_utc = _utc(now)
        if proposal.session_id != self.lease.session_id or proposal.action == "NO_TRADE":
            raise DemoTradingError("only an actionable proposal from this session may execute")
        if not _utc(self.lease.starts_at_utc) <= now_utc <= _utc(self.lease.expires_at_utc) or now_utc > _utc(proposal.expires_at_utc):
            raise DemoTradingError("the session or proposal has expired")
        if proposal.proposal_id in self.claimed_proposals or idempotency_key in self.idempotency_keys:
            raise DemoTradingError("proposal or idempotency key was already used")
        if self.open_positions >= self.lease.max_open_positions:
            raise DemoTradingError("the one-position limit is reached")
        notional = proposal.notional_usd
        if notional is None or notional > self.lease.max_notional_per_trade_usd or self.cumulative_notional_usd + notional > self.lease.max_cumulative_notional_usd:
            raise DemoTradingError("Demo session notional limit would be exceeded")
        self.claimed_proposals.add(proposal.proposal_id)
        self.idempotency_keys.add(idempotency_key)
        self.cumulative_notional_usd += notional
        self.open_positions += 1
        return ExecutionRequest(proposal.proposal_id, self.lease.session_id, idempotency_key, proposal.action, notional)
