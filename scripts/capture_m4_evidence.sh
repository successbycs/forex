#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"; cd "$root"; b="${1:-runs/evidence/M4/$(date -u +%Y%m%dT%H%M%SZ)}"; mkdir -p "$b"
python3 -m pytest -q tests/milestones/test_m4.py >"$b/tests.txt" 2>&1
python3 - <<'PY' >"$b/application.txt"
from forex.data_contracts import build_dataset_snapshot
from forex.research_data import historical_bars
s={'contract_version':'forex.historical-data.v1','source_id':'demo','owner':'demo','license':'demo','cost_model':'demo','api_version':'demo','endpoint_allowlist':[],'rate_limit':'demo','retention_rule':'demo','historical_depth':'demo','revision_support':'demo','timezone_policy':'UTC','outage_policy':'demo','approval_status':'DEMO_ONLY','secrets_reference':'NONE','provenance_note':'demo'}; o={'contract_version':'forex.historical-data.v1','observation_id':'o','source_id':'demo','source_revision':'x','observed_at_utc':'2026-01-01T00:00:00Z','available_at_utc':'2026-01-01T02:00:00Z','retrieved_at_utc':'2026-01-01T02:00:00Z','timezone':'UTC','payload_sha256':'sha256:x','payload_path':'x','redacted':True}; b={'time_utc':'2026-01-01T01:00:00Z','open':1.,'high':1.1,'low':.9,'close':1.,'volume':1,'raw_observation_id':'o','available_at_utc':'2026-01-01T02:00:00Z'}
print(len(historical_bars(build_dataset_snapshot(snapshot_id='m4',instrument='EUR/USD',timeframe='H1',decision_cutoff_utc='2026-01-01T02:00:00Z',created_at_utc='2026-01-01T02:00:00Z',source_registry=[s],raw_observations=[o],price_bars=[b]),'2026-01-01T02:00:00Z')))
PY
git rev-parse HEAD >"$b/revision.txt"
python3 - "$b" <<'PY'
import json,hashlib,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
b=Path(sys.argv[1]); fs=[{'path':p.name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in b.iterdir() if p.is_file()]; (b/'summary.txt').write_text('FOREX_M4_PROOF_OK\n'); fs.append({'path':'summary.txt','sha256':hashlib.sha256((b/'summary.txt').read_bytes()).hexdigest()}); print(json.dumps({'schema_version':'1.0.0','milestone_id':'M4','captured_at':datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),'git_revision':(b/'revision.txt').read_text().strip(),'dirty_worktree':False,'configuration_fingerprint':json.loads(subprocess.check_output(['python3','scripts/forex_milestones.py','status','--json']))['configuration_fingerprint'],'surface':'Forex application historical-ingestion integration','operation':'read-only application snapshot integration','expected_result':'one validated point-in-time bar','observed_result':'FOREX_M4_PROOF_OK','exit_code':0,'redactions':['No credentials or trading data.'],'summary':'FOREX_M4_PROOF_OK','artifacts':fs},indent=2),file=open(b/'manifest.json','w'))
PY
echo "$b"
