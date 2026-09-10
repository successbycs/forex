"""Real PostgreSQL tests; only an explicitly isolated local test database.

FOREX_W1_TEST_DSN must name forex_w1_test on localhost at a nonstandard port.
Synthetic equity paths are engineering fixtures, never broker evidence.
"""
from datetime import date, timedelta
import importlib.util
import math
import os
from pathlib import Path

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[2]


def load_bridge():
    spec = importlib.util.spec_from_file_location("w1_risk_bridge", ROOT / "t480/m20_postgres_audit_bridge.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def database(monkeypatch):
    dsn = os.environ.get("FOREX_W1_TEST_DSN")
    if not dsn:
        pytest.skip("requires isolated FOREX_W1_TEST_DSN; not broker proof")
    import psycopg
    from psycopg.conninfo import conninfo_to_dict
    options = conninfo_to_dict(dsn)
    assert options.get("host") in {"127.0.0.1", "localhost"}
    assert options.get("dbname") == "forex_w1_test"
    assert options.get("port") not in {None, "5432"}
    with psycopg.connect(dsn) as conn:
        conn.execute("DROP SCHEMA IF EXISTS forex CASCADE")
        conn.execute("CREATE SCHEMA forex")
    for name in ("019_m20_persistent_risk_policy.sql", "020_m20_risk_resume_audit.sql", "022_m20_independent_risk_pauses.sql"):
        path = ROOT / "sql/migrations" / name
        if path.exists():
            with psycopg.connect(dsn) as conn:
                conn.execute(path.read_text())
    monkeypatch.setenv("FOREX_M20_POSTGRES_DSN", dsn)
    return dsn


def observe(bridge, *, equity=100000, balance=100000, day="2026-09-10", scope="a" * 64):
    when = date.fromisoformat(day)
    policy = yaml.safe_load((ROOT / "config/runtime.yaml").read_text())["persistent_risk_policy"]
    return bridge.enforce_risk_policy({"policy": policy, "account": {
        "balance": balance, "equity": equity, "auckland_date": day, "account_scope_sha256": scope,
        "auckland_week_start": (when - timedelta(days=when.weekday())).isoformat(),
    }})["risk"]


def state(database):
    import psycopg
    with psycopg.connect(database) as conn:
        return conn.execute("SELECT row_to_json(s) FROM forex.demo_risk_policy_state s").fetchone()[0]


def test_overlapping_breaches_survive_recovery_and_day_rollover(database):
    bridge = load_bridge()
    observe(bridge)
    first = observe(bridge, equity=97500)
    assert not first["entry_allowed"]
    # Reload the module and reconnect on every call: no process-local latch.
    recovered = observe(load_bridge(), equity=99900, day="2026-09-11")
    assert not recovered["entry_allowed"]
    assert set(recovered["pause_reasons"]) == {"WEEKLY_LOSS", "PEAK_DRAWDOWN"}
    assert state(database)["peak_adjusted_equity"] == 100000


def test_manual_latches_survive_week_rollover(database):
    b = load_bridge(); observe(b); observe(b, equity=97500)
    result = observe(load_bridge(), equity=100000, day="2026-09-14")
    assert not result["entry_allowed"]
    assert set(result["pause_reasons"]) == {"WEEKLY_LOSS", "PEAK_DRAWDOWN"}


def test_daily_only_pause_expires_on_next_day(database):
    b = load_bridge(); observe(b)
    assert not observe(b, equity=99400)["entry_allowed"]
    assert not observe(b, equity=100000)["entry_allowed"]
    assert observe(b, day="2026-09-11")["entry_allowed"]


def test_resume_acknowledges_one_manual_reason_without_erasing_others(database):
    b = load_bridge(); observe(b); observe(b, equity=97500)
    b.resume_risk_policy({})
    after = state(database)
    assert "DAILY_LOSS" in after["pause_reasons"]
    assert len(set(after["pause_reasons"]) & {"WEEKLY_LOSS", "PEAK_DRAWDOWN"}) == 1
    assert not observe(b, equity=99900)["entry_allowed"]
    b.resume_risk_policy({})
    assert not observe(b, equity=99900)["entry_allowed"]  # daily cannot be manually cleared
    assert observe(b, equity=99900, day="2026-09-11")["entry_allowed"]


def test_current_breach_relatches_after_resume(database):
    b = load_bridge(); observe(b); observe(b, equity=97500)
    b.resume_risk_policy({})
    result = observe(b, equity=97500)
    assert set(result["pause_reasons"]) == {"DAILY_LOSS", "WEEKLY_LOSS", "PEAK_DRAWDOWN"}


def test_cash_flow_overlap_does_not_erase_drawdown(database):
    b = load_bridge(); observe(b); observe(b, equity=97500)
    observe(b, equity=98500, balance=101000)
    before = state(database)
    assert set(before["pause_reasons"]) == {"EXTERNAL_CASH_FLOW", "DAILY_LOSS", "WEEKLY_LOSS", "PEAK_DRAWDOWN"}
    b.resume_risk_policy({})  # cash-flow review is the first visible reason
    result = observe(b, equity=100900, balance=101000, day="2026-09-11")
    assert not result["entry_allowed"]
    assert set(result["pause_reasons"]) == {"WEEKLY_LOSS", "PEAK_DRAWDOWN"}
    after = state(database)
    assert after["peak_adjusted_equity"] == 101000
    assert after["baseline_balance"] == 100000


def test_remaining_daily_headroom_caps_new_planned_loss(database):
    b = load_bridge(); observe(b)
    result = observe(b, equity=99510)
    assert result["entry_allowed"]
    assert result["maximum_loss_aud"] <= 10


@pytest.mark.parametrize("bad", [math.nan, math.inf, -1, 0, True])
def test_invalid_equity_never_initialises_or_modifies_state(database, bad):
    b = load_bridge(); observe(b)
    before = state(database)
    with pytest.raises(SystemExit):
        observe(b, equity=bad)
    assert state(database) == before


def test_legacy_writer_cannot_clear_new_latches(database):
    import psycopg
    b = load_bridge(); observe(b); observe(b, equity=97500)
    with pytest.raises(psycopg.errors.CheckViolation):
        with psycopg.connect(database) as conn:
            conn.execute("UPDATE forex.demo_risk_policy_state SET pause_reason=NULL")
    assert not observe(b, equity=99900, day="2026-09-11")["entry_allowed"]


def test_different_account_cannot_inherit_or_reset_risk_state(database):
    b = load_bridge(); observe(b); observe(b, equity=97500)
    before = state(database)
    with pytest.raises(SystemExit, match="bound risk account"):
        observe(b, scope="b" * 64)
    assert state(database) == before


def test_migration_backfills_legacy_pause_without_resetting_anchors(database):
    import psycopg
    b = load_bridge(); observe(b)
    with psycopg.connect(database) as c:
        c.execute("ALTER TABLE forex.demo_risk_policy_state DROP CONSTRAINT demo_risk_pause_consistency")
        c.execute("UPDATE forex.demo_risk_policy_state SET pause_reason='WEEKLY_LOSS',pause_reasons='{}'")
    before = state(database)
    migration = (ROOT / "sql/migrations/022_m20_independent_risk_pauses.sql").read_text()
    for _ in range(2):
        with psycopg.connect(database) as c:
            c.execute(migration)
    after = state(database)
    assert after["pause_reasons"] == ["WEEKLY_LOSS"]
    for key in ("baseline_balance", "expected_balance", "peak_adjusted_equity", "daily_anchor_equity", "weekly_anchor_equity", "account_scope_sha256"):
        assert after[key] == before[key]


@pytest.mark.parametrize('condition', ['missing', 'paused', 'stale', 'wrong_account', 'over_headroom', 'nan', 'after_resume'])
def test_reservation_refuses_invalid_risk_state_before_claiming_slot(database, monkeypatch, condition):
    import psycopg
    b = load_bridge()
    if condition != 'missing':
        observe(b)
    if condition in {'paused', 'after_resume'}:
        observe(b, equity=98500)
        if condition == 'after_resume':
            observe(b, equity=100000, day='2026-09-11')
            b.resume_risk_policy({})
            assert state(database)['risk_observed_at_utc'] is None
    elif condition == 'stale':
        with psycopg.connect(database) as c:
            c.execute("UPDATE forex.demo_risk_policy_state SET risk_observed_at_utc=now()-interval '11 seconds'")
    elif condition == 'over_headroom':
        observe(b, equity=99510)
    # Isolate the actual reservation transaction, not the already separately
    # tested proposal serializers. No ledger tables exist: reaching the ledger
    # instead of refusing at its risk gate would fail this test.
    session = {'maximum_loss_per_trade_aud': 100}
    monkeypatch.setattr(b, '_session', lambda p: session)
    monkeypatch.setattr(b, '_proposal', lambda p: {'action': 'BUY'})
    monkeypatch.setattr(b, '_snapshot', lambda *a: None)
    monkeypatch.setattr(b, '_strategy_selection', lambda *a: None)
    monkeypatch.setattr(b, '_strategy_assessments', lambda *a: None)
    reservation = {'attempt_id': 'test', 'idempotency_key': 'test',
        'submitted_at_utc': '2026-09-10T00:00:00Z', 'redacted_result': 'test',
        'broker_open_positions': 0, 'account_scope_sha256': ('b' if condition == 'wrong_account' else 'a') * 64,
        'planned_loss_aud': math.nan if condition == 'nan' else 11}
    with pytest.raises(SystemExit, match='fresh, unpaused|capital headroom'):
        b.reserve_execution({'reservation': reservation})


def test_funded_reservation_reaches_session_gate_with_real_session_shape(database, monkeypatch):
    import psycopg
    b = load_bridge(); observe(b)
    with psycopg.connect(database) as c:
        c.execute((ROOT / 'sql/migrations/006_m20_demo_trading_audit.sql').read_text())
    session = {'session_id': 'absent-test-session', 'server': 'GOMarketsMU-Demo', 'instrument': 'EURUSD',
        'starts_at_utc': '2026-09-10T00:00:00Z', 'expires_at_utc': '2099-01-01T00:00:00Z',
        'max_trades': None, 'max_notional_per_trade_usd': 10000,
        'max_cumulative_notional_usd': 100000, 'max_open_positions': 1,
        'strategy_version': 'test', 'operator_label': 'test'}
    monkeypatch.setattr(b, '_proposal', lambda p: {'action': 'BUY'})
    monkeypatch.setattr(b, '_snapshot', lambda *a: None)
    monkeypatch.setattr(b, '_strategy_selection', lambda *a: None)
    monkeypatch.setattr(b, '_strategy_assessments', lambda *a: None)
    with pytest.raises(SystemExit, match='session is inactive'):
        b.reserve_execution({'session': session, 'reservation': {
            'attempt_id': 'test', 'idempotency_key': 'test', 'submitted_at_utc': '2026-09-10T00:00:00Z',
            'redacted_result': 'test', 'broker_open_positions': 0,
            'account_scope_sha256': 'a' * 64, 'planned_loss_aud': 1}})


def test_unknown_account_pause_survives_recovery_without_resetting_anchors(database):
    b = load_bridge(); observe(b); observe(b, equity=97500)
    before = state(database)
    b.pause_unknown_account_state({})
    result = observe(load_bridge(), equity=99900, day='2026-09-11')
    assert not result['entry_allowed']
    assert set(result['pause_reasons']) == {'UNKNOWN_ACCOUNT_STATE', 'WEEKLY_LOSS', 'PEAK_DRAWDOWN'}
    assert state(database)['baseline_balance'] == before['baseline_balance']
    b.resume_risk_policy({})
    assert 'UNKNOWN_ACCOUNT_STATE' not in state(database)['pause_reasons']
    assert set(state(database)['pause_reasons']) == {'WEEKLY_LOSS', 'PEAK_DRAWDOWN'}


def test_concurrent_reservations_across_leases_allow_only_one(database, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from datetime import datetime, timezone
    import psycopg
    b = load_bridge(); observe(b)
    now = datetime.now(timezone.utc)
    start, end = now - timedelta(minutes=1), now + timedelta(hours=1)
    with psycopg.connect(database) as c:
        for path in sorted((ROOT / 'sql/migrations').glob('*.sql')):
            if 6 <= int(path.name[:3]) <= 18 or path.name.startswith('021_'):
                c.execute(path.read_text())
        for key in ('one', 'two'):
            c.execute("INSERT INTO forex.demo_trade_session(session_id,operator_label,server,instrument,starts_at_utc,expires_at_utc,max_trades,max_notional_usd,max_cumulative_notional_usd,max_open_positions,status,strategy_version,application_revision,configuration_fingerprint) VALUES (%s,'test','GOMarketsMU-Demo','EURUSD',%s,%s,NULL,10000,100000,1,'ACTIVE','test','test',%s)", (key,start,end,'sha256:'+'a'*64))
            c.execute("INSERT INTO forex.demo_trade_proposal(proposal_id,session_id,decision_at_utc,expires_at_utc,selected_timeframe,action,proposed_entry,stop_loss,take_profit,notional_usd,confidence,rationale,decision_snapshot_sha256,strategy_version,application_revision,configuration_fingerprint) VALUES (%s,%s,%s,%s,'M1','BUY',1.16,1.159,1.162,1160,70,'test',%s,'test','test',%s)", (key,key,now,end,'sha256:'+'a'*64,'sha256:'+'a'*64))
            c.execute("INSERT INTO forex.demo_decision_snapshot(snapshot_id,proposal_id,observed_at_utc,captured_at_utc,bid,ask,spread_points,m1_closed_bars,m5_closed_bars,freshness_seconds,payload_sha256) VALUES (%s,%s,%s,%s,1.1599,1.16,10,'[]','[]',0,%s)", (key,key,now,now,'sha256:'+'a'*64))
            c.execute("INSERT INTO forex.demo_strategy_selection(proposal_id,market_regime,market_regime_reason,selected_strategy_id,strategy_rule_version,selection_status,trade_owner_id,trade_owner_strategy_id,cost_coverage_status,estimated_round_trip_cost_aud,minimum_net_profit_aud,expected_net_profit_at_take_profit_aud,entry_spread_cost_aud,expected_exit_spread_cost_aud,commission_allowance_aud,slippage_allowance_aud,expected_swap_aud,projected_gross_profit_at_take_profit_aud) VALUES (%s,'MOMENTUM_BREAKOUT','test','momentum_breakout','test','SELECTED_EXECUTABLE',%s,'momentum_breakout','FEASIBLE',0.2,0.1,0.8,0.1,0.1,0,0,0,1)", (key,key))
    # Exercise the actual complete SQL reservation transaction concurrently;
    # proposal/snapshot serializers are covered by separate tests.
    for name, key in (('_session','session'),('_proposal','proposal')):
        monkeypatch.setattr(b, name, lambda p, key=key: p[key])
    monkeypatch.setattr(b, '_snapshot', lambda *a: None)
    monkeypatch.setattr(b, '_strategy_selection', lambda *a: None)
    monkeypatch.setattr(b, '_strategy_assessments', lambda *a: None)
    barrier = Barrier(2)
    def reserve(key):
        payload = {'session': {'session_id':key,'starts_at_utc':start,'expires_at_utc':end,'max_trades':None,'max_notional_per_trade_usd':10000,'max_cumulative_notional_usd':100000},
            'proposal': {'proposal_id':key,'snapshot_id':key,'action':'BUY','notional_usd':1160},
            'reservation': {'attempt_id':key,'idempotency_key':key,'submitted_at_utc':now.isoformat(),'redacted_result':'test','broker_open_positions':0,'account_scope_sha256':'a'*64,'planned_loss_aud':1}}
        barrier.wait()
        try:
            b.reserve_execution(payload)
            return 'RESERVED'
        except SystemExit as error:
            assert 'global one-position limit' in str(error)
            return 'REFUSED'
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(reserve, ('one','two')))
    assert sorted(results) == ['REFUSED','RESERVED']
    with psycopg.connect(database) as c:
        assert c.execute('SELECT count(*) FROM forex.demo_execution_attempt').fetchone()[0] == 1
