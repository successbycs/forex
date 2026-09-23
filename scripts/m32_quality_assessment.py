#!/usr/bin/env python3
"""Offline final Demo quality assessment of retained, approved parent evidence."""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'src')]
from forex.m31_supplement import require
from forex.m31_scorecard import _instant, _json
from m30_natural_evidence import check_sources
from m30_natural_sources import load_sources
from m31_retained_evidence import compute as m31_compute
from scripts.listener_workflow_report import build_report, render_summary, render_workflow
import m20_demo_evidence_contract as m20

MARKER = 'FOREX_M32_PROOF_OK'
SURFACE = 'retained GOMarketsMU-Demo forward-evaluation evidence and live-readiness assessment'
TESTS = ['tests/milestones/test_m32.py', 'tests/test_listener_workflow_report.py',
         'tests/test_m20_listener_dashboard.py', 'tests/test_m20_listener_evidence_view.py',
         'tests/test_triad.py']
LOCAL = {'parent-approvals.json', 'operator-report.json', 'assessment.json',
         'operator-60.txt', 'operator-100.txt', 'operator-full.txt',
         'summary.txt', 'tests.txt', 'governance.txt'}


def read(path: Path) -> bytes:
    require(path.is_file() and not path.is_symlink(), f'not a regular artifact: {path.name}')
    return path.read_bytes()


def hash_inventory(bundle: Path) -> dict:
    """Validate only safe manifest-listed artifacts; no paths may escape."""
    require(bundle.is_dir() and not bundle.is_symlink(), 'unsafe evidence directory')
    manifest = _json(read(bundle / 'manifest.json'), 'manifest')
    require(isinstance(manifest, dict) and isinstance(manifest.get('artifacts'), list), 'invalid manifest')
    names = set()
    for item in manifest['artifacts']:
        require(isinstance(item, dict) and set(item) == {'path', 'sha256'}, 'invalid artifact')
        name = item['path']
        require(isinstance(name, str) and re.fullmatch(r'[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*', name)
                and all(p not in {'.', '..'} for p in Path(name).parts)
                and name != 'manifest.json' and name not in names, 'unsafe or duplicate artifact path')
        path = bundle / name
        require(not any(p.is_symlink() for p in (path, *path.parents) if p != bundle.parent), 'symlink artifact path')
        require(hashlib.sha256(read(path)).hexdigest() == item['sha256'], 'artifact digest mismatch')
        names.add(name)
    actual = {str(p.relative_to(bundle)) for p in bundle.rglob('*') if p.is_file()}
    require(actual == names | {'manifest.json'}, 'unlisted or absent artifact')
    return manifest


def operator_facts(report: dict, *, now: datetime) -> dict:
    require(isinstance(report, dict) and report.get('schema_version') == 'forex.listener-operator-report.v1', 'invalid operator report')
    sources = report.get('sources')
    require(isinstance(sources, dict) and set(sources) == {'status', 'assessment', 'account', 'ledger'}, 'operator sources missing')
    times = {name: _instant(value.get('fetched_at_utc'), 'operator source time') for name, value in sources.items()}
    require(all(timedelta(0) <= now - t < timedelta(hours=24) for t in times.values()), 'operator observation stale or future')
    generated = _instant(report.get('report_generated_at_utc'), 'operator report generation')
    require(max(times.values()) <= generated <= now and generated - max(times.values()) < timedelta(seconds=5),
            'operator report generation is not bound to source acquisition')
    derived = build_report(sources, observed_at=generated)
    for key in ('status', 'decision', 'assessment_join', 'risk', 'account', 'trades', 'attention', 'heartbeat_age_seconds'):
        require(report.get(key) == derived[key], 'operator source/derived fields differ')
    status, account, decision = derived['status'], derived['account'], derived['decision']
    require(account.get('ok') is True and account.get('server') == 'GOMarketsMU-Demo'
            and account.get('currency') == 'AUD' and type(account.get('open_positions')) is int
            and account['open_positions'] >= 0, 'operator account observation unavailable or unsafe')
    require(decision.get('server') == 'GOMarketsMU-Demo' and decision.get('symbol') == 'EURUSD', 'operator decision scope differs')
    binding = status.get('runtime_binding') or {}
    require(binding.get('server') == 'GOMarketsMU-Demo' and binding.get('currency') == 'AUD'
            and binding.get('state') == 'MAPPED' and binding.get('terminal_connected') is True,
            'observed runtime is not the connected Demo terminal')
    require(timedelta(0) <= times['status'] - _instant(binding.get('captured_at_utc'), 'runtime binding time') < timedelta(seconds=30),
            'observed runtime binding is stale/future')
    require(derived['assessment_join'] == 'MATCHED', 'assessment source unavailable or mismatched')
    ledger = sources['ledger'].get('data')
    require(isinstance(ledger, list) and bool(ledger) and all(isinstance(row,dict) and not row.get('error') for row in ledger),
            'ledger source unavailable')
    proposal = decision.get('proposal') or {}
    require(proposal.get('selected_timeframe') == 'M1' and proposal.get('action') in {'BUY', 'SELL', 'NO_TRADE'}
            and isinstance(proposal.get('rationale'), str) and bool(proposal['rationale']), 'operator decision is not explainable')
    heartbeat = _instant(status.get('heartbeat_at_utc'), 'heartbeat')
    require(timedelta(0) <= times['status'] - heartbeat < timedelta(seconds=30), 'heartbeat was stale at observation')
    decision_at = _instant(proposal.get('decision_at_utc'), 'decision time')
    candle_at = _instant(proposal.get('decision_candle_closed_at_utc'), 'closed candle')
    require(candle_at <= decision_at <= times['status'] and times['status'] - candle_at <= timedelta(seconds=120),
            'operator decision/candle stale or future at observation')
    return {'observed_at_utc': max(times.values()).isoformat(), 'heartbeat_at_utc': status['heartbeat_at_utc'],
            'state_at_observation': status.get('state'), 'open_positions_at_observation': account['open_positions'],
            'proposal_id': proposal.get('proposal_id'), 'action': proposal['action'], 'rationale': proposal['rationale'],
            'assessment_join': derived['assessment_join'], 'risk_permission_observed': derived['risk'],
            'recorded_trade_rows': len(derived['trades']), 'current_uptime_claim': False,
            'manual_position_protection_verified': False}


