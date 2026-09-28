import copy
import json
import os
from pathlib import Path
import re
import subprocess
from datetime import datetime, timezone

import pytest
from forex.incident_reconciliation import SCOPE, validate_observations, validate_source

ROOT = Path(__file__).resolve().parents[1]
SQL = (ROOT / 'sql/operations/incident_20260923_reconciliation.sql').read_text()
M33_MVP_SUMMARY_SQL = (ROOT / 'sql/m33_mvp_system_pnl_summary.sql').read_text()
DEALS = json.loads(re.search(r"deals CONSTANT JSONB := '(.*?)'::jsonb;", SQL).group(1))
NOW = datetime(2026, 9, 23, 5, 30, tzinfo=timezone.utc)


def observations():
    history = dict(ok=True,complete=True,server='GOMarketsMU-Demo',currency='AUD',
                   account_scope_sha256=SCOPE,broker_timestamp_offset_seconds=10800,
                   captured_at_utc=NOW.isoformat(),balance=100960.81,equity=100960.81,deals=copy.deepcopy(DEALS))
    account = dict(ok=True,server='GOMarketsMU-Demo',currency='AUD',account_scope_sha256='sha256:'+SCOPE,
                   open_positions=0,pending_orders=0,balance=100960.81,equity=100960.81)
    return history, account, dict(state='MAINTENANCE_HOLD',heartbeat_at_utc=NOW.isoformat())


def test_exact_broker_preflight():
    validate_observations(*observations(), DEALS, now=NOW)


def test_source_digest_refuses_tampering():
    with pytest.raises(ValueError, match='digest differs'):
        validate_source(b'changed evidence', DEALS)


@pytest.mark.parametrize('index,key,value', [
    (0,'complete',False),(0,'account_scope_sha256','wrong'),(0,'server','GOMarketsMU-Live'),
    (0,'balance',100989.45),(0,'captured_at_utc','2026-09-23T05:29:00Z'),
    (1,'open_positions',1),(1,'pending_orders',1),(1,'pending_orders',None),
    (1,'equity',100960.80),(2,'state','RUNNING'),(2,'heartbeat_at_utc','2026-09-23T05:31:00Z')])
def test_preflight_refuses_changed_or_unavailable_state(index,key,value):
    inputs=observations();inputs[index][key]=value
    with pytest.raises(ValueError): validate_observations(*inputs,DEALS,now=NOW)


def test_preflight_refuses_changed_deal():
    inputs=observations();inputs[0]['deals'][0]['price']=1.1
    with pytest.raises(ValueError): validate_observations(*inputs,DEALS,now=NOW)


@pytest.fixture
def pg():
    # Explicit opt-in to the disposable local cluster only; never the broker DB.
    root=os.environ.get('FOREX_INCIDENT_TEST_PG')
    if not root: pytest.skip('set FOREX_INCIDENT_TEST_PG to an isolated extracted PostgreSQL cluster')
    assert root.startswith('/tmp/forex-incident-pg.')
    env={**os.environ,'LD_LIBRARY_PATH':root+'/root/usr/lib/x86_64-linux-gnu'}
    def run(sql, *, ok=True):
        result=subprocess.run([root+'/root/usr/lib/postgresql/16/bin/psql','-X','-v','ON_ERROR_STOP=1',
            '-h',root,'-p','55439','-d','postgres','-qAt'],input=sql,text=True,capture_output=True,env=env)
        assert (result.returncode==0)==ok, result.stderr
        return result.stdout.strip()
    run("DROP SCHEMA IF EXISTS forex CASCADE; CREATE SCHEMA forex; CREATE FUNCTION forex.reject_demo_audit_mutation() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'immutable'; END $$;")
    for name in ('019_m20_persistent_risk_policy.sql','020_m20_risk_resume_audit.sql','022_m20_independent_risk_pauses.sql'):
        run((ROOT/'sql/migrations'/name).read_text())
    run("""CREATE TABLE forex.demo_open_position_state(position_ticket bigint);
        CREATE TABLE forex.demo_execution_attempt(attempt_id text,proposal_id text,status text,broker_order_reference text);
        CREATE TABLE forex.demo_trade_outcome(proposal_id text);
        CREATE TABLE forex.demo_position_event(attempt_id text,event_type text,payload jsonb);
        INSERT INTO forex.demo_risk_policy_state(policy_version,account_currency,baseline_balance,expected_balance,
        peak_adjusted_equity,daily_anchor_equity,daily_anchor_date,weekly_anchor_equity,weekly_anchor_date,
        pause_reason,pause_reasons,account_scope_sha256) VALUES
        ('forex.m20.conservative-risk.v1','AUD',100995.51,100989.45,100995.17,100989.45,'2026-09-23',100988.91,'2026-09-21',
        'EXTERNAL_CASH_FLOW',ARRAY['EXTERNAL_CASH_FLOW','WEEKLY_LOSS'],'"""+SCOPE+"');")
    return run


