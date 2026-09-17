#!/usr/bin/env python3
"""Read-only terminal evidence view for the latest M1 Demo decision.

This view only invokes the fixed T480 latest-assessment export and the fixed
PostgreSQL lifecycle summary.  It cannot assess, submit, modify, or recover a
trade.  A lifecycle row is joined only by the exact proposal id; missing or
ambiguous facts are deliberately displayed as UNKNOWN.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
import time
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
UNKNOWN = "UNKNOWN"


def _run_json(command: list[str], *, timeout: int, label: str) -> Any:
    try:
        completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True,
                                   check=False, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"error": f"{label} exceeded {timeout} seconds"}
    if completed.returncode:
        return {"error": completed.stderr.strip() or completed.stdout.strip() or f"{label} failed"}
    try:
        envelope = json.loads(completed.stdout)
        return json.loads(envelope["result"]["stdout"])
    except (KeyError, TypeError, json.JSONDecodeError) as error:
        return {"error": f"Unable to read {label}: {error}"}


def latest_assessment() -> dict[str, Any]:
    value = _run_json(
        [sys.executable, str(ROOT / "scripts" / "t480_adapter.py"), "execute",
         "--operation", "m20_listener_latest_assessment"],
        timeout=12, label="latest-assessment export",
    )
    return value if isinstance(value, dict) else {"error": "Latest-assessment export returned an invalid record"}


def lifecycle_rows() -> list[dict[str, Any]]:
    value = _run_json(
        [sys.executable, str(ROOT / "scripts" / "postgres_pgvector_adapter.py"),
         "forex-m20-lifecycle-summary"],
        timeout=15, label="PostgreSQL lifecycle summary",
    )
    if isinstance(value, list) and all(isinstance(row, dict) for row in value):
        return value
    if isinstance(value, dict) and value.get("error"):
        return [value]
    return [{"error": "PostgreSQL lifecycle summary returned an invalid row list"}]


def _value(value: Any, fallback: str = UNKNOWN) -> str:
    return fallback if value in (None, "") else str(value)


def _matching_lifecycle(rows: list[dict[str, Any]], proposal_id: Any, action: Any) -> tuple[dict[str, Any] | None, str]:
    if action == "NO_TRADE":
        return None, "NOT_APPLICABLE (terminal no-trade has no execution lifecycle)"
    if not proposal_id:
        return None, "NOT_APPLICABLE (no proposal id)"
    if rows and rows[0].get("error"):
        return None, f"UNKNOWN ({rows[0]['error']})"
    matches = [row for row in rows if row.get("proposal_id") == proposal_id]
    if len(matches) == 1:
        return matches[0], "MATCHED by exact proposal id"
    if not matches:
        return None, "UNRESOLVED (no exact lifecycle row)"
    return None, "UNKNOWN (multiple lifecycle rows share proposal id)"


def _costs(row: dict[str, Any] | None, action: Any) -> str:
    if action == "NO_TRADE":
        return "N/A (no order)"
    if row is None:
        return UNKNOWN
    return (f"gross {_value(row.get('gross_price_pnl_account'))} | commission {_value(row.get('commission_account'))} | "
            f"fee {_value(row.get('fee_account'))} | swap {_value(row.get('swap_account'))} | "
            f"spread {_value(row.get('estimated_spread_cost_account'))} | slippage {_value(row.get('slippage_cost_account'))} | "
            f"total {_value(row.get('estimated_total_cost_account'))} | realised {_value(row.get('realized_pnl_account'))} "
            f"{_value(row.get('account_currency'), '')}").rstrip()


def render(latest: dict[str, Any], rows: list[dict[str, Any]]) -> str:
    lines = [
        "M1 Demo Decision Evidence — read-only",
        "====================================",
        "Demo-only. This view cannot assess, submit, modify, or recover a trade.",
    ]
    if latest.get("error"):
        return "\n".join([*lines, f"Latest assessment: UNAVAILABLE — {latest['error']}"])
    if latest.get("observation") != "AVAILABLE" or not isinstance(latest.get("assessment"), dict):
        return "\n".join([*lines, f"Latest assessment: {_value(latest.get('observation'))}"])

    assessment = latest["assessment"]
    proposal = assessment.get("proposal") or {}
    snapshot = assessment.get("decision_snapshot") or {}
    market_context = snapshot.get("market_context") or {}
    execution = assessment.get("execution") or {}
    reconciliation = assessment.get("reconciliation") or {}
    selection = assessment.get("strategy_selection") or market_context
    proposal_id = proposal.get("proposal_id")
    lifecycle, join_state = _matching_lifecycle(rows, proposal_id, proposal.get("action"))
    lines.extend([
        f"Release: {_value(latest.get('listener_release_id'))} | sequence: {_value(latest.get('assessment_sequence'))}",
        f"Closed M1 candle: {_value(proposal.get('decision_candle_closed_at_utc'))}",
        f"Assessment completed: {_value(latest.get('assessment_completed_at_utc'))}",
        f"Decision: {_value(proposal.get('action'))} | refusal reason: {_value(proposal.get('rationale'))}",
        f"Selected owner: {_value(selection.get('selected_strategy_id'))} [{_value(selection.get('selection_status'))}]",
        "",
        "Five strategy signals",
    ])
    strategies = assessment.get("strategy_assessments") or snapshot.get("strategy_assessments") or []
    if not strategies:
        lines.append(f"{UNKNOWN} (strategy assessments absent)")
    else:
        for strategy in strategies:
            if isinstance(strategy, dict):
                lines.append(f"- {_value(strategy.get('id'))}: {_value(strategy.get('signal'))} — {_value(strategy.get('reason'))}")
    lines.extend([
        "",
        f"Proposal: {_value(proposal_id)} | entry {_value(proposal.get('proposed_entry'))} | SL {_value(proposal.get('stop_loss'))} | TP {_value(proposal.get('take_profit'))}",
        f"Attempt: {_value(execution.get('attempt_id'))} | execution {_value(execution.get('status'))}",
        f"Lifecycle join: {join_state}",
        f"Lifecycle: {_value(lifecycle.get('lifecycle') if lifecycle else reconciliation.get('status'), 'NO_EXECUTION_LIFECYCLE' if proposal.get('action') == 'NO_TRADE' else UNKNOWN)}",
        f"Actual outcome: close {_value(lifecycle.get('closed_at_utc') if lifecycle else None)} | exit {_value(lifecycle.get('exit_price') if lifecycle else None)} | reconciliation {_value(lifecycle.get('reconciliation_status') if lifecycle else reconciliation.get('status'))}",
        f"Actual costs/outcome: {_costs(lifecycle, proposal.get('action'))}",
        f"Unresolved joins: {_value(lifecycle.get('reconciliation_reason') if lifecycle else None, 'NONE' if proposal.get('action') == 'NO_TRADE' else UNKNOWN)}",
    ])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true", help="Render once then exit.")
    parser.add_argument("--interval", type=float, default=10.0, help="Refresh seconds (default: 10).")
    args = parser.parse_args(argv)
    if args.interval < 5:
        parser.error("--interval must be at least five seconds")
    while True:
        print("\033[2J\033[H" + render(latest_assessment(), lifecycle_rows()), flush=True)
        if args.once:
            return 0
        try:
            time.sleep(args.interval)
        except KeyboardInterrupt:
            print("\nEvidence view stopped.")
            return 0


if __name__ == "__main__":
    raise SystemExit(main())