def assess(bundle: Path, root: Path = ROOT) -> dict:
    approvals = _json(read(bundle / 'parent-approvals.json'), 'parent approvals')
    require(set(approvals) == {'M30', 'M31'}, 'parent approvals missing')
    parents = {}
    for key in ('M30', 'M31'):
        parent = bundle / key.lower()
        manifest = hash_inventory(parent)
        record = approvals[key]
        digest = hashlib.sha256(read(parent / 'manifest.json')).hexdigest()
        require(manifest.get('milestone_id') == key and manifest.get('observed_result') == f'FOREX_{key}_PROOF_OK', 'parent identity differs')
        signoff = record.get('human_signoff') or {}
        require(record.get('status') == 'PROVEN' and record.get('proven_at')
                and signoff.get('decision') == 'APPROVE' and signoff.get('inputs_reviewed') is True
                and signoff.get('outputs_reviewed') is True and signoff.get('evidence_manifest_sha256') == digest
                and signoff.get('git_revision') == manifest.get('git_revision')
                and signoff.get('configuration_fingerprint') == manifest.get('configuration_fingerprint'),
                'parent proof/approval does not bind retained manifest')
        parents[key] = {'manifest_sha256': digest, 'git_revision': manifest['git_revision'],
                        'runtime_revision': manifest.get('runtime_revision'), 'proven_at': record['proven_at']}
    m30 = bundle / 'm30'
    audit = check_sources(m30, root, _json(read(m30 / 'topology-authority.json'), 'topology authority'))
    require(audit == _json(read(m30 / 'm30-audit.json'), 'M30 audit'), 'M30 raw audit recomputation differs')
    forward = m31_compute(bundle / 'm31')
    require(forward == _json(read(bundle / 'm31/evaluation.json'), 'M31 evaluation'), 'M31 raw evaluation recomputation differs')
    require(forward['scorecard']['provenance']['configuration_fingerprint'] == audit['configuration_fingerprint']
            and forward['scorecard']['provenance']['application_revision'] == audit['runtime']['runtime_revision'],
            'parent runtime/configuration drift')
    require(timedelta(0) <= datetime.now(timezone.utc) - _instant(forward['scorecard']['interval']['to_utc'], 'M31 observation end') < timedelta(hours=24),
            'M31 observation stale or future')
    trade = load_sources(m30)['lifecycle']
    raw_operator = _json(read(bundle / 'operator-report.json'), 'operator')
    operator = operator_facts(raw_operator, now=datetime.now(timezone.utc))
    require(raw_operator['account'].get('account_scope_sha256') == 'sha256:' + forward['broker_crosscheck']['account_scope_sha256'],
            'operator broker-account scope differs from retained M31 broker observation')
    return {'schema_version': 'forex.m32.demo-quality-assessment.v1', 'parents': parents,
        'configuration_fingerprint': audit['configuration_fingerprint'],
        'runtime_revision': audit['runtime']['runtime_revision'],
        'demonstrated_lifecycle': {key: trade.get(key) for key in ('proposal_id', 'attempt_id', 'action',
            'trade_owner_strategy_id', 'actual_entry_price', 'exit_price', 'volume_lots', 'closed_at_utc',
            'reconciliation_status', 'realized_pnl_account', 'account_currency', 'close_reason',
            'commission_account', 'fee_account', 'swap_account', 'estimated_spread_cost_account', 'slippage_cost_account')},
        'forward_evaluation': {'interval': forward['scorecard']['interval'], 'counts': forward['scorecard']['counts'],
            'limitations': forward['scorecard']['limitations'], 'historical_reference': forward['historical_reference']},
        'operator_observation': operator,
        'demo_quality': 'SUPPORTED_WITH_EXPLICIT_OPERATING_CONDITIONS',
        'operating_conditions': ['Operator remains signed in with the approved Demo MT5 terminal open.',
            'Keep existing single-owner, account, quote, exposure, risk, durable-journal and no-retry gates unchanged.',
            'Use python3 scripts/m20_listener_dashboard.py; --full exposes detailed evidence and missing fields.',
            'Existing/manual positions are not inferred to be flat, protected or owned by the automation.',
            'NO_TRADE is a decision, not a stopped listener; a heartbeat is not permission to enter.'],
        'mvp_required_components': ['approved Demo MT5 terminal', 'protected listener and monitor',
            'PostgreSQL audit bridge and storage', 'existing read-only terminal view'],
        'excluded_from_required_mvp_path': ['new web/Discord UI', 'new orchestration frameworks',
            'multi-account routing', 'strategy optimisation', 'Live execution', 'retired legacy watchdog'],
        'runtime_components_removed_by_m32': [],
        'live_readiness': 'NOT_READY_FOR_LIVE', 'further_live_development': 'NON_EXECUTING_RESEARCH_ONLY_AFTER_SEPARATE_AUTHORISATION',
        'live_gaps': ['No qualified statistical or out-of-sample strategy performance result.',
            'Demo commission/slippage/financing do not establish Live-equivalent costs.',
            'Direct account/manual attribution and unresolved historical ledger rows need later design work.',
            'Interactive terminal availability is operator-dependent; unattended availability is not demonstrated.',
            'Current protection of unrelated operator positions and account-wide P&L are not verified.'],
        'limitations': audit['limitations'] + ['Self-attested retained evidence is not current uptime or future profitability.',
            'Optional components are excluded from the required checklist; no runtime service was removed by this assessment.'],
        'live_trading_enabled': False, 'execution_authority': False, 'profitability_claim': False}


