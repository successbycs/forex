#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
export PYTHONPATH="$root/src${PYTHONPATH:+:$PYTHONPATH}"
python3 - "$root" "$1" <<'PY'
import hashlib, json, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path
from forex.config import load_configuration
from forex.milestones import configuration_fingerprint

ROOT, BUNDLE = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
REQUIRED = {'governance.txt', 'tests.txt', 'pre-interruption-response.json', 'interrupted-client-attempt.txt', 'recovery-response.json', 'recovery-proof.json', 'revision.txt', 'summary.txt'}
def require(ok, message):
 if not ok: raise RuntimeError(message)
def utc(value, field):
 require(isinstance(value, str), field+' must be an RFC3339 timestamp')
 try: parsed=datetime.fromisoformat(value.replace('Z','+00:00'))
 except ValueError as exc: raise RuntimeError(field+' is invalid') from exc
 require(parsed.tzinfo is not None, field+' must include an offset')
 return parsed.astimezone(timezone.utc)
def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def raw_tick(name, manifest, offset):
 outer=json.loads((BUNDLE/name).read_text(encoding='utf-8'))
 require(outer.get('operation')=='m27_demo_tick', name+': unexpected operation')
 require(outer.get('approval_required') is False and outer.get('approved') is False, name+': approval state is unsafe')
 require(outer.get('ok') is True and outer.get('configuration_fingerprint')==manifest['configuration_fingerprint'], name+': envelope is unsuccessful or unbound')
 result=outer.get('result'); require(isinstance(result,dict) and result.get('ok') is True and result.get('exit_code')==0, name+': operation failed')
 tick=json.loads(result.get('stdout',''))
 require(tick.get('ok') is True and tick.get('server')=='GOMarketsMU-Demo' and tick.get('symbol')=='EURUSD', name+': wrong server or symbol')
 require(isinstance(tick.get('bid'),(int,float)) and isinstance(tick.get('ask'),(int,float)) and tick['bid']>0 and tick['ask']>=tick['bid'], name+': invalid quote')
 require(isinstance(tick.get('tick_time_msc'),int) and tick['tick_time_msc']>0, name+': invalid broker tick time')
 require(tick.get('broker_timestamp_offset_seconds')==offset and tick.get('broker_timestamp_offset_source')=='governed_configuration', name+': broker clock is not governed')
 tick_at=datetime.fromtimestamp(tick['tick_time_msc']/1000-offset,timezone.utc); captured=utc(tick.get('captured_at_utc'),name+'.captured_at_utc'); now=datetime.now(timezone.utc)
 require(tick_at<=now and captured<=now, name+': future tick refused')
 require(0<=(captured-tick_at).total_seconds()<=15, name+': stale or invalid response tick')
 require(0<=(now-tick_at).total_seconds()<=15, name+': stale tick refused')
 return outer,tick,tick_at

require(BUNDLE.is_relative_to(ROOT/'runs'/'evidence'/'M29'), 'bundle location invalid')
require(BUNDLE.is_dir() and not BUNDLE.is_symlink(), 'bundle directory invalid')
manifest_path=BUNDLE/'manifest.json'; require(manifest_path.is_file() and not manifest_path.is_symlink(), 'manifest missing')
manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
require(manifest.get('schema_version')=='1.0.0' and manifest.get('milestone_id')=='M29' and manifest.get('dirty_worktree') is False and manifest.get('exit_code')==0, 'manifest identity invalid')
require(manifest.get('git_revision')==subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(), 'revision mismatch')
state=json.loads((ROOT/'project_state.json').read_text(encoding='utf-8')); require(manifest.get('configuration_fingerprint')==configuration_fingerprint(ROOT,state), 'current configuration mismatch')
captured=utc(manifest.get('captured_at'),'manifest.captured_at'); now=datetime.now(timezone.utc); require(captured<=now and 0<=(now-captured).total_seconds()<24*3600, 'manifest freshness invalid')
artifacts=manifest.get('artifacts'); require(isinstance(artifacts,list) and artifacts, 'manifest artifacts missing')
names=set()
for artifact in artifacts:
 require(isinstance(artifact,dict) and set(artifact)=={'path','sha256'}, 'artifact entry invalid')
 name, hash_=artifact['path'],artifact['sha256']
 require(isinstance(name,str) and isinstance(hash_,str) and len(hash_)==64, 'artifact metadata invalid')
 candidate=BUNDLE/name
 require(not Path(name).is_absolute() and candidate.resolve().is_relative_to(BUNDLE) and candidate.is_file() and not candidate.is_symlink(), 'artifact path invalid')
 require(name not in names and digest(candidate)==hash_, 'artifact hash mismatch'); names.add(name)
require(names==REQUIRED, 'required artifacts missing or unexpected artifacts declared')
require({p.name for p in BUNDLE.iterdir() if p.is_file()}==REQUIRED|{'manifest.json'}, 'bundle contains undeclared or missing files')
require((BUNDLE/'revision.txt').read_text(encoding='utf-8').strip()==manifest['git_revision'], 'revision artifact mismatch')
require((BUNDLE/'summary.txt').read_text(encoding='utf-8').strip()=='FOREX_M29_OBSERVATION_CAPTURED_UNSUPPORTED', 'unsupported observation marker absent')
offset=load_configuration(ROOT,environ={}).mt5.broker_tick_time_offset_seconds
pre_outer,pre_tick,pre_at=raw_tick('pre-interruption-response.json',manifest,offset)
recovery_outer,recovery_tick,recovery_at=raw_tick('recovery-response.json',manifest,offset)
require(pre_at<=captured and recovery_at<=captured, 'raw tick was captured after manifest')
proof=json.loads((BUNDLE/'recovery-proof.json').read_text(encoding='utf-8'))
require(proof.get('request_identity')=='m27_demo_tick:GOMarketsMU-Demo:EURUSD', 'unexpected request identity')
require(proof.get('raw_envelopes')=={'pre_interruption_response_sha256':digest(BUNDLE/'pre-interruption-response.json'),'recovery_response_sha256':digest(BUNDLE/'recovery-response.json')}, 'raw-envelope binding mismatch')
for label,outer,tick in (('pre_interruption',pre_outer,pre_tick),('recovery',recovery_outer,recovery_tick)):
 require(proof.get(label)=={'operation':outer['operation'],'server':tick['server'],'symbol':tick['symbol'],'bid':tick['bid'],'ask':tick['ask'],'tick_time_msc':tick['tick_time_msc'],'broker_timestamp_offset_seconds':tick['broker_timestamp_offset_seconds'],'broker_timestamp_offset_source':tick['broker_timestamp_offset_source'],'tick_captured_at_utc':tick['captured_at_utc']}, label+' proof does not bind its raw envelope')
require(proof.get('interruption')=={'state':'INTERRUPTED_CLIENT_SIDE','exit_code':124,'remote_mutation':'STRUCTURALLY_DISABLED','note':'The timeout terminates only the local adapter client before response processing.'}, 'interruption is not bounded')
require(proof.get('idempotency')=='REPEATED_FIXED_READ_ONLY_REQUEST_NO_PERSISTENT_MUTATION', 'idempotency declaration invalid')
# No collector identity, lifecycle, outage, restart, or persisted receipt identity is retained.
raise RuntimeError('FOREX_M29_OBSERVATION_CAPTURED_UNSUPPORTED: client timeout plus stateless reads does not prove collector interruption, outage, restart, or durable deduplication')
PY
