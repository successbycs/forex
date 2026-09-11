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
t=json.loads((b/'tick-proof.json').read_text()); outer=json.loads((b/'listener-status.json').read_text()); assert outer['operation']=='m20_listener_status' and outer['approval_required'] is False and outer['approved'] is False and outer['ok'] is True; response=outer['result']; assert response['exit_code']==0 and response['ok'] is True; state=json.loads(response['stdout']); result=state['last_result']; quote=state['quote']; assert state['running'] is True and state['state'] not in {'STALE','STOPPED','STARTUP_FAILED'}; assert quote['server']=='GOMarketsMU-Demo' and quote['symbol']=='EURUSD'; assert result['server']=='GOMarketsMU-Demo' and result['symbol']=='EURUSD' and result['execution']['status']=='NOT_SUBMITTED'; assert t['operation']==outer['operation'] and t['server']==result['server'] and t['symbol']==result['symbol'] and t['quote_server']==quote['server'] and t['quote_symbol']==quote['symbol'] and t['assessment_captured_at_utc']==result['captured_at_utc'] and t['listener_state']==state['state'] and t['execution_status']==result['execution']['status']; captured=datetime.fromisoformat(result['captured_at_utc'].replace('Z','+00:00')); age=(datetime.now(timezone.utc)-captured).total_seconds(); assert 0<=age<=15 and 0<=t['age_seconds']<=15; print('FOREX_M27_EVIDENCE_VERIFIED')
PY
