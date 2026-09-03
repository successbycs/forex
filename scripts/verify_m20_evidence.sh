#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
python3 - "$root" "$1" <<'PY'
import hashlib,json,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
class VerificationError(RuntimeError):
    pass

def require(condition, message):
    if not condition:
        raise VerificationError(message)

r,b=Path(sys.argv[1]),Path(sys.argv[2]).resolve(); m=json.loads((b/'manifest.json').read_text())
require(b.is_relative_to(r/'runs/evidence/M20'), 'evidence bundle is outside the M20 evidence root')
require(m['milestone_id']=='M20', 'manifest milestone is not M20')
require(not m['dirty_worktree'], 'manifest records a dirty worktree')
require(m['git_revision']==subprocess.check_output(['git','rev-parse','HEAD'],cwd=r,text=True).strip(), 'manifest revision does not match HEAD')
require((datetime.now(timezone.utc)-datetime.fromisoformat(m['captured_at'].replace('Z','+00:00'))).total_seconds()<168*3600, 'evidence is stale')
dependencies=m.get('external_dependencies', [])
require(len(dependencies) == 1, 'manifest must contain exactly one external dependency')
dependency=dependencies[0]
require(dependency['ok'], 'external dependency verification failed')
require(dependency['clean_worktree'], 'external dependency worktree is not clean')
require(dependency['actual_git_revision']==dependency['expected_git_revision'], 'external dependency revision mismatch')
for a in m['artifacts']:
 p=b/a['path']; require(p.is_file(), f"missing artifact: {a['path']}"); require(hashlib.sha256(p.read_bytes()).hexdigest()==a['sha256'], f"artifact digest mismatch: {a['path']}")
p=json.loads((b/'evaluation-probe.json').read_text()); x=json.loads(p['result']['stdout']); e=x['evaluation']
require(p['ok'], 'probe wrapper reports failure')
require(x['marker']=='FOREX_M20_OLLAMA_EVALUATION_PROBE_OK', 'probe marker mismatch')
require(x['source']=='DEMO_ONLY_HISTORICAL', 'probe source is not Demo-only historical')
require(not x['order_capability'] and not x['live_trading_capability'], 'probe exposes an unsafe capability')
require(e['marker']=='FOREX_M20_EVALUATION_OK' and e['model']=='qwen2.5:3b', 'evaluation identity mismatch')
require(len(e['rows'])==3 and e['valid_model_response_count'] >= 1, 'evaluation rows are incomplete')
require(e['predeclared_controls']['chronological_only'] and not e['predeclared_controls']['random_shuffling_used'], 'evaluation controls are unsafe')
require(e['research_only'] and not e['order_capability'], 'evaluation is not research-only')
provenance=x['ollama_provenance']
require(provenance['runtime_version'] and provenance['model_inventory'] and provenance['model_details'], 'Ollama provenance is incomplete')
require(provenance['model_inventory_sha256'].startswith('sha256:') and provenance['model_details_sha256'].startswith('sha256:'), 'Ollama provenance digests are invalid')
require(all(set(row['invocation_metadata']) == {'input_context_sha256','prompt_sha256','response_schema_sha256'} and all(v.startswith('sha256:') for v in row['invocation_metadata'].values()) for row in e['rows']), 'invocation provenance is incomplete')
as_utc=lambda value: datetime.fromisoformat(value.replace('Z','+00:00')).astimezone(timezone.utc)
require(all(as_utc(row['decision_at_utc']) <= as_utc(row['entry_at_utc']) < as_utc(row['exit_at_utc']) for row in e['rows']), 'evaluation has lookahead ordering')
require('FOREX_M20_PROOF_OK' in (b/'summary.txt').read_text(), 'proof marker is missing')
print('FOREX_M20_EVIDENCE_VERIFIED')
PY
