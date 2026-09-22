"""Synthetic source-join controls; these fixtures are never real-world proof."""
import base64
from copy import deepcopy
import hashlib
import json
from uuid import NAMESPACE_URL, uuid5

import pytest

from scripts.m30_natural_sources import SourceError, load_sources, strict_json


def digest(value):
    return 'sha256:' + hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def output(operation, payload):
    return {'ok': True, 'operation': operation, 'tool_id': ('forex_t480' if operation == 'm20_listener_spool_page' else 'forex_postgres_pgvector_t480'),
            'result': {'ok': True, 'exit_code': 0, 'stdout': json.dumps(payload)}}


@pytest.fixture
def capture(tmp_path):
    context = {field: 0.1 for field in ('estimated_round_trip_cost_aud', 'minimum_net_profit_aud',
               'expected_net_profit_at_take_profit_aud', 'entry_spread_cost_aud',
               'expected_exit_spread_cost_aud', 'commission_allowance_aud', 'slippage_allowance_aud',
               'expected_swap_aud', 'projected_gross_profit_at_take_profit_aud')}
    context.update(market_regime='TREND_PULLBACK', market_regime_reason='test',
                   selected_strategy_id='trend_pullback', selection_status='SELECTED_EXECUTABLE',
                   strategy_rule_version='test', cost_coverage_status='FEASIBLE')
    snapshot = {'captured_at_utc': '2026-09-22T06:18:07Z', 'bid': 1.14622, 'market_context': context}
    sha = digest(snapshot)
    snapshot.update(payload_sha256=sha, snapshot_id=str(uuid5(NAMESPACE_URL, f'proposal:{sha}')))
    proposal = {'proposal_id': 'proposal', 'session_id': 'session',
                'snapshot_id': snapshot['snapshot_id'], 'decision_snapshot_sha256': sha,
                'decision_at_utc': '2026-09-22T06:18:07Z', 'expires_at_utc': '2026-09-22T06:23:07Z',
                'action': 'SELL', 'stop_loss': 1.1465100000000001,
                'proposed_entry': 1.14622, 'take_profit': 1.14578, 'notional_usd': 1146.22,
                'confidence': 70, 'rationale': 'synthetic', 'selected_timeframe': 'M1',
                'strategy_version': 'test', 'decision_key': 'test',
                'decision_candle_closed_at_utc': '2026-09-22T06:18:00Z'}
    record = {'listener_release_id': '0123456789abcdef', 'assessment_sequence': 1,
              'assessment': {'server': 'GOMarketsMU-Demo', 'symbol': 'EURUSD',
                             'configuration_fingerprint': 'config',
                             'proposal': proposal, 'decision_snapshot': snapshot}}
    data = json.dumps(record).encode()
    page = {'after_assessment_sequence': 0, 'listener_release_id': record['listener_release_id'],
            'observation': 'AVAILABLE', 'records': [{'assessment_sequence': 1,
            'raw_sha256': 'sha256:' + hashlib.sha256(data).hexdigest(),
            'raw_base64': base64.b64encode(data).decode()}]}
    persisted = {k: v for k, v in proposal.items() if k != 'snapshot_id'}
    persisted.update(application_revision='revision', configuration_fingerprint='config', stop_loss=1.14651)
    attempt = {'attempt_id': 'attempt', 'proposal_id': 'proposal', 'session_id': 'session',
               'submitted_at_utc': '2026-09-22T06:18:07+00:00'}
    selection = {**context, 'proposal_id': 'proposal', 'trade_owner_id': 'proposal',
                 'selected_strategy_id': 'trend_pullback', 'trade_owner_strategy_id': 'trend_pullback'}
    lifecycle = {**proposal, **attempt, 'application_revision': 'revision',
                 'snapshot_payload_sha256': sha, 'snapshot_captured_at_utc': snapshot['captured_at_utc'],
                 'configuration_fingerprint': 'config', 'proposal_expires_at_utc': proposal['expires_at_utc'],
                 **selection}
    files = {'spool-page-0000.json': output('m20_listener_spool_page', page),
             'lifecycle-summary.json': output('forex_m20_lifecycle_summary', [lifecycle]),
             'natural-entry-facts.json': output('forex_m30_natural_entry_facts', [
                 {'proposal': persisted, 'attempt': attempt, 'session': {'session_id': 'session'},
                  'selection': selection}]),
             **{name: {} for name in ('listener-diagnostics.json', 'listener-status.json',
                                      'terminal-identity.json', 'watchdog-status.json')}}
    receipt = {'schema_version': 'forex.m30.natural-raw-capture.v1',
               'proof_status': 'UNVERIFIED_RAW_CAPTURE', 'execution_authority': False,
               'proposal_id': 'proposal', 'attempt_id': 'attempt', 'application_revision': 'revision',
               'source_match': {'page': 'spool-page-0000.json', 'assessment_sequence': 1,
                                'raw_sha256': page['records'][0]['raw_sha256']}}

    def write():
        # Synthetic fixture generation only; no operational evidence is edited.
        for name, value in files.items():
            (tmp_path / name).write_text(json.dumps(value))
        receipt['artifacts'] = [{'path': name, 'sha256': hashlib.sha256((tmp_path / name).read_bytes()).hexdigest()}
                                for name in files]
        (tmp_path / 'raw-capture-receipt.json').write_text(json.dumps(receipt))
        return tmp_path
    return files, receipt, write


