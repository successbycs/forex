"""Fixed M20 Demo-only EUR/USD assessment, execution, and audit loop.

The runner accepts only the configured terminal path and fixed local session
lease supplied by the T480 adapter.  It is not a general MetaTrader interface:
callers cannot choose a server, symbol, account, timeframe, shell command, or
order parameters.  Any actionable assessment is persisted before reservation
and submission, then reconciled through the co-located PostgreSQL audit bridge.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from types import SimpleNamespace
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5
import math

import MetaTrader5 as mt5


SERVER = "GOMarketsMU-Demo"
SYMBOL = "EURUSD"
MAX_TICK_AGE_SECONDS = 30
CLOSED_BAR_COUNT = 64
SESSION_SCHEMA_VERSION = "forex.m20.demo-session-lease.v1"
SESSION_AUDIT_REQUIREMENTS = {
    "postgres_audit_schema": "READY",
    "proposal_persistence": "READY",
    "idempotency_store": "READY",
}
TIMEFRAMES = (
    ("M1", mt5.TIMEFRAME_M1, 60),
)
STRATEGY_VERSION = "forex.m20.m1-live-listener.v1"
OPERATOR_LABEL = "codex-m20-demo"
EXECUTOR_MAGIC = 20260020
CLOSE_TIMEOUT_SECONDS = 20
LISTENER_MAX_OBSERVATION_SECONDS = 5
MIN_LISTENER_POLL_SECONDS = 0.25
MAX_LISTENER_POLL_SECONDS = 5.0
MONITOR_POLL_SECONDS = 1.0
MONITOR_MAX_HOLD_SECONDS = 10 * 60


def utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def parse_utc(value: Any, field: str) -> datetime:
    if not isinstance(value, str):
        raise SystemExit(f"session lease {field} must be an ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise SystemExit(f"session lease {field} is invalid") from error
    if parsed.tzinfo is None:
        raise SystemExit(f"session lease {field} must include a timezone")
    return parsed.astimezone(timezone.utc)


def load_session_lease(path: Path, now: datetime) -> dict[str, Any]:
    """Load a fixed local lease and reject absent, stale, or widened sessions."""
    if not path.is_file():
        raise SystemExit("M20 session lease is absent; no market snapshot or execution is allowed")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SystemExit("M20 session lease is unreadable") from error
    expected_fields = {
        "schema_version",
        "session_id",
        "enabled",
        "server",
        "symbol",
        "starts_at_utc",
        "expires_at_utc",
        "maximum_trades",
        "maximum_duration_minutes",
        "maximum_open_positions",
        "maximum_notional_per_trade_usd",
        "maximum_cumulative_notional_usd",
        "maximum_loss_per_trade_aud",
        "audit_prerequisites",
    }
    if not isinstance(payload, dict) or set(payload) != expected_fields:
        raise SystemExit("M20 session lease fields are invalid")
    if payload["schema_version"] != SESSION_SCHEMA_VERSION or payload["enabled"] is not True:
        raise SystemExit("M20 session lease is not enabled")
    if payload["server"] != SERVER or payload["symbol"] != SYMBOL:
        raise SystemExit("M20 session lease is not fixed to GOMarketsMU-Demo EURUSD")
    try:
        UUID(str(payload["session_id"]))
    except (ValueError, AttributeError, TypeError) as error:
        raise SystemExit("M20 session lease has an invalid session_id") from error
    starts_at = parse_utc(payload["starts_at_utc"], "starts_at_utc")
    expires_at = parse_utc(payload["expires_at_utc"], "expires_at_utc")
    if not starts_at <= now <= expires_at or expires_at <= starts_at:
        raise SystemExit("M20 session lease is inactive or expired")
    if payload["maximum_duration_minutes"] != 0 and expires_at - starts_at > timedelta(minutes=60):
        raise SystemExit("M20 session lease exceeds 60 minutes")
    limits = (
        ("maximum_trades", 1, 10),
        ("maximum_duration_minutes", 0, 60),
        ("maximum_open_positions", 1, 1),
        ("maximum_notional_per_trade_usd", 1, 10000),
        ("maximum_cumulative_notional_usd", 1, 100000),
        ("maximum_loss_per_trade_aud", 100, 100),
    )
    for field, lower, upper in limits:
        value = payload[field]
        if isinstance(value, bool) or not isinstance(value, int) or not lower <= value <= upper:
            raise SystemExit(f"M20 session lease {field} is outside its fixed cap")
    if payload["maximum_cumulative_notional_usd"] < payload["maximum_notional_per_trade_usd"]:
        raise SystemExit("M20 session lease cumulative notional cannot be less than one trade")
    if payload["audit_prerequisites"] != SESSION_AUDIT_REQUIREMENTS:
        raise SystemExit("M20 session lease audit prerequisites are absent")
    return {
        "session_id": str(payload["session_id"]),
        "starts_at_utc": utc(starts_at),
        "expires_at_utc": utc(expires_at),
        "maximum_trades": payload["maximum_trades"],
        "maximum_duration_minutes": payload["maximum_duration_minutes"],
        "maximum_open_positions": payload["maximum_open_positions"],
        "maximum_notional_per_trade_usd": payload["maximum_notional_per_trade_usd"],
        "maximum_cumulative_notional_usd": payload["maximum_cumulative_notional_usd"],
        "maximum_loss_per_trade_aud": payload["maximum_loss_per_trade_aud"],
        "audit_prerequisites": SESSION_AUDIT_REQUIREMENTS,
    }


def _bar_rows(rates: Any, *, timeframe_name: str, seconds: int, cutoff: int, timestamp_offset_seconds: int) -> tuple[list[dict[str, Any]], str]:
    if rates is None:
        raise SystemExit(f"expected closed EURUSD {timeframe_name} candles")
    rows: list[dict[str, Any]] = []
    previous_open: int | None = None
    for rate in rates:
        opened_at = int(rate["time"]) - timestamp_offset_seconds
        # A candle is admissible only when its complete interval ended before
        # the current observed-tick timeframe boundary.
        if opened_at + seconds > cutoff:
            continue
        if previous_open is not None and opened_at <= previous_open:
            raise SystemExit(f"EURUSD {timeframe_name} candles are not chronological")
        previous_open = opened_at
        row = {
            "opened_at_utc": utc(datetime.fromtimestamp(opened_at, timezone.utc)),
            "closed_at_utc": utc(datetime.fromtimestamp(opened_at + seconds, timezone.utc)),
            "open": float(rate["open"]),
            "high": float(rate["high"]),
            "low": float(rate["low"]),
            "close": float(rate["close"]),
            "volume": int(rate["tick_volume"]),
        }
        ohlc = (row["open"], row["high"], row["low"], row["close"])
        if min(ohlc) <= 0 or row["low"] > min(row["open"], row["close"]) or row["high"] < max(row["open"], row["close"]):
            raise SystemExit(f"EURUSD {timeframe_name} candle has invalid OHLC")
        rows.append(row)
    rows = rows[-CLOSED_BAR_COUNT:]
    if len(rows) != CLOSED_BAR_COUNT:
        raise SystemExit(f"expected exactly {CLOSED_BAR_COUNT} closed EURUSD {timeframe_name} candles")
    raw = json.dumps(rows, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return rows, hashlib.sha256(raw).hexdigest()


def _bridge(payload: dict[str, Any], command: str) -> dict[str, Any]:
    """Invoke only the co-located, hash-bound bridge in T480 WSL.

    MT5 remains in Windows. PostgreSQL is loopback-bound inside T480 WSL, so
    the audit process must run there rather than opening a Windows-to-WSL port
    path that could silently target a different local service.
    """
    bridge_path = Path(__file__).with_name("m20_postgres_audit_bridge.payload")
    expected = os.environ.get("FOREX_M20_POSTGRES_AUDIT_BRIDGE_SHA256", "")
    actual = "sha256:" + hashlib.sha256(bridge_path.read_bytes()).hexdigest()
    if expected != actual:
        raise SystemExit("M20 PostgreSQL audit bridge is absent or differs from its fixed deployment hash")
    dsn = os.environ.get("FOREX_M20_POSTGRES_DSN", "")
    profile = os.environ.get("USERPROFILE", "")
    prefix = "C:\\Users\\"
    if not dsn or not profile.startswith(prefix):
        raise SystemExit("M20 PostgreSQL bridge WSL prerequisites are absent")
    drive = bridge_path.drive.rstrip(":").lower()
    bridge_parts = bridge_path.parts[1:]
    wsl_bridge = "/mnt/" + drive + "/" + "/".join(bridge_parts)
    completed = subprocess.run(
        ["wsl.exe", "-d", "Ubuntu", "--", "env", f"FOREX_M20_POSTGRES_DSN={dsn}", "python3", wsl_bridge, command],
        input=json.dumps(payload, separators=(",", ":")),
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise SystemExit(f"M20 PostgreSQL audit bridge failed closed: {completed.stderr.strip()}")
    try:
        result = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise SystemExit("M20 PostgreSQL audit bridge returned invalid JSON") from error
    if not isinstance(result, dict) or result.get("ok") is not True:
        raise SystemExit("M20 PostgreSQL audit bridge did not confirm its write")
    return result


def _provenance() -> tuple[str, str]:
    revision = os.environ.get("FOREX_M20_APPLICATION_REVISION", "")
    fingerprint = os.environ.get("FOREX_M20_CONFIGURATION_FINGERPRINT", "")
    if len(revision) != 40 or not fingerprint.startswith("sha256:"):
        raise SystemExit("M20 session provenance is absent or invalid")
    return revision, fingerprint


def tick_time_offset_seconds() -> int:
    """Return the explicit, bounded broker-server to UTC time offset."""
    try:
        value = int(os.environ.get("FOREX_M20_TICK_TIME_OFFSET_SECONDS", ""))
    except ValueError as error:
        raise SystemExit("M20 tick timestamp offset is absent or invalid") from error
    if not -50_400 <= value <= 50_400 or value % 900:
        raise SystemExit("M20 tick timestamp offset is outside the governed range")
    return value


def _session(lease: dict[str, Any]) -> dict[str, Any]:
    return {
        "session_id": lease["session_id"],
        "server": SERVER,
        "instrument": SYMBOL,
        "starts_at_utc": lease["starts_at_utc"],
        "expires_at_utc": lease["expires_at_utc"],
        "max_trades": lease["maximum_trades"],
        "max_notional_per_trade_usd": lease["maximum_notional_per_trade_usd"],
        "max_cumulative_notional_usd": lease["maximum_cumulative_notional_usd"],
        "max_open_positions": lease["maximum_open_positions"],
        "maximum_loss_per_trade_aud": lease["maximum_loss_per_trade_aud"],
        "strategy_version": STRATEGY_VERSION,
        "operator_label": OPERATOR_LABEL,
        "status": "ACTIVE",
    }


def _risk_levels(*, action: str, entry: float, volume: float, tick_size: float, tick_value_loss: float, point: float, maximum_loss_aud: int) -> tuple[float, float, float]:
    """Return stop, take-profit, and USD notional for the fixed minimum lot.

    Tick value is broker-reported in the account currency for one whole lot;
    the stop is always rounded toward the entry, so its theoretical loss never
    exceeds the AUD cap.  If even one broker tick would exceed that cap, the
    fixed executor refuses the order rather than widening the risk boundary.
    """
    if action not in {"BUY", "SELL"} or min(entry, volume, tick_size, tick_value_loss, point) <= 0:
        raise SystemExit("M20 broker risk inputs are invalid")
    loss_per_tick = volume * tick_value_loss
    ticks = math.floor(maximum_loss_aud / loss_per_tick)
    if ticks < 1:
        raise SystemExit("M20 minimum EURUSD price increment exceeds the AUD loss cap")
    distance = ticks * tick_size
    if action == "BUY":
        stop, take = entry - distance, entry + distance
    else:
        stop, take = entry + distance, entry - distance
    if stop <= 0 or take <= 0:
        raise SystemExit("M20 AUD loss cap cannot produce valid EURUSD levels")
    # Align the protective stop towards the entry.  Ordinary rounding or an
    # away-from-entry alignment could silently exceed the hard loss limit.
    epsilon = 1e-9
    if action == "BUY":
        stop = math.ceil(stop / point - epsilon) * point
    else:
        stop = math.floor(stop / point + epsilon) * point
    actual_loss = abs(entry - stop) / tick_size * loss_per_tick
    if actual_loss > maximum_loss_aud + 1e-7:
        raise SystemExit("M20 calculated stop would exceed the AUD loss cap")
    # EURUSD quote currency is USD; contract size times price is USD notional.
    return round(stop, 10), round(take, 10), volume * 100000 * entry


def _strategy_assessments(*, m1: list[dict[str, Any]], tick: dict[str, Any], active_action: str) -> list[dict[str, Any]]:
    """Compare five fixed M1 hypotheses; only momentum breakout can execute."""
    point = 0.00001
    spread_points = float(tick["spread_points"])

    def record(identifier: str, label: str, signal: str, reason: str, *, active: bool = False) -> dict[str, Any]:
        return {"id": identifier, "label": label, "signal": signal, "eligible_for_execution": active, "reason": reason}

    if len(m1) < 12:
        unavailable = "Needs twelve completed M1 candles."
        return [
            record("momentum_breakout", "Momentum breakout", active_action, "Active closed-candle breakout assessment.", active=True),
            record("compression_breakout", "Compression breakout", "NO_TRADE", unavailable),
            record("trend_pullback", "Trend pullback", "NO_TRADE", unavailable),
            record("range_reversion", "Range reversion", "NO_TRADE", unavailable),
            record("session_breakout", "Session breakout", "NO_TRADE", unavailable),
        ]

    setup, previous = m1[-1], m1[-2]
    setup_open = float(setup.get("open", previous["close"]))
    previous_open = float(previous.get("open", m1[-3]["close"]))
    setup_move = float(setup["close"]) - setup_open
    previous_move = float(previous["close"]) - previous_open
    direction = "BUY" if setup_move > 0 and previous_move > 0 else "SELL" if setup_move < 0 and previous_move < 0 else "NO_TRADE"
    momentum_points = abs(setup_move + previous_move) / point
    prior_five = m1[-6:-1]
    prior_high = max(float(bar.get("high", bar["close"])) for bar in prior_five)
    prior_low = min(float(bar.get("low", bar["close"])) for bar in prior_five)
    breakout_signal = "BUY" if direction == "BUY" and float(setup["close"]) > prior_high and momentum_points > spread_points else "SELL" if direction == "SELL" and float(setup["close"]) < prior_low and momentum_points > spread_points else "NO_TRADE"

    compression = m1[-8:-3]
    compression_high = max(float(bar.get("high", bar["close"])) for bar in compression)
    compression_low = min(float(bar.get("low", bar["close"])) for bar in compression)
    compression_points = (compression_high - compression_low) / point
    compression_limit = max(12.0, spread_points * 3.0)
    compression_signal = breakout_signal if compression_points <= compression_limit else "NO_TRADE"

    closes = [float(bar["close"]) for bar in m1]
    rising_trend = closes[-7] < closes[-6] < closes[-5] and closes[-4] < closes[-5] and float(setup["close"]) > float(previous["close"])
    falling_trend = closes[-7] > closes[-6] > closes[-5] and closes[-4] > closes[-5] and float(setup["close"]) < float(previous["close"])
    pullback_signal = "BUY" if rising_trend and momentum_points > spread_points else "SELL" if falling_trend and momentum_points > spread_points else "NO_TRADE"

    upper_rejection = float(setup.get("high", setup["close"])) >= prior_high and float(setup["close"]) < setup_open
    lower_rejection = float(setup.get("low", setup["close"])) <= prior_low and float(setup["close"]) > setup_open
    reversion_signal = "SELL" if upper_rejection and abs(setup_move) / point > spread_points else "BUY" if lower_rejection and abs(setup_move) / point > spread_points else "NO_TRADE"

    observed_hour = parse_utc(tick["observed_at_utc"], "observed_at_utc").hour
    liquid_session = 7 <= observed_hour < 20
    normal_spread = spread_points <= 12.0
    session_signal = breakout_signal if liquid_session and normal_spread else "NO_TRADE"

    # Each rule receives the same immutable captured snapshot. Parallelising
    # these pure calculations never adds MT5 reads or execution authority; the
    # canonical order below keeps dashboard and audit interpretation stable.
    rules = (
        lambda: record("momentum_breakout", "Momentum breakout", active_action, "Active rule: " + ("eligible after two aligned candles, range break, and spread check." if active_action != "NO_TRADE" else "no eligible closed-candle breakout."), active=True),
        lambda: record("compression_breakout", "Compression breakout", compression_signal, f"Prior five-candle range {compression_points:.1f} pts; limit {compression_limit:.1f} pts."),
        lambda: record("trend_pullback", "Trend pullback", pullback_signal, "Trend, pullback, and resumption checks are " + ("aligned." if pullback_signal != "NO_TRADE" else "not aligned.")),
        lambda: record("range_reversion", "Range reversion", reversion_signal, "Range-edge rejection check is " + ("present." if reversion_signal != "NO_TRADE" else "not present.")),
        lambda: record("session_breakout", "Session breakout", session_signal, f"UTC hour {observed_hour:02d}; liquid-session={liquid_session}, normal-spread={normal_spread}."),
    )
    with ThreadPoolExecutor(max_workers=len(rules), thread_name_prefix="m20-strategy") as executor:
        return list(executor.map(lambda rule: rule(), rules))


def _assessment(session: dict[str, Any], tick: dict[str, Any], bars: dict[str, list[dict[str, Any]]], captured_at: datetime, risk: dict[str, float], listener_poll_seconds: float) -> tuple[dict[str, Any], dict[str, Any]]:
    """Create an M1-only proposal from the non-persisted live tick listener."""
    observed_at = tick["observed_at_utc"]
    snapshot_body = {
        "observed_at_utc": observed_at,
        "captured_at_utc": utc(captured_at),
        "bid": tick["bid"], "ask": tick["ask"], "spread_points": tick["spread_points"],
        "freshness_seconds": int(tick["freshness_seconds"]),
        "m1_closed_bars": bars["M1"], "m5_closed_bars": bars["M5"],
    }
    digest = "sha256:" + hashlib.sha256(json.dumps(snapshot_body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    snapshot_id = str(uuid5(NAMESPACE_URL, f"{session['session_id']}:{digest}"))
    snapshot = {"snapshot_id": snapshot_id, **snapshot_body, "payload_sha256": digest}
    m1 = bars["M1"]
    action = "NO_TRADE"
    reason = "M1 listener requires six completed candles; no Demo order is submitted."
    technical_stop: float | None = None
    if len(m1) >= 6:
        setup, previous = m1[-1], m1[-2]
        window = m1[-6:-1]
        def opening(bar: dict[str, Any], prior: dict[str, Any]) -> float:
            return float(bar.get("open", prior["close"]))
        setup_open, previous_open = opening(setup, previous), opening(previous, m1[-3])
        setup_move = float(setup["close"]) - setup_open
        previous_move = float(previous["close"]) - previous_open
        spread_price = float(tick["ask"]) - float(tick["bid"])
        window_high = max(float(row.get("high", row["close"])) for row in window)
        window_low = min(float(row.get("low", row["close"])) for row in window)
        if setup_move > 0 and previous_move > 0 and float(setup["close"]) > window_high and setup_move + previous_move > spread_price:
            action, technical_stop = "BUY", window_low
        elif setup_move < 0 and previous_move < 0 and float(setup["close"]) < window_low and -(setup_move + previous_move) > spread_price:
            action, technical_stop = "SELL", window_high
        else:
            reason = "M1 closed-candle breakout conditions are not met after spread; no Demo order is submitted."
    proposal_id = str(uuid5(NAMESPACE_URL, f"{session['session_id']}:{snapshot_id}:assessment"))
    proposal = {
        "proposal_id": proposal_id, "session_id": session["session_id"], "snapshot_id": snapshot_id,
        "decision_at_utc": observed_at,
        "expires_at_utc": utc(min(parse_utc(observed_at, "observed_at_utc") + timedelta(minutes=5), parse_utc(session["expires_at_utc"], "expires_at_utc"))),
        "selected_timeframe": "M1", "action": action,
        "proposed_entry": None, "stop_loss": None, "take_profit": None,
        "notional_usd": None, "confidence": 100 if action == "NO_TRADE" else 60,
        "rationale": reason if action == "NO_TRADE" else f"M1 two-candle momentum broke the prior five-candle range after spread; listener cadence {listener_poll_seconds:.2f}s.",
        "decision_snapshot_sha256": digest, "strategy_version": STRATEGY_VERSION,
    }
    if action != "NO_TRADE":
        entry = tick["ask"] if action == "BUY" else tick["bid"]
        capped_stop, _, notional = _risk_levels(action=action, entry=entry, maximum_loss_aud=session["maximum_loss_per_trade_aud"], **risk)
        if technical_stop is None:
            raise SystemExit("M20 actionable M1 proposal is missing its technical stop")
        stop = max(capped_stop, technical_stop) if action == "BUY" else min(capped_stop, technical_stop)
        if (action == "BUY" and not 0 < stop < entry) or (action == "SELL" and stop <= entry):
            raise SystemExit("M20 technical M1 stop is invalid")
        distance = abs(entry - stop)
        take = entry + 1.5 * distance if action == "BUY" else entry - 1.5 * distance
        take = round(take / risk["point"]) * risk["point"]
        # A stop is aligned toward entry so an increment cannot widen the
        # independently calculated AUD 100 maximum-loss boundary.
        stop = (math.ceil(stop / risk["point"] - 1e-9) if action == "BUY" else math.floor(stop / risk["point"] + 1e-9)) * risk["point"]
        if notional > session["max_notional_per_trade_usd"]:
            raise SystemExit("M20 minimum EURUSD volume exceeds the Demo notional cap")
        proposal.update({"proposed_entry": entry, "stop_loss": stop, "take_profit": take, "notional_usd": round(notional, 2), "confidence": 70, "rationale": f"M1 breakout with two aligned closed candles; {risk['volume']:.2f} lot stop is capped at AUD {session['maximum_loss_per_trade_aud']} and target is 1.5R."})
    return snapshot, proposal


def _listen_for_tick() -> tuple[Any, float]:
    """Observe MT5's current refresh cadence without retaining the tick stream."""
    first = mt5.symbol_info_tick(SYMBOL)
    if not first:
        raise SystemExit("fresh EURUSD tick is unavailable")
    previous_time_msc = int(getattr(first, "time_msc", 0))
    poll_seconds = MIN_LISTENER_POLL_SECONDS
    deadline = time.monotonic() + LISTENER_MAX_OBSERVATION_SECONDS
    while time.monotonic() < deadline:
        time.sleep(poll_seconds)
        current = mt5.symbol_info_tick(SYMBOL)
        if not current:
            continue
        current_time_msc = int(getattr(current, "time_msc", 0))
        if current_time_msc > previous_time_msc:
            refresh_seconds = (current_time_msc - previous_time_msc) / 1000
            poll_seconds = min(MAX_LISTENER_POLL_SECONDS, max(MIN_LISTENER_POLL_SECONDS, refresh_seconds))
            return current, poll_seconds
    return first, poll_seconds


