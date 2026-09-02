#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
python3 - "$root" "$1" <<'PY'
import hashlib,json,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
r,b=Path(sys.argv[1]),Path(sys.argv[2]).resolve(); m=json.loads((b/'manifest.json').read_text())
assert b.is_relative_to(r/'runs/evidence/M20') and m['milestone_id']=='M20' and not m['dirty_worktree'] and m['git_revision']==subprocess.check_output(['git','rev-parse','HEAD'],cwd=r,text=True).strip()
assert (datetime.now(timezone.utc)-datetime.fromisoformat(m['captured_at'].replace('Z','+00:00'))).total_seconds()<168*3600
for a in m['artifacts']:
 p=b/a['path']; assert p.is_file() and hashlib.sha256(p.read_bytes()).hexdigest()==a['sha256']
p=json.loads((b/'evaluation-probe.json').read_text()); x=json.loads(p['result']['stdout']); e=x['evaluation']
assert p['ok'] and x['marker']=='FOREX_M20_OLLAMA_EVALUATION_PROBE_OK' and x['source']=='DEMO_ONLY_HISTORICAL' and not x['order_capability'] and not x['live_trading_capability']
assert e['marker']=='FOREX_M20_EVALUATION_OK' and e['model']=='qwen2.5:3b' and len(e['rows'])==3 and e['valid_model_response_count'] >= 1 and e['predeclared_controls']['chronological_only'] and not e['predeclared_controls']['random_shuffling_used'] and e['research_only'] and not e['order_capability']
assert 'FOREX_M20_PROOF_OK' in (b/'summary.txt').read_text(); print('FOREX_M20_EVIDENCE_VERIFIED')
PY
