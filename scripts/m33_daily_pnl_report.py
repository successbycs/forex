#!/usr/bin/env python3
"""Read-only operator report for PostgreSQL-recorded M33 daily P&L coverage."""
from __future__ import annotations
import argparse, json, subprocess, sys
from datetime import date
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def fetch_day(nz_date: date)->dict:
    completed=subprocess.run([sys.executable,str(ROOT/'scripts/postgres_pgvector_adapter.py'),'forex-m33-daily-commission-coverage-summary','--date',nz_date.isoformat()],cwd=ROOT,text=True,capture_output=True,check=False,timeout=15)
    if completed.returncode: raise RuntimeError(completed.stderr.strip() or completed.stdout.strip())
    envelope=json.loads(completed.stdout); return json.loads(envelope['result']['stdout'])
def money(value): return '—' if value is None else f'{float(value):+.2f} AUD'
def render(report:dict)->str:
    lines=[f"M33 Daily Demo P&L — {report['date']} NZST",'Actual broker P&L is recorded fact. Commission-adjusted P&L uses the ASSUMED GO Plus+ AUD profile.','']
    for row in report['rows']:
      line=f"{row['closed_at_utc']} | {row['proposal_id']} | Actual: {money(row['actual_broker_net_aud'])} | Recorded costs: commission {money(row['actual_broker_commission_aud'])}; fee {money(row['broker_fee_aud'])}; swap {money(row['broker_swap_aud'])}"
      if row['coverage_status']=='APPLIED': line+=f" | Expected commission: {money(row['expected_round_trip_commission_aud'])} | Adjusted: {money(row['commission_adjusted_pnl_aud'])}"
      else: line+=f" | Commission-adjusted: UNAVAILABLE ({row['unavailable_reason']})"
      lines.append(line)
    lines.append(f"\nClosed outcomes: {report['closed_outcome_count']} | Applied: {report['applied_count']} | Unavailable: {report['unavailable_count']}")
    return '\n'.join(lines)
def main()->int:
 p=argparse.ArgumentParser(); p.add_argument('--date',required=True,type=date.fromisoformat); p.add_argument('--once',action='store_true'); a=p.parse_args(); print(render(fetch_day(a.date))); return 0
if __name__=='__main__': raise SystemExit(main())
