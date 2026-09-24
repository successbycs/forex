\set ON_ERROR_STOP on
-- Synthetic verification is transaction-local and is always rolled back.
BEGIN;
CREATE FUNCTION pg_temp.m33_capture(label TEXT, amount NUMERIC, revision INTEGER, source JSONB)
RETURNS TEXT LANGUAGE plpgsql AS $$
DECLARE normalized JSONB; receipt JSONB; identifier TEXT := 'M33_VERIFY_'||label;
BEGIN
 SELECT jsonb_agg(jsonb_build_object(
   'ticket',d->'ticket','order',d->'order','position_identifier',d->'position_id',
   'broker_time_utc',to_timestamp((d->>'time_msc')::numeric/1000),
   'occurred_at_utc',to_timestamp((d->>'time_msc')::numeric/1000)-interval '3 hours',
   'entry',d->'entry','type',d->'type','volume',d->'volume','price',d->'price',
   'commission',d->'commission','fee',d->'fee','swap',d->'swap','profit',d->'profit',
   'reason',d->'reason','symbol',d->'symbol')) INTO normalized
 FROM jsonb_array_elements(source) d;
 receipt=jsonb_build_object('deals',normalized,'raw_deals',source,'account_currency','AUD',
   'account_balance_aud',amount,'account_balance_before_aud',amount,'broker_timestamp_offset_seconds',10800);
 INSERT INTO forex.demo_trade_pnl_capture(capture_id,account_scope_sha256,captured_at_utc,account_balance_aud,
 account_currency,deal_count,source_history_sha256,collection_version,raw_history,raw_history_text)
 VALUES(identifier,'sha256:'||repeat('f',64),'2026-09-24 00:00:00+00'::timestamptz+make_interval(secs=>revision),amount,'AUD',jsonb_array_length(source),
 'sha256:'||encode(sha256(convert_to(label,'UTF8')),'hex'),'forex.m33.broker-pnl-journal.v2',receipt,receipt::text);
 RETURN identifier;
END $$;
DO $$
DECLARE source JSONB := '[
 {"ticket":990001,"order":0,"position_id":0,"time":1790118000,"time_msc":1790118000123,"entry":0,"type":2,"volume":0,"price":0,"commission":0,"fee":0,"swap":0,"profit":100,"reason":0,"symbol":""},
 {"ticket":990002,"order":2,"position_id":2,"time":1790121600,"time_msc":1790121600456,"entry":0,"type":0,"volume":0.015,"price":1.10000,"commission":-0.01,"fee":0,"swap":0,"profit":0,"reason":0,"symbol":"EURUSD"}
 ]'; capture TEXT; count_rows INTEGER; amount NUMERIC;
BEGIN
 capture=pg_temp.m33_capture('first',99.99,1,source);
 IF forex.project_m33_broker_pnl_capture(capture)<>2 THEN RAISE EXCEPTION 'first projection count'; END IF;
 PERFORM forex.project_m33_broker_pnl_capture(capture);
 SELECT count(*) INTO count_rows FROM forex.demo_trade_pnl WHERE source_capture_id=capture;
 IF count_rows<>2 THEN RAISE EXCEPTION 'idempotent replay failed'; END IF;
 SELECT commission_adjusted_net_aud INTO amount FROM forex.demo_trade_pnl WHERE source_capture_id=capture AND deal_ticket=990002;
 IF amount<>-0.05 THEN RAISE EXCEPTION 'SQL rounding/commission replacement failed: %',amount; END IF;
 capture=pg_temp.m33_capture('corrected',109.99,2,jsonb_set(source,'{0,profit}','110'));
 PERFORM forex.project_m33_broker_pnl_capture(capture);
 SELECT balance_before_aud INTO amount FROM forex.demo_m33_current_trade_pnl WHERE source_capture_id=capture AND deal_ticket=990002;
 IF amount IS DISTINCT FROM 110 THEN RAISE EXCEPTION 'unchanged deal balance did not follow corrected snapshot'; END IF;
 capture=pg_temp.m33_capture('reverted',99.99,3,source);
 PERFORM forex.project_m33_broker_pnl_capture(capture);
 SELECT balance_before_aud INTO amount FROM forex.demo_m33_current_trade_pnl WHERE source_capture_id=capture AND deal_ticket=990002;
 IF amount IS DISTINCT FROM 100 THEN RAISE EXCEPTION 'reverted observation did not become current'; END IF;
 capture=pg_temp.m33_capture('partial',99.99,4,jsonb_build_array(source->1));
 BEGIN
   PERFORM forex.project_m33_broker_pnl_capture(capture);
   RAISE EXCEPTION 'partial history incorrectly accepted';
 EXCEPTION WHEN OTHERS THEN
   IF SQLERRM NOT LIKE '%does not reconcile%' THEN RAISE; END IF;
 END;
 IF EXISTS(SELECT 1 FROM forex.demo_trade_pnl_projection WHERE capture_id=capture) THEN RAISE EXCEPTION 'partial capture marked projected'; END IF;
 RAISE NOTICE 'M33_JOURNAL_SQL_VERIFIED: replay, SQL rounding, commission replacement, corrected balances, reversion, partial-history refusal';
END $$;
ROLLBACK;