def summary(report: dict) -> str:
    trade, counts, view = report['demonstrated_lifecycle'], report['forward_evaluation']['counts'], report['operator_observation']
    return '\n'.join([MARKER, 'DEMO MVP QUALITY ASSESSMENT — retained evidence, not Live approval',
        f"M30: {trade['action']} entry {trade['actual_entry_price']} -> exit {trade['exit_price']}; reconciliation {trade['reconciliation_status']}.",
        f"M31: {counts['decisions']} decisions, {counts['no_trade']} NO_TRADE, {counts['selected']} selected.",
        f"Operator view at {view['observed_at_utc']}: {view['action']}; broker positions {view['open_positions_at_observation']}.",
        'Conditions:', *report['operating_conditions'], 'Live readiness: NOT_READY_FOR_LIVE',
        'Live gaps:', *report['live_gaps'], 'Limitations:', *report['limitations'],
        'Formal M32 completion still requires independent recommendation and explicit human approval.', ''])


def clean():
    from forex.milestones import material_worktree_changes
    require(not material_worktree_changes(ROOT), 'material worktree must be clean')


def revision():
    return subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()


def verify(bundle: Path) -> dict:
    clean()
    manifest = hash_inventory(bundle)
    require(manifest.get('milestone_id') == 'M32' and manifest.get('schema_version') == '1.0.0'
            and manifest.get('surface') == SURFACE and manifest.get('observed_result') == MARKER
            and manifest.get('summary') == MARKER and manifest.get('dirty_worktree') is False
            and type(manifest.get('exit_code')) is int and manifest['exit_code'] == 0, 'M32 manifest binding differs')
    require(manifest.get('git_revision') == revision(), 'M32 evaluator revision differs')
    require(timedelta(0) <= datetime.now(timezone.utc) - _instant(manifest.get('captured_at'), 'M32 capture') < timedelta(hours=24), 'M32 capture stale/future')
    require({p.name for p in bundle.iterdir()} == LOCAL | {'manifest.json', 'm30', 'm31'}, 'M32 artifact set differs')
    report = assess(bundle)
    require(_instant(report['operator_observation']['observed_at_utc'], 'operator time') <= _instant(manifest['captured_at'], 'capture'),
            'operator observation postdates M32 capture')
    require(report == _json(read(bundle / 'assessment.json'), 'assessment'), 'M32 assessment recomputation differs')
    require(manifest.get('configuration_fingerprint') == report['configuration_fingerprint'] == m20.project_fingerprint(ROOT)
            and manifest.get('runtime_revision') == report['runtime_revision'], 'M32 configuration/runtime differs')
    require(read(bundle / 'summary.txt').decode() == summary(report), 'M32 summary differs')
    operator = _json(read(bundle / 'operator-report.json'), 'operator')
    for name, text in [('operator-60.txt', render_summary(operator,60)), ('operator-100.txt', render_summary(operator,100)),
                       ('operator-full.txt', render_workflow(operator,100))]:
        require(read(bundle / name).decode() == text + '\n', 'operator rendering differs')
    tests = read(bundle / 'tests.txt').decode()
    require(re.search(r'\b[1-9]\d* passed\b', tests) and not re.search(r'\b[1-9]\d* (failed|errors?)\b', tests), 'M32 tests failed')
    require('milestone governance valid' in read(bundle / 'governance.txt').decode(), 'M32 governance failed')
    state = json.loads((ROOT / 'project_state.json').read_text())
    require(state['live_trading_enabled'] is False and state['permitted_mt5_server'] == 'GOMarketsMU-Demo', 'current Demo boundary differs')
    for key in ('M30', 'M31'):
        current = state['milestones'][key]
        require(current['status'] == 'PROVEN' and current['proven_at'] == report['parents'][key]['proven_at']
                and current['evidence'][-1]['manifest_sha256'] == report['parents'][key]['manifest_sha256'], 'parent proof changed')
    return {'marker': MARKER, 'live_readiness': report['live_readiness'], 'execution_authority': False, 'formal_closeout': False}