def quote_identity(terminal_path: str) -> dict[str, Any]:
    """Read one fixed Demo EURUSD quote identity without assessing or trading."""
    if not mt5.initialize(path=terminal_path):
        raise SystemExit(mt5.last_error())
    try:
        account = mt5.account_info()
        symbol = mt5.symbol_info(SYMBOL)
        tick = mt5.symbol_info_tick(SYMBOL)
        if not account or account.server != SERVER or getattr(account, "currency", "") != "AUD":
            raise SystemExit("M20 quote identity is not connected to the required AUD GOMarketsMU-Demo account")
        if not symbol or symbol.name != SYMBOL or not tick:
            raise SystemExit("M20 quote identity has no EURUSD quote")
        bid, ask, tick_msc = float(tick.bid), float(tick.ask), int(getattr(tick, "time_msc", 0))
        if tick_msc <= 0 or bid <= 0 or ask < bid:
            raise SystemExit("M20 quote identity is invalid")
        return {"marker": "FOREX_M20_DEMO_QUOTE_IDENTITY_OK", "server": account.server,
                "symbol": SYMBOL, "tick_time_msc": tick_msc, "bid": bid, "ask": ask}
    finally:
        mt5.shutdown()


def _wait_for_position() -> Any:
    """Return the sole fixed-executor EURUSD position or fail closed.

    An accepted market order is not treated as a completed M20 action until
    the terminal exposes its position.  The runner never searches other
    symbols or positions belonging to another strategy.
    """
    deadline = time.monotonic() + CLOSE_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        positions = mt5.positions_get(symbol=SYMBOL) or ()
        owned = [position for position in positions if int(getattr(position, "magic", -1)) == EXECUTOR_MAGIC]
        if len(owned) == 1:
            return owned[0]
        if len(owned) > 1:
            raise SystemExit("M20 executor observed more than one owned EURUSD position")
        time.sleep(0.25)
    raise SystemExit("M20 accepted order did not produce a fixed EURUSD position before close timeout")


