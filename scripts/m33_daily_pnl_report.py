#!/usr/bin/env python3
"""Read-only operator report for the PostgreSQL broker P&L journal."""
from __future__ import annotations
import argparse, json, subprocess, sys
from datetime import date
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def fetch_day(nz_date: date)->dict:
    completed=subprocess.run([sys.executable,str(ROOT/'scripts/postgres_pgvector_adapter.py'),'forex-m33-broker-pnl-journal-summary','--date',nz_date.isoformat()],cwd=ROOT,text=True,capture_output=True,check=False,timeout=15)
    if completed.returncode: raise RuntimeError(completed.stderr.strip() or completed.stdout.strip())
    envelope=json.loads(completed.stdout)
    if not envelope.get('ok'): raise RuntimeError(envelope.get('result',{}).get('stderr') or 'broker P&L journal query failed')
    return json.loads(envelope['result']['stdout'])
def money(value): return '—' if value is None else f'{float(value):+.2f} AUD'
def render(report:dict)->str:
    lines=[f"Broker P&L journal — {report['date']} NZST",'Actual broker balance and P&L are recorded facts. Expected Live commission uses the ASSUMED GO Plus+ AUD 3.00-per-lot-per-side profile.','']
    if report['status']!='AVAILABLE': return '\n'.join(lines+[f"UNAVAILABLE: {report['unavailable_reason']}"])
    lines += ['NZST | Event | Side | Lots | Broker commission | Expected Live commission | Fee | Swap | Trade P&L | Net movement | Adjusted net']
    for row in report['rows']:
      lines.append(f"{row['occurred_at_utc']} | {row['event_kind']} | {row['side'] or '—'} | {float(row['volume_lots']):.2f} | {money(row['broker_commission_aud'])} | {money(row['expected_live_commission_aud'])} | {money(row['broker_fee_aud'])} | {money(row['broker_swap_aud'])} | {money(row['trade_pnl_aud'])} | {money(row['net_movement_aud'])} | {money(row['commission_adjusted_net_aud'])}")
    lines += ['',f"Balance at start of day: {money(report['opening_balance_aud'])}",f"Total broker balance change during day: {money(report['broker_balance_change_aud'])}",f"Balance at end of day: {money(report['closing_balance_aud'])}",f"Expected Live commission: {money(report['expected_live_commission_aud_total'])} | Commission-adjusted P&L: {money(report['commission_adjusted_net_aud_total'])}"]
    return '\n'.join(lines)
def main()->int:
 p=argparse.ArgumentParser(); p.add_argument('--date',required=True,type=date.fromisoformat); p.add_argument('--once',action='store_true'); a=p.parse_args(); print(render(fetch_day(a.date))); return 0
if __name__=='__main__': raise SystemExit(main())
