#!/usr/bin/env python3
"""Read-only terminal view of M20 Demo trade monitoring and realised P&L."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import time
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def trade_rows() -> list[dict[str, Any]]:
    """Read the fixed lifecycle summary; never contacts MT5 or submits orders."""
    try:
        completed = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "postgres_pgvector_adapter.py"), "forex-m20-lifecycle-summary"],
            cwd=ROOT, text=True, capture_output=True, check=False, timeout=8,
        )
    except subprocess.TimeoutExpired:
        return [{"error": "PostgreSQL ledger check exceeded eight seconds; dashboard will retry."}]
    if completed.returncode:
        return [{"error": completed.stderr.strip() or completed.stdout.strip()}]
    try:
        envelope = json.loads(completed.stdout)
        rows = json.loads(envelope["result"]["stdout"])
        return rows if isinstance(rows, list) else [{"error": "Ledger returned an invalid row list."}]
    except (KeyError, TypeError, json.JSONDecodeError) as error:
        return [{"error": f"Unable to read PostgreSQL trade ledger: {error}"}]


def active_monitor_attempt() -> str | None:
    """Return the one actively monitored attempt reported by the T480 listener."""
    try:
        completed = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "t480_adapter.py"), "execute", "--operation", "m20_listener_status"],
            cwd=ROOT, text=True, capture_output=True, check=False, timeout=8,
        )
        envelope = json.loads(completed.stdout)
        status = json.loads(envelope["result"]["stdout"])
        recovered = ((status.get("monitor") or {}).get("result") or {}).get("recovered") or []
        for item in recovered:
            if isinstance(item, dict) and item.get("attempt_id"):
                return str(item["attempt_id"])
    except (KeyError, TypeError, json.JSONDecodeError, subprocess.TimeoutExpired):
        pass
    return None


def _state(row: dict[str, Any], active_attempt_id: str | None) -> str:
    if active_attempt_id is not None and row.get("attempt_id") == active_attempt_id:
        return "MONITORING"
    lifecycle = row.get("lifecycle")
    if lifecycle == "OPEN_MONITORING":
        return "MONITORING"
    if lifecycle == "CLOSED_RECONCILIATION_ERROR":
        return "RECONCILIATION ERROR"
    if lifecycle == "CLOSED_MATCHED" and _outcome_is_plausible(row):
        return "SOLD / VERIFIED"
    if lifecycle == "CLOSED_MATCHED":
        return "RECONCILIATION ERROR"
    if lifecycle == "TERMINAL_REJECTED":
        return "REJECTED"
    if lifecycle == "TERMINAL_FAILED":
        return "NEEDS RECONCILIATION"
    return "PENDING"


def _outcome_is_plausible(row: dict[str, Any]) -> bool:
    """Use the authoritative reconciliation overlay; never invent a P&L guard."""
    if row.get("reconciliation_status") == "RECONCILIATION_ERROR":
        return False
    if row.get("reconciliation_disposition") in {"INVALIDATED", "HISTORY_UNAVAILABLE"}:
        return False
    return row.get("realized_pnl_account") is not None and bool(row.get("account_currency"))


def _pnl(row: dict[str, Any]) -> str:
    state = _state(row, None)
    if state == "REJECTED":
        return "N/A — no order opened"
    if state == "RECONCILIATION ERROR":
        return "Not verified"
    value, currency = row.get("realized_pnl_account"), row.get("account_currency")
    if value is None or not currency:
        return "Pending"
    if not _outcome_is_plausible(row):
        return "Invalid"
    return f"{float(value):+.2f} {currency}"


def _timestamp(value: Any) -> str:
    """Make ISO timestamps quick to scan while retaining their UTC meaning."""
    if not value:
        return "—"
    text = str(value)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is not None:
            return parsed.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    except ValueError:
        pass
    return text.replace("T", " ") + " (timezone not recorded)"


def _number(value: Any) -> str:
    """Use a deliberate placeholder rather than Python's ``None`` in the UI."""
    return str(value) if value not in (None, "") else "—"


