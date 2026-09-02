#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
python3 - "$root" "$1" <<'PY'
import hashlib,json,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
r,b=Path(sys.argv[1]),Path(sys.argv[2]).resolve(); m=json.loads((b/'manifest.json').read_text())
assert b.is_relative_to(r/'runs/evidence/M19') and m['milestone_id']=='M19' and not m['dirty_worktree'] and m['git_revision']==subprocess.check_output(['git','rev-parse','HEAD'],cwd=r,text=True).strip()
assert (datetime.now(timezone.utc)-datetime.fromisoformat(m['captured_at'].replace('Z','+00:00'))).total_seconds()<168*3600
for a in m['artifacts']:
 p=b/a['path']; assert p.is_file() and hashlib.sha256(p.read_bytes()).hexdigest()==a['sha256']
p=json.loads((b/'lineage-probe.json').read_text()); x=json.loads(p['result']['stdout']); q=json.loads((b/'lineage-verify.json').read_text())
assert p['ok'] and x['marker']=='FOREX_M19_LINEAGE_PROBE_OK' and x['model']=='qwen2.5:3b' and x['research_only'] and not x['order_capability'] and not x['live_trading_capability']
assert q['ok']; output=q['result']['stdout']
for marker in ('FOREX_M19_LINEAGE_VERIFY_OK','model=qwen2.5:3b=true','demo_only=true','validation_results_valid=true','research_only=true','hashes_present=true','decision_linkage=true','no_order_fields=true'): assert marker in output
assert 'FOREX_M19_PROOF_OK' in (b/'summary.txt').read_text(); print('FOREX_M19_EVIDENCE_VERIFIED')
PY