def _wait_until_closed(ticket: int) -> None:
    deadline = time.monotonic() + CLOSE_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        if not (mt5.positions_get(ticket=ticket) or ()):
            return
        time.sleep(0.25)
    raise SystemExit("M20 fixed EURUSD position did not close before close timeout")


def _closed_position_costs(*, position: Any, submitted_at: datetime, proposed_entry: float, entry_spread: float, risk: dict[str, float], expected_exit_price: float | None) -> tuple[float, dict[str, float]]:
    """Read the terminal's immutable deal history for one closed position.

    This is used for both a discretionary monitor exit and a broker-side
    stop/take-profit exit.  If an exit quote is no longer available after a
    broker-side close, the estimated exit slippage is recorded as zero rather
    than inventing a quote; realized P&L, commission, and swap still come
    directly from MT5 deal history.
    """
    ticket = int(getattr(position, "ticket", 0))
    volume = float(getattr(position, "volume", 0))
    position_type = int(getattr(position, "type", -1))
    if ticket <= 0:
        raise SystemExit("M20 closed position has an invalid ticket")
    # MT5 position history must be queried by identifier without a date range.
    deals = mt5.history_deals_get(position=ticket)
    if not deals:
        raise SystemExit("M20 closed position deal history is unavailable")
    ordered = sorted(deals, key=lambda deal: int(getattr(deal, "time_msc", 0)))
    if volume <= 0:
        volume = max(float(getattr(deal, "volume", 0)) for deal in ordered)
    if volume <= 0:
        raise SystemExit("M20 closed position deal history has no volume")
    # MT5 can append zero-price accounting rows (for example a commission or
    # balance adjustment) after the actual closing market deal.  Those rows
    # contribute to realised P&L but are not executable prices.  Select the
    # last priced, volume-bearing deal for the exit price while retaining all
    # deal rows below when calculating broker-reported P&L and fees.
    priced_deals = [
        deal for deal in ordered
        if float(getattr(deal, "price", 0)) > 0 and float(getattr(deal, "volume", 0)) > 0
    ]
    if not priced_deals:
        # Keep the diagnosis deliberately small and broker-derived.  It lets
        # the fixed status surface distinguish an absent position history
        # from post-close accounting rows without exposing credentials or a
        # generic MT5-history interface.
        diagnostic = [
            {
                "deal_ticket": int(getattr(deal, "ticket", 0)),
                "position_id": int(getattr(deal, "position_id", 0)),
                "entry": int(getattr(deal, "entry", -1)),
                "type": int(getattr(deal, "type", -1)),
                "volume": float(getattr(deal, "volume", 0)),
                "price": float(getattr(deal, "price", 0)),
            }
            for deal in ordered[-6:]
        ]
        raise SystemExit(f"M20 close deal history has no priced market deal: {json.dumps(diagnostic, separators=(',', ':'))}")
    exit_deal = priced_deals[-1]
    exit_price = float(getattr(exit_deal, "price", 0))
    gross_price_pnl = sum(float(getattr(deal, "profit", 0)) for deal in ordered)
    commission = sum(float(getattr(deal, "commission", 0)) for deal in ordered)
    swap = sum(float(getattr(deal, "swap", 0)) for deal in ordered)
    realized_pnl = gross_price_pnl + commission + swap
    entry_price = float(getattr(position, "price_open", 0))
    tick_size, tick_value_loss = risk["tick_size"], risk["tick_value_loss"]
    if entry_price <= 0 or min(tick_size, tick_value_loss) <= 0:
        raise SystemExit("M20 accepted EURUSD cost inputs are invalid")
    is_buy = position_type == mt5.POSITION_TYPE_BUY
    entry_slippage_price = entry_price - proposed_entry if is_buy else proposed_entry - entry_price
    exit_slippage_price = 0.0
    if expected_exit_price is not None:
        exit_slippage_price = expected_exit_price - exit_price if is_buy else exit_price - expected_exit_price
    # A closing quote is used when available.  A broker-side close has no
    # recoverable pre-close quote, so retain the known entry spread only.
    exit_spread = 0.0
    tick = mt5.symbol_info_tick(SYMBOL)
    if tick:
        bid, ask = float(tick.bid), float(tick.ask)
        if bid > 0 and ask >= bid:
            exit_spread = ask - bid
    spread_cost = (entry_spread + exit_spread) / tick_size * volume * tick_value_loss
    slippage_cost = (entry_slippage_price + exit_slippage_price) / tick_size * volume * tick_value_loss
    total_cost = spread_cost + slippage_cost - commission - swap
    costs = {
        "gross_price_pnl_account": round(gross_price_pnl, 2),
        "commission_account": round(commission, 2),
        "swap_account": round(swap, 2),
        "estimated_spread_cost_account": round(spread_cost, 2),
        "slippage_cost_account": round(slippage_cost, 2),
        "estimated_total_cost_account": round(total_cost, 2),
        "realized_pnl_account": round(realized_pnl, 2),
    }
    return exit_price, costs


