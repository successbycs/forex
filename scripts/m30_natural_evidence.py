"""Capture/verify a natural M30 proof from retained bytes, never place an order."""
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

import m20_demo_evidence_contract as m20
from m30_natural_sources import require, strict_json, load_sources
from m30_natural_lifecycle import validate_trade
from m30_natural_runtime import validate_runtime

OPERATION = 'retained natural T480 M1 listener lifecycle'
MARKER = 'FOREX_M30_PROOF_OK'
AUTHORITY_PATH = 'docs/plans/m30-demo-mvp-unblocking-work.json'
REQUIRED = {'raw-capture-receipt.json', 'topology-authority.json', 'tests.txt', 'governance.txt',
            'revision.txt', 'configuration.json', 'm30-audit.json', 'summary.txt', 'm30-verification.txt'}
TESTS = ['tests/milestones/test_m30.py', 'tests/test_m30_natural_capture.py',
         'tests/test_m30_natural_sources.py', 'tests/test_m30_natural_lifecycle.py', 'tests/test_m30_natural_runtime.py',
         'tests/test_m30_natural_evidence.py']


def revision(root):
    return subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()


def clean(root, *, allow_governance_records=False):
    """Reject implementation drift; recorder writes only these two state files."""
    output = subprocess.check_output(['git', 'status', '--porcelain', '--untracked-files=normal'],
                                     cwd=root, text=True)
    changed = []
    for line in output.splitlines():
        require(len(line) >= 4, 'unparseable worktree status')
        changed.append(line[3:])
    allowed = {'project_state.json', 'runs/run_history.json'} if allow_governance_records else set()
    require(set(changed) <= allowed, 'proof capture requires a clean committed worktree')


def write_new(path, data):
    with path.open('xb') as handle:
        handle.write(data)


def json_bytes(value):
    return (json.dumps(value, indent=2) + '\n').encode()


def check_sources(bundle, root, authority):
    joined = load_sources(bundle)
    captured = m20.utc(joined['receipt']['captured_at_utc'], 'raw capture time')
    require(timedelta(0) <= datetime.now(timezone.utc) - captured < timedelta(hours=24),
            'natural raw capture stale or future-dated')
    fingerprint = m20.project_fingerprint(root)
    runtime = validate_runtime(bundle, joined, root=root, fingerprint=fingerprint,
                               captured=captured, approval=authority)
    trade = validate_trade(joined, root=root, lease=runtime['lease'], captured=captured)
    return {'schema_version': 'forex.m30.natural-proof-audit.v1',
            'proposal_id': joined['receipt']['proposal_id'], 'attempt_id': joined['receipt']['attempt_id'],
            'source_match': joined['receipt']['source_match'], 'runtime': runtime, 'trade': trade,
            'configuration_fingerprint': fingerprint, 'captured_at': captured.isoformat(),
            'limitations': ['Self-attested integrity, not an external execution witness.',
                           'Historical mutable risk headroom is not independently replayed.',
                           'Protection is evidenced by the accepted protected request and guarded deployed code.',
                           'Interactive availability depends on the operator-managed terminal.']}


