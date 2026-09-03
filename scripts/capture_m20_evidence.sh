#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"; cd "$root"
export PYTHONPATH="$root/src${PYTHONPATH:+:$PYTHONPATH}"
bundle="${1:-runs/evidence/M20/$(date -u +%Y%m%dT%H%M%SZ)}"; mkdir -p "$bundle"
git diff --quiet
python3 -m pytest -q tests/milestones/test_m20.py >"$bundle/tests.txt" 2>&1
python3 scripts/forex_milestones.py validate >"$bundle/governance.txt" 2>&1
python3 scripts/postgres_pgvector_adapter.py forex-m20-ollama-evaluation-probe >"$bundle/evaluation-probe.json"
git rev-parse HEAD >"$bundle/revision.txt"
python3 - "$bundle" <<'PY'
import hashlib,json,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
b=Path(sys.argv[1]); probe=json.loads((b/'evaluation-probe.json').read_text()); value=json.loads(probe['result']['stdout']); evaluation=value['evaluation']
sys.path.insert(0, 'src'); from forex.t480_dependency import inspect_dependency
dependency=inspect_dependency(json.loads(Path('config/t480.json').read_text()) )
assert probe['ok'] and value['marker']=='FOREX_M20_OLLAMA_EVALUATION_PROBE_OK' and value['source']=='DEMO_ONLY_HISTORICAL'
assert evaluation['marker']=='FOREX_M20_EVALUATION_OK' and len(evaluation['rows'])==3 and evaluation['valid_model_response_count'] >= 1 and evaluation['research_only'] and not evaluation['order_capability'] and not value['live_trading_capability']
provenance=value['ollama_provenance']; assert provenance['runtime_version'] and provenance['model_inventory'] and provenance['model_details'] and provenance['model_inventory_sha256'].startswith('sha256:') and provenance['model_details_sha256'].startswith('sha256:')
assert all(set(row['invocation_metadata']) == {'input_context_sha256','prompt_sha256','response_schema_sha256'} and all(v.startswith('sha256:') for v in row['invocation_metadata'].values()) for row in evaluation['rows'])
as_utc=lambda value: datetime.fromisoformat(value.replace('Z','+00:00')).astimezone(timezone.utc)
assert all(as_utc(row['decision_at_utc']) <= as_utc(row['entry_at_utc']) < as_utc(row['exit_at_utc']) for row in evaluation['rows'])
assert dependency['ok'] and dependency['revision_matches'] and dependency['clean_worktree']
dependency={key:value for key,value in dependency.items() if key != 'revision_matches'}
(b/'comparison.json').write_text(json.dumps({'model':value['model_definition_sha256'],'ollama_provenance':provenance,'controls':evaluation['predeclared_controls'],'comparison':evaluation['comparison']},indent=2)+'\n')
(b/'summary.txt').write_text('FOREX_M20_PROOF_OK\n'); state=json.loads(subprocess.check_output(['python3','scripts/forex_milestones.py','status','--json']))
artifacts=[{'path':f.name,'sha256':hashlib.sha256(f.read_bytes()).hexdigest()} for f in sorted(b.iterdir()) if f.is_file()]
m={'schema_version':'1.0.0','milestone_id':'M20','captured_at':datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),'git_revision':(b/'revision.txt').read_text().strip(),'dirty_worktree':False,'configuration_fingerprint':state['configuration_fingerprint'],'surface':'offline Ollama-assisted historical evaluation environment','operation':'fixed T480 M20 chronological Ollama comparison','expected_result':'validated local-model sentiment is compared only with fixed price-only and no-change historical baselines','observed_result':'FOREX_M20_PROOF_OK','exit_code':0,'redactions':['No account, credential, broker-server, order or execution data retained.'],'summary':'FOREX_M20_PROOF_OK','external_dependencies':[dependency],'artifacts':artifacts}
(b/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
PY
echo "$bundle"