def capture(args):
    clean()
    require(not args.bundle.exists(), 'refusing to overwrite M32 bundle')
    state = json.loads((ROOT / 'project_state.json').read_text())
    args.bundle.mkdir(parents=True)
    approvals = {}
    for key in ('M30', 'M31'):
        parent = state['milestones'][key]
        manifest = ROOT / parent['evidence'][-1]['manifest_path']
        hash_inventory(manifest.parent)
        require(hashlib.sha256(read(manifest)).hexdigest() == parent['evidence'][-1]['manifest_sha256'], 'recorded parent digest differs')
        shutil.copytree(manifest.parent, args.bundle / key.lower())
        approvals[key] = {k:parent[k] for k in ('status','proven_at','human_signoff')}
    (args.bundle / 'parent-approvals.json').write_text(json.dumps(approvals,indent=2) + '\n')
    (args.bundle / 'operator-report.json').write_bytes(read(args.operator_report))
    report = assess(args.bundle)
    (args.bundle / 'assessment.json').write_text(json.dumps(report,sort_keys=True,indent=2) + '\n')
    (args.bundle / 'summary.txt').write_text(summary(report))
    operator = _json(read(args.bundle / 'operator-report.json'),'operator')
    for name,text in [('operator-60.txt',render_summary(operator,60)),('operator-100.txt',render_summary(operator,100)),('operator-full.txt',render_workflow(operator,100))]:
        (args.bundle / name).write_text(text+'\n')
    for name,argv in [('tests.txt',[sys.executable,'-m','pytest','-o','addopts=','-q',*TESTS]),
                      ('governance.txt',[sys.executable,'scripts/forex_milestones.py','validate'])]:
        result=subprocess.run(argv,cwd=ROOT,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
        (args.bundle / name).write_text(result.stdout)
        require(result.returncode==0,f'{name} failed; partial evidence retained')
    clean()
    manifest={'schema_version':'1.0.0','milestone_id':'M32','captured_at':datetime.now(timezone.utc).isoformat(),
        'git_revision':revision(),'runtime_revision':report['runtime_revision'],'dirty_worktree':False,
        'configuration_fingerprint':report['configuration_fingerprint'],'surface':SURFACE,
        'operation':'offline retained Demo quality assessment','expected_result':'bounded Demo handoff and explicit no-Live readiness assessment',
        'observed_result':MARKER,'exit_code':0,'summary':MARKER,'redactions':['No credentials or broker account login retained; account scope is hashed.'],
        'artifacts':[{'path':str(p.relative_to(args.bundle)),'sha256':hashlib.sha256(read(p)).hexdigest()} for p in sorted(args.bundle.rglob('*')) if p.is_file()]}
    (args.bundle/'manifest.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
    print(json.dumps(verify(args.bundle),sort_keys=True))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['capture','verify'])
    parser.add_argument('--bundle',required=True,type=Path)
    parser.add_argument('--operator-report',type=Path)
    args=parser.parse_args()
    try:
        if args.command=='capture':
            require(args.operator_report is not None,'operator report required')
            capture(args)
        else: print(json.dumps(verify(args.bundle),sort_keys=True))
        return 0
    except (OSError,ValueError,TypeError,KeyError,m20.VerificationError) as error:
        print(f'M32 assessment refused: {error}',file=sys.stderr)
        return 2


if __name__=='__main__':
    raise SystemExit(main())