def _close_accepted_position(*, position: Any, submitted_at: datetime, proposed_entry: float, entry_spread: float, risk: dict[str, float]) -> tuple[str, float, dict[str, float]]:
    """Close one monitor-owned position and derive its MT5-backed P&L."""
    ticket = int(getattr(position, "ticket", 0))
    volume = float(getattr(position, "volume", 0))
    position_type = int(getattr(position, "type", -1))
    if ticket <= 0 or volume <= 0:
        raise SystemExit("M20 accepted position has invalid ticket or volume")
    tick = mt5.symbol_info_tick(SYMBOL)
    if not tick:
        raise SystemExit("M20 close tick is unavailable")
    is_buy = position_type == mt5.POSITION_TYPE_BUY
    close_type = mt5.ORDER_TYPE_SELL if is_buy else mt5.ORDER_TYPE_BUY
    close_price = float(tick.bid if is_buy else tick.ask)
    if close_price <= 0:
        raise SystemExit("M20 close price is invalid")
    close_request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": SYMBOL,
        "volume": volume,
        "type": close_type,
        "position": ticket,
        "price": close_price,
        "deviation": 20,
        "magic": EXECUTOR_MAGIC,
        "comment": "forex-m20-demo-close",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    close_result = mt5.order_send(close_request)
    if not close_result or close_result.retcode != mt5.TRADE_RETCODE_DONE:
        raise SystemExit("M20 accepted EURUSD position close was rejected")
    _wait_until_closed(ticket)
    exit_price, costs = _closed_position_costs(
        position=position,
        submitted_at=submitted_at,
        proposed_entry=proposed_entry,
        entry_spread=entry_spread,
        risk=risk,
        expected_exit_price=close_price,
    )
    return str(getattr(close_result, "order", "")), exit_price, costs


