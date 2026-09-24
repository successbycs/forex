from scripts.m33_daily_pnl_report import render
from scripts.m33_daily_pnl_web import render_html


def _report():
    return {"date":"2026-09-23","currency":"AUD","status":"AVAILABLE","unavailable_reason":None,"deal_count":2,
      "opening_balance_aud":100989.45,"broker_balance_change_aud":-30.50,"closing_balance_aud":100958.95,
      "daily_trade_pnl_aud":-30.50,"expected_live_commission_aud_total":-0.12,"commission_adjusted_net_aud_total":-30.62,
      "rows":[
        {"occurred_at_utc":"2026-09-23T09:52:44Z","broker_time_utc":"2026-09-23T21:52:44Z","deal_ticket":1,"event_kind":"OPEN","side":"BUY","volume_lots":.02,"price":1.1,"broker_commission_aud":0,"expected_live_commission_aud":-.06,"broker_fee_aud":0,"broker_swap_aud":0,"trade_pnl_aud":0,"trade_result_aud":0,"net_movement_aud":0,"commission_adjusted_net_aud":-.06,"balance_before_aud":100989.45,"balance_after_aud":100989.45,"position_identifier":2,"source_deal_sha256":"sha256:"+'a'*64,"collection_version":"forex.m33.broker-pnl-journal.v1"},
        {"occurred_at_utc":"2026-09-23T16:59:40Z","broker_time_utc":"2026-09-24T04:59:40Z","deal_ticket":3,"event_kind":"CLOSE","side":"SELL","volume_lots":.02,"price":1.1,"broker_commission_aud":0,"expected_live_commission_aud":-.06,"broker_fee_aud":0,"broker_swap_aud":0,"trade_pnl_aud":-30.5,"trade_result_aud":-30.5,"net_movement_aud":-30.5,"commission_adjusted_net_aud":-30.56,"balance_before_aud":100989.45,"balance_after_aud":100958.95,"position_identifier":2,"source_deal_sha256":"sha256:"+'b'*64,"collection_version":"forex.m33.broker-pnl-journal.v1"}]}


def test_daily_report_renders_broker_line_items_and_balance_bridge():
    output=render(_report())
    assert 'OPEN | BUY | 0.02' in output and 'CLOSE | SELL | 0.02' in output
    assert 'Expected Live commission |' in output
    assert 'Balance at start of day: +100989.45 AUD' in output
    assert 'Total broker balance change during day: -30.50 AUD' in output
    assert 'Balance at end of day: +100958.95 AUD' in output


def test_web_renders_same_recorded_journal_facts():
    page=render_html(_report())
    for text in ('2026-09-23','OPEN','CLOSE','BUY','SELL','100989.45','100958.95','Expected Live commission'):
        assert text in page
    assert 'ASSUMED GO Plus+ AUD' in page


def test_times_are_auckland_local_and_follow_daylight_saving():
    from scripts.m33_daily_pnl_report import local_time
    assert local_time('2026-09-23T04:59:40Z')=='2026-09-23 16:59:40 NZST'
    assert local_time('2026-09-30T04:59:40+00:00')=='2026-09-30 17:59:40 NZDT'
    report=_report()
    assert '2026-09-23 21:52:44 NZST' in render(report)
    assert '2026-09-23 21:52:44 NZST' in render_html(report)


def test_total_trading_pnl_is_visible_in_both_operator_surfaces():
    report={**_report(),'total_trade_pnl_aud':-45.67,'total_commission_adjusted_trade_pnl_aud':-46.89}
    for output in (render(report),render_html(report)):
        assert '-45.67 AUD' in output and '-46.89 AUD' in output


def test_funding_is_a_balance_movement_and_not_trading_profit():
    report=_report()
    funding={**report['rows'][0], 'event_kind':'BALANCE', 'side':None,
             'volume_lots':0, 'trade_pnl_aud':1000, 'trade_result_aud':0,
             'expected_live_commission_aud':0, 'net_movement_aud':1000,
             'commission_adjusted_net_aud':1000}
    report['rows'].insert(0,funding)
    report['broker_balance_change_aud']=969.50
    output=render(report)
    funding_line=next(line for line in output.splitlines() if ' | BALANCE | ' in line)
    assert funding_line.split(' | ')[8:]==['+0.00 AUD','+1000.00 AUD','+1000.00 AUD']
    assert 'Daily trading P&L: -30.50 AUD' in output
    assert 'Commission-adjusted P&L: -30.62 AUD' in output
    page=render_html(report)
    assert 'Daily trading P&amp;L: -30.50 AUD' in page
    assert 'commission-adjusted P&amp;L: -30.62 AUD' in page
    assert '<td>+0.00 AUD</td><td>+1000.00 AUD</td><td>+1000.00 AUD</td>' in page