def _card(row: dict[str, Any], active_attempt_id: str | None) -> list[str]:
    """Render one attempt as a labelled, terminal-friendly summary card."""
    state = _state(row, active_attempt_id)
    side = _number(row.get("action")).upper()
    pnl = _pnl(row)
    lines = [
        "─" * 78,
        f"{side}  |  {state}  |  P&L: {pnl}",
        f"Opened: {_timestamp(row.get('submitted_at_utc'))}    Size: {_number(row.get('volume_lots'))} lots",
        "Proposed entry: {entry}    Stop loss: {stop_loss}    Take profit: {take_profit}".format(
            entry=_number(row.get("proposed_entry")),
            stop_loss=_number(row.get("stop_loss")),
            take_profit=_number(row.get("take_profit")),
        ),
    ]
    if row.get("closed_at_utc"):
        lines.extend([
            f"Closed: {_timestamp(row.get('closed_at_utc'))}    Exit price: {_number(row.get('exit_price'))}",
            f"Close reason: {_number(row.get('close_reason'))}",
        ])
        if state == "RECONCILIATION ERROR":
            reason = row.get("reconciliation_reason") or "broker outcome is not exactly reconciled"
            lines.append(f"Outcome check: NOT VERIFIED — {reason}")
    elif state == "MONITORING":
        lines.append("Now: position is open; the listener is monitoring its protected exit.")
    elif state == "NEEDS RECONCILIATION":
        lines.append("Outcome check: waiting for MT5 history to provide a verifiable close and P&L.")
    elif state == "REJECTED":
        context = row.get("rejection_context") or {}
        code = context.get("retcode") or "not recorded"
        comment = context.get("broker_comment") or "historical record has no broker message"
        lines.append(f"Broker response: MT5 {code} — {comment}")
        context_fields = ("requested_price", "observed_bid", "observed_ask", "spread_points")
        if all(context.get(field) not in (None, "") for field in context_fields):
            lines.append(
                f"Request: {context['requested_price']}    Market then: bid {context['observed_bid']} / "
                f"ask {context['observed_ask']}    Spread: {context['spread_points']} pts"
            )
        else:
            lines.append("Broker context: unavailable (legacy record).")
    return lines


def render(rows: list[dict[str, Any]], active_attempt_id: str | None = None) -> str:
    lines = [
        "M20 Demo Trade Ledger — monitoring, closes, and P&L",
        "=" * 58,
        "Demo-only. This screen is read-only; P&L appears only after MT5 reconciliation.",
        "",
    ]
    if rows and rows[0].get("error"):
        lines.append(f"Ledger: UNAVAILABLE — {rows[0]['error']}")
        return "\n".join(lines)
    visible = list(reversed(rows[-10:]))
    if not visible:
        lines.append("No Demo execution attempts have been recorded yet.")
        return "\n".join(lines)
    lines.append(f"Latest {len(visible)} attempt{'s' if len(visible) != 1 else ''} — newest first")
    for row in visible:
        lines.extend(_card(row, active_attempt_id))
    lines.append("\nCtrl+C exits. Refreshes do not change trades or ledger rows.")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="View M20 Demo trade monitoring and realised P&L.")
    parser.add_argument("--interval", type=float, default=2.0, help="Dashboard refresh seconds (default: 2).")
    parser.add_argument("--once", action="store_true", help="Render one update then exit.")
    args = parser.parse_args()
    if args.interval < 1:
        parser.error("--interval must be at least one second")
    while True:
        print("\033[2J\033[H" + render(trade_rows(), active_monitor_attempt()), flush=True)
        if args.once:
            return 0
        try:
            time.sleep(args.interval)
        except KeyboardInterrupt:
            print("\nDashboard stopped.")
            return 0


if __name__ == "__main__":
    raise SystemExit(main())
