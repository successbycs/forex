#!/usr/bin/env python3
"""Loopback-only read-only M33 daily P&L webpage."""
from __future__ import annotations
import argparse, html
from datetime import date
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse
from scripts.m33_daily_pnl_report import fetch_day, money

def render_html(report:dict)->str:
 rows=''.join('<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>'.format(html.escape(str(r['closed_at_utc'])),html.escape(str(r['proposal_id'])),html.escape(money(r['actual_broker_net_aud'])),html.escape(money(r['expected_round_trip_commission_aud']) if r['coverage_status']=='APPLIED' else 'UNAVAILABLE: '+r['unavailable_reason']),html.escape(money(r['commission_adjusted_pnl_aud']))) for r in report['rows'])
 return f'<!doctype html><title>M33 Daily P&L</title><h1>M33 Daily Demo P&amp;L — {html.escape(report["date"])}</h1><p>Actual broker P&amp;L is the record. Adjusted P&amp;L uses the ASSUMED GO Plus+ AUD profile.</p><table border=1><tr><th>Closed</th><th>Trade</th><th>Actual broker P&amp;L</th><th>Expected commission/status</th><th>Adjusted P&amp;L</th></tr>{rows}</table><p>Closed: {report["closed_outcome_count"]}; Applied: {report["applied_count"]}; Unavailable: {report["unavailable_count"]}</p>'
def main()->int:
 p=argparse.ArgumentParser();p.add_argument('--port',type=int,default=8044);a=p.parse_args()
 class Handler(BaseHTTPRequestHandler):
  def do_GET(self):
   q=parse_qs(urlparse(self.path).query); text=q.get('date',[date.today().isoformat()])[0]
   try: body=render_html(fetch_day(date.fromisoformat(text))).encode();self.send_response(200)
   except (ValueError,RuntimeError) as e: body=str(e).encode();self.send_response(400)
   self.send_header('Content-Type','text/html; charset=utf-8');self.end_headers();self.wfile.write(body)
  def log_message(self,*args): pass
 HTTPServer(('127.0.0.1',a.port),Handler).serve_forever();return 0
if __name__=='__main__':raise SystemExit(main())
