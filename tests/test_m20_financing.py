"""Behavioural financing tests; synthetic fixtures are not broker proof."""
import importlib.util
import json
import sys
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path
import pytest

@pytest.fixture
def runner(monkeypatch):
    monkeypatch.setitem(sys.modules, 'MetaTrader5', types.SimpleNamespace(TIMEFRAME_M1=1,TIMEFRAME_M5=5,TIMEFRAME_H1=60))
    spec=importlib.util.spec_from_file_location('financing_runner',Path('t480/m20_demo_trading_session.py'))
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod

@pytest.fixture
def inputs():
    now=datetime(2026,9,10,0,0,tzinfo=timezone.utc)
    terms=dict(captured_at_utc=now.isoformat(),conversion_at_utc=now.isoformat(),server='GOMarketsMU-Demo',symbol='EURUSD',profit_currency='USD',swap_mode=1,swap_long=-5.91,swap_short=2.3,point=.00001,contract_size=100000,audusd_bid=.72,audusd_ask=.721)
    policy=dict(policy_version='forex.m20.financing.v1',maximum_quote_age_seconds=10,calendar_valid_from_utc=(now-timedelta(days=1)).isoformat(),calendar_valid_until_utc=(now+timedelta(days=1)).isoformat(),calendar_source='synthetic-test-calendar',charge_source='synthetic-test-fees',round_trip_charge_aud_per_lot=5,rollovers=[dict(at_utc=(now+timedelta(minutes=1)).isoformat(),multiplier=1)])
    return dict(terms=terms,policy=policy,now=now,horizon=now+timedelta(minutes=10),volume=.01,action='BUY')

def test_debit_credit_triple_and_risk(runner,inputs):
    buy=runner.project_financing(**inputs);assert buy['expected_swap_aud']==pytest.approx(-.0591/.72)
    assert buy['commission_allowance_aud']==.05
    inputs['action']='SELL';sell=runner.project_financing(**inputs)
    assert sell['expected_swap_aud']==pytest.approx(.023/.721)
    assert sell['adverse_financing_aud']==0
    inputs['policy']['rollovers'][0]['multiplier']=3
    assert runner.project_financing(**inputs)['expected_swap_aud']==pytest.approx(3*sell['expected_swap_aud'])
    risk=dict(tick_size=.00001,tick_value_loss=1.4,volume=.01,observed_spread=0,financing=buy)
    assert runner._planned_stop_loss(1.1,1.0999,risk)==pytest.approx(.14+.05+.0591/.72)

@pytest.mark.parametrize('mutation', ['mode','stale','future','commission','calendar','duplicate','nan','currency','crossed'])
def test_unknown_inputs_refuse(runner,inputs,mutation):
    if mutation=='mode':inputs['terms']['swap_mode']=5
    if mutation=='stale':inputs['now']+=timedelta(seconds=11)
    if mutation=='future':inputs['terms']['captured_at_utc']=(inputs['now']+timedelta(seconds=1)).isoformat()
    if mutation=='commission':inputs['policy']['round_trip_charge_aud_per_lot']=None
    if mutation=='calendar':inputs['policy']['calendar_valid_until_utc']=None
    if mutation=='duplicate':inputs['policy']['rollovers']*=2
    if mutation=='nan':inputs['terms']['swap_long']=float('nan')
    if mutation=='currency':inputs['terms']['profit_currency']='EUR'
    if mutation=='crossed':inputs['terms']['audusd_ask']=.70
    result=runner.project_financing(**inputs);assert result['status']=='UNKNOWN';assert result['expected_swap_aud'] is None

def test_no_rollover_in_known_window_and_boundary(runner,inputs):
    inputs['horizon']=inputs['now']+timedelta(seconds=30)
    assert runner.project_financing(**inputs)['expected_swap_aud']==0
    inputs['horizon']=inputs['now']+timedelta(minutes=1)
    assert runner.project_financing(**inputs)['expected_swap_aud']<0

def test_uncertainty_and_risk_have_no_order_authority(runner,inputs):
    f=runner.project_financing(**inputs)
    args=dict(financing=f,forecast_lower_bound_aud=.10,benefit_buffer_aud=.05,forecast_qualified=True,risk_allowed=True)
    assert runner.review_holding(**args)['decision']=='CLOSE'
    args['forecast_lower_bound_aud']=.30
    assert runner.review_holding(**args)['decision']=='HOLD'
    assert runner.review_holding(**args)['execution_authority'] is False
    args['risk_allowed']=False;assert runner.review_holding(**args)['decision']=='CLOSE'
    args['forecast_qualified']=False;assert runner.review_holding(**args)['decision']=='REVIEW_REQUIRED'

def test_cost_projection_does_not_use_missing_fees_or_credit_to_expand_risk(runner,inputs):
    risk=dict(volume=.01,tick_size=.00001,tick_value_loss=1.4,observed_spread=.00008)
    kwargs=dict(action='BUY',entry=1.1,take_profit=1.101,risk=risk)
    assert runner._project_cost_coverage(**kwargs)['cost_coverage_status']=='NOT_FEASIBLE'
    risk['financing']=runner.project_financing(**inputs)
    with_debit=runner._project_cost_coverage(**kwargs)
    inputs['action']='SELL';risk['financing']=runner.project_financing(**inputs)
    with_credit=runner._project_cost_coverage(**kwargs)
    assert with_credit['expected_net_profit_at_take_profit_aud']>with_debit['expected_net_profit_at_take_profit_aud']
    assert with_credit['expected_swap_aud']>0

