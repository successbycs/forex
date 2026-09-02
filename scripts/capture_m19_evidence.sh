#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"; cd "$root"
export PYTHONPATH="$root/src${PYTHONPATH:+:$PYTHONPATH}"
bundle="${1:-runs/evidence/M19/$(date -u +%Y%m%dT%H%M%SZ)}"; mkdir -p "$bundle"
git diff --quiet
python3 -m pytest -q tests/milestones/test_m19.py >"$bundle/tests.txt" 2>&1
python3 scripts/forex_milestones.py validate >"$bundle/governance.txt" 2>&1
python3 scripts/postgres_pgvector_adapter.py forex-m19-apply-schema --approve >"$bundle/schema-apply.json"
python3 scripts/postgres_pgvector_adapter.py forex-m19-lineage-probe --approve >"$bundle/lineage-probe.json"
python3 scripts/postgres_pgvector_adapter.py forex-m19-lineage-verify >"$bundle/lineage-verify.json"
git rev-parse HEAD >"$bundle/revision.txt"
python3 - "$bundle" <<'PY'
import hashlib,json,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
b=Path(sys.argv[1]); probe=json.loads((b/'lineage-probe.json').read_text()); value=json.loads(probe['result']['stdout']); check=json.loads((b/'lineage-verify.json').read_text())
assert probe['ok'] and value['marker']=='FOREX_M19_LINEAGE_PROBE_OK' and value['research_only'] and not value['order_capability'] and not value['live_trading_capability']
assert check['ok'] and 'FOREX_M19_LINEAGE_VERIFY_OK' in check['result']['stdout']
(b/'model-lineage.json').write_text(json.dumps({k:value[k] for k in ('inference_id','decision_id','snapshot_id','model','model_definition_sha256','prompt_template_version','prompt_sha256','input_sha256','output_sha256','validation_result')},indent=2)+'\n')
(b/'summary.txt').write_text('FOREX_M19_PROOF_OK\n'); state=json.loads(subprocess.check_output(['python3','scripts/forex_milestones.py','status','--json']))
artifacts=[{'path':f.name,'sha256':hashlib.sha256(f.read_bytes()).hexdigest()} for f in sorted(b.iterdir()) if f.is_file()]
m={'schema_version':'1.0.0','milestone_id':'M19','captured_at':datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),'git_revision':(b/'revision.txt').read_text().strip(),'dirty_worktree':False,'configuration_fingerprint':state['configuration_fingerprint'],'surface':'offline decision and model-lineage persistence workflow','operation':'fixed T480 M19 schema, persistence and replay operations','expected_result':'validated bounded local-model observation is persisted with linked research decision lineage','observed_result':'FOREX_M19_PROOF_OK','exit_code':0,'redactions':['No account, credential, broker-server, order or execution data retained.'],'summary':'FOREX_M19_PROOF_OK','artifacts':artifacts}
(b/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
PY
echo "$bundle"