def mutate_output(files, name, mutate):
    payload = json.loads(files[name]['result']['stdout'])
    mutate(payload)
    files[name]['result']['stdout'] = json.dumps(payload)


def test_exact_source_join_and_db_float_rounding(capture):
    _, _, write = capture
    result = load_sources(write())
    assert result['entry']['proposal']['stop_loss'] == 1.14651
    assert result['source']['assessment']['proposal']['stop_loss'] == 1.1465100000000001


@pytest.mark.parametrize('field,value', [('attempt_id', 'other'), ('session_id', 'other'),
                                      ('application_revision', 'other'), ('configuration_fingerprint', 'other'),
                                      ('snapshot_id', 'other'), ('action', 'BUY')])
def test_rehashed_wrong_lifecycle_cannot_join(capture, field, value):
    files, _, write = capture
    mutate_output(files, 'lifecycle-summary.json', lambda rows: rows[0].update({field: value}))
    with pytest.raises(SourceError):
        load_sources(write())


def test_duplicate_attempt_rejected(capture):
    files, _, write = capture
    mutate_output(files, 'natural-entry-facts.json', lambda rows: rows.append(deepcopy(rows[0])))
    with pytest.raises(SourceError, match='ambiguous'):
        load_sources(write())


def test_changed_raw_bytes_rejected(capture):
    _, _, write = capture
    path = write()
    with (path / 'lifecycle-summary.json').open('a') as stream:
        stream.write(' ')
    with pytest.raises(SourceError, match='digest mismatch'):
        load_sources(path)


def test_artifact_traversal_rejected(capture):
    _, _, write = capture
    path = write()
    receipt = json.loads((path / 'raw-capture-receipt.json').read_text())
    receipt['artifacts'][0]['path'] = '../outside'
    (path / 'raw-capture-receipt.json').write_text(json.dumps(receipt))
    with pytest.raises(SourceError, match='unsafe'):
        load_sources(path)


@pytest.mark.parametrize('raw', ['{"a":1,"a":2}', '{"a":NaN}', '{"a":Infinity}'])
def test_ambiguous_json_rejected(raw):
    with pytest.raises(SourceError):
        strict_json(raw)


def test_wrong_source_sequence_rejected(capture):
    _, receipt, write = capture
    receipt['source_match']['assessment_sequence'] = 2
    with pytest.raises(SourceError, match='source proposal'):
        load_sources(write())


@pytest.mark.parametrize('field,value', [('snapshot_payload_sha256', 'wrong'),
    ('snapshot_captured_at_utc', '2026-09-22T06:18:08Z'), ('stop_loss', 1.15), ('take_profit', True)])
def test_additional_lifecycle_joins(capture, field, value):
    files, _, write = capture
    mutate_output(files, 'lifecycle-summary.json', lambda rows: rows[0].update({field: value}))
    with pytest.raises(SourceError):
        load_sources(write())


@pytest.mark.parametrize('field,value', [('market_regime', 'OTHER'), ('estimated_round_trip_cost_aud', 2),
                                      ('selection_status', 'NO_SELECTION')])
def test_selection_context_mismatch(capture, field, value):
    files, _, write = capture
    mutate_output(files, 'natural-entry-facts.json', lambda rows: rows[0]['selection'].update({field: value}))
    with pytest.raises(SourceError):
        load_sources(write())


def test_wrong_spool_adapter(capture):
    files, _, write = capture
    files['spool-page-0000.json']['tool_id'] = 'other'
    with pytest.raises(SourceError, match='adapter identity'):
        load_sources(write())