def test_assessment_records_and_refuses_missing_financing(runner,monkeypatch):
    now=datetime(2026,9,10,tzinfo=timezone.utc)
    monkeypatch.setattr(runner,'_strategy_assessments',lambda **kw:[dict(id='momentum_breakout',signal='BUY')])
    monkeypatch.setattr(runner,'_market_selection',lambda **kw:dict(selected_strategy_id='momentum_breakout',selection_status='SELECTED_EXECUTABLE',market_regime='MOMENTUM_BREAKOUT'))
    session=dict(session_id='test',maximum_loss_per_trade_aud=100,expires_at_utc=(now+timedelta(hours=1)).isoformat())
    tick=dict(observed_at_utc=now.isoformat(),bid=1.1,ask=1.1001,spread_points=10,freshness_seconds=0)
    snapshot,proposal,selection,_=runner._assessment(session,tick,dict(M1=[],M5=[]),now,dict(volume=.01,tick_size=.00001,tick_value_loss=1.4,point=.00001),.25)
    assert proposal['action']=='NO_TRADE'
    assert proposal['rationale'].startswith('FINANCING_UNQUALIFIED')
    assert snapshot['holding_review']['decision']=='REVIEW_REQUIRED'
    assert snapshot['financing']['status']=='UNKNOWN'

@pytest.mark.parametrize('stamp,allowed', [
    ('2026-09-10T05:59:00+00:00', False),
    ('2026-09-10T06:00:00+00:00', True),
    ('2026-09-10T17:49:59+00:00', True),
    ('2026-09-10T17:50:00+00:00', False),
    ('2026-09-11T12:00:00+00:00', True),
    ('2026-09-12T12:00:00+00:00', False),
    ('2026-09-13T12:00:00+00:00', False),
])
def test_demo_estimate_window_and_provenance(runner, inputs, stamp, allowed):
    now = datetime.fromisoformat(stamp)
    inputs.update(now=now, horizon=now+timedelta(minutes=10))
    inputs['terms'].update(captured_at_utc=stamp, conversion_at_utc=stamp)
    inputs['policy'].update(qualification_basis='DEMO_CONSERVATIVE_INTRADAY',
        entry_start_hour_utc=6, exit_by_hour_utc=18, round_trip_charge_aud_per_lot=6,
        calendar_valid_until_utc='2026-09-17T00:00:00Z', rollovers=[])
    result = runner.project_financing(**inputs)
    assert result['status'] == ('DEMO_ESTIMATE' if allowed else 'UNKNOWN')
    if allowed:
        assert result['commission_allowance_aud'] == pytest.approx(.06)
        assert result['expected_swap_aud'] == 0
        assert runner.review_holding(financing=result, forecast_qualified=True,
            forecast_lower_bound_aud=100, benefit_buffer_aud=0,
            risk_allowed=True)['decision'] == 'REVIEW_REQUIRED'

@pytest.mark.parametrize('change', ['expired', 'stale', 'missing_fee', 'cheap_fee', 'wider_hours', 'long_hold', 'unknown_basis'])
def test_demo_estimate_never_waives_missing_inputs(runner, inputs, change):
    now = inputs['now'] + timedelta(hours=12)
    inputs.update(now=now, horizon=now+timedelta(minutes=10))
    inputs['terms'].update(captured_at_utc=now.isoformat(), conversion_at_utc=now.isoformat())
    inputs['policy'].update(qualification_basis='DEMO_CONSERVATIVE_INTRADAY',
        entry_start_hour_utc=6, exit_by_hour_utc=18, round_trip_charge_aud_per_lot=6)
    if change == 'expired': inputs['policy']['calendar_valid_until_utc'] = now.isoformat()
    if change == 'stale': inputs['terms']['conversion_at_utc'] = (now-timedelta(seconds=11)).isoformat()
    if change == 'missing_fee': inputs['policy']['round_trip_charge_aud_per_lot'] = None
    if change == 'cheap_fee': inputs['policy']['round_trip_charge_aud_per_lot'] = 0
    if change == 'wider_hours': inputs['policy']['exit_by_hour_utc'] = 23
    if change == 'long_hold': inputs['horizon'] += timedelta(seconds=1)
    if change == 'unknown_basis': inputs['policy']['qualification_basis'] = 'GUESS'
    assert runner.project_financing(**inputs)['status'] == 'UNKNOWN'


def test_demo_financing_deferral_removes_calendar_and_hour_veto_without_assuming_costs(runner, inputs):
    """The later Live policy cannot silently become a Demo calendar veto."""
    now = datetime(2026, 9, 13, 23, 55, tzinfo=timezone.utc)  # Sunday, outside the old window.
    inputs.update(now=now, horizon=now + timedelta(minutes=10), terms={})
    inputs['policy'] = {
        'policy_version': 'forex.m20.financing.v2',
        'qualification_basis': 'DEFERRED_FOR_DEMO',
        'exit_mode': 'EXISTING_OWNER_EXITS',
        'maximum_quote_age_seconds': 10,
        'calendar_valid_from_utc': None,
        'calendar_valid_until_utc': None,
        'calendar_source': None,
        'rollovers': [],
        'round_trip_charge_aud_per_lot': None,
        'charge_source': None,
    }
    result = runner.project_financing(**inputs)
    assert result['status'] == 'DEFERRED_FOR_DEMO'
    assert result['reason'] == 'FINANCING_POLICY_DEFERRED_FOR_DEMO'
    assert result['expected_swap_aud'] == result['commission_allowance_aud'] == result['adverse_financing_aud'] == 0.0
    coverage = runner._project_cost_coverage(
        action='BUY', entry=1.1, take_profit=1.101,
        risk={'volume': .01, 'tick_size': .00001, 'tick_value_loss': 1.4, 'observed_spread': .00002, 'financing': result},
    )
    assert coverage['cost_coverage_status'] == 'FEASIBLE'
