#!/usr/bin/env python3
"""Fixed, best-effort Discord notifications for M20 Demo position lifecycle events.

The webhook URL is deliberately read only from the T480-local environment. A
notification failure is reported to the caller but is never allowed to alter a
Demo trade, its monitor, or its PostgreSQL lifecycle.
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


SALE_REQUIRED = {
    "server", "symbol", "proposal_id", "position_ticket", "side", "strategy",
    "opened_at_utc", "closed_at_utc", "entry_price", "exit_price", "lots",
    "close_reason", "gross_pnl_aud", "commission_aud", "fee_aud", "swap_aud",
    "estimated_cost_aud", "realized_pnl_aud", "liquidity",
}
OPEN_REQUIRED = {
    "server", "symbol", "proposal_id", "position_ticket", "side", "strategy",
    "opened_at_utc", "entry_price", "stop_loss", "take_profit", "lots",
}
LIQUIDITY_REQUIRED = {"currency", "balance", "equity", "free_margin", "margin", "floating_pnl"}
APPROVED_WEBHOOK_PREFIXES = ("https://discord.com/api/webhooks/", "https://discordapp.com/api/webhooks/")


def _number(value: Any, name: str) -> float:
    if not isinstance(value, (int, float)):
        raise ValueError(f"Discord notification {name} must be numeric")
    return float(value)


def _validate_identity(payload: dict[str, Any], required: set[str], event: str) -> None:
    if set(payload) != required:
        raise ValueError(f"Discord {event} notification payload fields are invalid")
    if payload["server"] != "GOMarketsMU-Demo" or payload["symbol"] != "EURUSD":
        raise ValueError(f"Discord {event} notification accepts only Demo EURUSD")
    if payload["side"] not in {"BUY", "SELL"}:
        raise ValueError(f"Discord {event} notification side is invalid")
    if not all(isinstance(payload[key], str) and payload[key] for key in (
        "proposal_id", "strategy", "opened_at_utc",
    )) or not isinstance(payload["position_ticket"], int) or payload["position_ticket"] <= 0:
        raise ValueError(f"Discord {event} notification identity is invalid")


def validate_sale(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate a Demo EURUSD close notification without accepting a URL."""
    _validate_identity(payload, SALE_REQUIRED, "sale")
    if not all(isinstance(payload[key], str) and payload[key] for key in (
        "closed_at_utc", "close_reason",
    )):
        raise ValueError("Discord sale notification identity is invalid")
    liquidity = payload["liquidity"]
    if not isinstance(liquidity, dict) or set(liquidity) != LIQUIDITY_REQUIRED or liquidity["currency"] != "AUD":
        raise ValueError("Discord sale notification liquidity is invalid")
    for name in ("entry_price", "exit_price", "lots", "gross_pnl_aud", "commission_aud", "fee_aud", "swap_aud", "estimated_cost_aud", "realized_pnl_aud"):
        _number(payload[name], name)
    for name in LIQUIDITY_REQUIRED - {"currency"}:
        _number(liquidity[name], f"liquidity.{name}")
    return payload


def validate_open(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate a protected Demo EURUSD open notification without accepting a URL."""
    _validate_identity(payload, OPEN_REQUIRED, "open")
    for name in ("entry_price", "stop_loss", "take_profit", "lots"):
        if _number(payload[name], name) <= 0:
            raise ValueError(f"Discord open notification {name} must be positive")
    return payload


def render_sale(payload: dict[str, Any]) -> str:
    """Render a concise, human-readable Demo close message."""
    payload = validate_sale(payload)
    liquidity = payload["liquidity"]
    result = float(payload["realized_pnl_aud"])
    outcome = "profit" if result > 0 else "loss" if result < 0 else "flat"
    return "\n".join((
        f"**Demo EURUSD sold — {outcome}: {result:+.2f} AUD**",
        f"{payload['side']} {float(payload['lots']):.2f} lots | {payload['strategy']} | ticket {payload['position_ticket']}",
        f"Entry {float(payload['entry_price']):.5f} → exit {float(payload['exit_price']):.5f} | {payload['close_reason']}",
        f"Gross {float(payload['gross_pnl_aud']):+.2f} | commission {float(payload['commission_aud']):+.2f} | fee {float(payload['fee_aud']):+.2f} | swap {float(payload['swap_aud']):+.2f} | estimated costs {float(payload['estimated_cost_aud']):.2f} AUD",
        f"Liquidity: balance {float(liquidity['balance']):,.2f} AUD | equity {float(liquidity['equity']):,.2f} | free margin {float(liquidity['free_margin']):,.2f} | used margin {float(liquidity['margin']):,.2f} | floating P/L {float(liquidity['floating_pnl']):+.2f}",
        f"Closed {payload['closed_at_utc']} | Demo-only, broker-reconciled",
    ))


def render_open(payload: dict[str, Any]) -> str:
    """Render the Wave 1 resumption prompt after durable protected OPENED state."""
    payload = validate_open(payload)
    return "\n".join((
        "**Demo EURUSD opened — resume Wave 1**",
        f"{payload['side']} {float(payload['lots']):.2f} lots | {payload['strategy']} | ticket {payload['position_ticket']}",
        f"Entry {float(payload['entry_price']):.5f} | SL {float(payload['stop_loss']):.5f} | TP {float(payload['take_profit']):.5f}",
        f"Opened {payload['opened_at_utc']} | broker protection and durable OPENED record confirmed",
    ))


def _webhook_url() -> str:
    if os.environ.get("FOREX_M20_DISCORD_NOTIFICATIONS_ENABLED", "false").lower() != "true":
        return ""
    url = os.environ.get("FOREX_M20_DISCORD_WEBHOOK_URL", "")
    if not url.startswith(APPROVED_WEBHOOK_PREFIXES):
        raise ValueError("M20 Discord webhook is absent or not an approved Discord webhook URL")
    return url


def _notify(payload: dict[str, Any], message: str) -> dict[str, Any]:
    url = _webhook_url()
    if not url:
        return {"ok": True, "delivery": "DISABLED", "proposal_id": payload["proposal_id"]}
    request = Request(url, data=json.dumps({"content": message}, separators=(",", ":")).encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urlopen(request, timeout=3) as response:
            if not 200 <= response.status < 300:
                return {"ok": False, "delivery": "FAILED", "proposal_id": payload["proposal_id"], "detail": f"Discord HTTP {response.status}"}
    except (HTTPError, URLError, TimeoutError, OSError) as error:
        return {"ok": False, "delivery": "FAILED", "proposal_id": payload["proposal_id"], "detail": str(error)[:160]}
    return {"ok": True, "delivery": "SENT", "proposal_id": payload["proposal_id"]}


def notify_sale(payload: dict[str, Any]) -> dict[str, Any]:
    """Send one close notification. Disabled or failed delivery is non-fatal."""
    return _notify(payload, render_sale(payload))


def notify_open(payload: dict[str, Any]) -> dict[str, Any]:
    """Send one durable protected-open notification. Delivery is non-fatal."""
    return _notify(payload, render_open(payload))


def main() -> int:
    try:
        value = json.load(sys.stdin)
        if not isinstance(value, dict):
            raise ValueError("Discord sale notification requires an object")
        print(json.dumps(notify_sale(value), separators=(",", ":")))
        return 0
    except (json.JSONDecodeError, ValueError) as error:
        print(json.dumps({"ok": False, "delivery": "INVALID", "detail": str(error)}), file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
