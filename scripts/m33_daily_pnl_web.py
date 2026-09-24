#!/usr/bin/env python3
"""Loopback-only read-only M33 daily P&L webpage."""
from __future__ import annotations

import argparse
import html
from datetime import date, datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

try:
    from scripts.m33_daily_pnl_report import fetch_day, money
except ModuleNotFoundError:  # direct execution from scripts/
    from m33_daily_pnl_report import fetch_day, money


def render_html(report: dict) -> str:
    rows = ''.join(
        '<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>'.format(
            html.escape(str(row['closed_at_utc'])),
            html.escape(str(row['proposal_id'])),
            html.escape(money(row['actual_broker_net_aud'])),
            html.escape(money(row['actual_broker_commission_aud'])),
            html.escape(money(row['broker_fee_aud'])),
            html.escape(money(row['broker_swap_aud'])),
            html.escape(money(row['expected_round_trip_commission_aud']) if row['coverage_status'] == 'APPLIED' else 'UNAVAILABLE: ' + row['unavailable_reason']),
            html.escape(money(row['commission_adjusted_pnl_aud'])),
        ) for row in report['rows']
    )
    profile = next((row.get('profile_version_id') for row in report['rows'] if row.get('profile_version_id')), 'No applied profile')
    generated = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')
    selected = html.escape(report['date'])
    return f'''<!doctype html><html><head><meta charset="utf-8"><title>M33 Daily P&amp;L</title></head><body>
<h1>M33 Daily Demo P&amp;L — {selected} NZST</h1>
<form action="/report" method="get"><label>Auckland day <input name="date" type="date" value="{selected}" required></label><button type="submit">Show report</button></form>
<p>Generated {generated}. Profile: {html.escape(str(profile))}. Actual broker P&amp;L is the record. Adjusted P&amp;L uses the ASSUMED GO Plus+ AUD profile.</p>
<table border="1"><tr><th>Closed</th><th>Trade</th><th>Actual broker P&amp;L</th><th>Broker commission</th><th>Broker fee</th><th>Broker swap</th><th>Expected commission/status</th><th>Adjusted P&amp;L</th></tr>{rows}</table>
<p>Closed: {report['closed_outcome_count']}; Applied: {report['applied_count']}; Unavailable: {report['unavailable_count']}</p>
</body></html>'''


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
