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
import ntpath
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import ctypes
from ctypes import wintypes as wintypes
from queue import Empty, Queue
from threading import Lock, Thread
import time
from types import SimpleNamespace
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5
import math
from zoneinfo import ZoneInfo

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
    # M5/H1 are collected only for the staged M20.12 shadow experiment.
    # Neither is passed to selection, trade planning, order submission, or
    # monitoring; M1 remains the sole execution timeframe.
    ("M5", mt5.TIMEFRAME_M5, 5 * 60),
    ("H1", mt5.TIMEFRAME_H1, 60 * 60),
)
STRATEGY_VERSION = "forex.m20.11.m1-five-strategy-trial.v2"
SHADOW_CONTEXT_RULE_VERSION = "forex.m20.12.m5-h1-shadow-context.v1"
OPERATOR_LABEL = "codex-m20-demo"
EXECUTOR_MAGIC = 20260020
CLOSE_TIMEOUT_SECONDS = 20
LISTENER_MAX_OBSERVATION_SECONDS = 5
MIN_LISTENER_POLL_SECONDS = 0.25
MAX_LISTENER_POLL_SECONDS = 5.0
MONITOR_POLL_SECONDS = 1.0
MONITOR_MAX_HOLD_SECONDS = 10 * 60
STRATEGY_IDS = (
    "momentum_breakout",
    "compression_breakout",
    "trend_pullback",
    "range_reversion",
    "session_breakout",
)
STRATEGY_REGIMES = (
    ("COMPRESSION_BREAKOUT", "compression_breakout"),
    ("TREND_PULLBACK", "trend_pullback"),
    ("RANGE_REVERSION", "range_reversion"),
    ("LIQUID_SESSION_BREAKOUT", "session_breakout"),
    ("MOMENTUM_BREAKOUT", "momentum_breakout"),
)
# The M20.11 trial deliberately keeps monitoring in the existing process.
# Strategy ownership changes only deterministic exit timing; broker-side SL/TP
# and the two-opposite-closed-candle invalidation remain universal protection.
OWNER_MAX_HOLD_SECONDS = {
    "momentum_breakout": 10 * 60,
    "compression_breakout": 8 * 60,
    "trend_pullback": 10 * 60,
    "range_reversion": 6 * 60,
    "session_breakout": 10 * 60,
}
# These are deliberately fixed M20 policy constants, rather than caller
# inputs.  Actual commission, swap, and realised P&L remain broker-derived
# when a trade closes; this gate is a conservative pre-trade projection.
COST_POLICY_VERSION = "forex.m20.m1-cost-coverage.v2"
EXPECTED_EXIT_SPREAD_MULTIPLIER = 1.0
EXPECTED_SLIPPAGE_SPREAD_MULTIPLIER = 0.5
# The canonical runtime configuration is injected into the fixed release by
# the adapter.  A 10c default keeps local tests deterministic; production
# provenance binds the actual value through config/runtime.yaml.
MINIMUM_NET_PROFIT_AUD = float(os.environ.get("FOREX_M20_MINIMUM_NET_PROFIT_AUD", "0.10"))
if not 0.10 <= MINIMUM_NET_PROFIT_AUD <= 5.00:
    raise SystemExit("M20 minimum projected net profit is outside the governed Demo range")

# This is a one-off, operator-approved W1.4 refusal drill, not an adjustable
# risk setting.  The normal continuous Demo lease remains fixed at AUD 100.
REFUSAL_DRILL_MAXIMUM_LOSS_AUD = 0.01
# This is a separately labelled terminal-to-broker diagnostic. It is not a
# strategy decision and cannot support M30's natural-lifecycle proof.
EXECUTION_DRILL_MAGIC = 20260330
EXECUTION_DRILL_VOLUME = 0.01
EXECUTION_DRILL_MAXIMUM_LOSS_AUD = 1.00


RISK_POLICY_REQUIRED = {"policy_version", "reporting_currency", "maximum_risk_per_trade_percent", "maximum_risk_per_trade_aud", "daily_loss_limit_percent", "weekly_loss_limit_percent", "peak_equity_drawdown_limit_percent", "loss_budget_timezone", "daily_pause_reset", "manual_resume_reasons", "require_known_external_cashflow"}
ACCOUNT_EXECUTION_PROFILE_ENV = "FOREX_M20_ACCOUNT_EXECUTION_PROFILE"
ACCOUNT_EXECUTION_PROFILE_ID = "M1_EURUSD_DEMO"
ACCOUNT_EXECUTION_PROFILE_FIELDS = {"profile_id", "server", "currency", "symbol", "account_scope_sha256"}

M1_EVENT_RISK_POLICY_PATH = Path(__file__).resolve().parents[1] / "config" / "m1_event_risk_gate.json"
_M1_EVENT_RISK_POLICY_FIELDS = {"schema_version", "enabled", "scope", "required_context_state", "blackout_before_seconds", "blackout_after_seconds", "execution_authority", "activation_requirement"}


def _calendar_overlay(*, candidate: dict[str, Any], gate: dict[str, Any]) -> dict[str, Any]:
    """Build the small, self-contained overlay verified by the audit bridge."""
    refused = candidate["action"] in {"BUY", "SELL"} and gate["new_entry_permitted"] is False
    final = "NO_TRADE" if refused else candidate["action"]
    reason = ("CALENDAR_NEW_ENTRY_REFUSED:" if refused else "BASELINE_CANDIDATE_PRESERVED:") + gate["reason"]
    body = {"schema_version": "forex.m1-calendar-decision-overlay.v1", "candidate": candidate,
            "gate_observation": gate, "final_action": final, "reason": reason,
            "execution_authority": False}
    return {**body, "overlay_sha256": "sha256:" + hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()}


def _m1_event_risk_policy() -> dict[str, Any]:
    """Load the governed, disabled-by-default M1 calendar policy."""
    try:
        return json.loads(M1_EVENT_RISK_POLICY_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError:
        # A fixed ProgramData release contains no external-news package.  Its
        # shipped state is therefore explicitly inactive, never implicitly
        # enabled by a missing repository-relative configuration file.
        return {"schema_version": "forex.m1-event-risk-gate-policy.v1", "enabled": False,
                "scope": "NEW_ENTRY_ONLY", "required_context_state": "QUALIFIED_CONTEXT_ONLY",
                "blackout_before_seconds": 1800, "blackout_after_seconds": 900,
                "execution_authority": False,
                "activation_requirement": "A separately approved governed policy amendment and deployed context package are required before this evaluator may affect M1 entry eligibility."}
    except (OSError, json.JSONDecodeError) as error:
        raise SystemExit("M1 calendar event-risk policy is absent or invalid") from error


def evaluate_new_entry(*, policy: Any, sidecar: Any = None, primary_context: Any = None) -> dict[str, Any]:
    """Evaluate the shipped calendar seam without a repository-only import.

    The released policy is disabled.  Any future enabled policy must ship its
    approved context evaluator; until then this fixed endpoint refuses a new
    entry rather than silently changing authority.
    """
    valid_policy = (isinstance(policy, dict) and set(policy) == _M1_EVENT_RISK_POLICY_FIELDS
                    and policy.get("schema_version") == "forex.m1-event-risk-gate-policy.v1"
                    and isinstance(policy.get("enabled"), bool) and policy.get("scope") == "NEW_ENTRY_ONLY"
                    and policy.get("execution_authority") is False)
    if valid_policy and policy["enabled"] is False:
        return {"schema_version": "forex.m1-event-risk-gate.v1", "execution_authority": False,
                "scope": "NEW_ENTRY_ONLY", "state": "ANNOTATION_ONLY_DISABLED",
                "new_entry_permitted": None, "reason": "SHIPPED_POLICY_DISABLED_NO_EXECUTION_BEHAVIOR_CHANGE"}
    if valid_policy:
        return {"schema_version": "forex.m1-event-risk-gate.v1", "execution_authority": False,
                "scope": "NEW_ENTRY_ONLY", "state": "FAIL_SAFE_CONTEXT_UNAVAILABLE",
                "new_entry_permitted": False, "reason": "CALENDAR_GATE_IMPLEMENTATION_UNAVAILABLE"}
    return {"schema_version": "forex.m1-event-risk-gate.v1", "execution_authority": False,
            "scope": "NEW_ENTRY_ONLY", "state": "FAIL_SAFE_CONTEXT_UNAVAILABLE",
            "new_entry_permitted": False, "reason": "CALENDAR_GATE_POLICY_INVALID"}


def _apply_m1_calendar_overlay(*, snapshot: dict[str, Any], proposal: dict[str, Any],
                               policy: dict[str, Any], sidecar: Any = None,
                               primary_context: Any = None) -> tuple[dict[str, Any], dict[str, Any]]:
    """Bind a calendar new-entry veto before proposal persistence or reservation."""
    candidate = {"proposal_id": proposal["proposal_id"], "action": proposal["action"]}
    gate = evaluate_new_entry(policy=policy, sidecar=sidecar, primary_context=primary_context)
    overlay = _calendar_overlay(candidate=candidate, gate=gate)
    snapshot["calendar_overlay"] = overlay
    body = {key: value for key, value in snapshot.items()
            if key not in {"snapshot_id", "payload_sha256"}}
    digest = "sha256:" + hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    # The proposal identifier remains the formed baseline-candidate identity
    # that the overlay records.  Re-key the snapshot from its completed,
    # overlay-bound body so the retained snapshot identifier and digest agree
    # without creating an ID/digest cycle through that candidate reference.
    snapshot_id = str(uuid5(NAMESPACE_URL, f"{proposal['proposal_id']}:{digest}"))
    snapshot["snapshot_id"] = snapshot_id
    proposal["snapshot_id"] = snapshot_id
    snapshot["payload_sha256"] = digest
    proposal["decision_snapshot_sha256"] = digest
    if overlay["final_action"] == "NO_TRADE" and proposal["action"] in {"BUY", "SELL"}:
        proposal.update({"action": "NO_TRADE", "proposed_entry": None, "stop_loss": None,
                         "take_profit": None, "notional_usd": None, "confidence": 100,
                         "rationale": overlay["reason"]})
    return gate, overlay


def persistent_risk_policy() -> dict[str, Any]:
    """Load only the configuration-bound Option B risk policy."""
    try:
        policy = json.loads(os.environ["FOREX_M20_PERSISTENT_RISK_POLICY"])
    except (KeyError, json.JSONDecodeError) as error:
        raise SystemExit("M20 persistent risk policy is absent") from error
    expected = {
        "policy_version": "forex.m20.conservative-risk.v1", "reporting_currency": "AUD",
        "maximum_risk_per_trade_percent": .10, "maximum_risk_per_trade_aud": 100.0,
        "daily_loss_limit_percent": .50, "weekly_loss_limit_percent": 1.0,
        "peak_equity_drawdown_limit_percent": 2.0, "loss_budget_timezone": "Pacific/Auckland",
        "daily_pause_reset": "NEXT_AUCKLAND_DAY",
        "manual_resume_reasons": ["WEEKLY_LOSS", "PEAK_DRAWDOWN", "EXTERNAL_CASH_FLOW", "UNKNOWN_ACCOUNT_STATE"],
        "require_known_external_cashflow": True,
    }
    if not isinstance(policy, dict) or set(policy) != RISK_POLICY_REQUIRED or policy != expected:
        raise SystemExit("M20 persistent risk policy differs from approved Option B")
    return policy


def risk_account_snapshot(account: Any, captured_at: datetime) -> dict[str, Any]:
    policy = persistent_risk_policy()
    balance, equity = float(getattr(account, "balance", 0)), float(getattr(account, "equity", 0))
    if not all(math.isfinite(value) and value > 0 for value in (balance, equity)):
        raise SystemExit("M20 persistent risk policy requires known positive account balance and equity")
    login = getattr(account, "login", None)
    if getattr(account, "server", None) != SERVER or getattr(account, "currency", None) != "AUD" or type(login) is not int or login <= 0:
        raise SystemExit("M20 persistent risk policy requires the fixed Demo account identity")
    scope = hashlib.sha256(f"{SERVER}:{login}".encode()).hexdigest()
    local = captured_at.astimezone(ZoneInfo(policy["loss_budget_timezone"]))
    return {"balance": balance, "equity": equity, "account_scope_sha256": scope, "auckland_date": local.date().isoformat(), "auckland_week_start": (local.date() - timedelta(days=local.weekday())).isoformat()}


def _account_execution_profile() -> dict[str, str]:
    """Load the one local M1 execution profile; its account hash is never tracked."""
    try:
        profile = json.loads(os.environ[ACCOUNT_EXECUTION_PROFILE_ENV])
    except (KeyError, json.JSONDecodeError) as error:
        raise SystemExit("M20 M1_EURUSD_DEMO account execution profile is absent or unreadable") from error
    if (not isinstance(profile, dict) or set(profile) != ACCOUNT_EXECUTION_PROFILE_FIELDS
            or profile.get("profile_id") != ACCOUNT_EXECUTION_PROFILE_ID
            or profile.get("server") != SERVER or profile.get("currency") != "AUD"
            or profile.get("symbol") != SYMBOL):
        raise SystemExit("M20 M1_EURUSD_DEMO account execution profile is invalid")
    scope = profile.get("account_scope_sha256")
    if not isinstance(scope, str) or re.fullmatch(r"sha256:[0-9a-f]{64}", scope) is None:
        raise SystemExit("M20 M1_EURUSD_DEMO account execution profile scope is invalid")
    return {key: profile[key] for key in ACCOUNT_EXECUTION_PROFILE_FIELDS}


def _require_account_execution_profile(account: Any) -> None:
    """Fail closed unless the observed account is the local M1 execution profile."""
    try:
        login = getattr(account, "login", None)
        if (getattr(account, "server", None) != SERVER or getattr(account, "currency", None) != "AUD"
                or type(login) is not int or login <= 0):
            raise ValueError("observed account identity is invalid")
        actual = "sha256:" + hashlib.sha256(f"{SERVER}:{login}".encode()).hexdigest()
        if _account_execution_profile()["account_scope_sha256"] != actual:
            raise ValueError("observed account differs from M1_EURUSD_DEMO")
    except (TypeError, ValueError, SystemExit) as error:
        _bridge({}, "pause-unknown-account-state")
        raise SystemExit(f"M20 account execution profile mismatch: {error}") from error


def _terminal_submission_refusal(account: Any) -> str | None:
    """Return a safe entry refusal before the sole MT5 order call."""
    try:
        terminal = mt5.terminal_info()
    except Exception:
        return "M1_TERMINAL_CAPABILITY_UNAVAILABLE: MT5 terminal capability is unavailable at submission recheck."
    if terminal is None or getattr(terminal, "connected", None) is not True:
        return "M1_TERMINAL_CAPABILITY_UNAVAILABLE: MT5 terminal capability is unavailable at submission recheck."
    if getattr(terminal, "trade_allowed", None) is not True or getattr(terminal, "tradeapi_disabled", None) is not False:
        return "M1_TERMINAL_TRADING_DISABLED: MT5 terminal AutoTrading or API trading is disabled."
    if getattr(account, "trade_allowed", None) is not True or getattr(account, "trade_expert", None) is not True:
        return "M1_ACCOUNT_TRADING_DISABLED: MT5 account trading permission is disabled."
    return None


def _entry_risk_snapshot(account: Any, captured_at: datetime) -> dict[str, Any]:
    try:
        return risk_account_snapshot(account, captured_at)
    except (SystemExit, TypeError, ValueError):
        _bridge({}, "pause-unknown-account-state")
        raise


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
        ("maximum_duration_minutes", 0, 60),
        ("maximum_open_positions", 1, 1),
        ("maximum_notional_per_trade_usd", 1, 10000),
        ("maximum_cumulative_notional_usd", 1, 100000),
    )
    for field, lower, upper in limits:
        value = payload[field]
        if isinstance(value, bool) or not isinstance(value, int) or not lower <= value <= upper:
            raise SystemExit(f"M20 session lease {field} is outside its fixed cap")
    maximum_loss = payload["maximum_loss_per_trade_aud"]
    if (isinstance(maximum_loss, bool) or not isinstance(maximum_loss, (int, float))
            or float(maximum_loss) not in {REFUSAL_DRILL_MAXIMUM_LOSS_AUD, 100.0}):
        raise SystemExit("M20 session lease maximum_loss_per_trade_aud is outside its fixed cap")
    if payload["maximum_trades"] is not None:
        raise SystemExit("M20 session lease maximum_trades is invalid")
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