def _closed_m1_bars_for_monitor(tick: Any, offset_seconds: int) -> list[dict[str, Any]]:
    """Load only completed M1 candles for a position exit decision."""
    observed_at = datetime.fromtimestamp(int(tick.time), timezone.utc) - timedelta(seconds=offset_seconds)
    boundary = int(observed_at.timestamp()) // 60 * 60
    rates = mt5.copy_rates_from_pos(SYMBOL, mt5.TIMEFRAME_M1, 1, CLOSED_BAR_COUNT + 8)
    rows, _ = _bar_rows(
        rates,
        timeframe_name="M1",
        seconds=60,
        cutoff=boundary,
        timestamp_offset_seconds=offset_seconds,
    )
    return rows


def _two_opposite_completed_m1_candles(*, bars: list[dict[str, Any]], action: str, opened_at: datetime) -> bool:
    """Return true only for two new, fully closed candles against the trade."""
    candidates = [
        bar for bar in bars
        if parse_utc(bar["closed_at_utc"], "closed_at_utc") > opened_at
    ]
    if len(candidates) < 2:
        return False
    last_two = candidates[-2:]
    moves = [float(bar["close"]) - float(bar["open"]) for bar in last_two]
    return (action == "BUY" and all(move < 0 for move in moves)) or (
        action == "SELL" and all(move > 0 for move in moves)
    )


def _record_closed_monitor_outcome(*, proposal: dict[str, Any], attempt_id: str, position: Any, submitted_at: datetime, entry_spread: float, risk: dict[str, float], close_reason: str, broker_order_reference: str, expected_exit_price: float | None, closed_costs: dict[str, float] | None = None) -> dict[str, Any]:
    """Write the final lifecycle event and immutable AUD outcome once."""
    if closed_costs is None:
        exit_price, costs = _closed_position_costs(
            position=position,
            submitted_at=submitted_at,
            proposed_entry=float(proposal["proposed_entry"]),
            entry_spread=entry_spread,
            risk=risk,
            expected_exit_price=expected_exit_price,
        )
    else:
        if expected_exit_price is None:
            raise SystemExit("M20 monitor close is missing its recorded exit price")
        exit_price, costs = expected_exit_price, closed_costs
    closed_at = utc(datetime.now(timezone.utc))
    result = {
        "event_id": str(uuid5(NAMESPACE_URL, f"{attempt_id}:closed")),
        "attempt_id": attempt_id,
        "event_type": "CLOSED",
        "observed_at_utc": closed_at,
        "broker_order_reference": broker_order_reference,
        "payload_sha256": "sha256:" + hashlib.sha256(json.dumps({"close_reason": close_reason, "broker_order_reference": broker_order_reference}, sort_keys=True).encode()).hexdigest(),
        "payload": {"close_reason": close_reason},
    }
    outcome = {
        "proposal_id": proposal["proposal_id"],
        "closed_at_utc": closed_at,
        "exit_price": exit_price,
        **costs,
        "account_currency": "AUD",
        "close_reason": close_reason,
        "reconciliation_status": "MATCHED",
    }
    _bridge({"result": result, "outcome": outcome}, "record-closed-outcome")
    reconciliation = _bridge({"proposal_id": proposal["proposal_id"]}, "reconcile")["reconciliation"]
    if reconciliation.get("status") != "MATCHED":
        raise SystemExit("M20 closed monitored position was not reconciled")
    return reconciliation


def _apply_break_even(*, proposal: dict[str, Any], attempt_id: str, position: Any, entry: float, take_profit: float) -> None:
    """Move the protective stop to entry only after the +1R trigger."""
    ticket = int(getattr(position, "ticket", 0))
    request = {
        "action": mt5.TRADE_ACTION_SLTP,
        "symbol": SYMBOL,
        "position": ticket,
        "sl": entry,
        "tp": take_profit,
    }
    result = mt5.order_send(request)
    if not result or result.retcode != mt5.TRADE_RETCODE_DONE:
        # Do not attempt an unprotected discretionary close.  The original
        # broker-side stop/take-profit remains the safety backstop.
        raise SystemExit("M20 break-even stop update failed closed; original broker SL/TP remains active")
    observed_at = utc(datetime.now(timezone.utc))
    result_payload = {
        "event_id": str(uuid5(NAMESPACE_URL, f"{attempt_id}:breakeven")),
        "attempt_id": attempt_id,
        "event_type": "UPDATED",
        "observed_at_utc": observed_at,
        "broker_order_reference": str(getattr(result, "order", "")),
        "payload_sha256": "sha256:" + hashlib.sha256(json.dumps({"stop_loss": entry, "take_profit": take_profit}, sort_keys=True).encode()).hexdigest(),
        "payload": {"reason": "PLUS_1R_BREAK_EVEN", "stop_loss": entry, "take_profit": take_profit},
    }
    state = {
        "proposal_id": proposal["proposal_id"],
        "position_ticket": ticket,
        "observed_at_utc": observed_at,
        "stop_loss": entry,
        "take_profit": take_profit,
        "break_even_applied": True,
    }
    _bridge({"result": result_payload, "state": state}, "update-open-position")


