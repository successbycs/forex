"""Reuse synthetic broker fixtures to exercise natural-ledger validation."""
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent / 'milestones'))
from test_m30 import fixture as lifecycle_fixture
from scripts.m30_natural_lifecycle import validate_trade
from m30_natural_sources import SourceError
from m20_demo_evidence_contract import VerificationError


@pytest.fixture
def natural(tmp_path):
    root, bundle = lifecycle_fixture(tmp_path)
    payload = json.loads(json.loads((bundle / 'demo-trading-operation.json').read_text())['result']['stdout'])
    row = json.loads(json.loads((bundle / 'lifecycle-summary.json').read_text())['result']['stdout'])[0]
    session = dict(payload['session'])
    session['max_notional_usd'] = session.pop('max_notional_per_trade_usd')
    lease = {'session_id': session['session_id'], 'server': session['server'], 'symbol': session['instrument'],
             'expires_at_utc': session['expires_at_utc'], 'maximum_trades': session['max_trades'],
             'maximum_notional_per_trade_usd': session['max_notional_usd'],
             'maximum_cumulative_notional_usd': session['max_cumulative_notional_usd'],
             'maximum_open_positions': 1, 'maximum_loss_per_trade_aud': session.pop('maximum_loss_per_trade_aud')}
    payload['decision_snapshot']['strategy_assessments'] = payload['strategy_assessments']
    proposal = payload['proposal']
    volume = row['opening_context']['broker_filled_volume']
    payload['decision_snapshot']['financing'] = {'inputs': {
        'server': 'GOMarketsMU-Demo', 'symbol': 'EURUSD', 'profit_currency': 'USD',
        'contract_size': proposal['notional_usd'] / volume / proposal['proposed_entry'], 'audusd_bid': 0.7}}
    row['opening_context'].update(retcode=10009, fill_status='FULL', symbol='EURUSD', action='BUY',
                                  volume=volume, broker_requested_volume=volume,
                                  visible_positions_count=0, max_open_positions=1,
                                  requested_price=proposal['proposed_entry'], broker_requested_price=proposal['proposed_entry'],
                                  stop_loss=proposal['stop_loss'], broker_requested_stop_loss=proposal['stop_loss'],
                                  take_profit=proposal['take_profit'], broker_requested_take_profit=proposal['take_profit'])
    joined = {'source': {'assessment': payload}, 'lifecycle': row,
              'entry': {'session': session, 'selection': payload['strategy_selection'],
                        'attempt': payload['execution'],
                        'session_reservations': {'attempt_count': 1, 'reserved_notional_usd': proposal['notional_usd']}}}
    return joined, {'root': root, 'lease': lease,
                    'runtime': {'runtime_revision': row['application_revision']},
                    'fingerprint': row['configuration_fingerprint'],
                    'captured': datetime.now(timezone.utc)}


def test_natural_lifecycle_validates_without_fake_executor_response(natural):
    joined, arguments = natural
    joined['entry']['attempt']['status'] = 'SUBMITTED'
    result = validate_trade(joined, **arguments)
    assert result['historical_risk_headroom_replayed'] is False
    assert result['all_session_attempt_count'] == 1
    assert result['session_provenance']['target_runtime_revision'] == joined['lifecycle']['application_revision']


@pytest.mark.parametrize('change', [
    lambda x: x['entry'].pop('session_reservations'),
    lambda x: x['entry']['session_reservations'].update(reserved_notional_usd=100001),
    lambda x: x['entry']['session_reservations'].update(attempt_count=True),
    lambda x: x['lifecycle']['opening_context'].update(visible_positions_count=1),
    lambda x: x['lifecycle']['opening_context'].update(broker_requested_stop_loss=0),
    lambda x: x['lifecycle']['opening_context'].update(retcode=10006),
    lambda x: x['lifecycle'].update(reconciliation_status='UNRESOLVED'),
    lambda x: x['lifecycle'].update(events='["CLOSED","OPENED"]'),
    lambda x: x['entry']['attempt'].update(idempotency_key=None),
    lambda x: x['lifecycle']['opening_context'].update(broker_requested_volume=0.000001),
    lambda x: x['lifecycle']['opening_context'].update(position_ticket=None),
    lambda x: x['lifecycle'].update(events='["OPENED","REJECTED","CLOSED"]'),
    lambda x: x['lifecycle']['opening_context'].update(retcode=10010),
])
def test_natural_entry_controls_fail_closed(natural, change):
    joined, arguments = natural
    change(joined)
    with pytest.raises((SourceError, VerificationError)):
        validate_trade(joined, **arguments)
