#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
python3 - "$root" "$1" <<'PY'
import hashlib,json,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
root,b=Path(sys.argv[1]),Path(sys.argv[2]).resolve()
if not b.is_relative_to(root/'runs'/'evidence'/'M5'): raise SystemExit('bundle must be beneath runs/evidence/M5')
m=json.loads((b/'manifest.json').read_text()); registry=json.loads((root/'milestone_registry.json').read_text()); contract=next(x for x in registry['milestones'] if x['milestone_id']=='M5')
if m.get('schema_version')!='1.0.0' or m.get('milestone_id')!='M5': raise SystemExit('M5 manifest mismatch')
if m.get('exit_code')!=0 or m.get('dirty_worktree') is not False: raise SystemExit('M5 capture was unsuccessful or dirty')
if m.get('surface')!=contract['real_world_proof']['surface']: raise SystemExit('M5 proof surface mismatch')
captured=datetime.fromisoformat(m['captured_at'].replace('Z','+00:00'))
if (datetime.now(timezone.utc)-captured).total_seconds()>contract['real_world_proof']['freshness_hours']*3600: raise SystemExit('M5 evidence is stale')
if m.get('git_revision')!=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(): raise SystemExit('Git revision mismatch')
state=json.loads((root/'project_state.json').read_text()); digest=hashlib.sha256()
for rel in sorted(state['governed_configuration_paths']): digest.update(rel.encode()); digest.update(b'\0'); digest.update((root/rel).read_bytes()); digest.update(b'\0')
if m.get('configuration_fingerprint')!='sha256:'+digest.hexdigest(): raise SystemExit('configuration fingerprint mismatch')
required={'tests.txt','governance.txt','configuration.json','repository-verification.txt','reimport.json','verify.json','provenance-negative-control.json','exit-codes.txt','revision.txt','summary.txt'}
if {x.get('path') for x in m.get('artifacts',[])}!=required: raise SystemExit('unexpected or missing M5 artifact set')
for x in m['artifacts']:
 p=b/x['path']
 if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=x['sha256']: raise SystemExit('artifact hash mismatch: '+x['path'])
if any(line.rsplit('=',1)[-1]!='0' for line in (b/'exit-codes.txt').read_text().splitlines() if '=' in line): raise SystemExit('captured command failure')
combined=''.join((b/name).read_text(errors='replace') for name in required)
for marker in ('FOREX_M2_IMPORT_ALREADY_PRESENT','FOREX_M2_POSTGRES_VERIFY_OK','FOREX_M2_SEALED_RAW_OBSERVATION_NEGATIVE_CONTROL_OK','FOREX_REPOSITORY_VERIFICATION_OK','source_status=DEMO_ONLY','snapshot=EUR/USD:H1','lineage_ok=true','bar_availability_ok=true','point_in_time_triggers=2','FOREX_M5_PROOF_OK'):
 if marker not in combined: raise SystemExit('required marker missing: '+marker)
print('FOREX_M5_EVIDENCE_VERIFIED')
PY
