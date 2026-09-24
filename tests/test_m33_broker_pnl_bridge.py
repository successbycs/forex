"""The bridge preserves evidence and delegates all monetary derivation to SQL."""
import importlib.util
import json
from pathlib import Path
from contextlib import contextmanager
import pytest


def bridge():
    spec = importlib.util.spec_from_file_location('journal_bridge', Path('t480/m20_postgres_audit_bridge.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def capture():
    return {'account_scope_sha256': 'sha256:'+'a'*64, 'captured_at_utc':'2026-09-24T00:00:00Z',
            'account_balance_aud':100.005, 'account_balance_before_aud':100.005, 'account_currency':'AUD',
            'deals':[{'profit':100.005}], 'raw_deals':[{'profit':100.005,'comment':'original'}],
            'broker_timestamp_offset_seconds':10800,'collection_version':'forex.m33.broker-pnl-journal.v2'}


def test_raw_capture_commits_before_projection_and_preserves_precision(monkeypatch):
    module=bridge(); events=[]
    class Cursor:
        def execute(self, sql, args): events.append((sql,args))
        def fetchone(self): return (1,)
        def __enter__(self): return self
        def __exit__(self,*args): pass
    class Connection:
        def cursor(self): return Cursor()
    @contextmanager
    def connection():
        yield Connection()
        events.append(('commit',None))
    monkeypatch.setattr(module,'_connection',connection)
    result=module.record_broker_pnl_capture({'capture':capture()})
    assert result['deal_count']==1
    assert events[1][0]=='commit'
    assert 'project_m33_broker_pnl_capture' in events[2][0]
    assert json.loads(events[0][1][-1])==capture()
    assert events[0][1][3]==100.005  # no Python monetary rounding


def test_failed_projection_does_not_erase_committed_raw_receipt(monkeypatch):
    module=bridge(); committed=[]
    class Cursor:
        def execute(self,sql,args):
            if 'SELECT' in sql: raise RuntimeError('projection refused')
        def __enter__(self): return self
        def __exit__(self,*args): pass
    class Connection:
        def cursor(self): return Cursor()
    @contextmanager
    def connection():
        yield Connection()
        committed.append(True)
    monkeypatch.setattr(module,'_connection',connection)
    with pytest.raises(RuntimeError,match='projection refused'):
        module.record_broker_pnl_capture({'capture':capture()})
    assert committed==[True]


def test_unstable_balance_refused_before_database(monkeypatch):
    module=bridge(); receipt=capture();receipt['account_balance_aud']=90
    monkeypatch.setattr(module,'_connection',lambda:pytest.fail('unstable receipt reached database'))
    with pytest.raises(SystemExit,match='changed during capture'):
        module.record_broker_pnl_capture({'capture':receipt})
