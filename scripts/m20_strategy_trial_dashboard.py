#!/usr/bin/env python3
"""Read-only M20.11 five-strategy Demo trial scoreboard."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OWNERS = (
    ("momentum_breakout", "Momentum"),
    ("compression_breakout", "Compression"),
    ("trend_pullback", "Trend pullback"),
    ("range_reversion", "Range reversion"),
    ("session_breakout", "Session"),
)


def trial_rows() -> list[dict[str, Any]]:
    """Read the fixed PostgreSQL summary; this dashboard cannot trade."""
    try:
        completed = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "postgres_pgvector_adapter.py"), "forex-m20-strategy-trial-summary"],
            cwd=ROOT, text=True, capture_output=True, check=False, timeout=8,
        )
    except subprocess.TimeoutExpired:
        return [{"error": "PostgreSQL trial summary exceeded eight seconds; retry."}]
    if completed.returncode:
        return [{"error": completed.stderr.strip() or completed.stdout.strip()}]
    try:
        envelope = json.loads(completed.stdout)
        rows = json.loads(envelope["result"]["stdout"])
        return rows if isinstance(rows, list) else [{"error": "Trial summary returned an invalid row list."}]
    except (KeyError, TypeError, json.JSONDecodeError) as error:
        return [{"error": f"Unable to read M20.11 trial summary: {error}"}]


def render(rows: list[dict[str, Any]]) -> str:
    lines = [
        "M20.11 v2 Demo Strategy Trial — broker-countable outcomes",
        "=" * 60,
        "Demo-only and read-only. Current v2 rule version only; zero means no verified sample yet, not a loss or a pass.",
        "",
    ]
    if rows and rows[0].get("error"):
        lines.append(f"Trial summary: UNAVAILABLE — {rows[0]['error']}")
        return "\n".join(lines)
    lines.extend([
        "Strategy          Signals  Selected  Not tried  Attempts  Opened  Rejected  Closed  W/L    Net P&L",
        "----------------  -------  --------  ---------  --------  ------  --------  ------  -----  --------",
    ])
    by_strategy = {str(row.get("strategy_id")): row for row in rows}
    totals = {key: 0 for key in ("signal_count", "selected_count", "attempt_count", "opened_count", "rejected_count", "verified_closed_count", "win_count", "loss_count")}
    net_total = 0.0
    for strategy_id, label in OWNERS:
        row = {"strategy_id": strategy_id, "strategy_label": label, **by_strategy.get(strategy_id, {})}
        net = float(row.get("net_realized_pnl_aud") or 0)
        selected = int(row.get("selected_count") or 0)
        attempts = int(row.get("attempt_count") or 0)
        for key in totals:
            totals[key] += int(row.get(key) or 0)
        net_total += net
        lines.append(
            f"{str(row.get('strategy_label') or '—'):<16}  "
            f"{int(row.get('signal_count') or 0):>7}  {selected:>8}  {max(0, selected - attempts):>9}  "
            f"{attempts:>8}  {int(row.get('opened_count') or 0):>6}  "
            f"{int(row.get('rejected_count') or 0):>8}  {int(row.get('verified_closed_count') or 0):>6}  "
            f"{int(row.get('win_count') or 0)}/{int(row.get('loss_count') or 0):<3}  {net:+.2f} AUD"
        )
    lines.append(
        f"{'TOTAL':<16}  {totals['signal_count']:>7}  {totals['selected_count']:>8}  "
        f"{max(0, totals['selected_count'] - totals['attempt_count']):>9}  {totals['attempt_count']:>8}  "
        f"{totals['opened_count']:>6}  {totals['rejected_count']:>8}  {totals['verified_closed_count']:>6}  "
        f"{totals['win_count']}/{totals['loss_count']:<3}  {net_total:+.2f} AUD"
    )
    lines.append("\nSignals are observations; selected means regime precedence chose that owner. Not tried means no MT5 attempt followed that selection.")
    return "\n".join(lines)


def main() -> int:
    print(render(trial_rows()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
