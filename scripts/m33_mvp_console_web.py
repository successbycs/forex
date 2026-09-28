#!/usr/bin/env python3
"""Loopback-only, read-only M33.5 Demo MVP operator console.

The page composes fixed read operations.  It contains no broker, MT5, order,
risk, session, hold, or retry control and intentionally accepts no user input.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import html
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from pathlib import Path
import subprocess
import sys
from typing import Any
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
AUCKLAND = ZoneInfo("Pacific/Auckland")
READ_TIMEOUT_SECONDS = 10


def _operation(script: str, *args: str) -> Any:
    """Run one named fixed reader and return only its JSON result payload."""
    try:
        completed = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / script), *args], cwd=ROOT,
            text=True, capture_output=True, check=False, timeout=READ_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        return {"_unavailable": f"{args[-1] if args else script} exceeded {READ_TIMEOUT_SECONDS} seconds"}
    if completed.returncode:
        return {"_unavailable": completed.stderr.strip() or completed.stdout.strip() or "fixed read failed"}
    try:
        envelope = json.loads(completed.stdout)
        result = envelope["result"]
        if not isinstance(result, dict) or result.get("ok") is not True:
            return {"_unavailable": "fixed read returned no successful result"}
        return json.loads(result.get("stdout", ""))
    except (KeyError, TypeError, json.JSONDecodeError) as error:
        return {"_unavailable": f"invalid fixed-reader result: {error}"}


def fetch_console() -> dict[str, Any]:
    """Collect the four fixed read models. Failure is visible, never retried here."""
    readers = {
        "listener": ("t480_adapter.py", "execute", "--operation", "m20_listener_status"),
        "trace": ("t480_adapter.py", "execute", "--operation", "m20_listener_trace_page"),
        "pnl": ("postgres_pgvector_adapter.py", "forex-m33-mvp-system-pnl-summary"),
        "strategies": ("postgres_pgvector_adapter.py", "forex-m20-strategy-trial-summary"),
    }
    # A slow unavailable source must not serially delay every other panel.
    with ThreadPoolExecutor(max_workers=len(readers)) as pool:
        futures = {name: pool.submit(_operation, *command) for name, command in readers.items()}
        return {name: future.result() for name, future in futures.items()}


def _text(value: Any, fallback: str = "—") -> str:
    if value is None or value == "":
        return fallback
    return html.escape(str(value))


def _time(value: Any) -> str:
    if not value:
        return "—"
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return _text(value)
        return html.escape(parsed.astimezone(AUCKLAND).strftime("%d %b %Y %H:%M:%S %Z"))
    except ValueError:
        return _text(value)


def _money(value: Any, currencies: Any = None) -> str:
    if value is None:
        return "UNAVAILABLE"
    try:
        suffix = ""
        if isinstance(currencies, list) and len(currencies) == 1:
            suffix = " " + str(currencies[0])
        elif currencies:
            suffix = " (mixed/unknown currency)"
        return f"{float(value):+.2f}{html.escape(suffix)}"
    except (TypeError, ValueError):
        return "UNAVAILABLE"


def _unavailable(model: Any) -> str | None:
    return str(model.get("_unavailable")) if isinstance(model, dict) and model.get("_unavailable") else None


def _panel(title: str, body: str) -> str:
    return f"<section><h2>{html.escape(title)}</h2>{body}</section>"


def _facts_table(facts: Any) -> str:
    if not isinstance(facts, dict):
        return "<p>Facts unavailable.</p>"
    preferred = ("server", "symbol", "bid", "ask", "spread_points", "freshness_seconds", "completed_m1_count", "m1_input_status", "selected_strategy_id", "selection_status", "market_regime", "market_regime_reason", "entry_allowed", "pause_reason", "action", "rationale", "planned_entry", "planned_stop_loss", "planned_take_profit", "planned_notional_usd", "execution_status", "reconciliation_status", "reconciliation_reason")
    rows = "".join(f"<tr><th>{html.escape(key.replace('_', ' '))}</th><td>{_text(facts.get(key))}</td></tr>" for key in preferred if key in facts)
    return "<table class=compact>" + rows + "</table>" if rows else "<p>No allowed facts were retained.</p>"


def render_html(models: dict[str, Any]) -> str:
    generated = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    listener, trace, pnl, strategies = (models.get(name) for name in ("listener", "trace", "pnl", "strategies"))
    listener_error = _unavailable(listener)
    if listener_error:
        listener_body = f"<p class=bad>UNAVAILABLE — {_text(listener_error)}</p>"
    else:
        runtime = listener.get("runtime_binding") if isinstance(listener, dict) else {}
        last = listener.get("last_result") if isinstance(listener, dict) else {}
        proposal = last.get("proposal") if isinstance(last, dict) else {}
        risk = last.get("risk_policy") if isinstance(last, dict) else {}
        held = (listener or {}).get("state") == "MAINTENANCE_HOLD"
        listener_body = "<table class=compact>" + "".join((
            f"<tr><th>{label}</th><td>{value}</td></tr>" for label, value in (
                ("Listener state", _text((listener or {}).get("state"))),
                ("Heartbeat", _time((listener or {}).get("heartbeat_at_utc"))),
                ("Release", _text((listener or {}).get("release_id"))),
                ("Demo server", _text((runtime or {}).get("server"))),
                ("Symbol", _text((runtime or {}).get("symbol"))),
                ("Entry eligibility", _text((risk or {}).get("entry_allowed"))),
                ("Maintenance hold", _text(held)),
                ("Latest decision", _text((proposal or {}).get("action"))),
                ("Latest assessment", _time((last or {}).get("captured_at_utc"))),
            )
        )) + "</table>"

    trace_error = _unavailable(trace)
    if trace_error:
        trace_body = f"<p class=bad>TRACE UNAVAILABLE — {_text(trace_error)}</p>"
    elif not isinstance(trace, dict) or trace.get("observation") != "TRACE_COMPLETE":
        trace_body = f"<p class=bad>TRACE UNAVAILABLE — {_text((trace or {}).get('observation', 'no verified trace'))}: {_text((trace or {}).get('reason'))}</p>"
    else:
        events = trace.get("events") if isinstance(trace.get("events"), list) else []
        event_html = "".join(
            f"<details {'open' if index == len(events) - 1 else ''}><summary>#{_text(event.get('sequence'))} {_text(event.get('event_type'))} — {_time(event.get('occurred_at_utc'))}</summary>{_facts_table(event.get('facts'))}</details>"
            for index, event in enumerate(events) if isinstance(event, dict)
        )
        trace_body = f"<p>Verified event set bound to assessment #{_text(trace.get('assessment_sequence'))}. Showing the latest {len(events)} retained events.</p>" + (event_html or "<p>No trace events returned.</p>")

    if listener_error:
        execution_body = "<p class=bad>UNAVAILABLE — listener state is unavailable.</p>"
    else:
        last = listener.get("last_result") if isinstance(listener, dict) else {}
        proposal = last.get("proposal") if isinstance(last, dict) else {}
        execution = last.get("execution") if isinstance(last, dict) else {}
        reconciliation = last.get("reconciliation") if isinstance(last, dict) else {}
        selection = last.get("strategy_selection") if isinstance(last, dict) else {}
        execution_body = "<table class=compact>" + "".join(
            f"<tr><th>{label}</th><td>{value}</td></tr>" for label, value in (
                ("Proposal", _text((proposal or {}).get("proposal_id"))),
                ("Attempt", _text((execution or {}).get("attempt_id"))),
                ("Strategy owner", _text((selection or {}).get("trade_owner_strategy_id"))),
                ("Rule version", _text((proposal or {}).get("strategy_version"))),
                ("Planned entry / SL / TP", " / ".join(_text((proposal or {}).get(key)) for key in ("proposed_entry", "stop_loss", "take_profit"))),
                ("Execution", _text((execution or {}).get("status"))),
                ("Reconciliation", _text((reconciliation or {}).get("status"))),
                ("Reconciliation reason", _text((reconciliation or {}).get("reason"))),
            )
        ) + "</table><p>Planned prices are not broker fills.</p>"

    pnl_error = _unavailable(pnl)
    if pnl_error:
        pnl_body = f"<p class=bad>JOURNAL / P&amp;L UNAVAILABLE — {_text(pnl_error)}</p>"
    elif not isinstance(pnl, dict) or pnl.get("schema_version") != "forex.m33.5.system-pnl-summary.v1":
        pnl_body = "<p class=bad>JOURNAL / P&amp;L UNAVAILABLE — unexpected fixed summary.</p>"
    else:
        period_rows = "".join(
            "<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>".format(
                _text(row.get("period")), _money(row.get("actual_net_pnl_account"), row.get("account_currencies")),
                _text(row.get("matched_closed_count"), "0"), _text(row.get("excluded_closed_count"), "0"),
            ) for row in pnl.get("periods", []) if isinstance(row, dict)
        )
        journal_rows = "".join(
            "<tr><td>{}</td><td>{}<br>{}</td><td>{}<br><small>{}</small></td><td>{}</td><td>{} / {} / {}</td><td>{} / {} / {}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>".format(
                _time(row.get("closed_at_utc")), _text(row.get("proposal_id")), _text(row.get("attempt_id")),
                _text(row.get("trade_owner_strategy_id")), _text(row.get("strategy_version")), _text(row.get("action")),
                _text(row.get("proposed_entry")), _text(row.get("stop_loss")), _text(row.get("take_profit")),
                _text(row.get("actual_entry_price")), _text(row.get("exit_price")), _text(row.get("volume_lots")),
                _text(row.get("reconciliation_status")), _money(row.get("gross_price_pnl_account"), [row.get("account_currency")]),
                _money(row.get("commission_account"), [row.get("account_currency")]), _money(row.get("fee_account"), [row.get("account_currency")]),
                _money(row.get("swap_account"), [row.get("account_currency")]), _money(row.get("realized_pnl_account"), [row.get("account_currency")]),
            ) for row in pnl.get("journal", []) if isinstance(row, dict)
        )
        excluded_rows = "".join(
            "<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>".format(
                _time(row.get("closed_at_utc")), _text(row.get("proposal_id")), _text(row.get("attempt_id")),
                _text(row.get("reconciliation_status")), _text(row.get("exclusion_reason")),
            ) for row in pnl.get("excluded_journal", []) if isinstance(row, dict)
        )
        pnl_body = "<p>Actual broker net P&amp;L only. Auckland calendar. Unreconciled closures are excluded, not treated as zero.</p>" + \
            "<table><tr><th>Period</th><th>Actual net P&amp;L</th><th>Broker-matched closes</th><th>Excluded closures</th></tr>" + period_rows + "</table>" + \
            f"<p>Unclosed system attempts: {_text(pnl.get('unclosed_system_attempt_count'), '0')}. Source time: {_time(pnl.get('generated_at_utc'))}.</p>" + \
            "<h3>Broker-matched system journal (latest 50)</h3><table><tr><th>Auckland close</th><th>Proposal / attempt</th><th>Strategy / version</th><th>Side</th><th>Planned entry / SL / TP</th><th>Broker entry / exit / lots</th><th>Reconciliation</th><th>Gross</th><th>Commission</th><th>Fee</th><th>Swap</th><th>Actual net</th></tr>" + (journal_rows or "<tr><td colspan=12>No broker-matched system outcomes retained.</td></tr>") + "</table>" + \
            "<h3>Excluded closed system outcomes (no monetary values)</h3><table><tr><th>Auckland close</th><th>Proposal</th><th>Attempt</th><th>Reconciliation</th><th>Reason</th></tr>" + (excluded_rows or "<tr><td colspan=5>No excluded closed outcomes retained.</td></tr>") + "</table>"

    strategy_error = _unavailable(strategies)
    if strategy_error:
        strategy_body = f"<p class=bad>STRATEGY EVIDENCE UNAVAILABLE — {_text(strategy_error)}</p>"
    elif not isinstance(strategies, list):
        strategy_body = "<p class=bad>STRATEGY EVIDENCE UNAVAILABLE — invalid summary.</p>"
    else:
        strategy_rows = "".join(
            "<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}/{}</td><td>{}</td></tr>".format(
                _text(row.get("strategy_id")), _text(row.get("selected_count"), "0"), _text(row.get("attempt_count"), "0"),
                _text(row.get("verified_closed_count"), "0"), _text(row.get("win_count"), "0"), _text(row.get("loss_count"), "0"),
                _money(row.get("net_realized_pnl_aud"), ["AUD"]),
            ) for row in strategies if isinstance(row, dict)
        )
        strategy_body = "<p>Rule version: <code>forex.m20.11.m1-five-strategy-trial.v2</code>. This evidence does not establish an edge or authorise Live trading.</p>" + \
            "<table><tr><th>Strategy</th><th>Selected</th><th>Attempts</th><th>Matched closes</th><th>W/L</th><th>Actual net P&amp;L</th></tr>" + (strategy_rows or "<tr><td colspan=6>No strategy rows retained.</td></tr>") + "</table>"

    return f"""<!doctype html><html><head><meta charset=utf-8><meta http-equiv=refresh content=20><title>Forex Demo MVP Console</title>
