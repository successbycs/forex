"""Validate retained natural-entry facts; no broker imports or execution calls."""
from datetime import timedelta
from pathlib import Path
import math
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import m20_demo_evidence_contract as m20
from m30_evidence_contract import owner_hold_seconds
from m30_natural_sources import require, same_value


def validate_trade(joined, *, root, lease, captured):
    """Explicitly map ledger names; never synthesize an executor response.

    The deployed lease supplies the loss limit absent from the session table.
    All-session reservations are a conservative upper bound, not invented
    historical headroom. Historical mutable risk state is not replayed here.
    """
    source, entry, row = joined['source']['assessment'], joined['entry'], joined['lifecycle']
    proposal, snapshot, selection = source['proposal'], source['decision_snapshot'], entry['selection']
    session = dict(entry['session'])
    require(lease.get('session_id') == session.get('session_id')
            and lease.get('server') == session.get('server') == 'GOMarketsMU-Demo'
            and lease.get('symbol') == session.get('instrument') == 'EURUSD', 'deployed lease identity mismatch')
    for stored, deployed in [('max_notional_usd', 'maximum_notional_per_trade_usd'),
                             ('max_cumulative_notional_usd', 'maximum_cumulative_notional_usd'),
                             ('max_open_positions', 'maximum_open_positions'),
                             ('max_trades', 'maximum_trades')]:
        require(stored in session and deployed in lease and session[stored] == lease[deployed],
                f'ledger/deployed lease mismatch: {stored}')
    same_value(session['expires_at_utc'], lease.get('expires_at_utc'), 'expires_at_utc')
    session['max_notional_per_trade_usd'] = session['max_notional_usd']
    session['maximum_loss_per_trade_aud'] = lease.get('maximum_loss_per_trade_aud')
    # These are original records joined as validator arguments, not a claimed
    # raw operation response. No execution/reconciliation fields are invented.
    arguments = {'session': session, 'proposal': proposal, 'decision_snapshot': snapshot,
                 'strategy_selection': selection, 'strategy_assessments': snapshot.get('strategy_assessments')}
    m20.validate_session(arguments)
    m20.validate_snapshot(arguments, session)
    m20.validate_proposal(arguments, session, snapshot)
    m20.validate_strategy_selection(arguments, snapshot, proposal)
    require(proposal['action'] in {'BUY', 'SELL'}, 'natural proof requires actionable proposal')
    totals = entry.get('session_reservations')
    require(isinstance(totals, dict), 'missing all-session reservation totals')
    count = totals.get('attempt_count')
    total = m20.finite_number(totals.get('reserved_notional_usd'), 'session reserved notional', positive=True)
    require(type(count) is int and count >= 1
            and (session['max_trades'] is None or count <= session['max_trades']), 'session trade count cap exceeded')
    require(proposal['notional_usd'] <= total <= session['max_cumulative_notional_usd'],
            'all-session cumulative cap exceeded')
    attempt = entry['attempt']
    m20.string(attempt.get('idempotency_key'), 'attempt idempotency key')
    require(attempt.get('status') in {'SUBMITTED', 'ACCEPTED', 'ACCEPTED_PARTIAL'}, 'unexpected entry reservation status')
    require(row.get('lifecycle') == 'CLOSED_MATCHED' and row.get('reconciliation_status') == 'MATCHED',
            'lifecycle not broker matched')
    from m30_natural_sources import strict_json
    events = strict_json(row.get('events'))
    require(isinstance(events, list) and events.count('OPENED') == events.count('CLOSED') == 1
            and events.index('OPENED') < events.index('CLOSED')
            and not {'REJECTED', 'NOT_SUBMITTED'}.intersection(events), 'lifecycle event ordering mismatch')
    m20.validate_closed_trade(row, session, captured)
    submitted = m20.utc(attempt['submitted_at_utc'], 'submitted')
    require(captured - timedelta(hours=24) <= submitted <= captured, 'entry outside fresh proof interval')
    opening = row['opening_context']
    require(opening.get('retcode') in {10009, 10010}
            and opening.get('fill_status') in {'FULL', 'PARTIAL'}
            and opening.get('symbol') == 'EURUSD' and opening.get('action') == proposal['action'],
            'broker accepted entry context mismatch')
    requested = m20.finite_number(opening.get('broker_requested_volume'), 'requested volume', positive=True)
    filled = m20.finite_number(opening.get('broker_filled_volume'), 'filled volume', positive=True)
    same_value(requested, opening.get('volume'), 'requested volume')
    require(filled <= requested, 'broker fill exceeds requested volume')
    require((opening['retcode'] == 10009 and opening['fill_status'] == 'FULL'
             and math.isclose(filled, requested, rel_tol=0, abs_tol=1e-9))
            or (opening['retcode'] == 10010 and opening['fill_status'] == 'PARTIAL' and filled < requested),
            'broker retcode/fill classification mismatch')
    financing = snapshot.get('financing', {})
    inputs = financing.get('inputs', {})
    require(inputs.get('server') == 'GOMarketsMU-Demo' and inputs.get('symbol') == 'EURUSD'
            and inputs.get('profit_currency') == 'USD', 'contract/conversion surface mismatch')
    contract_size = m20.finite_number(inputs.get('contract_size'), 'contract size', positive=True)
    require(math.isclose(requested * contract_size * proposal['proposed_entry'], proposal['notional_usd'],
                         rel_tol=0, abs_tol=0.011), 'requested volume/notional mismatch')
    audusd_bid = m20.finite_number(inputs.get('audusd_bid'), 'AUDUSD conversion bid', positive=True)
    loss = requested * contract_size * abs(proposal['proposed_entry'] - proposal['stop_loss']) / audusd_bid
    require(loss <= session['maximum_loss_per_trade_aud'], 'theoretical stop loss exceeds AUD cap')
    require(type(opening.get('visible_positions_count')) is int and opening['visible_positions_count'] == 0
            and opening.get('max_open_positions') == 1, 'entry was not flat and one-position bounded')
    for field, original in [('requested_price', 'proposed_entry'), ('broker_requested_price', 'proposed_entry'),
                            ('stop_loss', 'stop_loss'), ('broker_requested_stop_loss', 'stop_loss'),
                            ('take_profit', 'take_profit'), ('broker_requested_take_profit', 'take_profit')]:
        same_value(proposal[original], opening.get(field), field)
    if proposal['action'] == 'BUY':
        require(proposal['stop_loss'] < proposal['proposed_entry'] < proposal['take_profit'], 'BUY protection invalid')
    else:
        require(proposal['take_profit'] < proposal['proposed_entry'] < proposal['stop_loss'], 'SELL protection invalid')
    require(type(opening.get('position_ticket')) is int and opening['position_ticket'] > 0
            and opening['position_ticket'] == row['closing_context'].get('position_ticket')
            and opening.get('position_observation_error') is None, 'position monitoring identity mismatch')
    owner = selection['trade_owner_strategy_id']
    hold = owner_hold_seconds(root, owner)
    closing = row['closing_context']
    reason = row.get('close_reason')
    require(reason == closing.get('close_reason') and reason in {
        'BROKER_SIDE_CLOSE', f'{owner.upper()}_M1_TWO_OPPOSITE_CLOSED_CANDLES',
        f'{owner.upper()}_M1_TIME_STOP_{hold // 60}_MINUTES'}, 'owner close reason mismatch')
    exits = [m20.utc(deal['time_utc'], 'broker exit') for deal in closing['broker_history']['broker_deals']
             if deal['volume'] > 0 and deal['entry'] in {1, 3}]
    require(max(exits) <= submitted + timedelta(seconds=hold), 'broker exit after owner cutoff')
    return {'session': session, 'all_session_reserved_notional_usd': total,
            'all_session_attempt_count': count, 'owner_cutoff_seconds': hold,
            'historical_risk_headroom_replayed': False,
            'protection_evidence': 'accepted broker request and guarded deployed implementation'}