def test_postgres_exact_correction_replay_and_immutable_evidence(pg):
    pg(SQL)
    expected='100960.81|100995.17|100989.45|100988.91|{WEEKLY_LOSS}|f|t'
    query="SELECT expected_balance,peak_adjusted_equity,daily_anchor_equity,weekly_anchor_equity,pause_reasons,cash_flow_review_approved,risk_observed_at_utc IS NULL FROM forex.demo_risk_policy_state;"
    assert pg(query)==expected
    assert pg('SELECT count(*) FROM forex.demo_account_incident_deal;')=='8'
    pg(SQL)
    assert pg(query)==expected
    assert pg('SELECT count(*) FROM forex.demo_account_incident;')=='1'
    pg("UPDATE forex.demo_account_incident SET actual_net_aud=0;",ok=False)
    pg("DELETE FROM forex.demo_account_incident_deal;",ok=False)
    pg(SQL.replace('068bb6d05046fbf018362c22fcd35cbdc6920f3b520948d0a57d8f5096dbcf18','a'*64),ok=False)
    assert pg(query)==expected


@pytest.mark.parametrize('change', [
    "UPDATE forex.demo_risk_policy_state SET expected_balance=100989.44;",
    "UPDATE forex.demo_risk_policy_state SET account_scope_sha256=repeat('a',64);",
    "UPDATE forex.demo_risk_policy_state SET peak_adjusted_equity=100995.18;",
    "UPDATE forex.demo_risk_policy_state SET cash_flow_review_approved=true;",
    "INSERT INTO forex.demo_open_position_state VALUES(1);",
    "INSERT INTO forex.demo_execution_attempt VALUES('pending','p','SUBMITTED',NULL);",
    "INSERT INTO forex.demo_execution_attempt VALUES('owned','p','ACCEPTED','43135808'); INSERT INTO forex.demo_trade_outcome VALUES('p');",
    "INSERT INTO forex.demo_position_event VALUES('a','CLOSED','{\"position_ticket\":43135808}');"])
def test_postgres_rejects_changed_state_and_rolls_back_all_incident_writes(pg,change):
    pg(change)
    before=pg('SELECT row_to_json(r) FROM forex.demo_risk_policy_state r;')
    pg(SQL,ok=False)
    assert pg("SELECT to_regclass('forex.demo_account_incident') IS NULL;")=='t'
    assert pg('SELECT row_to_json(r) FROM forex.demo_risk_policy_state r;')==before


def test_postgres_scoreboard_aggregates_verified_owned_outcomes_only(pg):
    pg("""CREATE TABLE forex.demo_trade_proposal(proposal_id text PRIMARY KEY,strategy_version text);
      CREATE TABLE forex.demo_strategy_signal(proposal_id text,strategy_id text,signal text);
      CREATE TABLE forex.demo_strategy_selection(proposal_id text PRIMARY KEY,selected_strategy_id text,
        trade_owner_strategy_id text,selection_status text);
      CREATE TABLE forex.demo_trade_ledger(proposal_id text,reconciliation_status text,realized_pnl_account numeric);
      INSERT INTO forex.demo_trade_proposal SELECT x,'forex.m20.11.m1-five-strategy-trial.v2' FROM unnest(ARRAY['a','b','c']) x;
      INSERT INTO forex.demo_strategy_signal SELECT proposal_id,'momentum_breakout','BUY' FROM forex.demo_trade_proposal;
      INSERT INTO forex.demo_strategy_selection SELECT proposal_id,'momentum_breakout','momentum_breakout','SELECTED_EXECUTABLE' FROM forex.demo_trade_proposal;
      INSERT INTO forex.demo_execution_attempt SELECT proposal_id,proposal_id,'ACCEPTED',NULL FROM forex.demo_trade_proposal;
      INSERT INTO forex.demo_position_event SELECT proposal_id,'OPENED','{}'::jsonb FROM forex.demo_trade_proposal;
      INSERT INTO forex.demo_trade_ledger VALUES ('a','MATCHED',2),('b','REPAIRED',-1),('c','RECONCILIATION_ERROR',99);""")
    rows=json.loads(pg((ROOT/'sql/m20_strategy_trial_summary.sql').read_text()))
    assert len(rows)==1
    assert rows[0]['attempt_count']==3 and rows[0]['opened_count']==3
    assert rows[0]['verified_closed_count']==2
    assert rows[0]['win_count']==1 and rows[0]['loss_count']==1
    assert rows[0]['net_realized_pnl_aud']==1