<style>body{{font:16px system-ui,sans-serif;max-width:1200px;margin:2rem auto;padding:0 1rem;color:#17212b}} section{{border:1px solid #ccd6dd;border-radius:8px;padding:1rem;margin:1rem 0}} table{{border-collapse:collapse;width:100%;margin:.5rem 0}} th,td{{border:1px solid #d8e0e5;padding:.45rem;text-align:left;vertical-align:top}}th{{background:#f3f6f8}}.compact{{width:auto}}.bad{{color:#9d1c1c;font-weight:600}}details{{border-top:1px solid #ddd;padding:.5rem 0}}summary{{cursor:pointer;font-weight:600}}code{{white-space:nowrap}}</style></head><body>
<h1>Forex Demo MVP Console</h1><p>Loopback-only, read-only, Demo-only. Refreshed every 20 seconds. Generated {_time(generated)}.</p>
{_panel('T480 listener state', listener_body)}
{_panel('Actual listener decision trace', trace_body)}
{_panel('Current execution and reconciliation', execution_body)}
{_panel('Broker-matched system journal and P&L', pnl_body)}
{_panel('Strategy-version evidence', strategy_body)}
</body></html>"""


class ConsoleHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        if self.path != "/":
            self.send_error(404)
            return
        body = render_html(fetch_console()).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, _format: str, *_args: Any) -> None:
        return


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Loopback-only M33.5 Demo MVP console")
    parser.add_argument("--port", type=int, default=8055)
    args = parser.parse_args(argv)
    if not 1024 <= args.port <= 65535:
        parser.error("port must be between 1024 and 65535")
    server = HTTPServer(("127.0.0.1", args.port), ConsoleHandler)
    print(f"M33.5 Demo MVP console: http://127.0.0.1:{args.port}/")
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
