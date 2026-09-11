#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
python3 - "$root" "$1" <<'PY'
import hashlib,json,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
r,b=Path(sys.argv[1]),Path(sys.argv[2]).resolve();m=json.loads((b/'manifest.json').read_text());
if not (b.is_relative_to(r/'runs/evidence/M28') and m['milestone_id']=='M28' and not m['dirty_worktree'] and m['git_revision']==subprocess.check_output(['git','rev-parse','HEAD'],cwd=r,text=True).strip()): raise RuntimeError('invalid bundle')
for a in m['artifacts']:
 p=b/a['path'];
 if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=a['sha256']: raise RuntimeError('artifact mismatch')
c=json.loads((b/'market-conditions.json').read_text());
if not (c['server']=='GOMarketsMU-Demo' and c['symbol']=='EURUSD' and 0<=c['tick_age_seconds']<=15 and c['spread_points']>=0 and c['market_condition'] in {'ACCEPTED_FOR_SIMULATED_INTENT_ONLY','SPREAD_LIMIT'} and c['order_submission']=='STRUCTURALLY_DISABLED'): raise RuntimeError('condition guard invalid')
print('FOREX_M28_EVIDENCE_VERIFIED')
PY
