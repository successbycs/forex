#!/usr/bin/env python3
"""Small live T16 terminal dashboard for the permanent M20 Demo listener."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
import time
import shutil
import textwrap
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


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


def _context_by_timeframe(context: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Index the fixed M20.12 records without inferring a missing timeframe."""
    records = context.get("contexts") or []
    return {
        str(record.get("timeframe")): record
        for record in records
        if isinstance(record, dict) and str(record.get("timeframe")) in {"M5", "H1"}
    }


def _context_line(timeframe: str, record: dict[str, Any] | None) -> str:
    """Render one context row; it is deliberately descriptive, never directive."""
    if record is None:
        return f"{timeframe}: NOT RECORDED | close UTC — | age —"
    status = _value(record.get("integrity_status"), "UNAVAILABLE")
    state = _value(record.get("market_state"), "UNKNOWN")
    alignment = _value(record.get("alignment"), "UNAVAILABLE")
    close = _value(record.get("closed_at_utc"))
    age = record.get("data_age_seconds")
    age_display = "—" if age is None else f"{age}s"
    volatility = _value(record.get("volatility_state"), "UNKNOWN")
    liquidity = _value(record.get("liquidity_state"), "UNKNOWN")
    return (f"{timeframe}: {status} | {state} | {alignment} | close UTC {close} | age {age_display}"
            f" | vol {volatility} | liquidity {liquidity}")


def _shadow_context_lines(context: Any) -> list[str]:
    """Return the M20.12 read-only panel from the persisted runner payload."""
    lines = [
        "Shadow context only — does not change this trade.",
        "M5/H1 context is recorded after the M1 decision and has no entry, exit, or ownership authority.",
    ]
    if not isinstance(context, dict):
        lines.extend([
            "Context: NOT RECORDED in this assessment (staged-only listener output or unavailable record).",
            "M5: NOT RECORDED | close UTC — | age —",
            "H1: NOT RECORDED | close UTC — | age —",
        ])
        return lines
    lines.append(
        f"Context: alignment {_value(context.get('overall_alignment'), 'UNAVAILABLE')}"
        f" | disposition {_value(context.get('context_disposition'), 'OBSERVE_ONLY')}"
        f" | rule {_value(context.get('rule_version'))}"
    )
    by_timeframe = _context_by_timeframe(context)
    lines.extend([_context_line("M5", by_timeframe.get("M5")), _context_line("H1", by_timeframe.get("H1"))])
    if context.get("reason") is not None:
        lines.append(f"Context reason: {_value(context.get('reason'))}")
    return lines