def _bar_rows(rates: Any, *, timeframe_name: str, seconds: int, cutoff: int,
              timestamp_offset_seconds: int, receipt_at: datetime | None = None) -> tuple[list[dict[str, Any]], str]:
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
        # MT5 bars do not carry a publication timestamp.  For entry evidence,
        # retain the local instant at which this fixed read received every
        # completed M1 candle.  The row is hash-bound into the immutable
        # snapshot and proposal before any reservation can occur.
        if receipt_at is not None:
            row["available_at_utc"] = utc(receipt_at)
        ohlc = (row["open"], row["high"], row["low"], row["close"])
        if (not all(math.isfinite(value) for value in ohlc) or min(ohlc) <= 0
                or row["low"] > min(row["open"], row["close"])
                or row["high"] < max(row["open"], row["close"])):
            raise SystemExit(f"EURUSD {timeframe_name} candle has invalid OHLC")
        rows.append(row)
    rows = rows[-CLOSED_BAR_COUNT:]
    if len(rows) != CLOSED_BAR_COUNT:
        raise SystemExit(f"expected exactly {CLOSED_BAR_COUNT} closed EURUSD {timeframe_name} candles")
    raw = json.dumps(rows, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return rows, hashlib.sha256(raw).hexdigest()


def _entry_m1_history_is_synchronized(*, rows: list[dict[str, Any]], observed_at: datetime,
                                      receipt_cutoff: datetime | None = None) -> bool:
    """Accept an entry window only when it ends at the observed M1 boundary.

    This is deliberately an entry-data gate.  Position monitoring keeps using
    its existing closed-bar reader so a terminal-history delay cannot suppress
    broker SL/TP, owner wall-clock exits, or other protective management.
    """
    if len(rows) != CLOSED_BAR_COUNT:
        return False
    boundary = int(observed_at.timestamp()) // 60 * 60
    previous_closed_at: int | None = None
    for row in rows:
        try:
            opened_at = int(parse_utc(row["opened_at_utc"], "M1 opened_at_utc").timestamp())
            closed_at = int(parse_utc(row["closed_at_utc"], "M1 closed_at_utc").timestamp())
            available_at = (parse_utc(row["available_at_utc"], "M1 available_at_utc")
                            if receipt_cutoff is not None else None)
        except (KeyError, TypeError, ValueError, SystemExit):
            return False
        if closed_at - opened_at != 60 or closed_at > boundary:
            return False
        if available_at is not None and (available_at < datetime.fromtimestamp(closed_at, timezone.utc)
                                         or available_at > receipt_cutoff):
            return False
        if previous_closed_at is not None and opened_at != previous_closed_at:
            return False
        previous_closed_at = closed_at
    return previous_closed_at == boundary


def _current_entry_inputs(*, offset_seconds: int, expected_boundary: int | None = None, expected_m1_digest: str | None = None) -> tuple[Any | None, list[dict[str, Any]], str | None]:
    """Read a fresh quote and its complete M1 window at the current UTC time.

    This is used both at capture and immediately after reservation.  A failed
    recheck is deliberately an entry refusal only: it has no bearing on the
    monitor's broker protection or owner wall-clock exits.
    """
    tick = mt5.symbol_info_tick(SYMBOL)
    if not tick:
        return None, [], "M1_INPUT_UNAVAILABLE: EURUSD quote is unavailable at submission recheck."
    observed_at = datetime.fromtimestamp(int(getattr(tick, "time", 0)), timezone.utc) - timedelta(seconds=offset_seconds)
    # Copying terminal rates can block through a synchronization boundary.
    # Read the wall clock only after every broker read below.
    checked_at = datetime.now(timezone.utc)
    freshness_seconds = (checked_at - observed_at).total_seconds()
    bid, ask = float(getattr(tick, "bid", 0)), float(getattr(tick, "ask", 0))
    if (not 0 <= freshness_seconds <= MAX_TICK_AGE_SECONDS or not math.isfinite(bid) or not math.isfinite(ask) or bid <= 0 or ask < bid
            or int(observed_at.timestamp()) // 60 != int(checked_at.timestamp()) // 60):
        return tick, [], "M1_INPUT_UNAVAILABLE: EURUSD quote is stale or invalid at submission recheck."
    try:
        rows, digest = _bar_rows(
            mt5.copy_rates_from_pos(SYMBOL, mt5.TIMEFRAME_M1, 1, CLOSED_BAR_COUNT + 8),
            timeframe_name="M1", seconds=60,
            cutoff=int(observed_at.timestamp()) // 60 * 60,
            timestamp_offset_seconds=offset_seconds,
        )
    except (SystemExit, KeyError, TypeError, ValueError, OverflowError):
        return tick, [], "M1_INPUT_UNAVAILABLE: closed M1 history is invalid or insufficient at submission recheck."
    checked_at = datetime.now(timezone.utc)
    boundary = int(checked_at.timestamp()) // 60 * 60
    freshness_seconds = (checked_at - observed_at).total_seconds()
    if (not 0 <= freshness_seconds <= MAX_TICK_AGE_SECONDS
            or int(observed_at.timestamp()) // 60 != int(checked_at.timestamp()) // 60
            or expected_boundary is not None and boundary != expected_boundary
            or expected_m1_digest is not None and digest != expected_m1_digest
            or not _entry_m1_history_is_synchronized(rows=rows, observed_at=checked_at)):
        return tick, rows, "M1_INPUT_UNSYNCHRONIZED: closed M1 history does not end at the current quote minute."
    return tick, rows, None


def _shadow_context_rows(*, timeframe_name: str, timeframe: Any, seconds: int, observed_at: datetime, timestamp_offset_seconds: int) -> tuple[list[dict[str, Any]], str | None]:
    """Read fixed native closed context candles without blocking M1 execution.

    M20.12 records absence or invalidity as visible `UNAVAILABLE` context. It
    never turns a higher-timeframe read problem into a M1 order refusal.
    """
    try:
        rates = mt5.copy_rates_from_pos(SYMBOL, timeframe, 1, CLOSED_BAR_COUNT + 8)
        rows, digest = _bar_rows(
            rates, timeframe_name=timeframe_name, seconds=seconds,
            cutoff=int(observed_at.timestamp()) // seconds * seconds,
            timestamp_offset_seconds=timestamp_offset_seconds,
        )
        return [{"timeframe": timeframe_name, **row} for row in rows], digest
    except (SystemExit, TypeError, ValueError, KeyError):
        return [], None


def _shadow_context(*, proposal: dict[str, Any], selection: dict[str, Any], assessments: list[dict[str, Any]], bars: dict[str, list[dict[str, Any]]], observed_at: str, spread_points: float, pre_context_owner: str | None = None, pre_context_candidate: str | None = None) -> dict[str, Any]:
    """Classify fixed closed M5/H1 candles as non-authoritative context."""
    observed = parse_utc(observed_at, "observed_at_utc")
    signals = {str(item.get("id")): str(item.get("signal")) for item in assessments}
    owner = pre_context_owner if pre_context_owner is not None else selection.get("selected_strategy_id")
    candidate = pre_context_candidate if pre_context_candidate is not None else (signals.get(str(owner), "NO_TRADE") if owner else "NO_TRADE")

    def one(timeframe: str, seconds: int) -> dict[str, Any]:
        rows = bars.get(timeframe, [])
        if len(rows) < 5:
            return {
                "timeframe": timeframe, "closed_at_utc": None, "data_age_seconds": None,
                "integrity_status": "UNAVAILABLE", "market_state": "UNKNOWN",
                "volatility_state": "UNKNOWN", "liquidity_state": "UNKNOWN",
                "alignment": "UNAVAILABLE", "reason": f"No usable closed {timeframe} context candle was returned.",
                "source_inputs": {"selected_m1_owner": owner, "pre_context_m1_candidate": candidate,
                                  "final_m1_action": proposal["action"], "rows_returned": len(rows)},
            }
        latest = rows[-1]
        closed_at = parse_utc(latest["closed_at_utc"], "closed_at_utc")
        age = max(0, round((observed - closed_at).total_seconds()))
        recent = rows[-5:]
        start, end = float(recent[0]["close"]), float(recent[-1]["close"])
        ranges = [max(0.0, float(row["high"]) - float(row["low"])) / 0.00001 for row in recent]
        average_range = sum(ranges) / len(ranges)
        trend_points = (end - start) / 0.00001
        threshold = max(2.0, average_range * 0.25)
        market_state = "BULLISH" if trend_points > threshold else "BEARISH" if trend_points < -threshold else "RANGE"
        volatility = "HIGH" if average_range > 30 else "LOW" if average_range < 8 else "NORMAL"
        liquidity = "THIN" if spread_points > 12 or min(int(row["volume"]) for row in recent) <= 0 else "LIQUID"
        if candidate == "BUY" and market_state == "BULLISH":
            alignment = "ALIGNED"
        elif candidate == "SELL" and market_state == "BEARISH":
            alignment = "ALIGNED"
        elif candidate in {"BUY", "SELL"} and market_state in {"BULLISH", "BEARISH"}:
            alignment = "OPPOSED"
        else:
            alignment = "NEUTRAL"
        return {
            "timeframe": timeframe, "closed_at_utc": latest["closed_at_utc"], "data_age_seconds": age,
            "integrity_status": "VALID", "market_state": market_state,
            "volatility_state": volatility, "liquidity_state": liquidity, "alignment": alignment,
            "reason": f"Five-candle close change {trend_points:.1f} pts; average range {average_range:.1f} pts; M1 candidate {candidate}.",
            "source_inputs": {"selected_m1_owner": owner, "pre_context_m1_candidate": candidate,
                              "final_m1_action": proposal["action"], "latest_close": end,
                              "five_candle_start_close": start, "trend_points": round(trend_points, 3),
                              "average_range_points": round(average_range, 3),
                              "observed_spread_points": round(spread_points, 3),
                              "native_period_seconds": seconds},
        }

    contexts = [one("M5", 5 * 60), one("H1", 60 * 60)]
    alignments = {item["alignment"] for item in contexts}
    if "OPPOSED" in alignments:
        overall, disposition = "OPPOSED", "HARD_CONFLICT"
        reason = "At least one available higher timeframe opposes the selected M1 candidate; recorded only."
    elif candidate in {"BUY", "SELL"} and alignments == {"ALIGNED"}:
        overall, disposition = "ALIGNED", "OBSERVE_ONLY"
        reason = "Both available higher timeframes align with the selected M1 candidate; recorded only."
    elif "UNAVAILABLE" in alignments:
        overall, disposition = "NEUTRAL", "NEUTRAL"
        reason = "One or more higher-timeframe inputs are unavailable; M1 authority is unchanged."
    else:
        overall, disposition = "NEUTRAL", "OBSERVE_ONLY"
        reason = "Available higher-timeframe context is mixed, ranging, or has no selected M1 candidate."
    source_inputs = {"m1_candidate_action": candidate, "selected_m1_strategy": owner, "final_proposal_action": proposal["action"], "m1_strategy_version": proposal["strategy_version"], "contexts": [item["source_inputs"] for item in contexts]}
    source_inputs_sha256 = "sha256:" + hashlib.sha256(json.dumps(source_inputs, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    context_id = str(uuid5(NAMESPACE_URL, f"{proposal['proposal_id']}:{source_inputs_sha256}"))
    return {
        "context_id": context_id, "proposal_id": proposal["proposal_id"], "selected_m1_action": proposal["action"],
        "overall_alignment": overall, "context_disposition": disposition, "reason": reason,
        "rule_version": SHADOW_CONTEXT_RULE_VERSION, "retrieved_at_utc": observed_at,
        "source_inputs_sha256": source_inputs_sha256, "contexts": contexts,
    }


_BRIDGE_PROCESS: subprocess.Popen[str] | None = None
_BRIDGE_RESPONSES: Queue[str | None] | None = None
_BRIDGE_LOCK = Lock()
_RUNNER_BRIDGE_COMMANDS = {
    "pause-unknown-account-state", "record-historical-reconciliation",
    "record-closed-outcome", "update-open-position", "load-open-positions",
    "pre-isolation-readiness",
    "enforce-risk-policy", "persist-proposal", "reconcile", "reserve-execution",
    "record-result", "record-open-position",
}


def _bridge_reader(stream: Any, responses: Queue[str | None]) -> None:
    try:
        for line in stream:
            responses.put(line)
    finally:
        responses.put(None)


def _start_bridge_before_mt5() -> None:
    """Start the existing fixed WSL audit bridge before child creation is banned."""
    global _BRIDGE_PROCESS, _BRIDGE_RESPONSES
    if _BRIDGE_PROCESS is not None:
        raise SystemExit("M20 audit bridge lifecycle is already active")
    bridge_path = Path(__file__).with_name("m20_postgres_audit_bridge.payload")
    expected = os.environ.get("FOREX_M20_POSTGRES_AUDIT_BRIDGE_SHA256", "")
    actual = "sha256:" + hashlib.sha256(bridge_path.read_bytes()).hexdigest()
    if expected != actual:
        raise SystemExit("M20 PostgreSQL audit bridge is absent or differs from its fixed deployment hash")
    dsn = os.environ.get("FOREX_M20_POSTGRES_DSN", "")
    profile = os.environ.get("USERPROFILE", "")
    if not dsn or not profile.startswith("C:\\Users\\"):
        raise SystemExit("M20 PostgreSQL bridge WSL prerequisites are absent")
    drive = bridge_path.drive.rstrip(":").lower()
    wsl_bridge = "/mnt/" + drive + "/" + "/".join(bridge_path.parts[1:])
    process = subprocess.Popen(
        ["wsl.exe", "-d", "Ubuntu", "--", "env", f"FOREX_M20_POSTGRES_DSN={dsn}",
         "python3", wsl_bridge, "serve"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        text=True, bufsize=1,
    )
    if process.stdin is None or process.stdout is None:
        process.kill()
        raise SystemExit("M20 PostgreSQL audit bridge pipes are unavailable")
    responses: Queue[str | None] = Queue(maxsize=2)
    Thread(target=_bridge_reader, args=(process.stdout, responses), daemon=True).start()
    _BRIDGE_PROCESS, _BRIDGE_RESPONSES = process, responses
    try:
        ready = _bridge({}, "ready")
        if ready.get("marker") != "FOREX_M20_AUDIT_BRIDGE_READY":
            raise SystemExit("M20 PostgreSQL audit bridge readiness was not confirmed")
    except BaseException:
        _close_bridge()
        raise


def _close_bridge() -> None:
    """Close and reap the per-runner WSL child; never leave an audit helper alive."""
    global _BRIDGE_PROCESS, _BRIDGE_RESPONSES
    process, _BRIDGE_PROCESS = _BRIDGE_PROCESS, None
    _BRIDGE_RESPONSES = None
    if process is None:
        return
    try:
        if process.stdin:
            process.stdin.close()
        process.wait(timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        try:
            process.terminate()
            process.wait(timeout=5)
        except (OSError, subprocess.TimeoutExpired):
            process.kill()
            process.wait(timeout=5)


def _enforce_no_child_launch() -> None:
    """Irreversibly block child creation before importing/using the MT5 terminal."""
    if os.name != "nt":
        raise SystemExit("M20 single-client restriction requires Windows")
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    kernel.SetProcessMitigationPolicy.argtypes = [ctypes.c_int, ctypes.c_void_p, ctypes.c_size_t]
    kernel.SetProcessMitigationPolicy.restype = wintypes.BOOL
    kernel.GetProcessMitigationPolicy.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, ctypes.c_size_t]
    kernel.GetProcessMitigationPolicy.restype = wintypes.BOOL
    flags, observed = wintypes.DWORD(1), wintypes.DWORD()
    if not kernel.SetProcessMitigationPolicy(13, ctypes.byref(flags), ctypes.sizeof(flags)):
        raise SystemExit("M20 single-client child restriction could not be applied")
    if (not kernel.GetProcessMitigationPolicy(kernel.GetCurrentProcess(), 13, ctypes.byref(observed), ctypes.sizeof(observed))
            or observed.value != 1):
        raise SystemExit("M20 single-client child restriction was not verified")
    try:
        subprocess.run([sys.executable, "-c", "pass"], check=True, capture_output=True, timeout=5)
    except OSError as error:
        if error.winerror == 367:
            return
    raise SystemExit("M20 single-client child restriction canary failed")


def _bridge(payload: dict[str, Any], command: str) -> dict[str, Any]:
    """Use the prestarted, hash-bound WSL bridge after MT5 isolation begins.

    MT5 remains in Windows. PostgreSQL is loopback-bound inside T480 WSL, so
    the audit process must run there rather than opening a Windows-to-WSL port
    path that could silently target a different local service.
    """
    process, responses = _BRIDGE_PROCESS, _BRIDGE_RESPONSES
    if command not in _RUNNER_BRIDGE_COMMANDS and command != "ready":
        raise SystemExit("M20 PostgreSQL audit bridge command is not permitted for the runner")
    if process is None or responses is None or process.stdin is None or process.poll() is not None:
        raise SystemExit("M20 PostgreSQL audit bridge is unavailable")
    request = json.dumps({"command": command, "payload": payload}, separators=(",", ":"))
    if len(request) > 1_048_576:
        raise SystemExit("M20 PostgreSQL audit bridge request is too large")
    with _BRIDGE_LOCK:
        try:
            process.stdin.write(request + "\n")
            process.stdin.flush()
            encoded = responses.get(timeout=10)
        except (OSError, Empty) as error:
            raise SystemExit("M20 PostgreSQL audit bridge did not acknowledge the request") from error
    if encoded is None or len(encoded) > 1_048_576:
        raise SystemExit("M20 PostgreSQL audit bridge response is unavailable")
    try:
        response = json.loads(encoded)
    except json.JSONDecodeError as error:
        raise SystemExit("M20 PostgreSQL audit bridge returned invalid JSON") from error
    result = response.get("result") if isinstance(response, dict) and response.get("ok") is True else None
    if not isinstance(result, dict) or result.get("ok") is not True:
        raise SystemExit("M20 PostgreSQL audit bridge did not confirm its write")
    return result


def _run_single_client(operation: Any, *, requires_bridge: bool) -> Any:
    """Make one runner invocation unable to spawn a replacement MT5 terminal."""
    if requires_bridge:
        _start_bridge_before_mt5()
    try:
        _enforce_no_child_launch()
        return operation()
    finally:
        _close_bridge()


def audit_isolation_spike() -> dict[str, Any]:
    """Read the fixed audit state twice after restriction; never contacts MT5."""
    first = _bridge({}, "load-open-positions").get("open_positions")
    second = _bridge({}, "load-open-positions").get("open_positions")
    if not isinstance(first, list) or not isinstance(second, list):
        raise SystemExit("M20 audit isolation spike did not receive fixed open-position data")
    return {
        "marker": "FOREX_M30_AUDIT_ISOLATION_SPIKE_OK",
        "child_policy_verified": True,
        "first_open_positions_count": len(first),
        "second_open_positions_count": len(second),
        "mt5_called": False,
        "broker_mutation": "NONE",
    }


def pre_isolation_readiness() -> dict[str, Any]:
    """Read the fixed durable no-work predicate through the prestarted bridge."""
    result = _bridge({}, "pre-isolation-readiness")
    required = {"ok", "marker", "captured_at_utc", "durable_open_positions_count",
                "unresolved_execution_attempts_count", "clear"}
    if (set(result) != required or result.get("ok") is not True
            or result.get("marker") != "FOREX_M30_PRE_ISOLATION_READINESS"
            or not isinstance(result.get("clear"), bool)
            or not all(isinstance(result.get(key), int) and result[key] >= 0
                       for key in ("durable_open_positions_count", "unresolved_execution_attempts_count"))):
        raise SystemExit("M30 pre-isolation readiness response is invalid")
    return {**result, "broker_mutation": "NONE"}


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


def _risk_levels(*, action: str, entry: float, volume: float, tick_size: float, tick_value_loss: float, point: float, maximum_loss_aud: float) -> tuple[float, float, float]:
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


def _strategy_assessments(*, m1: list[dict[str, Any]], tick: dict[str, Any], active_action: str = "NO_TRADE") -> list[dict[str, Any]]:
    """Compare five fixed M1 hypotheses on one immutable candle snapshot.

    All five strategy contracts are available for the M20.11 Demo trial.
    Regime selection below, not this comparison table, grants exactly one
    owner authority for any assessment.
    """
    point = 0.00001
    spread_points = float(tick["spread_points"])

    def record(identifier: str, label: str, signal: str, reason: str, *, active: bool = False) -> dict[str, Any]:
        return {"id": identifier, "label": label, "signal": signal, "eligible_for_execution": active, "reason": reason}

    if len(m1) < 12:
        unavailable = "Needs twelve completed M1 candles."
        return [
            record("momentum_breakout", "Momentum breakout", active_action, "Closed-candle breakout assessment.", active=True),
            record("compression_breakout", "Compression breakout", "NO_TRADE", unavailable, active=True),
            record("trend_pullback", "Trend pullback", "NO_TRADE", unavailable, active=True),
            record("range_reversion", "Range reversion", "NO_TRADE", unavailable, active=True),
            record("session_breakout", "Session breakout", "NO_TRADE", unavailable, active=True),
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
        lambda: record("momentum_breakout", "Momentum breakout", breakout_signal, "Rule: two aligned candles, range break, and spread check.", active=True),
        lambda: record("compression_breakout", "Compression breakout", compression_signal, f"Prior five-candle range {compression_points:.1f} pts; limit {compression_limit:.1f} pts.", active=True),
        lambda: record("trend_pullback", "Trend pullback", pullback_signal, "Trend, pullback, and resumption checks are " + ("aligned." if pullback_signal != "NO_TRADE" else "not aligned."), active=True),
        lambda: record("range_reversion", "Range reversion", reversion_signal, "Range-edge rejection check is " + ("present." if reversion_signal != "NO_TRADE" else "not present."), active=True),
        lambda: record("session_breakout", "Session breakout", session_signal, f"UTC hour {observed_hour:02d}; liquid-session={liquid_session}, normal-spread={normal_spread}.", active=True),
    )
    with ThreadPoolExecutor(max_workers=len(rules), thread_name_prefix="m20-strategy") as executor:
        return list(executor.map(lambda rule: rule(), rules))


def _market_selection(*, tick: dict[str, Any], m1: list[dict[str, Any]], assessments: list[dict[str, Any]], safety_gates: dict[str, bool]) -> dict[str, Any]:
    """Classify one market regime and select at most one fixed strategy.

    The order is a deterministic M20.11 policy. It classifies the first
    signal under regime precedence and grants only that selected strategy
    executable ownership. Other signals remain recorded context.
    """
    if not all(safety_gates.values()) or int(tick["freshness_seconds"]) > MAX_TICK_AGE_SECONDS or float(tick["spread_points"]) > 12.0 or len(m1) < 12:
        reason = "Freshness, spread, or completed-candle safety gate is not satisfied."
        return {"market_regime": "UNSAFE_OR_UNTRADEABLE", "market_regime_reason": reason,
                "selected_strategy_id": None, "strategy_rule_version": None,
                "selection_status": "NO_SELECTION"}
    by_id = {item["id"]: item for item in assessments}
    for regime, strategy_id in STRATEGY_REGIMES:
        signal = by_id[strategy_id]["signal"]
        if signal in {"BUY", "SELL"}:
            return {
                "market_regime": regime,
                "market_regime_reason": f"{by_id[strategy_id]['label']} produced {signal} under deterministic regime precedence.",
                "selected_strategy_id": strategy_id,
                "strategy_rule_version": f"forex.m20.11.{strategy_id}.v2",
                "selection_status": "SELECTED_EXECUTABLE",
            }
    return {"market_regime": "NO_CLEAR_REGIME", "market_regime_reason": "No fixed M1 strategy produced an eligible market signal.",
            "selected_strategy_id": None, "strategy_rule_version": None, "selection_status": "NO_SELECTION"}


def financing_policy() -> dict[str, Any]:
    """Load the explicit Demo or later-Live financing policy; never alter exits."""
    try:
        policy = json.loads(os.environ['FOREX_M20_FINANCING_POLICY'])
        if policy['policy_version'] not in {'forex.m20.financing.v1', 'forex.m20.financing.v2'} or policy['exit_mode'] != 'EXISTING_OWNER_EXITS':
            raise ValueError('unsupported mandate')
        return policy
    except (KeyError, ValueError, TypeError) as error:
        raise SystemExit('M20 financing mandate is absent or invalid') from error


def project_financing(*, terms: dict[str, Any], action: str, volume: float,
                      now: datetime, horizon: datetime, policy: dict[str, Any]) -> dict[str, Any]:
    """Signed points-mode EURUSD financing; explicit calendar, no guessed fees.

    USD debits convert at AUDUSD bid; credits at ask. Unsupported broker modes
    remain unqualified. Calendar coverage includes the entire holding horizon.
    """
    result = {'status': 'UNKNOWN', 'policy_version': policy.get('policy_version'),
              'expected_swap_aud': None, 'commission_allowance_aud': None,
              'adverse_financing_aud': None, 'reason': None, 'inputs': terms,
              'mandate': policy, 'horizon_utc': utc(horizon)}
    try:
        def finite(value: Any, positive: bool = False) -> float:
            if isinstance(value, bool): raise ValueError('invalid numeric value')
            value = float(value)
            if not math.isfinite(value) or (positive and value <= 0): raise ValueError('invalid numeric value')
            return value
        if action not in {'BUY', 'SELL'} or horizon < now: raise ValueError('invalid action/horizon')
        volume = finite(volume, True)
        basis = policy.get('qualification_basis', 'BROKER_CALENDAR')
        if basis == 'DEFERRED_FOR_DEMO':
            if policy.get('policy_version') != 'forex.m20.financing.v2':
                raise ValueError('unsupported deferred Demo financing policy')
            # Chris explicitly deferred financing and rollover qualification to
            # Live readiness. This fixed Demo-only runner records that fact and
            # never invents a fee, swap, calendar, or overnight authority.
            result.update(status='DEFERRED_FOR_DEMO', expected_swap_aud=0.0,
                          commission_allowance_aud=0.0, adverse_financing_aud=0.0,
                          multiplier=0, reason='FINANCING_POLICY_DEFERRED_FOR_DEMO',
                          calendar_source=None, charge_source=None)
            return result
        age = (now - parse_utc(terms['captured_at_utc'], 'financing capture')).total_seconds()
        quote_age = (now - parse_utc(terms['conversion_at_utc'], 'conversion quote')).total_seconds()
        maximum_age = finite(policy['maximum_quote_age_seconds'], True)
        if not 0 <= age <= maximum_age or not 0 <= quote_age <= maximum_age:
            raise ValueError('stale financing/conversion observation')
        if terms['server'] != SERVER or terms['symbol'] != SYMBOL or terms['profit_currency'] != 'USD':
            raise ValueError('unsupported financing surface')
        if terms['swap_mode'] != 1 or isinstance(terms['swap_mode'], bool):
            raise ValueError('unsupported swap mode')
        bid, ask = finite(terms['audusd_bid'], True), finite(terms['audusd_ask'], True)
        if ask < bid: raise ValueError('crossed conversion quote')
        start = parse_utc(policy['calendar_valid_from_utc'], 'calendar start')
        end = parse_utc(policy['calendar_valid_until_utc'], 'calendar end')
        if not start <= now <= horizon < end or not policy['calendar_source']:
            raise ValueError('unqualified rollover calendar coverage')
        fee_per_lot = finite(policy['round_trip_charge_aud_per_lot'])
        if fee_per_lot < 0 or not policy['charge_source']: raise ValueError('unqualified commission/fee terms')
        if basis not in {'BROKER_CALENDAR', 'DEMO_CONSERVATIVE_INTRADAY'}:
            raise ValueError('unsupported qualification basis')
        if basis == 'DEMO_CONSERVATIVE_INTRADAY':
            # Temporary operator-authorised estimate, never account tariff proof.
            # Both endpoints must be inside one weekday window; no rollover
            # calendar or holiday multiplier is invented for excluded hours.
            opening = finite(policy['entry_start_hour_utc'])
            closing = finite(policy['exit_by_hour_utc'])
            now = now.astimezone(timezone.utc)
            horizon = horizon.astimezone(timezone.utc)
            if not (6 <= opening < closing <= 18) or fee_per_lot < 6:
                raise ValueError('invalid conservative Demo bounds')
            if (now.weekday() >= 5 or now.date() != horizon.date()
                    or now.hour + now.minute / 60 < opening
                    or horizon.hour + horizon.minute / 60 + horizon.second / 3600 >= closing
                    or (horizon - now).total_seconds() > max(OWNER_MAX_HOLD_SECONDS.values())):
                raise ValueError('outside conservative Demo intraday window')
            result.update(status='DEMO_ESTIMATE', expected_swap_aud=0.0,
                          commission_allowance_aud=fee_per_lot * volume,
                          adverse_financing_aud=0.0, multiplier=0,
                          reason='PUBLIC_TERMS_INTRADAY_ESTIMATE_NOT_ACCOUNT_FEE_PROOF',
                          calendar_source=policy['calendar_source'], charge_source=policy['charge_source'])
            return result
        swap_points = finite(terms['swap_long'] if action == 'BUY' else terms['swap_short'])
        per_day_usd = swap_points * finite(terms['point'], True) * finite(terms['contract_size'], True) * volume
        multipliers = 0.0
        seen = set()
        for row in policy['rollovers']:
            at = parse_utc(row['at_utc'], 'rollover')
            multiplier = finite(row['multiplier'])
            if at in seen or multiplier < 0 or not start <= at < end:
                raise ValueError('invalid/duplicate rollover calendar event')
            seen.add(at)
            if now <= at <= horizon: multipliers += multiplier
        signed_usd = per_day_usd * multipliers
        signed_aud = signed_usd / (bid if signed_usd < 0 else ask)
        # Keep full precision for risk; round only when presenting or reconciling.
        result.update(status='QUALIFIED_INPUTS', expected_swap_aud=signed_aud,
                      commission_allowance_aud=fee_per_lot * volume,
                      adverse_financing_aud=max(0.0, -signed_aud),
                      reason='POINTS_MODE_WITH_DECLARED_CALENDAR', multiplier=multipliers,
                      horizon_utc=utc(horizon), inputs=terms, calendar_source=policy['calendar_source'],
                      charge_source=policy['charge_source'])
    except (KeyError, TypeError, ValueError, OverflowError, SystemExit) as error:
        result['reason'] = str(error)
    return result


def review_holding(*, forecast_lower_bound_aud: float | None, benefit_buffer_aud: float | None,
                   forecast_qualified: bool, risk_allowed: bool,
                   financing: dict[str, Any]) -> dict[str, Any]:
    """Read-only recommendation; W1 grants no forecast or new exit authority.

    Forecast is incremental executable-price benefit minus incremental exit
    friction, before future swap. Entry costs/accrued charges are already sunk.
    """
    if financing.get('status') != 'QUALIFIED_INPUTS' or not forecast_qualified:
        return {'decision': 'REVIEW_REQUIRED', 'reason': 'COST_OR_HORIZON_EVIDENCE_UNQUALIFIED', 'execution_authority': False}
    values = (forecast_lower_bound_aud, benefit_buffer_aud, financing.get('expected_swap_aud'))
    if any(v is None or isinstance(v, bool) or not math.isfinite(float(v)) for v in values) or benefit_buffer_aud < 0:
        return {'decision': 'REVIEW_REQUIRED', 'reason': 'INVALID_FORECAST_BOUND', 'execution_authority': False}
    lower = float(forecast_lower_bound_aud) + float(financing['expected_swap_aud'])
    return {'decision': 'HOLD' if risk_allowed and lower > benefit_buffer_aud else 'CLOSE',
            'reason': 'INCREMENTAL_VALUE_AND_RISK', 'conservative_incremental_aud': lower,
            'execution_authority': False}


def financing_preview(terminal_path: str) -> dict[str, Any]:
    """Fixed read-only deployed calculator proof; no order or ledger mutation."""
    if not mt5.initialize(path=terminal_path): raise SystemExit('Demo terminal unavailable')
    try:
        account = mt5.account_info()
        if not account or account.server != SERVER or account.currency != 'AUD':
            raise SystemExit('Demo AUD account required')
        symbol = mt5.symbol_info(SYMBOL)
        if not symbol: raise SystemExit('EURUSD unavailable')
        now = datetime.now(timezone.utc)
        policy = financing_policy()
        terms = _financing_terms(symbol, now)
        projections = {side: project_financing(terms=terms, action=side, volume=float(symbol.volume_min), now=now,
                       horizon=now + timedelta(seconds=max(OWNER_MAX_HOLD_SECONDS.values())), policy=policy) for side in ('BUY', 'SELL')}
        return {'server': account.server, 'captured_at_utc': utc(now), 'projections': projections,
                'order_submitted': False, 'new_holding_authority': False, 'exit_mode': policy['exit_mode']}
    finally:
        mt5.shutdown()


def _financing_terms(symbol: Any, captured_at: datetime) -> dict[str, Any]:
    conversion = mt5.symbol_info_tick('AUDUSD')
    return {'captured_at_utc': utc(captured_at), 'server': SERVER, 'symbol': SYMBOL,
            'profit_currency': getattr(symbol, 'currency_profit', None),
            'swap_mode': getattr(symbol, 'swap_mode', None),
            'swap_long': getattr(symbol, 'swap_long', None), 'swap_short': getattr(symbol, 'swap_short', None),
            'point': getattr(symbol, 'point', None), 'contract_size': getattr(symbol, 'trade_contract_size', None),
            'audusd_bid': getattr(conversion, 'bid', None), 'audusd_ask': getattr(conversion, 'ask', None),
            'conversion_at_utc': utc(datetime.fromtimestamp(int(getattr(conversion, 'time', 0)), timezone.utc)
                                     - timedelta(seconds=tick_time_offset_seconds()))}


def _project_cost_coverage(*, action: str, entry: float, take_profit: float, risk: dict[str, float]) -> dict[str, Any]:
    """Project minimum profitable outcome from fixed, explicit M20 inputs."""
    if action not in {"BUY", "SELL"}:
        return {"entry_spread_cost_aud": None, "expected_exit_spread_cost_aud": None,
                "commission_allowance_aud": None, "slippage_allowance_aud": None,
                "expected_swap_aud": None, "projected_gross_profit_at_take_profit_aud": None,
                "estimated_round_trip_cost_aud": None, "minimum_net_profit_aud": None,
                "expected_net_profit_at_take_profit_aud": None, "cost_coverage_status": "NOT_APPLICABLE"}
    spread = max(0.0, float(risk["observed_spread"]))
    value_per_price = float(risk["volume"]) * float(risk["tick_value_loss"]) / float(risk["tick_size"])
    entry_spread = spread * value_per_price
    exit_spread = spread * EXPECTED_EXIT_SPREAD_MULTIPLIER * value_per_price
    slippage = spread * EXPECTED_SLIPPAGE_SPREAD_MULTIPLIER * value_per_price
    financing = risk.get("financing", {})
    if financing.get("status") not in {"QUALIFIED_INPUTS", "DEMO_ESTIMATE", "DEFERRED_FOR_DEMO"}:
        return {**_project_cost_coverage(action="NO_TRADE", entry=entry, take_profit=take_profit, risk=risk), "cost_coverage_status": "NOT_FEASIBLE"}
    commission = float(financing["commission_allowance_aud"])
    signed_swap = float(financing["expected_swap_aud"])
    estimated_cost = entry_spread + exit_spread + slippage + commission + max(0.0, -signed_swap)
    gross_profit = abs(take_profit - entry) * value_per_price
    expected_net = round(gross_profit - estimated_cost, 2)
    return {"entry_spread_cost_aud": round(entry_spread, 2),
            "expected_exit_spread_cost_aud": round(exit_spread, 2),
            "commission_allowance_aud": round(commission, 2),
            "slippage_allowance_aud": round(slippage, 2),
            "expected_swap_aud": round(signed_swap, 2),
            "projected_gross_profit_at_take_profit_aud": round(gross_profit, 2),
            "estimated_round_trip_cost_aud": round(estimated_cost, 2),
            "minimum_net_profit_aud": MINIMUM_NET_PROFIT_AUD,
            "expected_net_profit_at_take_profit_aud": expected_net,
            "cost_coverage_status": "FEASIBLE" if expected_net >= MINIMUM_NET_PROFIT_AUD else "NOT_FEASIBLE"}


def _strategy_trade_plan(*, strategy_id: str | None, signal: str, m1: list[dict[str, Any]], tick: dict[str, Any], session: dict[str, Any], risk: dict[str, float]) -> tuple[str, float | None, float | None, float | None, float | None, str]:
    """Return the selected strategy's fixed entry, protective SL and TP.

    The plan is deliberately constructed only after deterministic selection.
    Every owner uses the same AUD risk cap and a minimum 1.5R target, while
    its technical stop comes from the candles that define that strategy.
    """
    if strategy_id not in STRATEGY_IDS or signal not in {"BUY", "SELL"} or len(m1) < 12:
        return "NO_TRADE", None, None, None, None, "No selected actionable M1 strategy."
    if float(session["maximum_loss_per_trade_aud"]) <= 0:
        return "NO_TRADE", None, None, None, None, "No remaining Option B loss headroom."
    action = signal
    entry = float(tick["ask"] if action == "BUY" else tick["bid"])
    prior_five = m1[-6:-1]
    compression = m1[-8:-3]
    setup, previous = m1[-1], m1[-2]
    high = lambda rows: max(float(row.get("high", row["close"])) for row in rows)
    low = lambda rows: min(float(row.get("low", row["close"])) for row in rows)
    if strategy_id == "compression_breakout":
        technical_stop = low(compression) if action == "BUY" else high(compression)
        plan_reason = "Compression range boundary supplies the technical stop; target is 1.5R."
    elif strategy_id == "trend_pullback":
        technical_stop = low(m1[-5:-1]) if action == "BUY" else high(m1[-5:-1])
        plan_reason = "Pullback swing boundary supplies the technical stop; target is 1.5R."
    elif strategy_id == "range_reversion":
        technical_stop = high(prior_five) if action == "SELL" else low(prior_five)
        plan_reason = "Rejected range edge supplies the protective technical stop; target is 1.5R."
    elif strategy_id == "session_breakout":
        technical_stop = low(prior_five) if action == "BUY" else high(prior_five)
        plan_reason = "Pre-breakout session boundary supplies the technical stop; target is 1.5R."
    else:
        technical_stop = low(prior_five) if action == "BUY" else high(prior_five)
        plan_reason = "Prior five-candle range boundary supplies the technical stop; target is 1.5R."
    notional = float(risk["volume"]) * 100000 * entry
    stop = _normalized_technical_stop(
        action=action, entry=entry, technical_stop=technical_stop,
        tick_size=float(risk["tick_size"]),
    )
    if stop is None:
        return "NO_TRADE", None, None, None, None, "Selected strategy's technical stop is invalid at the current quote."
    if _planned_stop_loss(entry, stop, risk) > session["maximum_loss_per_trade_aud"]:
        return "NO_TRADE", None, None, None, None, "Minimum volume at the valid technical stop exceeds remaining capital headroom."
    distance = abs(entry - stop)
    if strategy_id == "range_reversion":
        # A reversion trade is owned by its range hypothesis: the first
        # credible target is the range midpoint, never a generic breakout R.
        take = (high(prior_five) + low(prior_five)) / 2
        plan_reason = "Rejected range edge supplies the protective stop; range midpoint is the initial target."
    else:
        take = entry + 1.5 * distance if action == "BUY" else entry - 1.5 * distance
    take = round(take / risk["point"]) * risk["point"]
    if (action == "BUY" and take <= entry) or (action == "SELL" and take >= entry):
        return "NO_TRADE", None, None, None, None, "Selected strategy's target is not beyond the current executable quote."
    if notional > session["max_notional_per_trade_usd"]:
        raise SystemExit("M20 minimum EURUSD volume exceeds the Demo notional cap")
    return action, entry, stop, take, notional, plan_reason


def _normalized_technical_stop(*, action: str, entry: float, technical_stop: float, tick_size: float) -> float | None:
    """Return the executable tick-aligned stop used by every strategy owner."""
    if (not all(math.isfinite(value) for value in (entry, technical_stop, tick_size))
            or min(entry, tick_size) <= 0
            or (action == "BUY" and not 0 < technical_stop < entry)
            or (action == "SELL" and not technical_stop > entry)
            or action not in {"BUY", "SELL"}):
        return None
    return (math.floor(technical_stop / tick_size + 1e-9) if action == "BUY"
            else math.ceil(technical_stop / tick_size - 1e-9)) * tick_size


def _planned_stop_loss(entry: float, stop: float, risk: dict[str, float]) -> float:
    # Include qualified round-trip charges and adverse financing at full
    # precision; positive financing cannot expand Option B risk capacity.
    distance = abs(entry - stop) + max(0.0, float(risk.get("observed_spread", 0))) * .5
    return distance / float(risk["tick_size"]) * float(risk["tick_value_loss"]) * float(risk["volume"]) + float(risk.get("financing", {}).get("adverse_financing_aud", 0)) + float(risk.get("financing", {}).get("commission_allowance_aud", 0))


def _assessment(session: dict[str, Any], tick: dict[str, Any], bars: dict[str, list[dict[str, Any]]], captured_at: datetime, risk: dict[str, float], listener_poll_seconds: float, safety_gates: dict[str, bool] | None = None) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    """Create an M1-only proposal from the non-persisted live tick listener."""
    observed_at = tick["observed_at_utc"]
    m1 = bars["M1"]
    action = "NO_TRADE"
    reason = "No executable M1 strategy produced a signal."
    entry = stop = take = notional = None
    gates = safety_gates or {"fresh_quote": True, "completed_m1": len(m1) >= 12, "normal_spread": float(tick["spread_points"]) <= 12.0, "no_existing_position": True, "demo_lease_active": True, "news_blackout_inactive": True, "abnormal_volatility_inactive": True}
    assessments = _strategy_assessments(m1=m1, tick=tick)
    selection = _market_selection(tick=tick, m1=m1, assessments=assessments, safety_gates=gates)
    risk = {**risk, "observed_spread": float(tick["ask"]) - float(tick["bid"])}
    signals = {item["id"]: item["signal"] for item in assessments}
    executable_strategy_id = selection["selected_strategy_id"] if selection["selection_status"] == "SELECTED_EXECUTABLE" else None
    candidate_side = signals.get(executable_strategy_id, "NO_TRADE")
    financing = risk.get("financing_by_side", {}).get(candidate_side, {"status": "UNKNOWN"})
    risk = {**risk, "financing": financing}
    financing_allowed = financing.get("status") in {"QUALIFIED_INPUTS", "DEMO_ESTIMATE", "DEFERRED_FOR_DEMO"}
    if not financing_allowed:
        executable_strategy_id = None
    action, entry, stop, take, notional, reason = _strategy_trade_plan(
        strategy_id=executable_strategy_id, signal=signals.get(executable_strategy_id, "NO_TRADE"),
        m1=m1, tick=tick, session=session, risk=risk,
    )
    if not financing_allowed and candidate_side in {"BUY", "SELL"}:
        reason = "FINANCING_UNQUALIFIED: " + str(financing.get("reason", "missing financing terms"))
    cost_coverage = _project_cost_coverage(action=action, entry=float(entry or 0), take_profit=float(take or 0), risk=risk)
    selection.update(cost_coverage)
    if action != "NO_TRADE" and selection["selection_status"] != "SELECTED_EXECUTABLE":
        reason = f"{selection['market_regime']} has no executable strategy owner; no Demo order is submitted."
        action, entry, stop, take, notional = "NO_TRADE", None, None, None, None
    elif action != "NO_TRADE" and selection["cost_coverage_status"] != "FEASIBLE":
        reason = "COST_COVERAGE_NOT_FEASIBLE: projected take-profit net result does not meet the fixed minimum."
        action, entry, stop, take, notional = "NO_TRADE", None, None, None, None
    elif action != "NO_TRADE":
        reason = f"{selection['selected_strategy_id']} owns this {selection['market_regime']} trade. {reason} {COST_POLICY_VERSION} is feasible."
    # Selection identifies the best regime hypothesis.  It becomes execution
    # authority only if that owner's complete plan survives target, cost and
    # safety gates.  Keep a blocked selected rule observable without claiming
    # it sent, or could send, an order.
    if action == "NO_TRADE" and selection["selected_strategy_id"] is not None:
        selection["selection_status"] = "SELECTED_SHADOW"

    snapshot_body = {
        "observed_at_utc": observed_at, "captured_at_utc": utc(captured_at),
        "bid": tick["bid"], "ask": tick["ask"], "spread_points": tick["spread_points"],
        "freshness_seconds": int(tick["freshness_seconds"]), "m1_closed_bars": bars["M1"], "m5_closed_bars": bars["M5"],
        "safety_gates": gates, "market_context": selection, "strategy_assessments": assessments,
        "financing": financing, "holding_review": review_holding(forecast_lower_bound_aud=None, benefit_buffer_aud=None, forecast_qualified=False, risk_allowed=True, financing=financing),
    }
    digest = "sha256:" + hashlib.sha256(json.dumps(snapshot_body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    snapshot_id = str(uuid5(NAMESPACE_URL, f"{session['session_id']}:{digest}"))
    # A malformed/absent history still needs one safe terminal refusal for the
    # observed M1 boundary. It must not index a missing bar or invent OHLC.
    candle_closed_at = (str(m1[-1]["closed_at_utc"]) if m1 else utc(
        datetime.fromtimestamp(int(parse_utc(observed_at, "observed_at_utc").timestamp()) // 60 * 60, timezone.utc)
    ))
    decision_key = "|".join((SERVER, SYMBOL, "M1", candle_closed_at))
    # The proposal is deliberately keyed by the closed candle, not the quote or
    # capture time. Later quote polls therefore cannot create another terminal
    # decision for this M1 candle.
    proposal_id = str(uuid5(NAMESPACE_URL, f"forex.m1.decision:{decision_key}"))
    selection = {"proposal_id": proposal_id, **selection, "trade_owner_id": proposal_id,
                 "trade_owner_strategy_id": selection["selected_strategy_id"]}
    snapshot = {"snapshot_id": snapshot_id, **snapshot_body, "payload_sha256": digest}
    proposal = {
        "proposal_id": proposal_id, "session_id": session["session_id"], "snapshot_id": snapshot_id,
        "decision_key": decision_key, "decision_candle_closed_at_utc": candle_closed_at,
        # A decision cannot predate the completed-bar receipt retained above.
        # Keep the broker tick separately as ``observed_at_utc`` while binding
        # the executable proposal to the post-read snapshot capture instant.
        "decision_at_utc": utc(captured_at),
        "expires_at_utc": utc(min(captured_at + timedelta(minutes=5), parse_utc(session["expires_at_utc"], "expires_at_utc"))),
        "selected_timeframe": "M1", "action": action, "proposed_entry": entry, "stop_loss": stop, "take_profit": take,
        "notional_usd": round(float(notional), 2) if notional is not None else None,
        "confidence": 100 if action == "NO_TRADE" else 70, "rationale": reason,
        "decision_snapshot_sha256": digest, "strategy_version": STRATEGY_VERSION,
    }
    return snapshot, proposal, selection, assessments


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


def terminal_runtime_binding(terminal_path: str) -> dict[str, Any]:
    """Report the terminal context of a listener-owned worker without trading.

    This is deliberately invoked by the permanent listener as one of its own
    child processes.  A separately SSH-launched Python process is not evidence
    of the Scheduled Task's MT5 context, so it must not be used for this
    observation.  Paths are hashed before leaving this worker.
    """
    # MT5 may return the same Windows executable with a different case or
    # slash spelling.  Bind the canonical Windows path, not its presentation.
    def digest(value: Any) -> str | None:
        if not value:
            return None
        canonical = ntpath.normcase(ntpath.normpath(str(value)))
        return "sha256:" + hashlib.sha256(canonical.encode()).hexdigest()
    if not mt5.initialize(path=terminal_path):
        return {"marker": "FOREX_M20_TERMINAL_RUNTIME_BINDING", "state": "UNAVAILABLE",
                "reason": "MT5_INITIALIZE_FAILED", "mt5_error": str(mt5.last_error())}
    try:
        terminal = mt5.terminal_info()
        account = mt5.account_info()
        if not terminal or not account or account.server != SERVER or getattr(account, "currency", "") != "AUD":
            return {"marker": "FOREX_M20_TERMINAL_RUNTIME_BINDING", "state": "UNAVAILABLE",
                    "reason": "DEMO_ACCOUNT_OR_TERMINAL_UNAVAILABLE"}
        terminal_allowed = getattr(terminal, "trade_allowed", None)
        api_disabled = getattr(terminal, "tradeapi_disabled", None)
        account_allowed = getattr(account, "trade_allowed", None)
        expert_allowed = getattr(account, "trade_expert", None)
        # initialize() takes an executable; terminal_info().path is the
        # installation DIRECTORY (MetaQuotes API contract). Comparing those
        # directly manufactured a mismatch for every real installation.
        configured = ntpath.normcase(ntpath.normpath(str(terminal_path)))
        directory = getattr(terminal, "path", None)
        valid_configured = (ntpath.isabs(configured)
                            and ntpath.basename(configured) in {"terminal.exe", "terminal64.exe"})
        valid_directory = isinstance(directory, str) and bool(directory) and ntpath.isabs(directory)
        configured_path = digest(configured) if valid_configured else None
        # This is an installation-derived executable identity, not a claim
        # that the API exposes the terminal process's executable or PID.
        connected_path = (digest(ntpath.join(directory, ntpath.basename(configured)))
                          if valid_configured and valid_directory else None)
        data_path = digest(getattr(terminal, "data_path", None))
        if not data_path:
            return {"marker": "FOREX_M20_TERMINAL_RUNTIME_BINDING", "state": "UNAVAILABLE",
                    "reason": "TERMINAL_DATA_PROFILE_UNAVAILABLE"}
        if not configured_path or configured_path != connected_path:
            return {"marker": "FOREX_M20_TERMINAL_RUNTIME_BINDING", "state": "UNAVAILABLE",
                    "reason": "TERMINAL_EXECUTABLE_PATH_MISMATCH",
                    "configured_terminal_path_sha256": configured_path,
                    "connected_terminal_path_sha256": connected_path}
        return {
            "marker": "FOREX_M20_TERMINAL_RUNTIME_BINDING", "state": "MAPPED",
            "server": account.server, "currency": account.currency,
            "configured_terminal_path_sha256": configured_path,
            "connected_terminal_path_sha256": connected_path,
            "connected_terminal_data_path_sha256": data_path,
            "terminal_connected": getattr(terminal, "connected", None),
            "terminal_trade_allowed": terminal_allowed,
            "terminal_tradeapi_disabled": api_disabled,
            "account_trade_allowed": account_allowed,
            "account_trade_expert": expert_allowed,
            "submission_permitted": bool(
                getattr(terminal, "connected", None) is True and terminal_allowed is True
                and api_disabled is False and account_allowed is True and expert_allowed is True
            ),
        }
    finally:
        mt5.shutdown()


def risk_refusal_drill(terminal_path: str, session_path: Path) -> dict[str, Any]:
    """Prove the exact temporary AUD 0.01 boundary with live Demo metadata.

    This is deliberately a calculation-only operation.  It validates the
    broker account, EURUSD quote and minimum volume, then applies the normal
    technical-stop loss predicate to the smallest valid stop derived from the
    current quote.  It has no signal, order request, or submission path.
    """
    lease = load_session_lease(session_path, datetime.now(timezone.utc))
    if float(lease["maximum_loss_per_trade_aud"]) != REFUSAL_DRILL_MAXIMUM_LOSS_AUD:
        raise SystemExit("M20 risk refusal drill requires the fixed temporary AUD 0.01 lease")
    if not mt5.initialize(path=terminal_path):
        raise SystemExit(mt5.last_error())
    try:
        account = mt5.account_info()
        symbol = mt5.symbol_info(SYMBOL)
        tick = mt5.symbol_info_tick(SYMBOL)
        if not account or account.server != SERVER or getattr(account, "currency", "") != "AUD":
            raise SystemExit("M20 risk refusal drill is not connected to the required AUD GOMarketsMU-Demo account")
        if not symbol or symbol.name != SYMBOL or not tick:
            raise SystemExit("M20 risk refusal drill has no EURUSD broker metadata")
        volume = float(symbol.volume_min)
        tick_size = float(symbol.trade_tick_size)
        tick_value_loss = float(symbol.trade_tick_value_loss)
        point = float(symbol.point)
        bid, entry = float(tick.bid), float(tick.ask)
        try:
            quote_observed_at = datetime.fromtimestamp(int(getattr(tick, "time", 0)), timezone.utc)
        except (TypeError, ValueError, OverflowError, OSError) as error:
            raise SystemExit("M20 risk refusal drill received an invalid EURUSD quote timestamp") from error
        quote_observed_at -= timedelta(seconds=tick_time_offset_seconds())
        # Do this after every broker read.  A valid-looking value captured
        # before a terminal synchronization delay is not current metadata.
        captured_at = datetime.now(timezone.utc)
        quote_age_seconds = (captured_at - quote_observed_at).total_seconds()
        if (not all(math.isfinite(value) for value in (volume, tick_size, tick_value_loss, point, bid, entry))
                or min(volume, tick_size, tick_value_loss, point, bid, entry) <= 0 or entry < bid
                or not 0 <= quote_age_seconds <= MAX_TICK_AGE_SECONDS):
            raise SystemExit("M20 risk refusal drill received invalid EURUSD broker metadata")
        stop = _normalized_technical_stop(
            action="BUY", entry=entry, technical_stop=entry - tick_size,
            tick_size=tick_size,
        )
        if stop is None:
            raise SystemExit("M20 risk refusal drill cannot form a valid minimum EURUSD technical stop")
        # This is a lower-bound loss calculation: actual qualified financing
        # and commission can only increase the entry risk.  Current spread is
        # retained because the normal-path predicate charges it immediately.
        risk = {"volume": volume, "tick_size": tick_size,
                "tick_value_loss": tick_value_loss, "observed_spread": entry - bid}
        planned_stop_loss = _planned_stop_loss(entry, stop, risk)
        if planned_stop_loss > REFUSAL_DRILL_MAXIMUM_LOSS_AUD:
            reason = "Minimum volume at the valid technical stop exceeds remaining capital headroom."
            return {
                "marker": "FOREX_M20_DEMO_RISK_REFUSAL_DRILL_OK",
                "server": account.server,
                "symbol": SYMBOL,
                "maximum_loss_per_trade_aud": REFUSAL_DRILL_MAXIMUM_LOSS_AUD,
                "minimum_volume": volume,
                "quote_observed_at_utc": utc(quote_observed_at),
                "captured_at_utc": utc(captured_at),
                "quote_freshness_seconds": round(quote_age_seconds, 3),
                "minimum_valid_stop": round(stop, 10),
                "planned_stop_loss_aud": round(planned_stop_loss, 6),
                "refusal_reason": reason,
                "order_submitted": False,
            }
        raise SystemExit("M20 risk refusal drill did not refuse the minimum valid technical stop")
    finally:
        mt5.shutdown()


def _positions_or_fail(*, context: str, **query: Any) -> tuple[Any, ...]:
    """Read positions without confusing an MT5 API failure with a flat book."""
    positions = mt5.positions_get(**query)
    if positions is None:
        last_error = getattr(mt5, "last_error", lambda: "unavailable")()
        raise SystemExit(f"M20 {context} position query failed: {last_error}")
    return tuple(positions)


def _execution_result_state(result: Any) -> tuple[bool, bool]:
    """Classify MT5 execution without collapsing partial completion to reject."""
    retcode = getattr(result, "retcode", None) if result else None
    return (
        retcode == mt5.TRADE_RETCODE_DONE,
        retcode == getattr(mt5, "TRADE_RETCODE_DONE_PARTIAL", 10010),
    )


def _wait_for_position(*, magic: int = EXECUTOR_MAGIC) -> Any:
    """Return the sole fixed-executor EURUSD position or fail closed.

    An accepted market order is not treated as a completed M20 action until
    the terminal exposes its position.  The runner never searches other
    symbols or positions belonging to another strategy.
    """
    deadline = time.monotonic() + CLOSE_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        positions = _positions_or_fail(context="accepted-order", symbol=SYMBOL)
        owned = [position for position in positions if int(getattr(position, "magic", -1)) == magic]
        if len(owned) == 1:
            return owned[0]
        if len(owned) > 1:
            raise SystemExit("M20 executor observed more than one owned EURUSD position")
        time.sleep(0.25)
    raise SystemExit("M20 accepted order did not produce a fixed EURUSD position before close timeout")


def _wait_until_closed(ticket: int) -> None:
    deadline = time.monotonic() + CLOSE_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        if not _positions_or_fail(context="close-confirmation", ticket=ticket):
            return
        time.sleep(0.25)
    raise SystemExit("M20 fixed EURUSD position did not close before close timeout")


def _closed_position_costs(*, position: Any, submitted_at: datetime, proposed_entry: float, entry_spread: float, risk: dict[str, float], expected_exit_price: float | None) -> tuple[float, dict[str, Any]]:
    """Read the terminal's immutable deal history for one closed position.

    This is used for both a discretionary monitor exit and a broker-side
    stop/take-profit exit.  If an exit quote is no longer available after a
    broker-side close, the estimated exit slippage is recorded as zero rather
    than inventing a quote; realized P&L, commission, and swap still come
    directly from MT5 deal history.
    """
    ticket = int(getattr(position, "ticket", 0))
    position_identifier = int(getattr(position, "identifier", ticket) or ticket)
    position_type = int(getattr(position, "type", -1))
    if ticket <= 0:
        raise SystemExit("M20 closed position has an invalid ticket")
    # MT5 history uses DEAL_POSITION_ID. A terminal error is not empty
    # history: treating it as such would incorrectly erase an open exposure.
    deals = mt5.history_deals_get(position=position_identifier)
    if deals is None:
        last_error = getattr(mt5, "last_error", lambda: "unavailable")()
        raise SystemExit(f"M20 closed position deal-history query failed: {last_error}")
    if not deals:
        raise SystemExit("M20 closed position deal history is unavailable")
    ordered = sorted(
        (deal for deal in deals if int(getattr(deal, "position_id", 0)) == position_identifier),
        key=lambda deal: int(getattr(deal, "time_msc", 0)),
    )
    if not ordered:
        raise SystemExit("M20 closed position deal history does not match its broker position identifier")
    entry_in = int(getattr(mt5, "DEAL_ENTRY_IN", 0))
    entry_out = int(getattr(mt5, "DEAL_ENTRY_OUT", 1))
    entry_inout = int(getattr(mt5, "DEAL_ENTRY_INOUT", 2))
    entry_out_by = int(getattr(mt5, "DEAL_ENTRY_OUT_BY", 3))
    market_deals = [
        deal for deal in ordered
        if float(getattr(deal, "price", 0)) > 0 and float(getattr(deal, "volume", 0)) > 0
    ]
    opening_deals = [deal for deal in market_deals if int(getattr(deal, "entry", -1)) in {entry_in, entry_inout}]
    closing_deals = [deal for deal in market_deals if int(getattr(deal, "entry", -1)) in {entry_out, entry_inout, entry_out_by}]
    if not opening_deals or not closing_deals:
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
        raise SystemExit(f"M20 close deal history lacks attributable opening or closing market deals: {json.dumps(diagnostic, separators=(',', ':'))}")
    opening_volume = sum(float(getattr(deal, "volume", 0)) for deal in opening_deals)
    closing_volume = sum(float(getattr(deal, "volume", 0)) for deal in closing_deals)
    if opening_volume <= 0 or closing_volume <= 0 or not math.isclose(opening_volume, closing_volume, rel_tol=0.0, abs_tol=1e-9):
        raise SystemExit("M20 close deal history has unmatched opening and closing volume")
    exit_price = sum(float(getattr(deal, "price", 0)) * float(getattr(deal, "volume", 0)) for deal in closing_deals) / closing_volume
    gross_price_pnl = sum(float(getattr(deal, "profit", 0)) for deal in ordered)
    commission = sum(float(getattr(deal, "commission", 0)) for deal in ordered)
    fee = sum(float(getattr(deal, "fee", 0)) for deal in ordered)
    swap = sum(float(getattr(deal, "swap", 0)) for deal in ordered)
    realized_pnl = gross_price_pnl + commission + fee + swap
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
    spread_cost = (entry_spread + exit_spread) / tick_size * opening_volume * tick_value_loss
    slippage_cost = (entry_slippage_price + exit_slippage_price) / tick_size * opening_volume * tick_value_loss
    # Actual commission and swap already form part of broker realised P&L.
    # Keep execution estimates separate so reports cannot subtract them twice.
    total_cost = spread_cost + slippage_cost
    costs = {
        "gross_price_pnl_account": round(gross_price_pnl, 2),
        "commission_account": round(commission, 2),
        "fee_account": round(fee, 2),
        "swap_account": round(swap, 2),
        "estimated_spread_cost_account": round(spread_cost, 2),
        "slippage_cost_account": round(slippage_cost, 2),
        "estimated_total_cost_account": round(total_cost, 2),
        "realized_pnl_account": round(realized_pnl, 2),
    }
    # Retain the same broker rows used above, not a later re-query or a
    # reconstructed ledger. The CLOSED event preserves these immutable facts
    # so an offline verifier can independently recompute exit and actual costs.
    broker_deals = [_historical_deal_row(deal, tick_time_offset_seconds()) for deal in ordered]
    costs["broker_history"] = {
        "server": SERVER, "symbol": SYMBOL, "account_currency": "AUD",
        "position_identifier": position_identifier,
        "broker_deals": broker_deals,
        "broker_deals_sha256": "sha256:" + hashlib.sha256(json.dumps(broker_deals, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
    }
    return exit_price, costs


def _close_accepted_position(*, position: Any, submitted_at: datetime, proposed_entry: float, entry_spread: float, risk: dict[str, float], magic: int = EXECUTOR_MAGIC, close_comment: str = "forex-m20-demo-close") -> tuple[str, float, dict[str, Any]]:
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
        "magic": magic,
        "comment": close_comment,
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    close_result = mt5.order_send(close_request)
    if close_result and close_result.retcode == getattr(mt5, "TRADE_RETCODE_DONE_PARTIAL", 10010):
        # Do not record a close outcome. The durable state and attached broker
        # protection remain so a later monitor pass observes the residual
        # position and no second entry can be reserved.
        raise SystemExit("M20 EURUSD close was partially filled; residual broker exposure remains protected and unresolved")
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


def execution_drill(terminal_path: str, session_path: Path) -> dict[str, Any]:
    """Run the one-shot fixed Demo broker round-trip diagnostic."""
    load_session_lease(session_path, datetime.now(timezone.utc))
    marker_path = session_path.with_name("m30_demo_execution_drill.local.json")
    lock_path = session_path.with_name("m30_demo_execution_drill.lock.json")
    if marker_path.exists():
        raise SystemExit("M30 Demo execution drill already has a submitted or completed marker")
    if not lock_path.exists():
        raise SystemExit("M30 Demo execution drill requires its fixed listener broker-path lock")
    submitted = False
    resolved = False
    if not mt5.initialize(path=terminal_path):
        raise SystemExit(f"M30 Demo execution drill could not initialize MT5: {mt5.last_error()}")
    try:
        account = mt5.account_info()
        _require_account_execution_profile(account)
        refusal = _terminal_submission_refusal(account)
        if refusal:
            return {"marker": "FOREX_M30_DEMO_EXECUTION_DRILL_REFUSED", "classification": "EXECUTION_DRILL", "server": getattr(account, "server", None), "symbol": SYMBOL, "order_submitted": False, "reason": refusal}
        if _positions_or_fail(context="execution-drill-preflight", symbol=SYMBOL):
            return {"marker": "FOREX_M30_DEMO_EXECUTION_DRILL_REFUSED", "classification": "EXECUTION_DRILL", "server": account.server, "symbol": SYMBOL, "order_submitted": False, "reason": "M30 execution drill requires a flat EURUSD Demo position state."}
        symbol = mt5.symbol_info(SYMBOL)
        tick = mt5.symbol_info_tick(SYMBOL)
        if not symbol or not tick or getattr(symbol, "name", None) != SYMBOL:
            raise SystemExit("M30 Demo execution drill has no fixed EURUSD metadata or quote")
        volume, tick_size = float(symbol.volume_min), float(symbol.trade_tick_size)
        tick_value_loss, point = float(symbol.trade_tick_value_loss), float(symbol.point)
        bid, ask = float(tick.bid), float(tick.ask)
        quote_at = datetime.fromtimestamp(int(getattr(tick, "time", 0)), timezone.utc) - timedelta(seconds=tick_time_offset_seconds())
        now = datetime.now(timezone.utc)
        quote_age = (now - quote_at).total_seconds()
        if (not all(math.isfinite(value) for value in (volume, tick_size, tick_value_loss, point, bid, ask))
                or not math.isclose(volume, EXECUTION_DRILL_VOLUME, abs_tol=1e-9)
                or min(tick_size, tick_value_loss, point, bid, ask) <= 0 or ask < bid
                or not 0 <= quote_age <= MAX_TICK_AGE_SECONDS):
            raise SystemExit("M30 Demo execution drill has invalid fixed EURUSD broker metadata or a stale quote")
        stop, take, notional = _risk_levels(action="BUY", entry=ask, volume=volume, tick_size=tick_size, tick_value_loss=tick_value_loss, point=point, maximum_loss_aud=EXECUTION_DRILL_MAXIMUM_LOSS_AUD)
        marker_path.write_text(json.dumps({"schema_version": "forex.m30.demo-execution-drill.v1", "state": "SUBMISSION_STARTED", "classification": "EXECUTION_DRILL", "submitted_at_utc": utc(now)}, separators=(",", ":")), encoding="utf-8")
        lock_path.write_text(json.dumps({"schema_version": "forex.m30.execution-drill-lock.v1", "state": "SUBMISSION_STARTED"}, separators=(",", ":")), encoding="utf-8")
        submitted = True
        request = {"action": mt5.TRADE_ACTION_DEAL, "symbol": SYMBOL, "volume": volume, "type": mt5.ORDER_TYPE_BUY, "price": ask, "sl": stop, "tp": take, "deviation": 20, "magic": EXECUTION_DRILL_MAGIC, "comment": "forex-m30-execution-drill", "type_time": mt5.ORDER_TIME_GTC, "type_filling": mt5.ORDER_FILLING_IOC}
        result = mt5.order_send(request)
        full_fill, partial_fill = _execution_result_state(result)
        if not full_fill:
            marker_path.write_text(json.dumps({"schema_version": "forex.m30.demo-execution-drill.v1", "state": "SUBMISSION_REJECTED", "classification": "EXECUTION_DRILL", "submitted_at_utc": utc(now), "retcode": getattr(result, "retcode", None), "broker_comment": str(getattr(result, "comment", ""))[:160]}, separators=(",", ":")), encoding="utf-8")
            resolved = True
            return {"marker": "FOREX_M30_DEMO_EXECUTION_DRILL_REJECTED", "classification": "EXECUTION_DRILL", "server": account.server, "symbol": SYMBOL, "order_submitted": True, "partial_fill": partial_fill, "broker_retcode": getattr(result, "retcode", None), "broker_comment": str(getattr(result, "comment", ""))[:160]}
        position = _wait_for_position(magic=EXECUTION_DRILL_MAGIC)
        close_order, exit_price, costs = _close_accepted_position(position=position, submitted_at=now, proposed_entry=ask, entry_spread=ask - bid, risk={"tick_size": tick_size, "tick_value_loss": tick_value_loss}, magic=EXECUTION_DRILL_MAGIC, close_comment="forex-m30-execution-drill-close")
        marker_path.write_text(json.dumps({"schema_version": "forex.m30.demo-execution-drill.v1", "state": "CLOSED_MATCHED", "classification": "EXECUTION_DRILL", "submitted_at_utc": utc(now), "position_ticket": int(position.ticket), "open_order": str(getattr(result, "order", "")), "close_order": close_order}, separators=(",", ":")), encoding="utf-8")
        resolved = True
        return {"marker": "FOREX_M30_DEMO_EXECUTION_DRILL_OK", "classification": "EXECUTION_DRILL", "server": account.server, "symbol": SYMBOL, "order_submitted": True, "volume": volume, "maximum_loss_aud": EXECUTION_DRILL_MAXIMUM_LOSS_AUD, "notional_usd": round(notional, 2), "position_ticket": int(position.ticket), "open_order": str(getattr(result, "order", "")), "close_order": close_order, "exit_price": exit_price, "costs": costs}
    finally:
        mt5.shutdown()
        # An unresolved broker request keeps the narrow lock in place. Pre-
        # submission refusals and completed terminal outcomes release it.
        if not submitted or resolved:
            try:
                lock_path.unlink(missing_ok=True)
            except OSError:
                pass



# Exact legacy broker positions, captured by the fixed read-only attribution
# probe.  This is intentionally finite: it is a one-time recovery path, not a
# general historical order/deal interface.
_HISTORICAL_RECOVERY = (
    ("feffc714-c88f-5d34-bdca-705040a28565", "3f40a116-bc15-5897-9062-c743b9ee5199", "SELL", 41488649, "2026-09-03T09:18:05Z", "2026-09-03T09:28:07Z", 0.18),
    ("e0dac54c-6b56-5a84-9022-126c3c21e00b", "ee9f449b-dca7-549b-81de-5efcdabcb579", "BUY", 41495536, "2026-09-03T11:18:08Z", "2026-09-03T11:21:00Z", 0.01),
    ("15dffa0b-0446-500c-af09-ddce686e11f9", "b3259891-acb5-54d8-a183-86b076dcbec1", "BUY", 41499398, "2026-09-03T12:04:03Z", "2026-09-03T12:13:02Z", -0.56),
    ("c66d1af4-3d00-56a8-83e2-881f1eec416b", "a802ff2c-2c91-57aa-a364-030a4faeb8a7", "SELL", 41499981, "2026-09-03T12:13:07Z", "2026-09-03T12:15:01Z", -0.21),
)


def _historical_deal_row(deal: Any, offset_seconds: int) -> dict[str, Any]:
    """Return the complete non-secret, broker-derived deal facts we preserve."""
    broker_time = datetime.fromtimestamp(int(getattr(deal, "time", 0)), timezone.utc)
    return {
        "ticket": int(getattr(deal, "ticket", 0)), "order": int(getattr(deal, "order", 0)),
        "position_identifier": int(getattr(deal, "position_id", 0)),
        "broker_time_utc": utc(broker_time), "time_utc": utc(broker_time - timedelta(seconds=offset_seconds)),
        "entry": int(getattr(deal, "entry", -1)), "type": int(getattr(deal, "type", -1)),
        "volume": float(getattr(deal, "volume", 0)), "price": float(getattr(deal, "price", 0)),
        "profit": float(getattr(deal, "profit", 0)), "commission": float(getattr(deal, "commission", 0)),
        "swap": float(getattr(deal, "swap", 0)), "fee": float(getattr(deal, "fee", 0)),
        "reason": int(getattr(deal, "reason", -1)), "symbol": str(getattr(deal, "symbol", "")),
    }


def reconcile_historical_retained_positions(terminal_path: str) -> dict[str, Any]:
    """Validate and append only four known closed Demo positions.

    No order, position modification, lease write, or risk-policy adjustment is
    possible on this path.  It exists solely to turn independently retained
    broker history into complete append-only lifecycle evidence.
    """
    offset_seconds = tick_time_offset_seconds()
    if not mt5.initialize(path=terminal_path):
        raise SystemExit(f"M20 retained-history reconciliation could not initialize MT5: {mt5.last_error()}")
    try:
        account = mt5.account_info()
        if not account or account.server != SERVER or getattr(account, "currency", "") != "AUD":
            raise SystemExit("M20 retained-history reconciliation requires the configured AUD GOMarketsMU-Demo account")
        entry_in, entry_out = int(getattr(mt5, "DEAL_ENTRY_IN", 0)), int(getattr(mt5, "DEAL_ENTRY_OUT", 1))
        buy, sell = int(getattr(mt5, "DEAL_TYPE_BUY", 0)), int(getattr(mt5, "DEAL_TYPE_SELL", 1))
        rows: list[dict[str, Any]] = []
        for attempt_id, proposal_id, action, position_id, expected_open, expected_close, expected_net in _HISTORICAL_RECOVERY:
            deals = mt5.history_deals_get(position=position_id)
            if deals is None:
                raise SystemExit(f"M20 retained-history reconciliation deal query failed for {position_id}: {mt5.last_error()}")
            normalized = sorted((_historical_deal_row(deal, offset_seconds) for deal in deals if int(getattr(deal, "position_id", 0)) == position_id), key=lambda item: (item["time_utc"], item["ticket"]))
            if len(normalized) != 2:
                raise SystemExit(f"M20 retained-history reconciliation requires exactly two broker deals for {position_id}")
            opening, closing = normalized
            expected_open_type, expected_close_type = (sell, buy) if action == "SELL" else (buy, sell)
            if (opening["symbol"] != SYMBOL or closing["symbol"] != SYMBOL
                    or opening["entry"] != entry_in or closing["entry"] != entry_out
                    or opening["type"] != expected_open_type or closing["type"] != expected_close_type
                    or opening["time_utc"] != expected_open or closing["time_utc"] != expected_close
                    or not math.isclose(opening["volume"], 0.01, abs_tol=1e-9)
                    or not math.isclose(closing["volume"], 0.01, abs_tol=1e-9)):
                raise SystemExit(f"M20 retained-history reconciliation broker attribution changed for {position_id}")
            gross = round(sum(item["profit"] for item in normalized), 2)
            commission = round(sum(item["commission"] for item in normalized), 2)
            fee = round(sum(item["fee"] for item in normalized), 2)
            swap = round(sum(item["swap"] for item in normalized), 2)
            net = round(gross + commission + fee + swap, 2)
            if net != expected_net:
                raise SystemExit(f"M20 retained-history reconciliation broker net P&L changed for {position_id}")
            rows.append({
                "attempt_id": attempt_id, "proposal_id": proposal_id, "action": action,
                "position_identifier": position_id, "closed_at_utc": closing["time_utc"],
                "exit_price": closing["price"], "gross_price_pnl_account": gross,
                "commission_account": commission, "fee_account": fee, "swap_account": swap,
                "realized_pnl_account": net, "account_currency": "AUD",
                "broker_order_reference": str(closing["order"]), "broker_deals": normalized,
                "broker_deals_sha256": "sha256:" + hashlib.sha256(json.dumps(normalized, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
            })
        result = _bridge({"recoveries": rows}, "record-historical-reconciliation")
        if result.get("risk_policy_state_changed") is not False:
            raise SystemExit("M20 retained-history reconciliation unexpectedly changed risk state")
        return {"marker": "FOREX_M20_HISTORICAL_RECONCILIATION_OPERATION_OK", "server": account.server, "symbol": SYMBOL, "reconciliation": result}
    finally:
        mt5.shutdown()

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


def _notify_opened_position(*, proposal: dict[str, Any], position: Any, opened_at_utc: str) -> None:
    """Prompt the operator only after protected OPENED state is durable.

    This best-effort notification is outside broker execution, PostgreSQL
    persistence, and monitor scheduling. It cannot change a Demo position or
    make a failed delivery look like an incomplete lifecycle.
    """
    try:
        adapter_path = Path(__file__).with_name("m20_discord_trade_notification.payload")
        loader = importlib.machinery.SourceFileLoader("m20_discord_trade_notification", str(adapter_path))
        spec = importlib.util.spec_from_loader("m20_discord_trade_notification", loader)
        if spec is None or spec.loader is None:
            raise ImportError("M20 Discord open-notification payload is unavailable")
        adapter = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(adapter)
        notification = adapter.notify_open({
            "server": SERVER, "symbol": SYMBOL, "proposal_id": proposal["proposal_id"],
            "position_ticket": int(getattr(position, "ticket", 0)), "side": proposal["action"],
            "strategy": str(proposal.get("trade_owner_strategy_id", "unknown")),
            "opened_at_utc": opened_at_utc, "entry_price": float(getattr(position, "price_open", 0)),
            "stop_loss": float(getattr(position, "sl", 0)), "take_profit": float(getattr(position, "tp", 0)),
            "lots": float(getattr(position, "volume", 0)),
        })
        if not notification.get("ok"):
            print(f"M20 Discord open notification failed after durable OPENED state: {notification.get('detail', 'unknown failure')}", file=sys.stderr)
    except (ImportError, AttributeError, TypeError, ValueError, OSError) as error:
        print(f"M20 Discord open notification unavailable after durable OPENED state: {error}", file=sys.stderr)


def _notify_reconciled_sale(*, proposal: dict[str, Any], position: Any, outcome: dict[str, Any], costs: dict[str, float]) -> None:
    """Best-effort human notification after the immutable close is reconciled.

    Notification is deliberately outside the execution and reconciliation
    boundary: a missing webhook, unavailable Discord, or malformed account
    snapshot cannot reverse, delay, or invalidate an already broker-matched
    Demo outcome.
    """
    try:
        # Endpoint protection can lock newly-created .py files under
        # ProgramData.  The hash-checked release therefore stages this fixed
        # source as a non-executable payload, then loads it explicitly.
        adapter_path = Path(__file__).with_name("m20_discord_trade_notification.payload")
        loader = importlib.machinery.SourceFileLoader("m20_discord_trade_notification", str(adapter_path))
        spec = importlib.util.spec_from_loader("m20_discord_trade_notification", loader)
        if spec is None or spec.loader is None:
            raise ImportError("M20 Discord sale-notification payload is unavailable")
        adapter = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(adapter)
        notify_sale = adapter.notify_sale

        account = mt5.account_info()
        ticket = int(getattr(position, "ticket", 0))
        liquidity = {
            "currency": str(getattr(account, "currency", "")),
            "balance": float(getattr(account, "balance", 0)),
            "equity": float(getattr(account, "equity", 0)),
            "free_margin": float(getattr(account, "margin_free", 0)),
            "margin": float(getattr(account, "margin", 0)),
            "floating_pnl": float(getattr(account, "profit", 0)),
        }
        notification = notify_sale({
            "server": SERVER, "symbol": SYMBOL, "proposal_id": proposal["proposal_id"],
            "position_ticket": ticket, "side": proposal["action"],
            "strategy": str(proposal.get("trade_owner_strategy_id", "unknown")),
            "opened_at_utc": str(proposal.get("decision_at_utc", "unknown")),
            "closed_at_utc": outcome["closed_at_utc"],
            "entry_price": float(getattr(position, "price_open", 0)),
            "exit_price": float(outcome["exit_price"]),
            "lots": float(getattr(position, "volume", 0)),
            "close_reason": outcome["close_reason"],
            "gross_pnl_aud": costs["gross_price_pnl_account"],
            "commission_aud": costs["commission_account"], "fee_aud": costs["fee_account"],
            "swap_aud": costs["swap_account"],
            "estimated_cost_aud": costs["estimated_total_cost_account"],
            "realized_pnl_aud": costs["realized_pnl_account"],
            "liquidity": liquidity,
        })
        if not notification.get("ok"):
            print(f"M20 Discord sale notification failed after reconciliation: {notification.get('detail', 'unknown failure')}", file=sys.stderr)
    except (ImportError, AttributeError, TypeError, ValueError, OSError) as error:
        print(f"M20 Discord sale notification unavailable after reconciliation: {error}", file=sys.stderr)


def _record_closed_monitor_outcome(*, proposal: dict[str, Any], attempt_id: str, position: Any, submitted_at: datetime, entry_spread: float, risk: dict[str, float], close_reason: str, broker_order_reference: str, expected_exit_price: float | None, closed_costs: dict[str, Any] | None = None) -> dict[str, Any]:
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
    broker_history = costs.get("broker_history")
    if not isinstance(broker_history, dict):
        raise SystemExit("M20 close is missing retained broker deal history")
    costs = {key: value for key, value in costs.items() if key != "broker_history"}
    closed_payload = {
        "close_reason": close_reason,
        "position_ticket": int(getattr(position, "ticket", 0)),
        "position_identifier": int(getattr(position, "identifier", 0) or 0),
        "closed_volume": float(getattr(position, "volume", 0)),
        "broker_history": broker_history,
    }
    result = {
        "event_id": str(uuid5(NAMESPACE_URL, f"{attempt_id}:closed")),
        "attempt_id": attempt_id,
        "event_type": "CLOSED",
        "observed_at_utc": closed_at,
        "broker_order_reference": broker_order_reference,
        "payload_sha256": "sha256:" + hashlib.sha256(json.dumps(closed_payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
        "payload": closed_payload,
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
    # This comes last: PostgreSQL remains the source of truth even if Discord
    # is intentionally disabled or temporarily unavailable.
    _notify_reconciled_sale(proposal=proposal, position=position, outcome=outcome, costs=costs)
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
        "payload_sha256": "sha256:" + hashlib.sha256(json.dumps({"reason": "PLUS_1R_BREAK_EVEN", "stop_loss": entry, "take_profit": take_profit}, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
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


def _owner_exit_contract(owner: str) -> tuple[int, str]:
    """Return the fixed owner-specific time stop and common invalidation rule.

    Every owner retains attached MT5 SL/TP and the same closed-candle
    invalidation safety check.  The shorter Range and Compression windows are
    specific to their short-lived M1 hypotheses and remain fully deterministic
    in the persisted owner rule version.
    """
    seconds = OWNER_MAX_HOLD_SECONDS.get(owner)
    if seconds is None:
        raise SystemExit("M20 monitor refuses a position without a known selected strategy owner")
    return seconds, "M1_TWO_OPPOSITE_CLOSED_CANDLES"


def _monitor_open_position(*, proposal: dict[str, Any], attempt_id: str, position: Any, submitted_at: datetime, entry_spread: float, risk: dict[str, float], offset_seconds: int, single_pass: bool = False, break_even_applied: bool = False) -> dict[str, Any]:
    """Hold one Demo position with static broker protection and M1 exits.

    Any monitor, pricing, candle, or audit failure stops discretionary action.
    It never removes the broker-side SL/TP, never opens a second position, and
    leaves the durable open state intact for recovery by a future monitor.
    """
    ticket = int(getattr(position, "ticket", 0))
    action = proposal["action"]
    entry = float(getattr(position, "price_open", 0))
    current_stop = float(getattr(position, "sl", 0))
    take_profit = float(getattr(position, "tp", 0))
    owner = proposal.get("trade_owner_strategy_id")
    maximum_hold_seconds, invalidation = _owner_exit_contract(str(owner))
    # The durable open-state stop is intentionally updated to entry after the
    # +1R break-even protection fires.  Recovery must retain the immutable
    # proposal stop as the *initial* risk reference; otherwise it would see a
    # zero-distance stop and abandon the owner's time/candle exits.
    initial_stop = float(proposal.get("initial_stop_loss", proposal.get("stop_loss", current_stop)) or 0)
    if ticket <= 0 or action not in {"BUY", "SELL"} or min(entry, current_stop, initial_stop, take_profit) <= 0:
        raise SystemExit("M20 open position monitor inputs are invalid")
    risk_distance = abs(entry - initial_stop)
    if risk_distance <= 0:
        raise SystemExit("M20 open position has no measurable initial risk")
    # A recovery pass is deliberately short, but the trade's M1 exit window
    # is not.  Use durable submission time so the owner's time-stop and
    # closed-candle invalidation survive every five-second supervisor pass.
    opened_at = submitted_at
    closes_at = opened_at + timedelta(seconds=maximum_hold_seconds)
    while True:
        positions = _positions_or_fail(context="monitor", ticket=ticket)
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
                close_reason=f"{owner.upper()}_M1_TIME_STOP_{maximum_hold_seconds // 60}_MINUTES", broker_order_reference=reference,
                expected_exit_price=exit_price, closed_costs=costs,
            )
        # Reversal invalidation is discretionary. Delayed, gapped, or invalid
        # terminal history cannot close a protected position; broker SL/TP and
        # the owner wall-clock exit above remain available.
        try:
            bars = _closed_m1_bars_for_monitor(tick, offset_seconds)
        except (SystemExit, KeyError, TypeError, ValueError, OverflowError):
            bars = []
        monitor_checked_at = datetime.now(timezone.utc)
        monitor_tick_at = datetime.fromtimestamp(int(tick.time), timezone.utc) - timedelta(seconds=offset_seconds)
        monitor_age = (monitor_checked_at - monitor_tick_at).total_seconds()
        if (0 <= monitor_age <= MAX_TICK_AGE_SECONDS
                and int(monitor_tick_at.timestamp()) // 60 == int(monitor_checked_at.timestamp()) // 60
                and _entry_m1_history_is_synchronized(rows=bars, observed_at=monitor_checked_at)
                and _two_opposite_completed_m1_candles(bars=bars, action=action, opened_at=opened_at)):
            reference, exit_price, costs = _close_accepted_position(
                position=current, submitted_at=submitted_at,
                proposed_entry=float(proposal["proposed_entry"]), entry_spread=entry_spread, risk=risk,
            )
            return _record_closed_monitor_outcome(
                proposal=proposal, attempt_id=attempt_id, position=current,
                submitted_at=submitted_at, entry_spread=entry_spread, risk=risk,
                close_reason=f"{owner.upper()}_{invalidation}", broker_order_reference=reference,
                expected_exit_price=exit_price, closed_costs=costs,
            )
        if single_pass:
            return {"status": "OPEN_MONITORING", "position_ticket": ticket}
        remaining_seconds = max(0.0, (closes_at - datetime.now(timezone.utc)).total_seconds())
        time.sleep(min(MONITOR_POLL_SECONDS, remaining_seconds))


def _monitor_job_path(session_path: Path) -> Path:
    """Return the fixed, durable monitor-job location for this listener."""
    return session_path.with_name("m20_demo_monitor_job.local.json")


def _write_monitor_job(*, session_path: Path, proposal: dict[str, Any], trade_owner_strategy_id: str, attempt_id: str, position: Any, submitted_at: str, entry_spread: float, risk: dict[str, float], offset_seconds: int) -> Path:
    """Persist accepted-position context so monitoring survives supervisor restart."""
    job = {
        "schema_version": "forex.m20.monitor-job.v1",
        "proposal": {**proposal, "trade_owner_strategy_id": trade_owner_strategy_id},
        "attempt_id": attempt_id,
        "position": {"ticket": int(position.ticket), "identifier": int(getattr(position, "identifier", 0) or 0), "price_open": float(position.price_open), "sl": float(position.sl), "tp": float(position.tp), "volume": float(position.volume), "type": int(position.type)},
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
                proposal = {"proposal_id": row["proposal_id"], "action": row["action"], "proposed_entry": float(row["proposed_entry"]), "initial_stop_loss": float(row["initial_stop_loss"]), "trade_owner_strategy_id": row["trade_owner_strategy_id"]}
                position = SimpleNamespace(
                    ticket=int(row["position_ticket"]), price_open=float(row["entry_price"]),
                    sl=float(row["stop_loss"]), tp=float(row["take_profit"]), volume=volume,
                    identifier=int(row.get("position_identifier") or row["position_ticket"]),
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
        # Missing or incomplete history is unresolved exposure/accounting
        # state. Preserve the durable row and block new entries for operator
        # reconciliation; it is never converted into a fabricated FAILED
        # close merely because a current terminal query is flat.
        return {"marker": "FOREX_M20_DEMO_MONITOR_OPERATION_OK", "recovered": results}
    finally:
        mt5.shutdown()


def capture(terminal_path: str, session_path: Path, trigger_tick_time_msc: int | None = None) -> dict[str, Any]:
    lease = load_session_lease(session_path, datetime.now(timezone.utc))
    if not mt5.initialize(path=terminal_path):
        _bridge({}, "pause-unknown-account-state")
        raise SystemExit("Demo terminal account observation unavailable")
    try:
        account = mt5.account_info()
        if not account or account.server != SERVER:
            _bridge({}, "pause-unknown-account-state")
            raise SystemExit("MT5 is not connected to GOMarketsMU-Demo")
        if getattr(account, "currency", "") != "AUD":
            _bridge({}, "pause-unknown-account-state")
            raise SystemExit("M20 AUD loss-cap executor requires an AUD Demo account")
        # This must precede all executable M1 assessment work. A mismatch has
        # no proposal reservation or broker-order path.
        _require_account_execution_profile(account)
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
        m1_input_reason: str | None = None
        for name, timeframe, seconds in TIMEFRAMES:
            if name == "M1":
                rates = mt5.copy_rates_from_pos(SYMBOL, timeframe, 1, CLOSED_BAR_COUNT + 8)
                receipt_at = datetime.now(timezone.utc)
                boundary = int(observed_at.timestamp()) // seconds * seconds
                try:
                    rows, _ = _bar_rows(rates, timeframe_name=name, seconds=seconds,
                                        cutoff=boundary, timestamp_offset_seconds=offset_seconds,
                                        receipt_at=receipt_at)
                    raw_bars[name] = [{"timeframe": name, **row} for row in rows]
                except (SystemExit, KeyError, TypeError, ValueError, OverflowError):
                    # Retain no partly parsed or invented rows.  The durable
                    # NO_TRADE rationale records why this entry input was not
                    # usable; a later poll must obtain a complete fresh run.
                    raw_bars[name] = []
                    m1_input_reason = "M1_INPUT_INVALID_OR_INSUFFICIENT: no complete chronological closed M1 window was available."
            else:
                raw_bars[name], _ = _shadow_context_rows(
                    timeframe_name=name, timeframe=timeframe, seconds=seconds,
                    observed_at=observed_at, timestamp_offset_seconds=offset_seconds,
                )
        # Context reads can cross a minute. Bind the persisted assessment to
        # the wall clock after the complete entry input capture, not its start.
        captured_at = datetime.now(timezone.utc)
        freshness_seconds = (captured_at - observed_at).total_seconds()
        entry_m1_synchronized = (
            int(observed_at.timestamp()) // 60 == int(captured_at.timestamp()) // 60
            and _entry_m1_history_is_synchronized(rows=raw_bars["M1"], observed_at=observed_at,
                                                   receipt_cutoff=captured_at)
        )
        session = _session(lease)
        risk_policy = persistent_risk_policy()
        risk_gate = _bridge(
            {"policy": risk_policy, "account": _entry_risk_snapshot(account, captured_at)},
            "enforce-risk-policy",
        )["risk"]
        if not isinstance(risk_gate, dict) or not isinstance(risk_gate.get("entry_allowed"), bool):
            raise SystemExit("M20 persistent risk policy returned an invalid gate")
        session["maximum_loss_per_trade_aud"] = min(
            float(session["maximum_loss_per_trade_aud"]), float(risk_gate["maximum_loss_aud"])
        )
        tick_record = {
                "observed_at_utc": utc(observed_at),
                "freshness_seconds": int(freshness_seconds),
                "bid": bid,
                "ask": ask,
                "spread_points": round((ask - bid) / float(symbol.point), 4),
        }
        risk = {"volume": float(symbol.volume_min), "tick_size": float(symbol.trade_tick_size), "tick_value_loss": float(symbol.trade_tick_value_loss), "point": float(symbol.point)}
        mandate = financing_policy()
        terms = _financing_terms(symbol, captured_at)
        horizon = captured_at + timedelta(seconds=max(OWNER_MAX_HOLD_SECONDS.values()))
        risk["financing_by_side"] = {side: project_financing(terms=terms, action=side, volume=risk["volume"], now=captured_at, horizon=horizon, policy=mandate) for side in ("BUY", "SELL")}
        visible_positions = _positions_or_fail(context="assessment", symbol=SYMBOL)
        safety_gates = {
            "fresh_quote": (0 <= freshness_seconds <= MAX_TICK_AGE_SECONDS
                            and int(observed_at.timestamp()) // 60 == int(captured_at.timestamp()) // 60),
            # Count alone is insufficient: a reconnect can return an old,
            # internally plausible M1 window alongside a fresh quote.  Entry
            # requires 64 consecutive completed bars ending at this quote's
            # current minute boundary.  A failed gate remains auditable as a
            # persisted NO_TRADE assessment.
            "completed_m1": entry_m1_synchronized,
            "normal_spread": tick_record["spread_points"] <= 12.0,
            "no_existing_position": len(visible_positions) == 0,
            "demo_lease_active": True,
            # M20 has no configured economic-calendar blackout source yet;
            # this explicit fixed state prevents a silent, inferred claim.
            "news_blackout_inactive": True,
            "abnormal_volatility_inactive": tick_record["spread_points"] <= 12.0,
        }
        snapshot, proposal, strategy_selection, strategy_assessments = _assessment(
            session, tick_record, raw_bars, captured_at, risk, listener_poll_seconds, safety_gates
        )
        if m1_input_reason:
            proposal["rationale"] = m1_input_reason
            strategy_selection.update({"selected_strategy_id": None, "strategy_rule_version": None,
                                       "selection_status": "NO_SELECTION", "trade_owner_strategy_id": None,
                                       "market_regime": "UNSAFE_OR_UNTRADEABLE",
                                       "market_regime_reason": m1_input_reason,
                                       "entry_spread_cost_aud": None, "expected_exit_spread_cost_aud": None,
                                       "commission_allowance_aud": None, "slippage_allowance_aud": None,
                                       "expected_swap_aud": None, "projected_gross_profit_at_take_profit_aud": None,
                                       "estimated_round_trip_cost_aud": None, "minimum_net_profit_aud": None,
                                       "expected_net_profit_at_take_profit_aud": None,
                                       "cost_coverage_status": "NOT_APPLICABLE"})
        pre_context_owner = strategy_selection.get("selected_strategy_id")
        pre_context_candidate = next((item["signal"] for item in strategy_assessments if item["id"] == pre_context_owner), "NO_TRADE")
        if proposal["action"] != "NO_TRADE" and risk_gate["entry_allowed"] is not True:
            proposal.update({"action": "NO_TRADE", "proposed_entry": None, "stop_loss": None,
                             "take_profit": None, "notional_usd": None, "confidence": 100,
                             "rationale": f"Persistent Option B risk policy paused new entries: {risk_gate.get('pause_reason')}."})
            strategy_selection.update({"selected_strategy_id": None, "strategy_rule_version": None,
                                       "selection_status": "NO_SELECTION", "trade_owner_strategy_id": None,
                                       "market_regime": "UNSAFE_OR_UNTRADEABLE",
                                       "market_regime_reason": "Persistent Option B risk policy blocks new entries.",
                                       "entry_spread_cost_aud": None, "expected_exit_spread_cost_aud": None,
                                       "commission_allowance_aud": None, "slippage_allowance_aud": None,
                                       "expected_swap_aud": None, "projected_gross_profit_at_take_profit_aud": None,
                                       "estimated_round_trip_cost_aud": None, "minimum_net_profit_aud": None,
                                       "expected_net_profit_at_take_profit_aud": None,
                                       "cost_coverage_status": "NOT_APPLICABLE"})
        revision, fingerprint = _provenance()
        bridge_session_keys = {"session_id", "server", "instrument", "starts_at_utc", "expires_at_utc", "max_trades", "max_notional_per_trade_usd", "max_cumulative_notional_usd", "max_open_positions", "strategy_version", "operator_label"}
        bridge_payload = {"session": {key: session[key] for key in bridge_session_keys}, "proposal": proposal,
                          "decision_snapshot": snapshot, "strategy_selection": strategy_selection,
                          "strategy_assessments": strategy_assessments, "application_revision": revision,
                          "configuration_fingerprint": fingerprint}
        if proposal["action"] != "NO_TRADE":
            positions = _positions_or_fail(context="pre-submit", symbol=SYMBOL)
            if positions:
                proposal.update({
                    "action": "NO_TRADE", "proposed_entry": None, "stop_loss": None,
                    "take_profit": None, "notional_usd": None, "confidence": 100,
                    "rationale": "An owned EURUSD Demo position is already being monitored; this assessment is recorded without a second order.",
                })
                # A position gate changes an actionable proposal to a refusal;
                # it must also cease to claim executable selection/cost status.
                strategy_selection.update({"selected_strategy_id": None, "strategy_rule_version": None,
                                           "selection_status": "NO_SELECTION", "trade_owner_strategy_id": None,
                                           "market_regime": "UNSAFE_OR_UNTRADEABLE",
                                           "market_regime_reason": "A fixed M20 EURUSD Demo position is already open.",
                                           "entry_spread_cost_aud": None, "expected_exit_spread_cost_aud": None,
                                           "commission_allowance_aud": None, "slippage_allowance_aud": None,
                                           "expected_swap_aud": None, "projected_gross_profit_at_take_profit_aud": None,
                                           "estimated_round_trip_cost_aud": None, "minimum_net_profit_aud": None,
                                           "expected_net_profit_at_take_profit_aud": None,
                                           "cost_coverage_status": "NOT_APPLICABLE"})
                bridge_payload["proposal"] = proposal
                bridge_payload["strategy_selection"] = strategy_selection
        # This is deliberately after every pre-existing M20 refusal.  The
        # overlay binds the final proposal action that will be persisted, not
        # an earlier strategy candidate that a later safety gate changed.
        _apply_m1_calendar_overlay(
            snapshot=snapshot, proposal=proposal, policy=_m1_event_risk_policy(),
        )
        bridge_payload["proposal"] = proposal
        bridge_payload["decision_snapshot"] = snapshot
        bridge_payload["strategy_selection"] = strategy_selection
        multi_timeframe_context = _shadow_context(
            proposal=proposal, selection=strategy_selection, assessments=strategy_assessments,
            bars=raw_bars, observed_at=tick_record["observed_at_utc"],
            spread_points=float(tick_record["spread_points"]),
            pre_context_owner=str(pre_context_owner) if pre_context_owner else None,
            pre_context_candidate=str(pre_context_candidate),
        )
        bridge_payload["multi_timeframe_context"] = multi_timeframe_context
        persisted = _bridge(bridge_payload, "persist-proposal")
        if persisted["postgres_audit"].get("already_persisted"):
            reconciliation = _bridge({"proposal_id": proposal["proposal_id"]}, "reconcile")["reconciliation"]
            return {"marker": "FOREX_M20_DEMO_TRADING_OPERATION_OK", "schema_version": "forex.m20.demo-trading-operation.v1", "operation": "m20_demo_trading_session", "server": account.server, "symbol": SYMBOL, "captured_at_utc": utc(captured_at), "configuration_fingerprint": fingerprint, "tick_timestamp_offset_seconds": offset_seconds, "session": session, "risk_policy": risk_gate, "decision_snapshot": snapshot, "proposal": proposal, "strategy_selection": strategy_selection, "strategy_assessments": strategy_assessments, "multi_timeframe_context": multi_timeframe_context, "execution": {"status": "ALREADY_PERSISTED_NO_RESUBMISSION", "proposal_id": proposal["proposal_id"]}, "reconciliation": reconciliation, "postgres_audit": persisted["postgres_audit"], "probe_sha256": os.environ.get("FOREX_M20_DEMO_TRADING_SESSION_SHA256", "UNDECLARED")}
        if proposal["action"] != "NO_TRADE":
            # The reservation is the execution boundary. Re-checking here
            # prevents an account mismatch from claiming a slot or order.
            _require_account_execution_profile(mt5.account_info())
            fresh_account = _entry_risk_snapshot(mt5.account_info(), datetime.now(timezone.utc))
            _bridge({"policy": risk_policy, "account": fresh_account}, "enforce-risk-policy")
            financing = risk["financing_by_side"][proposal["action"]]
            risk["financing"] = financing
            fresh_terms = _financing_terms(mt5.symbol_info(SYMBOL), datetime.now(timezone.utc))
            fresh_now = datetime.now(timezone.utc)
            fresh_financing = project_financing(terms=fresh_terms, action=proposal["action"], volume=risk["volume"], now=fresh_now, horizon=fresh_now + timedelta(seconds=max(OWNER_MAX_HOLD_SECONDS.values())), policy=mandate)
            if fresh_financing.get("status") not in {"QUALIFIED_INPUTS", "DEMO_ESTIMATE", "DEFERRED_FOR_DEMO"} or any(fresh_financing[k] != financing[k] for k in ("status", "expected_swap_aud", "commission_allowance_aud", "adverse_financing_aud")):
                raise SystemExit("M20 financing changed before reservation; fresh assessment required")
            planned_loss = _planned_stop_loss(float(proposal["proposed_entry"]), float(proposal["stop_loss"]), {**risk, "observed_spread": float(tick_record["ask"]) - float(tick_record["bid"])})
            submitted_at = utc(datetime.now(timezone.utc))
            attempt_id = str(uuid5(NAMESPACE_URL, f"{proposal['proposal_id']}:attempt"))
            reservation = {
                "attempt_id": attempt_id, "idempotency_key": str(uuid5(NAMESPACE_URL, f"{proposal['proposal_id']}:idempotency")),
                "submitted_at_utc": submitted_at, "redacted_result": "MT5 result pending", "broker_open_positions": 0,
                "account_scope_sha256": fresh_account["account_scope_sha256"], "planned_loss_aud": planned_loss,
            }
            reserved = _bridge({**bridge_payload, "reservation": reservation}, "reserve-execution")
            _, _, submission_refusal = _current_entry_inputs(
                offset_seconds=offset_seconds,
                expected_boundary=int(parse_utc(proposal["decision_at_utc"], "decision_at_utc").timestamp()) // 60 * 60,
                # Receipt timestamps prove the original decision's
                # availability but naturally differ on the fresh submission
                # recheck; compare only the broker candle values here.
                expected_m1_digest=hashlib.sha256(json.dumps([{key: value for key, value in row.items()
                                                                if key not in {"timeframe", "available_at_utc"}}
                                                               for row in raw_bars["M1"]], sort_keys=True,
                                                              separators=(",", ":")).encode()).hexdigest(),
            )
            if submission_refusal is None:
                submission_refusal = _terminal_submission_refusal(mt5.account_info())
            if submission_refusal:
                validation_at = utc(datetime.now(timezone.utc))
                non_submission_context = {
                    "schema_version": "forex.m20.not-submitted.v1", "reason": submission_refusal,
                    "validation_at_utc": validation_at,
                }
                _bridge({"result": {
                    "event_id": str(uuid5(NAMESPACE_URL, f"{attempt_id}:not-submitted")),
                    "attempt_id": attempt_id, "event_type": "NOT_SUBMITTED",
                    "observed_at_utc": validation_at, "broker_order_reference": "",
                    "payload_sha256": "sha256:" + hashlib.sha256(json.dumps(non_submission_context, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
                    "payload": non_submission_context,
                }}, "record-result")
                reconciliation = _bridge({"proposal_id": proposal["proposal_id"]}, "reconcile")["reconciliation"]
                if reconciliation.get("status") != "NOT_SUBMITTED_RECONCILED":
                    raise SystemExit("M20 stale submission refusal was not reconciled")
                return {"marker": "FOREX_M20_DEMO_TRADING_OPERATION_OK", "schema_version": "forex.m20.demo-trading-operation.v1", "operation": "m20_demo_trading_session", "server": account.server, "symbol": SYMBOL, "captured_at_utc": utc(captured_at), "configuration_fingerprint": fingerprint, "tick_timestamp_offset_seconds": offset_seconds, "session": session, "risk_policy": risk_gate, "decision_snapshot": snapshot, "proposal": proposal, "strategy_selection": strategy_selection, "strategy_assessments": strategy_assessments, "multi_timeframe_context": multi_timeframe_context, "execution": {"status": "NOT_SUBMITTED_AFTER_RESERVATION", "attempt_id": attempt_id, "session_id": session["session_id"], "proposal_id": proposal["proposal_id"], "idempotency_key": reservation["idempotency_key"], "submitted_at_utc": submitted_at, "open_positions_before": 0, "cumulative_notional_before_usd": 0}, "reconciliation": reconciliation, "postgres_audit": reserved["postgres_audit"], "probe_sha256": os.environ.get("FOREX_M20_DEMO_TRADING_SESSION_SHA256", "UNDECLARED")}
            # The earlier check protects the reservation boundary. This final
            # check is deliberately adjacent to the only broker order call.
            _require_account_execution_profile(mt5.account_info())
            order_type = mt5.ORDER_TYPE_BUY if proposal["action"] == "BUY" else mt5.ORDER_TYPE_SELL
            request = {"action": mt5.TRADE_ACTION_DEAL, "symbol": SYMBOL, "volume": risk["volume"], "type": order_type,
                       "price": proposal["proposed_entry"], "sl": proposal["stop_loss"], "tp": proposal["take_profit"],
                       "deviation": 20, "magic": EXECUTOR_MAGIC, "comment": "forex-m20-demo", "type_time": mt5.ORDER_TIME_GTC,
                       "type_filling": mt5.ORDER_FILLING_IOC}
            result = mt5.order_send(request)
            full_fill, partial_fill = _execution_result_state(result)
            broker_reports_fill = full_fill or partial_fill
            broker_reference = str(getattr(result, "order", "")) if result else ""
            # Preserve the complete non-secret request and market/cap context
            # on the immutable broker-result event.  This makes future MT5
            # rejections diagnosable without an unsafe retry or generic order
            # interface.  Existing sparse historical rejections remain raw
            # incomplete evidence rather than receiving invented causes.
            position = None
            position_observation_error = None
            if broker_reports_fill:
                try:
                    position = _wait_for_position()
                except SystemExit as error:
                    # The broker has reported execution but the terminal has
                    # not proved the resulting exposure. Persist an immutable
                    # UNKNOWN result and leave the reservation blocking; a
                    # retry here could duplicate a real position.
                    position_observation_error = str(error)
            observed_open = position is not None
            event_type = "OPENED" if observed_open else ("UNKNOWN" if broker_reports_fill else "REJECTED")
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
                "position_identifier": int(getattr(position, "identifier", 0) or 0) if position else None,
                "fill_status": "FULL" if full_fill else ("PARTIAL" if partial_fill else ("UNKNOWN" if broker_reports_fill else "REJECTED")),
                "broker_filled_volume": float(getattr(position, "volume", 0)) if position else None,
                "position_observation_error": position_observation_error,
            }
            if position is not None:
                # The proposal price is only the requested price.  Preserve
                # the broker-observed opening fill separately for the ledger.
                result_context["actual_entry_price"] = float(position.price_open)
                if float(position.volume) <= 0 or float(position.volume) > float(risk["volume"]) + 1e-9:
                    raise SystemExit("M20 broker opening fill volume is invalid")
            result_payload = {"event_id": str(uuid5(NAMESPACE_URL, f"{attempt_id}:result")), "attempt_id": attempt_id,
                              "event_type": event_type, "observed_at_utc": utc(datetime.now(timezone.utc)),
                              "broker_order_reference": broker_reference, "payload_sha256": "sha256:" + hashlib.sha256(json.dumps(result_context, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
                              "payload": result_context}
            _bridge({"result": result_payload}, "record-result")
            if observed_open:
                opened_at_utc = utc(datetime.now(timezone.utc))
                _bridge({"state": {"proposal_id": proposal["proposal_id"], "attempt_id": attempt_id, "position_ticket": int(position.ticket), "action": proposal["action"], "opened_at_utc": opened_at_utc, "observed_at_utc": opened_at_utc, "entry_price": float(position.price_open), "stop_loss": float(position.sl), "take_profit": float(position.tp)}}, "record-open-position")
                monitor_job = _write_monitor_job(
                    session_path=session_path, proposal=proposal, trade_owner_strategy_id=strategy_selection["trade_owner_strategy_id"], attempt_id=attempt_id,
                    position=position, submitted_at=submitted_at, entry_spread=ask - bid,
                    risk=risk, offset_seconds=offset_seconds,
                )
                _notify_opened_position(proposal=proposal, position=position, opened_at_utc=opened_at_utc)
                reconciliation = {"status": "OPEN_MONITORING", "position_ticket": int(position.ticket)}
            elif event_type == "REJECTED":
                reconciliation = _bridge({"proposal_id": proposal["proposal_id"]}, "reconcile")["reconciliation"]
            else:
                raise SystemExit("M20 broker-reported fill has unresolved position exposure; new entries remain blocked")
            expected_status = "OPEN_MONITORING" if observed_open else "MATCHED"
            if reconciliation.get("status") != expected_status:
                raise SystemExit("M20 actionable execution was not reconciled")
            return {"marker": "FOREX_M20_DEMO_TRADING_OPERATION_OK", "schema_version": "forex.m20.demo-trading-operation.v1", "operation": "m20_demo_trading_session", "server": account.server, "symbol": SYMBOL, "captured_at_utc": utc(captured_at), "configuration_fingerprint": fingerprint, "tick_timestamp_offset_seconds": offset_seconds, "session": session, "risk_policy": risk_gate, "decision_snapshot": snapshot, "proposal": proposal, "strategy_selection": strategy_selection, "strategy_assessments": strategy_assessments, "multi_timeframe_context": multi_timeframe_context, "execution": {"status": "ACCEPTED" if full_fill else ("ACCEPTED_PARTIAL" if partial_fill else "REJECTED"), "attempt_id": attempt_id, "session_id": session["session_id"], "proposal_id": proposal["proposal_id"], "idempotency_key": reservation["idempotency_key"], "submitted_at_utc": submitted_at, "open_positions_before": 0, "cumulative_notional_before_usd": 0, "broker_retcode": getattr(result, "retcode", None), "monitor_job_scheduled": observed_open, "monitor_job_path": str(monitor_job) if observed_open else None}, "reconciliation": reconciliation, "postgres_audit": reserved["postgres_audit"], "probe_sha256": os.environ.get("FOREX_M20_DEMO_TRADING_SESSION_SHA256", "UNDECLARED")}
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
            "session": session, "risk_policy": risk_gate, "decision_snapshot": snapshot, "proposal": proposal, "strategy_selection": strategy_selection, "strategy_assessments": strategy_assessments, "multi_timeframe_context": multi_timeframe_context,
            "execution": {"status": "NOT_SUBMITTED", "attempt_id": None},
            "reconciliation": reconciliation, "postgres_audit": persisted["postgres_audit"],
            "probe_sha256": os.environ.get("FOREX_M20_DEMO_TRADING_SESSION_SHA256", "UNDECLARED"),
        }
    finally:
        mt5.shutdown()


def main(terminal_path: str, session_path: str, trigger_tick_time_msc: int | None = None) -> None:
    print(json.dumps(capture(terminal_path, Path(session_path), trigger_tick_time_msc), separators=(",", ":")))


def held_readiness_assessment(terminal_path: str) -> None:
    """Evaluate current Demo account risk while structurally unable to trade.

    This is the pre-release counterpart to an ordinary listener assessment.
    It deliberately does not load a lease, proposal, or execution path: its
    sole broker interaction is read-only account/position inspection, followed
    by the existing persistent-risk evaluator.  In particular, this function
    contains no order request and cannot reserve or submit an order.
    """
    initialized = False
    try:
        initialized = mt5.initialize(path=terminal_path)
        if not initialized:
            raise SystemExit("M20 readiness assessment could not initialize MT5")
        account = mt5.account_info()
        _require_account_execution_profile(account)
        captured_at = datetime.now(timezone.utc)
        positions = _positions_or_fail(context="held-readiness", symbol=SYMBOL)
        policy = persistent_risk_policy()
        risk_gate = _bridge(
            {"policy": policy, "account": _entry_risk_snapshot(account, captured_at)},
            "enforce-risk-policy",
        )["risk"]
        if not isinstance(risk_gate, dict) or not isinstance(risk_gate.get("entry_allowed"), bool):
            raise SystemExit("M20 persistent risk policy returned an invalid readiness gate")
        revision, fingerprint = _provenance()
        print(json.dumps({
            "marker": "FOREX_M20_DEMO_HELD_READINESS_ASSESSMENT_OK",
            "schema_version": "forex.m20.held-readiness-assessment.v1",
            "operation": "m20_demo_held_readiness_assessment",
            "server": account.server,
            "currency": account.currency,
            "symbol": SYMBOL,
            "captured_at_utc": utc(captured_at),
            "application_revision": revision,
            "configuration_fingerprint": fingerprint,
            "risk_policy": risk_gate,
            "open_positions": len(positions),
            "broker_mutation": "NONE",
            "order_submission": "STRUCTURALLY_UNAVAILABLE",
        }, separators=(",", ":")))
    finally:
        if initialized:
            mt5.shutdown()


if __name__ == "__main__":
    if len(sys.argv) == 3:
        _run_single_client(lambda: main(sys.argv[1], sys.argv[2]), requires_bridge=True)
    elif len(sys.argv) == 5 and sys.argv[3] == "--assessment-trigger-tick-ms":
        try:
            trigger = int(sys.argv[4])
        except ValueError as error:
            raise SystemExit("M20 assessment trigger tick must be an integer") from error
        if trigger <= 0:
            raise SystemExit("M20 assessment trigger tick must be positive")
        _run_single_client(lambda: main(sys.argv[1], sys.argv[2], trigger), requires_bridge=True)
    elif len(sys.argv) == 4 and sys.argv[3] == "--monitor-once":
        result = _run_single_client(lambda: monitor(sys.argv[1], Path(sys.argv[2]), single_pass=True), requires_bridge=True)
        print(json.dumps(result, separators=(",", ":")))
    elif len(sys.argv) == 4 and sys.argv[3] == "--recover-open-positions-once":
        result = _run_single_client(lambda: recover_open_positions(sys.argv[1]), requires_bridge=True)
        print(json.dumps(result, separators=(",", ":")))
    elif len(sys.argv) == 4 and sys.argv[3] == "--quote-identity":
        result = _run_single_client(lambda: quote_identity(sys.argv[1]), requires_bridge=False)
        print(json.dumps(result, separators=(",", ":")))
    elif len(sys.argv) == 4 and sys.argv[3] == "--terminal-runtime-binding":
        result = _run_single_client(lambda: terminal_runtime_binding(sys.argv[1]), requires_bridge=False)
        print(json.dumps(result, separators=(",", ":")))
    elif len(sys.argv) == 4 and sys.argv[3] == "--financing-preview":
        result = _run_single_client(lambda: financing_preview(sys.argv[1]), requires_bridge=False)
        print(json.dumps(result, separators=(",", ":")))
    elif len(sys.argv) == 4 and sys.argv[3] == "--risk-refusal-drill":
        result = _run_single_client(lambda: risk_refusal_drill(sys.argv[1], Path(sys.argv[2])), requires_bridge=True)
        print(json.dumps(result, separators=(",", ":")))
    elif len(sys.argv) == 4 and sys.argv[3] == "--execution-drill":
        result = _run_single_client(lambda: execution_drill(sys.argv[1], Path(sys.argv[2])), requires_bridge=True)
        print(json.dumps(result, separators=(",", ":")))
    elif len(sys.argv) == 4 and sys.argv[3] == "--reconcile-retained-history":
        result = _run_single_client(lambda: reconcile_historical_retained_positions(sys.argv[1]), requires_bridge=True)
        print(json.dumps(result, separators=(",", ":")))
    elif len(sys.argv) == 4 and sys.argv[3] == "--audit-isolation-spike":
        result = _run_single_client(audit_isolation_spike, requires_bridge=True)
        print(json.dumps(result, separators=(",", ":")))
    elif len(sys.argv) == 4 and sys.argv[3] == "--pre-isolation-readiness":
        result = _run_single_client(pre_isolation_readiness, requires_bridge=True)
        print(json.dumps(result, separators=(",", ":")))
    elif len(sys.argv) == 3 and sys.argv[2] == "--held-readiness-assessment":
        _run_single_client(lambda: held_readiness_assessment(sys.argv[1]), requires_bridge=True)
    else:
        raise SystemExit("expected fixed terminal path and fixed M20 session lease path")