def _monitor_open_position(*, proposal: dict[str, Any], attempt_id: str, position: Any, submitted_at: datetime, entry_spread: float, risk: dict[str, float], offset_seconds: int, single_pass: bool = False, break_even_applied: bool = False) -> dict[str, Any]:
    """Hold one Demo position with static broker protection and M1 exits.

    Any monitor, pricing, candle, or audit failure stops discretionary action.
    It never removes the broker-side SL/TP, never opens a second position, and
    leaves the durable open state intact for recovery by a future monitor.
    """
    ticket = int(getattr(position, "ticket", 0))
    action = proposal["action"]
    entry = float(getattr(position, "price_open", 0))
    original_stop = float(getattr(position, "sl", 0))
    take_profit = float(getattr(position, "tp", 0))
    if ticket <= 0 or action not in {"BUY", "SELL"} or min(entry, original_stop, take_profit) <= 0:
        raise SystemExit("M20 open position monitor inputs are invalid")
    risk_distance = abs(entry - original_stop)
    if risk_distance <= 0:
        raise SystemExit("M20 open position has no measurable initial risk")
    # A recovery pass is deliberately short, but the trade's M1 exit window
    # is not.  Use the durable submission time so its ten-minute maximum hold
    # and two-opposite-candle check survive every five-second supervisor pass.
    opened_at = submitted_at
    closes_at = opened_at + timedelta(seconds=MONITOR_MAX_HOLD_SECONDS)
    while True:
        positions = mt5.positions_get(ticket=ticket) or ()
        if not positions:
            # The broker's attached SL/TP (or a terminal-side action) closed
            # the trade.  The immutable deal history is now the source of P&L.
            return _record_closed_monitor_outcome(
                proposal=proposal, attempt_id=attempt_id, position=position,
                submitted_at=submitted_at, entry_spread=entry_spread, risk=risk,
                close_reason="BROKER_SIDE_CLOSE", broker_order_reference=str(ticket),
                expected_exit_price=None,
            )
        if len(positions) != 1 or int(getattr(positions[0], "magic", -1)) != EXECUTOR_MAGIC:
            raise SystemExit("M20 monitor observed an unexpected EURUSD position; broker SL/TP remains active")
        current = positions[0]
        tick = mt5.symbol_info_tick(SYMBOL)
        if not tick:
            raise SystemExit("M20 monitor tick is unavailable; broker SL/TP remains active")
        bid, ask = float(tick.bid), float(tick.ask)
        if bid <= 0 or ask < bid:
            raise SystemExit("M20 monitor tick is invalid; broker SL/TP remains active")
        executable_price = bid if action == "BUY" else ask
        reached_one_r = executable_price >= entry + risk_distance if action == "BUY" else executable_price <= entry - risk_distance
        if reached_one_r and not break_even_applied:
            _apply_break_even(proposal=proposal, attempt_id=attempt_id, position=current, entry=entry, take_profit=take_profit)
            break_even_applied = True
        if datetime.now(timezone.utc) >= closes_at:
            reference, exit_price, costs = _close_accepted_position(
                position=current, submitted_at=submitted_at,
                proposed_entry=float(proposal["proposed_entry"]), entry_spread=entry_spread, risk=risk,
            )
            return _record_closed_monitor_outcome(
                proposal=proposal, attempt_id=attempt_id, position=current,
                submitted_at=submitted_at, entry_spread=entry_spread, risk=risk,
                close_reason="M1_TIME_STOP_10_MINUTES", broker_order_reference=reference,
                expected_exit_price=exit_price, closed_costs=costs,
            )
        bars = _closed_m1_bars_for_monitor(tick, offset_seconds)
        if _two_opposite_completed_m1_candles(bars=bars, action=action, opened_at=opened_at):
            reference, exit_price, costs = _close_accepted_position(
                position=current, submitted_at=submitted_at,
                proposed_entry=float(proposal["proposed_entry"]), entry_spread=entry_spread, risk=risk,
            )
            return _record_closed_monitor_outcome(
                proposal=proposal, attempt_id=attempt_id, position=current,
                submitted_at=submitted_at, entry_spread=entry_spread, risk=risk,
                close_reason="M1_TWO_OPPOSITE_CLOSED_CANDLES", broker_order_reference=reference,
                expected_exit_price=exit_price, closed_costs=costs,
            )
        if single_pass:
            return {"status": "OPEN_MONITORING", "position_ticket": ticket}
        remaining_seconds = max(0.0, (closes_at - datetime.now(timezone.utc)).total_seconds())
        time.sleep(min(MONITOR_POLL_SECONDS, remaining_seconds))


def _monitor_job_path(session_path: Path) -> Path:
    """Return the fixed, durable monitor-job location for this listener."""
    return session_path.with_name("m20_demo_monitor_job.local.json")


