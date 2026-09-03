#!/usr/bin/env python3
"""Read-only M20 Demo account liquidity report."""
from __future__ import annotations
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
completed = subprocess.run([sys.executable, str(ROOT / 'scripts' / 't480_adapter.py'), 'execute', '--operation', 'm20_demo_account_liquidity'], cwd=ROOT, text=True, capture_output=True, check=False, timeout=12)
if completed.returncode:
    raise SystemExit(completed.stderr.strip() or completed.stdout.strip())
data = json.loads(json.loads(completed.stdout)['result']['stdout'])
if not data.get('ok'):
    raise SystemExit(f"Report unavailable: {data.get('mt5_error') or 'unexpected account'}")
print('M20 Demo account liquidity report')
print(f"Account: {data['server']} ({data['currency']})")
for label, key, suffix in [('Balance', 'balance', ''), ('Equity', 'equity', ''), ('Margin used', 'margin', ''), ('Free margin', 'free_margin', '')]:
    print(f"{label + ':':<14} {data[key]:.2f} {data['currency']}")
print(f"{'Margin level:':<14} {data['margin_level']:.2f}%")
print(f"{'Leverage:':<14} 1:{data['leverage']}")
print(f"Open positions: {data['open_positions']}")
