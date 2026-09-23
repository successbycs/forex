"""Offline, fail-closed checks for the final Demo assessment."""
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import m32_quality_assessment as m32
from forex.m31_scorecard import M31ScorecardInputError
from scripts.listener_workflow_report import build_report, render_summary


def operator_report():
    now = datetime.now(timezone.utc).replace(microsecond=0)
    observed = now - timedelta(seconds=2)
    proposal = {'proposal_id':'p','selected_timeframe':'M1','action':'NO_TRADE',
                'rationale':'No selected actionable M1 strategy.', 'decision_at_utc':observed.isoformat(),
                'decision_candle_closed_at_utc':(observed-timedelta(seconds=60)).isoformat()}
    data = {'status': {'state':'RUNNING','heartbeat_at_utc':observed.isoformat(),
                      'last_result':{'proposal':proposal,'server':'GOMarketsMU-Demo','symbol':'EURUSD'},
                      'runtime_binding':{'server':'GOMarketsMU-Demo','currency':'AUD','state':'MAPPED',
                          'terminal_connected':True,'captured_at_utc':observed.isoformat()}},
            'assessment': {'observation':'AVAILABLE','assessment':{'proposal':proposal}},
            'account': {'ok':True,'server':'GOMarketsMU-Demo','currency':'AUD','open_positions':4},
            'ledger': [{'lifecycle':'CLOSED_MATCHED','realized_pnl_account':0.1,'account_currency':'AUD'}]}
    return build_report({k:{'data':v,'fetched_at_utc':now.isoformat()} for k,v in data.items()}, observed_at=now), now


def test_operator_snapshot_is_not_current_uptime_or_flatness_claim():
    report, now = operator_report()
    facts = m32.operator_facts(report,now=now)
    assert facts['open_positions_at_observation'] == 4
    assert facts['current_uptime_claim'] is False
    assert facts['manual_position_protection_verified'] is False
    assert facts['risk_permission_observed'] is None
    text = render_summary(report,60)
    assert 'Open positions: 4' in text and 'Reason: No selected actionable M1 strategy.' in text


@pytest.mark.parametrize('change',['live','future','stale','missing_source','derived_drift','old_heartbeat','missing_reason','false_flatness',
                                'forged_age','forged_warnings','live_runtime','missing_ledger','missing_assessment','old_decision'])
def test_operator_snapshot_refuses_missing_or_unsafe_facts(change):
    report, now = operator_report()
    if change == 'live': report['sources']['account']['data']['server']='GOMarketsMU-Live'
    elif change == 'future': report['sources']['status']['fetched_at_utc']=(now+timedelta(seconds=5)).isoformat()
    elif change == 'stale': now += timedelta(days=2)
    elif change == 'missing_source': report['sources'].pop('ledger')
    elif change == 'derived_drift': report['decision']={}
    elif change == 'old_heartbeat': report['status']['heartbeat_at_utc']=(now-timedelta(minutes=5)).isoformat()
    elif change == 'missing_reason': report['decision']['proposal']['rationale']=''
    elif change == 'false_flatness': report['account']=dict(report['account'],open_positions=0)
    elif change == 'forged_age': report['heartbeat_age_seconds']=-999
    elif change == 'forged_warnings': report['attention']=['invented warning']
    elif change in ('live_runtime','missing_ledger','missing_assessment','old_decision'):
        if change == 'live_runtime': report['sources']['status']['data']['runtime_binding']['server']='GOMarketsMU-Live'
        elif change == 'missing_ledger': report['sources']['ledger']['data']={'error':'unavailable'}
        elif change == 'missing_assessment': report['sources']['assessment']['data']={'error':'unavailable'}
        elif change == 'old_decision': report['sources']['status']['data']['last_result']['proposal']['decision_at_utc']='2020-01-01T00:00:00Z'
        report=build_report(report['sources'], observed_at=now)
    with pytest.raises(M31ScorecardInputError): m32.operator_facts(report,now=now)


def inventory(tmp_path):
    (tmp_path/'source.json').write_text('{"raw":true}')
    manifest={'artifacts':[{'path':'source.json','sha256':hashlib.sha256((tmp_path/'source.json').read_bytes()).hexdigest()}]}
    (tmp_path/'manifest.json').write_text(json.dumps(manifest))
    return manifest


@pytest.mark.parametrize('change',['digest','duplicate','traversal','extra','symlink','missing'])
def test_source_inventory_rejects_mutation_or_unsafe_paths(tmp_path,change):
    manifest=inventory(tmp_path)
    assert m32.hash_inventory(tmp_path)==manifest
    if change=='digest': (tmp_path/'source.json').write_text('{}')
    elif change=='duplicate': manifest['artifacts'].append(manifest['artifacts'][0])
    elif change=='traversal': manifest['artifacts'][0]['path']='../source.json'
    elif change=='extra': (tmp_path/'unlisted.json').write_text('{}')
    elif change=='symlink':
        (tmp_path/'source.json').rename(tmp_path/'target.json')
        (tmp_path/'source.json').symlink_to(tmp_path/'target.json')
    elif change=='missing': (tmp_path/'source.json').unlink()
    (tmp_path/'manifest.json').write_text(json.dumps(manifest))
    with pytest.raises(M31ScorecardInputError): m32.hash_inventory(tmp_path)


def test_parent_approval_cannot_be_omitted(tmp_path):
    (tmp_path/'parent-approvals.json').write_text('{}')
    with pytest.raises(M31ScorecardInputError,match='parent approvals'):
        m32.assess(tmp_path)


def test_m32_review_fingerprint_binds_actual_assessor_dependencies():
    from forex.triad import _verifier_paths
    registry=json.loads((ROOT/'milestone_registry.json').read_text())
    contract=next(m for m in registry['milestones'] if m['milestone_id']=='M32')
    paths=set(_verifier_paths(ROOT,contract))
    assert {'scripts/m32_quality_assessment.py','scripts/m30_natural_sources.py',
            'scripts/m30_natural_lifecycle.py','scripts/m30_natural_runtime.py',
            'scripts/m31_retained_evidence.py','scripts/listener_workflow_report.py',
            'src/forex/m31_supplement.py'} <= paths