def finalize(bundle: Path, root: Path):
    require(bundle.is_relative_to((root / 'runs/evidence/M30').resolve()), 'bundle outside M30 evidence root')
    clean(root)
    require(not any((bundle / name).exists() for name in REQUIRED - {'raw-capture-receipt.json'} | {'manifest.json'}),
            'derived proof files already exist; retain bundle without overwriting')
    collector_revision = revision(root)
    authority_raw = subprocess.check_output(['git', 'show', f'{collector_revision}:{AUTHORITY_PATH}'], cwd=root)
    audit = check_sources(bundle, root, strict_json(authority_raw))
    write_new(bundle / 'topology-authority.json', authority_raw)
    for name, argv in [('tests.txt', [sys.executable, '-m', 'pytest', '-q', '-o', 'addopts=', *TESTS]),
                       ('governance.txt', [sys.executable, 'scripts/forex_milestones.py', 'validate'])]:
        result = subprocess.run(argv, cwd=root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=300)
        write_new(bundle / name, result.stdout)
        require(result.returncode == 0, f'{name} failed; original output retained')
    clean(root)
    require(revision(root) == collector_revision, 'collector revision changed during capture')
    write_new(bundle / 'revision.txt', (collector_revision + '\n').encode())
    write_new(bundle / 'configuration.json', json_bytes({
        'configuration_fingerprint': audit['configuration_fingerprint'], 'runtime_mode': 'DEMO_TRADING',
        'live_trading_enabled': False, 'permitted_mt5_server': 'GOMarketsMU-Demo'}))
    write_new(bundle / 'm30-audit.json', json_bytes(audit))
    write_new(bundle / 'm30-verification.txt', b'FOREX_M30_TARGETED_VERIFICATION_OK\n')
    write_new(bundle / 'summary.txt', (MARKER + '\nNatural Demo EURUSD entry, owner exit and matched broker history.\n').encode())
    artifacts = [{'path': p.name, 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
                 for p in sorted(bundle.iterdir()) if p.is_file()]
    manifest = dict(schema_version='1.0.0', milestone_id='M30', operation=OPERATION,
        surface='GOMarketsMU-Demo execution and reconciliation surface', captured_at=audit['captured_at'],
        git_revision=collector_revision, dirty_worktree=False,
        configuration_fingerprint=audit['configuration_fingerprint'], exit_code=0,
        expected_result='one naturally selected bounded Demo EURUSD entry closes and reconciles',
        observed_result=MARKER, summary=MARKER, artifacts=artifacts,
        redactions=['No credentials, account login identifiers or non-Demo broker data retained.'])
    write_new(bundle / 'manifest.json', json_bytes(manifest))
    verify(bundle, root)


def verify(bundle: Path, root: Path):
    clean(root, allow_governance_records=True)
    require(bundle.is_relative_to((root / 'runs/evidence/M30').resolve()) and not bundle.is_symlink(),
            'bundle outside M30 evidence root')
    require(not (bundle / 'manifest.json').is_symlink(), 'unsafe manifest path')
    manifest = strict_json((bundle / 'manifest.json').read_bytes())
    for key, value in [('schema_version', '1.0.0'), ('milestone_id', 'M30'), ('operation', OPERATION),
                       ('surface', 'GOMarketsMU-Demo execution and reconciliation surface'),
                       ('observed_result', MARKER), ('summary', MARKER)]:
        require(manifest.get(key) == value, f'manifest {key} mismatch')
    require(manifest.get('dirty_worktree') is False and type(manifest.get('exit_code')) is int
            and manifest['exit_code'] == 0, 'manifest capture not clean/successful')
    collector_revision = revision(root)
    require(manifest.get('git_revision') == collector_revision, 'collector revision differs from HEAD')
    names = set()
    require(isinstance(manifest.get('artifacts'), list), 'manifest artifacts missing')
    for item in manifest['artifacts']:
        require(isinstance(item, dict), 'invalid manifest artifact')
        name = item.get('path')
        require(isinstance(name, str) and re.fullmatch('[A-Za-z0-9_.-]+', name)
                and name not in {'.', '..', 'manifest.json'} and name not in names, 'invalid manifest artifact path')
        path = bundle / name
        require(not path.is_symlink() and path.is_file(), 'unsafe manifest artifact')
        require(hashlib.sha256(path.read_bytes()).hexdigest() == item.get('sha256'), 'manifest artifact hash mismatch')
        names.add(name)
    receipt = strict_json((bundle / 'raw-capture-receipt.json').read_bytes())
    expected = REQUIRED | {item['path'] for item in receipt['artifacts']}
    require(names == expected, 'manifest/raw inventory mismatch')
    authority_raw = (bundle / 'topology-authority.json').read_bytes()
    require(authority_raw == subprocess.check_output(['git', 'show', f'{collector_revision}:{AUTHORITY_PATH}'], cwd=root),
            'topology authority differs from committed record')
    audit = check_sources(bundle, root, strict_json(authority_raw))
    require(strict_json((bundle / 'm30-audit.json').read_bytes()) == audit, 'derived natural audit mismatch')
    for key, value in [('configuration_fingerprint', audit['configuration_fingerprint']),
                       ('captured_at', audit['captured_at'])]:
        require(manifest.get(key) == value, f'manifest {key} source mismatch')
    require((bundle / 'revision.txt').read_text().strip() == collector_revision, 'revision receipt mismatch')
    configuration = strict_json((bundle / 'configuration.json').read_bytes())
    require(configuration == {'configuration_fingerprint': audit['configuration_fingerprint'],
        'runtime_mode': 'DEMO_TRADING', 'live_trading_enabled': False, 'permitted_mt5_server': 'GOMarketsMU-Demo'},
        'configuration receipt mismatch')
    tests = (bundle / 'tests.txt').read_text()
    require(re.search(r'\b[1-9]\d* passed\b', tests) and not re.search(r'\b[1-9]\d* (failed|errors?)\b', tests),
            'targeted tests not successful')
    require('milestone governance valid' in (bundle / 'governance.txt').read_text(), 'governance not successful')
    require((bundle / 'm30-verification.txt').read_text().strip() == 'FOREX_M30_TARGETED_VERIFICATION_OK',
            'targeted verification marker missing')
    require((bundle / 'summary.txt').read_text().splitlines()[0] == MARKER, 'summary marker missing')
    print('FOREX_M30_EVIDENCE_VERIFIED')
    print(MARKER)
