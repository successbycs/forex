#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
python3 - "$root" "$1" <<'PY'
import hashlib,json,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
r,b=Path(sys.argv[1]),Path(sys.argv[2]).resolve(); m=json.loads((b/'manifest.json').read_text()); assert b.is_relative_to(r/'runs/evidence/M27') and m['milestone_id']=='M27' and not m['dirty_worktree']; assert m['git_revision']==subprocess.check_output(['git','rev-parse','HEAD'],cwd=r,text=True).strip(); assert (datetime.now(timezone.utc)-datetime.fromisoformat(m['captured_at'].replace('Z','+00:00'))).total_seconds()<24*3600
for a in m['artifacts']:
 p=b/a['path']; assert p.is_file() and hashlib.sha256(p.read_bytes()).hexdigest()==a['sha256']
t=json.loads((b/'tick-proof.json').read_text()); outer=json.loads((b/'tick-response.json').read_text()); assert outer['operation']=='m27_demo_tick' and outer['approval_required'] is False and outer['approved'] is False and outer['ok'] is True; response=outer['result']; assert response['exit_code']==0 and response['ok'] is True; tick=json.loads(response['stdout']); assert tick['ok'] is True and tick['server']=='GOMarketsMU-Demo' and tick['symbol']=='EURUSD' and tick['bid']>0 and tick['ask']>=tick['bid'] and tick['tick_time_msc']>0 and tick['broker_timestamp_offset_seconds']==10800; assert t['operation']==outer['operation'] and t['server']==tick['server'] and t['symbol']==tick['symbol'] and t['bid']==tick['bid'] and t['ask']==tick['ask'] and t['tick_time_msc']==tick['tick_time_msc'] and t['broker_timestamp_offset_seconds']==tick['broker_timestamp_offset_seconds'] and t['tick_captured_at_utc']==tick['captured_at_utc']; tick_at=datetime.fromtimestamp(tick['tick_time_msc']/1000-tick['broker_timestamp_offset_seconds'],timezone.utc); response_at=datetime.fromisoformat(tick['captured_at_utc'].replace('Z','+00:00')); bundle_capture=datetime.fromisoformat(m['captured_at'].replace('Z','+00:00')); assert 0<=t['tick_age_seconds']<=15 and 0<=(response_at-tick_at).total_seconds()<=15 and 0<=(bundle_capture-tick_at).total_seconds()<=15; print('FOREX_M27_EVIDENCE_VERIFIED')
PY