def test_m33_mvp_summary_uses_auckland_periods_and_excludes_unmatched_or_non_demo_rows(pg):
    pg("""ALTER TABLE forex.demo_position_event ADD COLUMN observed_at_utc timestamptz DEFAULT now();
      ALTER TABLE forex.demo_position_event ADD COLUMN event_id bigint GENERATED ALWAYS AS IDENTITY;
      CREATE TABLE forex.demo_trade_session(session_id text PRIMARY KEY,server text);
      CREATE TABLE forex.demo_trade_proposal(proposal_id text PRIMARY KEY,session_id text,action text,
        application_revision text,configuration_fingerprint text,strategy_version text,decision_at_utc timestamptz,
        proposed_entry numeric,stop_loss numeric,take_profit numeric);
      CREATE TABLE forex.demo_strategy_selection(proposal_id text PRIMARY KEY,selected_strategy_id text,trade_owner_strategy_id text);
      CREATE TABLE forex.demo_trade_ledger(proposal_id text PRIMARY KEY,closed_at_utc timestamptz,exit_price numeric,
        gross_price_pnl_account numeric,commission_account numeric,fee_account numeric,swap_account numeric,
        realized_pnl_account numeric,account_currency text,close_reason text,reconciliation_status text,
        reconciliation_disposition text,reconciliation_reason text);
      INSERT INTO forex.demo_trade_session VALUES ('demo','GOMarketsMU-Demo'),('other','OTHER');
      INSERT INTO forex.demo_trade_proposal VALUES
        ('matched','demo','BUY','r','f','v','2026-09-28T09:59:00Z',1.1,1.0,1.2),
        ('unmatched','demo','SELL','r','f','v','2026-09-28T10:00:00Z',1.1,1.2,1.0),
        ('prior-week','demo','BUY','r','f','v','2026-09-27T10:00:00Z',1.1,1.0,1.2),
        ('other-server','other','BUY','r','f','v','2026-09-28T10:00:00Z',1.1,1.0,1.2),
        ('unclosed','demo','BUY','r','f','v','2026-09-28T10:00:00Z',1.1,1.0,1.2);
      INSERT INTO forex.demo_strategy_selection SELECT proposal_id,'owner','owner' FROM forex.demo_trade_proposal;
      INSERT INTO forex.demo_execution_attempt(attempt_id,proposal_id,status,broker_order_reference)
        VALUES ('a1','matched','ACCEPTED',NULL),('a2','unmatched','ACCEPTED',NULL),('a3','prior-week','ACCEPTED',NULL),('a4','other-server','ACCEPTED',NULL),('a5','unclosed','ACCEPTED',NULL);
      INSERT INTO forex.demo_position_event(attempt_id,event_type,payload) VALUES
        ('a1','OPENED','{\"actual_entry_price\":\"1.1001\",\"volume\":\"0.01\"}'),
        ('a2','OPENED','{\"actual_entry_price\":\"1.1002\",\"volume\":\"0.01\"}'),
        ('a3','OPENED','{\"actual_entry_price\":\"1.1003\",\"volume\":\"0.01\"}');
      INSERT INTO forex.demo_trade_ledger VALUES
        ('matched','2026-09-28T10:05:00Z',1.2,3,-1,-0.2,0.1,1.9,'AUD','TP','MATCHED',NULL,NULL),
        ('unmatched','2026-09-28T10:06:00Z',1.0,999,999,0,0,999,'AUD','SL','RECONCILIATION_ERROR',NULL,'history incomplete'),
        ('prior-week','2026-09-27T10:05:00Z',1.2,0.5,0,0,0,0.5,'AUD','TP','MATCHED',NULL,NULL),
        ('other-server','2026-09-28T10:07:00Z',1.2,888,0,0,0,888,'AUD','TP','MATCHED',NULL,NULL);""")
    summary = json.loads(pg(M33_MVP_SUMMARY_SQL.replace("now()", "TIMESTAMPTZ '2026-09-28T10:30:00Z'")))
    today = next(row for row in summary['periods'] if row['period'] == 'today')
    week = next(row for row in summary['periods'] if row['period'] == 'week')
    month = next(row for row in summary['periods'] if row['period'] == 'month')
    assert today['matched_closed_count'] == 1 and today['excluded_closed_count'] == 1
    assert float(today['actual_net_pnl_account']) == 1.9
    assert week['matched_closed_count'] == 1 and month['matched_closed_count'] == 2
    assert float(month['actual_net_pnl_account']) == 2.4
    assert {row['proposal_id'] for row in summary['journal']} == {'matched', 'prior-week'}
    assert summary['excluded_journal'][0]['proposal_id'] == 'unmatched'
    assert 'realized_pnl_account' not in summary['excluded_journal'][0]
    assert summary['unclosed_system_attempt_count'] == 1