def _write_monitor_job(*, session_path: Path, proposal: dict[str, Any], attempt_id: str, position: Any, submitted_at: str, entry_spread: float, risk: dict[str, float], offset_seconds: int) -> Path:
    """Persist accepted-position context so monitoring survives supervisor restart."""
    job = {
        "schema_version": "forex.m20.monitor-job.v1",
        "proposal": proposal,
        "attempt_id": attempt_id,
        "position": {"ticket": int(position.ticket), "price_open": float(position.price_open), "sl": float(position.sl), "tp": float(position.tp), "volume": float(position.volume), "type": int(position.type)},
        "submitted_at_utc": submitted_at,
        "entry_spread": entry_spread,
        "risk": risk,
        "tick_timestamp_offset_seconds": offset_seconds,
    }
    path = _monitor_job_path(session_path)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(job, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    temporary.replace(path)
    return path


def monitor(terminal_path: str, session_path: Path, *, single_pass: bool = False) -> dict[str, Any]:
    """Monitor one durable Demo position independently of assessment cadence."""
    path = _monitor_job_path(session_path)
    try:
        job = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as error:
        raise SystemExit("M20 monitor job is absent or unreadable") from error
    required = {"schema_version", "proposal", "attempt_id", "position", "submitted_at_utc", "entry_spread", "risk", "tick_timestamp_offset_seconds"}
    if not isinstance(job, dict) or set(job) != required or job["schema_version"] != "forex.m20.monitor-job.v1":
        raise SystemExit("M20 monitor job fields are invalid")
    proposal, position_data, risk = job["proposal"], job["position"], job["risk"]
    if not isinstance(proposal, dict) or not isinstance(position_data, dict) or not isinstance(risk, dict):
        raise SystemExit("M20 monitor job payload is invalid")
    if not mt5.initialize(path=terminal_path):
        raise SystemExit(mt5.last_error())
    try:
        account = mt5.account_info()
        if not account or account.server != SERVER or getattr(account, "currency", "") != "AUD":
            raise SystemExit("M20 monitor is not connected to the required AUD GOMarketsMU-Demo account")
        # Legacy v1 jobs omitted volume/type.  The broker's immutable deal
        # history supplies volume after a broker-side close; action supplies
        # the owned direction without inventing a trading decision.
        position_data.setdefault("type", mt5.POSITION_TYPE_BUY if proposal.get("action") == "BUY" else mt5.POSITION_TYPE_SELL)
        reconciliation = _monitor_open_position(
            proposal=proposal, attempt_id=str(job["attempt_id"]), position=SimpleNamespace(**position_data),
            submitted_at=parse_utc(str(job["submitted_at_utc"]), "submitted_at_utc"),
            entry_spread=float(job["entry_spread"]), risk={key: float(value) for key, value in risk.items()},
            offset_seconds=int(job["tick_timestamp_offset_seconds"]), single_pass=single_pass,
        )
        if reconciliation.get("status") != "OPEN_MONITORING":
            path.unlink(missing_ok=True)
        return {"marker": "FOREX_M20_DEMO_MONITOR_OPERATION_OK", "reconciliation": reconciliation, "position_ticket": position_data["ticket"]}
    finally:
        mt5.shutdown()


def recover_open_positions(terminal_path: str) -> dict[str, Any]:
    """Perform one broker-backed pass for every durable M20 open projection."""
    recovered = _bridge({}, "load-open-positions").get("open_positions")
    if not isinstance(recovered, list):
        raise SystemExit("M20 durable open-position recovery returned invalid data")
    if not mt5.initialize(path=terminal_path):
        raise SystemExit(mt5.last_error())
    try:
        account = mt5.account_info()
        symbol = mt5.symbol_info(SYMBOL)
        if not account or account.server != SERVER or getattr(account, "currency", "") != "AUD" or not symbol:
            raise SystemExit("M20 recovery is not connected to the required AUD GOMarketsMU-Demo account")
        base_risk = {"tick_size": float(symbol.trade_tick_size), "tick_value_loss": float(symbol.trade_tick_value_loss), "point": float(symbol.point)}
        results: list[dict[str, Any]] = []
        for row in recovered:
            if not isinstance(row, dict) or row.get("action") not in {"BUY", "SELL"}:
                results.append({"status": "RECOVERY_FAILED", "error": "invalid durable recovery row"})
                continue
            try:
                volume = float(row["volume"])
                if volume <= 0:
                    raise ValueError("missing broker-recorded volume")
                proposal = {"proposal_id": row["proposal_id"], "action": row["action"], "proposed_entry": float(row["proposed_entry"])}
                position = SimpleNamespace(
                    ticket=int(row["position_ticket"]), price_open=float(row["entry_price"]),
                    sl=float(row["stop_loss"]), tp=float(row["take_profit"]), volume=volume,
                    type=mt5.POSITION_TYPE_BUY if row["action"] == "BUY" else mt5.POSITION_TYPE_SELL,
                )
                reconciliation = _monitor_open_position(
                    proposal=proposal, attempt_id=str(row["attempt_id"]), position=position,
                    submitted_at=parse_utc(str(row["submitted_at_utc"]), "submitted_at_utc"),
                    entry_spread=float(row["entry_spread"]), risk={**base_risk, "volume": volume},
                    offset_seconds=tick_time_offset_seconds(), single_pass=True,
                    break_even_applied=bool(row.get("break_even_applied", False)),
                )
                results.append({"attempt_id": row["attempt_id"], "position_ticket": row["position_ticket"], "reconciliation": reconciliation})
            except (KeyError, TypeError, ValueError, SystemExit) as error:
                results.append({"attempt_id": row.get("attempt_id"), "position_ticket": row.get("position_ticket"), "status": "RECOVERY_FAILED", "error": str(error)})
        # The first MVP implementation persisted two accepted positions but
        # the broker retains no market-deal history for either (only account
        # rows with position_id=0), while the current terminal has no owned
        # EURUSD position.  Preserve those raw diagnostics as terminal FAILED
        # events and remove only their stale mutable-open projections.  This
        # is intentionally limited to the exact, broker-derived condition;
        # it does not invent a close price, P&L, or fee.
        history_unavailable = [
            {"attempt_id": item.get("attempt_id"), "history_diagnostic": item.get("error")}
            for item in results
            if item.get("status") == "RECOVERY_FAILED"
            and isinstance(item.get("error"), str)
            and item["error"].startswith("M20 close deal history has no priced market deal")
        ]
        owned_positions = [
            item for item in (mt5.positions_get(symbol=SYMBOL) or ())
            if int(getattr(item, "magic", -1)) == EXECUTOR_MAGIC
        ]
        if recovered and len(history_unavailable) == len(recovered) and not owned_positions:
            archived = _bridge(
                {"broker_open_position_count": 0, "reason": "BROKER_HISTORY_UNAVAILABLE", "attempts": history_unavailable},
                "archive-history-unavailable-positions",
            )
            archived_ids = set(archived.get("archived_attempt_ids", ()))
            results = [
                {**item, "status": "RECOVERY_ARCHIVED_HISTORY_UNAVAILABLE"}
                if item.get("attempt_id") in archived_ids else item
                for item in results
            ]
        return {"marker": "FOREX_M20_DEMO_MONITOR_OPERATION_OK", "recovered": results}
    finally:
        mt5.shutdown()


def capture(terminal_path: str, session_path: Path, trigger_tick_time_msc: int | None = None) -> dict[str, Any]:
    lease = load_session_lease(session_path, datetime.now(timezone.utc))
    if not mt5.initialize(path=terminal_path):
        raise SystemExit(mt5.last_error())
    try:
        account = mt5.account_info()
        if not account or account.server != SERVER:
            raise SystemExit("MT5 is not connected to GOMarketsMU-Demo")
        if getattr(account, "currency", "") != "AUD":
            raise SystemExit("M20 AUD loss-cap executor requires an AUD Demo account")
        symbol = mt5.symbol_info(SYMBOL)
        if not symbol or symbol.name != SYMBOL or float(symbol.point) <= 0:
            raise SystemExit("required EURUSD symbol is unavailable")
        if trigger_tick_time_msc is None:
            tick, listener_poll_seconds = _listen_for_tick()
        else:
            tick = mt5.symbol_info_tick(SYMBOL)
            actual_tick_time_msc = int(getattr(tick, "time_msc", 0)) if tick else 0
            if not tick or actual_tick_time_msc < trigger_tick_time_msc:
                raise SystemExit("M20 assessment tick predates its fresh-quote trigger")
            listener_poll_seconds = 0.0
        captured_at = datetime.now(timezone.utc)
        if captured_at > parse_utc(lease["expires_at_utc"], "expires_at_utc"):
            raise SystemExit("M20 session lease expired during market snapshot capture")
        offset_seconds = tick_time_offset_seconds()
        broker_observed_at = datetime.fromtimestamp(int(tick.time), timezone.utc)
        observed_at = broker_observed_at - timedelta(seconds=offset_seconds)
        freshness_seconds = (captured_at - observed_at).total_seconds()
        if not 0 <= freshness_seconds <= MAX_TICK_AGE_SECONDS:
            raise SystemExit("EURUSD tick is stale or later than the local capture clock")
        bid, ask = float(tick.bid), float(tick.ask)
        if bid <= 0 or ask < bid:
            raise SystemExit("EURUSD tick bid/ask is invalid")
        raw_bars: dict[str, list[dict[str, Any]]] = {}
        for name, timeframe, seconds in TIMEFRAMES:
            rates = mt5.copy_rates_from_pos(SYMBOL, timeframe, 1, CLOSED_BAR_COUNT + 8)
            boundary = int(observed_at.timestamp()) // seconds * seconds
            rows, digest = _bar_rows(
                rates,
                timeframe_name=name,
                seconds=seconds,
                cutoff=boundary,
                timestamp_offset_seconds=offset_seconds,
            )
            raw_bars[name] = [{"timeframe": name, **row} for row in rows]
        # The audit schema retains this legacy field but M20's M1-only
        # listener deliberately does not collect, use, or retain M5 data.
        raw_bars["M5"] = []
        session = _session(lease)
        tick_record = {
                "observed_at_utc": utc(observed_at),
                "freshness_seconds": int(freshness_seconds),
                "bid": bid,
                "ask": ask,
                "spread_points": round((ask - bid) / float(symbol.point), 4),
        }
        risk = {"volume": float(symbol.volume_min), "tick_size": float(symbol.trade_tick_size), "tick_value_loss": float(symbol.trade_tick_value_loss), "point": float(symbol.point)}
        snapshot, proposal = _assessment(session, tick_record, raw_bars, captured_at, risk, listener_poll_seconds)
        strategy_assessments = _strategy_assessments(m1=raw_bars["M1"], tick=tick_record, active_action=proposal["action"])
        revision, fingerprint = _provenance()
        bridge_session_keys = {"session_id", "server", "instrument", "starts_at_utc", "expires_at_utc", "max_trades", "max_notional_per_trade_usd", "max_cumulative_notional_usd", "max_open_positions", "strategy_version", "operator_label"}
        bridge_payload = {"session": {key: session[key] for key in bridge_session_keys}, "proposal": proposal, "decision_snapshot": snapshot, "application_revision": revision, "configuration_fingerprint": fingerprint}
        if proposal["action"] != "NO_TRADE":
            positions = mt5.positions_get(symbol=SYMBOL) or ()
            if positions:
                proposal.update({
                    "action": "NO_TRADE", "proposed_entry": None, "stop_loss": None,
                    "take_profit": None, "notional_usd": None, "confidence": 100,
                    "rationale": "An owned EURUSD Demo position is already being monitored; this assessment is recorded without a second order.",
                })
                bridge_payload["proposal"] = proposal
        persisted = _bridge(bridge_payload, "persist-proposal")
        if proposal["action"] != "NO_TRADE":
            submitted_at = utc(datetime.now(timezone.utc))
            attempt_id = str(uuid5(NAMESPACE_URL, f"{proposal['proposal_id']}:attempt"))
            reservation = {
                "attempt_id": attempt_id, "idempotency_key": str(uuid5(NAMESPACE_URL, f"{proposal['proposal_id']}:idempotency")),
                "submitted_at_utc": submitted_at, "redacted_result": "MT5 result pending", "broker_open_positions": 0,
            }
            reserved = _bridge({**bridge_payload, "reservation": reservation}, "reserve-execution")
            order_type = mt5.ORDER_TYPE_BUY if proposal["action"] == "BUY" else mt5.ORDER_TYPE_SELL
            request = {"action": mt5.TRADE_ACTION_DEAL, "symbol": SYMBOL, "volume": risk["volume"], "type": order_type,
                       "price": proposal["proposed_entry"], "sl": proposal["stop_loss"], "tp": proposal["take_profit"],
                       "deviation": 20, "magic": EXECUTOR_MAGIC, "comment": "forex-m20-demo", "type_time": mt5.ORDER_TIME_GTC,
                       "type_filling": mt5.ORDER_FILLING_IOC}
            result = mt5.order_send(request)
            accepted = bool(result) and result.retcode == mt5.TRADE_RETCODE_DONE
            event_type = "OPENED" if accepted else "REJECTED"
            broker_reference = str(getattr(result, "order", "")) if result else ""
            # Preserve the complete non-secret request and market/cap context
            # on the immutable broker-result event.  This makes future MT5
            # rejections diagnosable without an unsafe retry or generic order
            # interface.  Existing sparse historical rejections remain raw
            # incomplete evidence rather than receiving invented causes.
            position = _wait_for_position() if accepted else None
            broker_request = getattr(result, "request", None) if result else None
            result_context = {
                "schema_version": "forex.m20.mt5-result-context.v1",
                "retcode": getattr(result, "retcode", None),
                "broker_comment": str(getattr(result, "comment", ""))[:160] if result else "MT5 returned no result",
                "symbol": SYMBOL,
                "action": proposal["action"],
                "volume": risk["volume"],
                "requested_price": request["price"],
                "stop_loss": request["sl"],
                "take_profit": request["tp"],
                "deviation_points": request["deviation"],
                "filling_mode": request["type_filling"],
                "time_mode": request["type_time"],
                "magic": EXECUTOR_MAGIC,
                "observed_bid": bid,
                "observed_ask": ask,
                "spread_points": tick_record["spread_points"],
                "tick_freshness_seconds": int(freshness_seconds),
                "symbol_point": float(symbol.point),
                "trade_tick_size": float(symbol.trade_tick_size),
                "stops_level_points": int(getattr(symbol, "trade_stops_level", 0)),
                "freeze_level_points": int(getattr(symbol, "trade_freeze_level", 0)),
                "volume_min": float(symbol.volume_min),
                "volume_max": float(symbol.volume_max),
                "volume_step": float(symbol.volume_step),
                "visible_positions_count": len(positions),
                "lease_max_trades": session["max_trades"],
                "max_open_positions": session["max_open_positions"],
                "max_notional_per_trade_usd": session["max_notional_per_trade_usd"],
                "max_cumulative_notional_usd": session["max_cumulative_notional_usd"],
                "reservation_slot_number": reserved["reservation"]["slot_number"],
                "broker_order_reference": broker_reference,
                "broker_requested_price": getattr(broker_request, "price", None),
                "broker_requested_volume": getattr(broker_request, "volume", None),
                "broker_requested_stop_loss": getattr(broker_request, "sl", None),
                "broker_requested_take_profit": getattr(broker_request, "tp", None),
                "position_ticket": int(position.ticket) if position else None,
            }
            result_payload = {"event_id": str(uuid5(NAMESPACE_URL, f"{attempt_id}:result")), "attempt_id": attempt_id,
                              "event_type": event_type, "observed_at_utc": utc(datetime.now(timezone.utc)),
                              "broker_order_reference": broker_reference, "payload_sha256": "sha256:" + hashlib.sha256(json.dumps(result_context, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
                              "payload": result_context}
            _bridge({"result": result_payload}, "record-result")
            if accepted:
                if position is None:
                    raise SystemExit("M20 accepted broker result has no owned EURUSD position")
                _bridge({"state": {"proposal_id": proposal["proposal_id"], "attempt_id": attempt_id, "position_ticket": int(position.ticket), "action": proposal["action"], "opened_at_utc": utc(datetime.now(timezone.utc)), "observed_at_utc": utc(datetime.now(timezone.utc)), "entry_price": float(position.price_open), "stop_loss": float(position.sl), "take_profit": float(position.tp)}}, "record-open-position")
                monitor_job = _write_monitor_job(
                    session_path=session_path, proposal=proposal, attempt_id=attempt_id,
                    position=position, submitted_at=submitted_at, entry_spread=ask - bid,
                    risk=risk, offset_seconds=offset_seconds,
                )
                reconciliation = {"status": "OPEN_MONITORING", "position_ticket": int(position.ticket)}
            else:
                reconciliation = _bridge({"proposal_id": proposal["proposal_id"]}, "reconcile")["reconciliation"]
            expected_status = "OPEN_MONITORING" if accepted else "MATCHED"
            if reconciliation.get("status") != expected_status:
                raise SystemExit("M20 actionable execution was not reconciled")
            return {"marker": "FOREX_M20_DEMO_TRADING_OPERATION_OK", "schema_version": "forex.m20.demo-trading-operation.v1", "operation": "m20_demo_trading_session", "server": account.server, "symbol": SYMBOL, "captured_at_utc": utc(captured_at), "configuration_fingerprint": fingerprint, "tick_timestamp_offset_seconds": offset_seconds, "session": session, "decision_snapshot": snapshot, "proposal": proposal, "strategy_assessments": strategy_assessments, "execution": {"status": "ACCEPTED" if accepted else "REJECTED", "attempt_id": attempt_id, "session_id": session["session_id"], "proposal_id": proposal["proposal_id"], "idempotency_key": reservation["idempotency_key"], "submitted_at_utc": submitted_at, "open_positions_before": 0, "cumulative_notional_before_usd": 0, "broker_retcode": getattr(result, "retcode", None), "monitor_job_scheduled": accepted, "monitor_job_path": str(monitor_job) if accepted else None}, "reconciliation": reconciliation, "postgres_audit": reserved["postgres_audit"], "probe_sha256": os.environ.get("FOREX_M20_DEMO_TRADING_SESSION_SHA256", "UNDECLARED")}
        reconciled = _bridge({"proposal_id": proposal["proposal_id"]}, "reconcile")
        reconciliation = reconciled.get("reconciliation")
        if not isinstance(reconciliation, dict) or reconciliation.get("status") != "NO_TRADE_RECONCILED":
            raise SystemExit("M20 NO_TRADE reconciliation was not confirmed")
        return {
            "marker": "FOREX_M20_DEMO_TRADING_OPERATION_OK",
            "schema_version": "forex.m20.demo-trading-operation.v1",
            "operation": "m20_demo_trading_session", "server": account.server, "symbol": SYMBOL,
            "captured_at_utc": utc(captured_at), "configuration_fingerprint": fingerprint,
            "tick_timestamp_offset_seconds": offset_seconds,
            "session": session, "decision_snapshot": snapshot, "proposal": proposal, "strategy_assessments": strategy_assessments,
            "execution": {"status": "NOT_SUBMITTED", "attempt_id": None},
            "reconciliation": reconciliation, "postgres_audit": persisted["postgres_audit"],
            "probe_sha256": os.environ.get("FOREX_M20_DEMO_TRADING_SESSION_SHA256", "UNDECLARED"),
        }
    finally:
        mt5.shutdown()


def main(terminal_path: str, session_path: str, trigger_tick_time_msc: int | None = None) -> None:
    print(json.dumps(capture(terminal_path, Path(session_path), trigger_tick_time_msc), separators=(",", ":")))


if __name__ == "__main__":
    if len(sys.argv) == 3:
        main(sys.argv[1], sys.argv[2])
    elif len(sys.argv) == 5 and sys.argv[3] == "--assessment-trigger-tick-ms":
        try:
            trigger = int(sys.argv[4])
        except ValueError as error:
            raise SystemExit("M20 assessment trigger tick must be an integer") from error
        if trigger <= 0:
            raise SystemExit("M20 assessment trigger tick must be positive")
        main(sys.argv[1], sys.argv[2], trigger)
    elif len(sys.argv) == 4 and sys.argv[3] == "--monitor-once":
        print(json.dumps(monitor(sys.argv[1], Path(sys.argv[2]), single_pass=True), separators=(",", ":")))
    elif len(sys.argv) == 4 and sys.argv[3] == "--recover-open-positions-once":
        print(json.dumps(recover_open_positions(sys.argv[1]), separators=(",", ":")))
    elif len(sys.argv) == 4 and sys.argv[3] == "--quote-identity":
        print(json.dumps(quote_identity(sys.argv[1]), separators=(",", ":")))
    else:
        raise SystemExit("expected fixed terminal path and fixed M20 session lease path")