def render(status: dict[str, Any]) -> str:
    if status.get("state") == "UNAVAILABLE":
        return "\n".join([
            "M20 Demo Listener — live assessment dashboard",
            "=" * 47,
            "Listener status is temporarily unavailable.",
            f"Detail: {_value(status.get('detail'))}",
            "The dashboard will retry automatically; no trading action was taken by this view.",
            "Ctrl+C exits. Data is Demo-only and the dashboard is read-only.",
        ])
    result = status.get("last_result") or {}
    proposal = result.get("proposal") or {}
    metrics = result.get("assessment_metrics") or {}
    execution = result.get("execution") or {}
    reconciliation = result.get("reconciliation") or {}
    monitor = status.get("monitor") or {}
    quote = status.get("quote") or {}
    strategies = result.get("strategy_assessments") or []
    selection = result.get("strategy_selection") or {}
    shadow_context = result.get("multi_timeframe_context")
    supervisor = "RUNNING" if status.get("running") else _value(status.get("state"))
    listener_detail = "" if status.get("state") == "RUNNING" else f" — {_value(status.get('state'))}"
    lines = [
        "M20 Demo Listener — live assessment dashboard",
        "=" * 47,
        f"Listener: {supervisor}{listener_detail}",
        f"Heartbeat: UTC {_value(status.get('heartbeat_at_utc'))} | NZST {_value(status.get('heartbeat_at_nzst'))}",
        f"Assessment: #{_value(status.get('iteration'))} in this service | #{_value(status.get('assessment_total'))} since persistent counter began",
        f"Assessment completed: {_value(status.get('assessment_completed_at_utc'))} ({_value(status.get('assessment_duration_ms'))} ms)",
        f"Next: UTC {_value(status.get('next_assessment_at_utc'))} | NZST {_value(status.get('next_assessment_at_nzst'))}",
        f"Quote gate: MT5 tick {_value(quote.get('tick_time_msc'))} | bid/ask {_value(quote.get('bid'))}/{_value(quote.get('ask'))}",
        f"Market: {_value(result.get('server'))}  {_value(result.get('symbol'))} / {_value(proposal.get('selected_timeframe'))}",
        "",
        f"M1 decision: {_value(proposal.get('action'))}   Order: {_value(execution.get('status'))}",
        f"Reason: {_value(proposal.get('rationale'))}",
        f"Reconciliation: {_value(reconciliation.get('status'))}",
        f"Monitor: {_value(monitor.get('state'))}   PID: {_value(monitor.get('pid'))}",
        f"M1 strategy owner: {_value(selection.get('selected_strategy_id'))} [{_value(selection.get('selection_status'))}]   Regime: {_value(selection.get('market_regime'))}",
        f"Regime reason: {_value(selection.get('market_regime_reason'))}",
        f"Selected plan: entry {_value(proposal.get('proposed_entry'))} | SL {_value(proposal.get('stop_loss'))} | TP {_value(proposal.get('take_profit'))}",
        f"Cost gate: {_value(selection.get('cost_coverage_status'))} | estimated costs {_value(selection.get('estimated_round_trip_cost_aud'))} AUD | expected net at TP {_value(selection.get('expected_net_profit_at_take_profit_aud'))} AUD | minimum {_value(selection.get('minimum_net_profit_aud'))} AUD",
        "",
        "Candle checks",
        f"Last close: {_value(metrics.get('last_close'))}   Previous: {_value(metrics.get('previous_close'))}",
        f"Prior five-candle range: {_value(metrics.get('prior_five_low'))} – {_value(metrics.get('prior_five_high'))}",
        f"Direction: {_value(metrics.get('two_candle_direction'))}   Aligned: {_value(metrics.get('two_candle_aligned'))}",
        f"Breakout above / below: {_value(metrics.get('breakout_above_prior_high'))} / {_value(metrics.get('breakout_below_prior_low'))}",
        f"Combined move: {_value(metrics.get('combined_move_points'))} pts   Spread: {_value(metrics.get('spread_points'))} pts   Exceeds spread: {_value(metrics.get('combined_move_exceeds_spread'))}",
        "",
    ]
    lines.extend(["M5/H1 shadow context", "-------------------", *_shadow_context_lines(shadow_context), ""])
    lines.extend([
        "Strategy comparison — regime precedence may select one executable owner",
        "Strategy               Signal       Mode      What this assessment means",
        "---------------------  -----------  --------  ----------------------------------------",
    ])
    for strategy in strategies:
        if not isinstance(strategy, dict):
            continue
        strategy_id = strategy.get("id")
        if (strategy_id == selection.get("selected_strategy_id")
                and selection.get("selection_status") == "SELECTED_EXECUTABLE"
                and proposal.get("action") in {"BUY", "SELL"}):
            eligibility = "EXECUTABLE"
        elif strategy_id == selection.get("selected_strategy_id"):
            eligibility = "BLOCKED"
        elif strategy.get("signal") in {"BUY", "SELL"}:
            eligibility = "SIGNAL ONLY"
        elif strategy.get("eligible_for_execution"):
            eligibility = "NO SIGNAL"
        else:
            eligibility = "BLOCKED"
        label = _value(strategy.get("label"))[:21]
        signal = _value(strategy.get("signal"))[:11]
        reason = _value(strategy.get("reason"))
        lines.append(f"{label:<21}  {signal:<11}  {eligibility:<8}  {reason}")
    lines.extend(["", "Ctrl+C exits. Data is Demo-only and the dashboard is read-only."])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="View the live M20 Demo listener in a terminal.")
    parser.add_argument("--interval", type=float, default=2.0, help="Dashboard refresh seconds (default: 2).")
    parser.add_argument("--once", action="store_true", help="Render one status update then exit.")
    parser.add_argument("--json", action="store_true", help="Emit one reusable operator report as JSON.")
    parser.add_argument("--width", type=int, default=None, help="Override terminal column width (minimum 40).")
    args = parser.parse_args()
    if args.interval < 1:
        parser.error("--interval must be at least one second")
    if args.width is not None and args.width < 40:
        parser.error("--width must be at least 40")
    from scripts.listener_workflow_report import collect, render_workflow
    while True:
        try:
            report = collect(listener_status, ROOT, sys.executable)
        except KeyboardInterrupt:
            print('\nDashboard stopped.')
            return 0
        if args.json:
            print(json.dumps(report, indent=2))
            return 0
        width = args.width or max(40, shutil.get_terminal_size((100, 30)).columns)
        details = '\n'.join('\n'.join(textwrap.wrap(line, width=width, subsequent_indent='  ')) if line else '' for line in render(report['status']).splitlines())
        screen = render_workflow(report, width) + '\n\nFULL ASSESSMENT DETAILS\n' + details
        print(("\033[2J\033[H" if sys.stdout.isatty() and not args.once else '') + screen, flush=True)
        if args.once:
            return 0
        try:
            time.sleep(args.interval)
        except KeyboardInterrupt:
            print("\nDashboard stopped.")
            return 0


if __name__ == "__main__":
    raise SystemExit(main())
