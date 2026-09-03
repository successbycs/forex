#!/usr/bin/env python3
"""Small live T16 terminal dashboard for the permanent M20 Demo listener."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
import time
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def listener_status() -> dict[str, Any]:
    try:
        completed = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "t480_adapter.py"), "execute", "--operation", "m20_listener_status"],
            cwd=ROOT, text=True, capture_output=True, check=False, timeout=8,
        )
    except subprocess.TimeoutExpired:
        return {"state": "UNAVAILABLE", "detail": "T480 listener-status check exceeded eight seconds; dashboard will retry."}
    if completed.returncode:
        return {"state": "UNAVAILABLE", "detail": completed.stderr.strip() or completed.stdout.strip()}
    try:
        payload = json.loads(completed.stdout)
        return json.loads(payload["result"]["stdout"])
    except (KeyError, TypeError, json.JSONDecodeError) as error:
        return {"state": "UNAVAILABLE", "detail": f"Unable to read listener status: {error}"}


def _value(value: Any, fallback: str = "—") -> str:
    return fallback if value is None else str(value)


def render(status: dict[str, Any]) -> str:
    result = status.get("last_result") or {}
    proposal = result.get("proposal") or {}
    metrics = result.get("assessment_metrics") or {}
    execution = result.get("execution") or {}
    reconciliation = result.get("reconciliation") or {}
    strategies = result.get("strategy_assessments") or []
    lines = [
        "M20 Demo Listener — live assessment dashboard",
        "=" * 47,
        f"Listener: {_value(status.get('state'))}",
        f"Heartbeat: UTC {_value(status.get('heartbeat_at_utc'))} | NZST {_value(status.get('heartbeat_at_nzst'))}",
        f"Assessment: #{_value(status.get('iteration'))}",
        f"Next: UTC {_value(status.get('next_assessment_at_utc'))} | NZST {_value(status.get('next_assessment_at_nzst'))}",
        f"Market: {_value(result.get('server'))}  {_value(result.get('symbol'))} / {_value(proposal.get('selected_timeframe'))}",
        "",
        f"Decision: {_value(proposal.get('action'))}   Order: {_value(execution.get('status'))}",
        f"Reason: {_value(proposal.get('rationale'))}",
        f"Reconciliation: {_value(reconciliation.get('status'))}",
        "",
        "Candle checks",
        f"Last close: {_value(metrics.get('last_close'))}   Previous: {_value(metrics.get('previous_close'))}",
        f"Prior five-candle range: {_value(metrics.get('prior_five_low'))} – {_value(metrics.get('prior_five_high'))}",
        f"Direction: {_value(metrics.get('two_candle_direction'))}   Aligned: {_value(metrics.get('two_candle_aligned'))}",
        f"Breakout above / below: {_value(metrics.get('breakout_above_prior_high'))} / {_value(metrics.get('breakout_below_prior_low'))}",
        f"Combined move: {_value(metrics.get('combined_move_points'))} pts   Spread: {_value(metrics.get('spread_points'))} pts   Exceeds spread: {_value(metrics.get('combined_move_exceeds_spread'))}",
        "",
    ]
    lines.append("Strategy comparisons (only Momentum breakout can execute)")
    for strategy in strategies:
        if not isinstance(strategy, dict):
            continue
        eligibility = "ACTIVE" if strategy.get("eligible_for_execution") else "SHADOW"
        lines.append(f"{_value(strategy.get('label'))}: {_value(strategy.get('signal'))} [{eligibility}] — {_value(strategy.get('reason'))}")
    lines.extend(["", "Ctrl+C exits. Data is Demo-only and the dashboard is read-only."])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="View the live M20 Demo listener in a terminal.")
    parser.add_argument("--interval", type=float, default=2.0, help="Dashboard refresh seconds (default: 2).")
    parser.add_argument("--once", action="store_true", help="Render one status update then exit.")
    args = parser.parse_args()
    if args.interval < 1:
        parser.error("--interval must be at least one second")
    while True:
        print("\033[2J\033[H" + render(listener_status()), flush=True)
        if args.once:
            return 0
        try:
            time.sleep(args.interval)
        except KeyboardInterrupt:
            print("\nDashboard stopped.")
            return 0


if __name__ == "__main__":
    raise SystemExit(main())
