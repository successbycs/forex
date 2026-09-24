#!/usr/bin/env python3
"""Loopback-only read-only M33 daily P&L webpage."""
from __future__ import annotations

import argparse
import html
from datetime import date, datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

try:
    from scripts.m33_daily_pnl_report import fetch_day, money, local_time
except ModuleNotFoundError:  # direct execution from scripts/
    from m33_daily_pnl_report import fetch_day, money, local_time


def render_html(report: dict) -> str:
    selected = html.escape(report['date'])
    generated = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')
    if report['status'] != 'AVAILABLE':
        table = '<p>UNAVAILABLE: ' + html.escape(report['unavailable_reason']) + '</p>'
        totals = ''
    else:
        body = ''.join('<tr>' + ''.join('<td>{}</td>'.format(html.escape(str(value))) for value in (
            local_time(row['occurred_at_utc']), row['event_kind'], row['side'] or '—', f"{float(row['volume_lots']):.2f}",
            money(row['broker_commission_aud']), money(row['expected_live_commission_aud']), money(row['broker_fee_aud']),
            money(row['broker_swap_aud']), money(row['trade_pnl_aud']), money(row['net_movement_aud']), money(row['commission_adjusted_net_aud'])
        )) + '</tr>' for row in report['rows'])
        table = '<table border="1"><tr><th>Auckland time</th><th>Event</th><th>Side</th><th>Lots</th><th>Broker commission</th><th>Expected Live commission</th><th>Fee</th><th>Swap</th><th>Trade P&amp;L</th><th>Net movement</th><th>Adjusted net</th></tr>' + body + '</table>'
        totals = '<p>Balance at start: {}; broker balance change: {}; balance at end: {}.</p><p>Expected Live commission: {}; commission-adjusted P&amp;L: {}.</p>'.format(
            money(report['opening_balance_aud']), money(report['broker_balance_change_aud']), money(report['closing_balance_aud']),
            money(report['expected_live_commission_aud_total']), money(report['commission_adjusted_net_aud_total']))
    if report['status'] == 'AVAILABLE' and 'total_trade_pnl_aud' in report:
        totals += '<p>Total trading P&amp;L (all retained days): {}; commission-adjusted: {}.</p>'.format(money(report['total_trade_pnl_aud']), money(report['total_commission_adjusted_trade_pnl_aud']))
    source_time = html.escape(local_time(report['captured_at_utc'])) if report.get('captured_at_utc') else 'unavailable'
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>Broker P&amp;L journal</title></head><body>
<h1>Broker P&amp;L journal — {selected} Auckland</h1>
<form action="/report" method="get"><label>Auckland day <input name="date" type="date" value="{selected}" required></label><button type="submit">Show report</button></form>
<p>Generated {generated}. Broker snapshot: {source_time}. Broker balance is observed; historical balances are reconstructed from retained deals. Expected Live commission uses the ASSUMED GO Plus+ AUD profile for EURUSD and replaces actual commission in adjusted P&amp;L.</p>
{table}{totals}</body></html>"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8044)
    args = parser.parse_args()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urlparse(self.path)
            if parsed.path not in ('/', '/report'):
                self.send_error(404)
                return
            query = parse_qs(parsed.query)
            text = query.get('date', [date.today().isoformat()])[0]
            try:
                body = render_html(fetch_day(date.fromisoformat(text))).encode()
                self.send_response(200)
            except (ValueError, RuntimeError) as error:
                body = str(error).encode()
                self.send_response(400)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    HTTPServer(('127.0.0.1', args.port), Handler).serve_forever()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
