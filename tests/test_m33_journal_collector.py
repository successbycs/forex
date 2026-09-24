"""The journal must never combine changing history with an old balance."""
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace
import pytest


def collector(monkeypatch, tmp_path):
    raw = dict(ticket=1, order=0, position_id=0, time=1750000000,
               time_msc=1750000000123, entry=0, type=2, volume=0,
               price=0, commission=0, fee=0, swap=0, profit=1000,
               reason=0, symbol='', comment='funding')
    row = SimpleNamespace(_asdict=lambda: dict(raw))
    account = SimpleNamespace(login=1, server='GOMarketsMU-Demo', currency='AUD', balance=1000)
    mt5 = SimpleNamespace(TIMEFRAME_M1=1,TIMEFRAME_M5=5,TIMEFRAME_H1=60,
        account_info=lambda: account, history_deals_get=lambda *_: [row],
        initialize=lambda **_: True, shutdown=lambda: None)
    monkeypatch.setitem(sys.modules,'MetaTrader5',mt5)
    monkeypatch.setenv('FOREX_M20_ACCOUNT_EXECUTION_PROFILE',json.dumps(dict(
        profile_id='M1_EURUSD_DEMO',server=account.server,currency='AUD',symbol='EURUSD',
        account_scope_sha256='sha256:'+hashlib.sha256(b'GOMarketsMU-Demo:1').hexdigest())))
    spec=importlib.util.spec_from_file_location('m33_collector',Path(__file__).resolve().parents[1]/'t480/m20_demo_trading_session.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    monkeypatch.setattr(module,'tick_time_offset_seconds',lambda:10800)
    monkeypatch.setattr(module, '_journal_cache_path', lambda: tmp_path/'receipt.json')
    sent=[]
    monkeypatch.setattr(module,'_bridge',lambda payload,command: sent.append((payload,command)) or {'ok':True})
    return module,mt5,row,account,sent


def test_retains_full_raw_source_and_milliseconds(monkeypatch, tmp_path):
    module,mt5,row,account,sent=collector(monkeypatch, tmp_path)
    assert module.collect_broker_pnl_journal('fixed-terminal')['ok']
    capture=sent[0][0]['capture']
    assert capture['raw_deals']==[row._asdict()]
    assert capture['deals'][0]['broker_time_utc'].endswith('40.123000Z')
    assert capture['account_balance_before_aud']==capture['account_balance_aud']==1000
    assert sent[0][1]=='record-broker-pnl-capture'


@pytest.mark.parametrize('change',['balance','history','missing','bound'])
def test_rejects_unstable_or_unavailable_receipt(monkeypatch, tmp_path, change):
    module,mt5,row,account,sent=collector(monkeypatch, tmp_path)
    accounts=iter([account,SimpleNamespace(**{**vars(account),'balance':999})])
    histories=iter([[row],[]])
    if change=='balance': mt5.account_info=lambda:next(accounts)
    elif change=='history': mt5.history_deals_get=lambda *_:next(histories)
    elif change=='missing': mt5.history_deals_get=lambda *_:None
    else: mt5.history_deals_get=lambda *_:[row]*10001
    shutdown=[];mt5.shutdown=lambda:shutdown.append(True)
    with pytest.raises(SystemExit):module.collect_broker_pnl_journal('fixed-terminal')
    assert not sent
    assert shutdown==[True]


def test_collection_operation_is_bound_and_has_no_listener_start():
    from scripts import t480_adapter as adapter
    from t480_core import build_ssh_command
    for name in ('m33_broker_pnl_collect','m20_listener_diagnostics'):
        command=adapter.OPERATIONS[name].powershell_command
        assert len(build_ssh_command('OEM@192.168.0.210',command,adapter.TRANSPORT_SETTINGS)[-1])<7500
    command=adapter.OPERATIONS['m33_broker_pnl_collect'].powershell_command
    assert 'prepared.local.json' in command
    assert '--collect-broker-pnl-journal' in command
    assert 'Start-ScheduledTask' not in command
    assert 'Register-ScheduledTask' not in command


def test_unchanged_history_skips_only_acknowledged_receipts(monkeypatch, tmp_path):
    module, mt5, row, account, sent = collector(monkeypatch, tmp_path)
    module._collect_broker_pnl_journal(force=False)
    assert module._collect_broker_pnl_journal(force=False)['unchanged']
    assert len(sent) == 1
    original = row._asdict()
    row._asdict = lambda: {**original, 'profit': 1001}
    account.balance = 1001
    module._collect_broker_pnl_journal(force=False)
    assert len(sent) == 2
    module._collect_broker_pnl_journal(force=True)
    assert len(sent) == 3


def test_secondary_journal_failure_preserves_primary_failure(monkeypatch, tmp_path):
    module, *_ = collector(monkeypatch, tmp_path)
    def failed(**kwargs): raise SystemExit('journal failed')
    monkeypatch.setattr(module, '_collect_broker_pnl_journal', failed)
    with pytest.raises(ValueError, match='primary'):
        try: raise ValueError('primary')
        finally: module._finish_journal_capture()
    with pytest.raises(SystemExit, match='journal failed'):
        module._finish_journal_capture()


def test_failed_forced_projection_cannot_reuse_old_cache(monkeypatch, tmp_path):
    module, mt5, row, account, sent = collector(monkeypatch, tmp_path)
    module._collect_broker_pnl_journal(force=False)
    bridge = module._bridge
    def failed(*args): raise SystemExit('projection failed')
    monkeypatch.setattr(module, '_bridge', failed)
    with pytest.raises(SystemExit, match='projection failed'):
        module._collect_broker_pnl_journal(force=True)
    monkeypatch.setattr(module, '_bridge', bridge)
    module._collect_broker_pnl_journal(force=False)
    assert len(sent) == 2


def test_missing_timezone_data_is_visible(monkeypatch, tmp_path):
    module, mt5, row, account, sent = collector(monkeypatch, tmp_path)
    from zoneinfo import ZoneInfoNotFoundError
    def missing(*args): raise ZoneInfoNotFoundError('timezone unavailable')
    monkeypatch.setattr(module, 'ZoneInfo', missing)
    with pytest.raises(ZoneInfoNotFoundError): module._collect_broker_pnl_journal(force=False)
    assert not sent
