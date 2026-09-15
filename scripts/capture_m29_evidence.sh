#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"; cd "$root"; bundle="${1:-runs/evidence/M29/$(date -u +%Y%m%dT%H%M%SZ)}"
[ ! -e "$bundle" ] || { echo "Refusing to overwrite evidence bundle" >&2; exit 2; }
# Evidence registration updates these two local operational ledgers.  They are
# intentionally uncommitted and must not prevent a later source-clean capture.
# Everything else, including staged or untracked source, must be absent: the
# manifest attests exactly to HEAD, never an index or local overlay.
dirty_source="$( { git diff --name-only; git diff --cached --name-only; git ls-files --others --exclude-standard; } | sort -u | grep -vx -e project_state.json -e runs/run_history.json || true )"
[ -z "$dirty_source" ] || { echo "M29 capture requires clean source; changed: $dirty_source" >&2; exit 2; }
mkdir -p "$bundle"
python3 -m pytest -q tests/milestones/test_m29.py >"$bundle/tests.txt" 2>&1; python3 scripts/forex_milestones.py validate >"$bundle/governance.txt" 2>&1
for x in m20_listener_continuity_status:m29-continuity.json m20_listener_status:postflight-listener.json m20_demo_account_liquidity:postflight-account.json m20_listener_diagnostics:postflight-diagnostics.json; do python3 scripts/t480_adapter.py execute --operation "${x%%:*}" >"$bundle/${x#*:}"; done
git rev-parse HEAD >"$bundle/revision.txt"; echo FOREX_M29_PROOF_OK >"$bundle/summary.txt"
python3 - "$bundle" <<'PY'
import hashlib,json,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
b=Path(sys.argv[1]); s=json.loads(subprocess.check_output(['python3','scripts/forex_milestones.py','status','--json'])); files=sorted(b.iterdir()); a=[{'path':p.name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in files if p.is_file()]; m={'schema_version':'1.0.0','milestone_id':'M29','captured_at':datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),'git_revision':(b/'revision.txt').read_text().strip(),'dirty_worktree':False,'configuration_fingerprint':s['configuration_fingerprint'],'surface':'real-time GOMarketsMU-Demo collection and recovery workflow','operation':'fixed held listener continuity protocol plus postflight observations','expected_result':'recovered held listener and flat Demo account without an order','observed_result':'FOREX_M29_PROOF_OK','exit_code':0,'redactions':['No credentials retained.'],'summary':'FOREX_M29_PROOF_OK','artifacts':a}; (b/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
PY
echo "$bundle"
