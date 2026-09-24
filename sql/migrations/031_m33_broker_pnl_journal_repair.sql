-- Correct v1 projections without rewriting retained observations.
BEGIN;
ALTER TABLE forex.demo_trade_pnl_capture ADD COLUMN IF NOT EXISTS raw_history_text TEXT;
ALTER TABLE forex.demo_trade_pnl ADD COLUMN IF NOT EXISTS calculation_version TEXT;
ALTER TABLE forex.demo_trade_pnl ADD COLUMN IF NOT EXISTS commission_profile_version TEXT;
-- A snapshot must retain unchanged deals too: their running balance can change
-- when an earlier deal is corrected, and revisions can revert to old values.
DO $$ DECLARE c RECORD; BEGIN
  FOR c IN SELECT conname FROM pg_constraint
    WHERE conrelid='forex.demo_trade_pnl'::regclass AND contype='u'
      AND pg_get_constraintdef(oid) LIKE '%source_deal_sha256%'
  LOOP EXECUTE format('ALTER TABLE forex.demo_trade_pnl DROP CONSTRAINT %I',c.conname); END LOOP;
  FOR c IN SELECT conname FROM pg_constraint
    WHERE conrelid='forex.demo_trade_pnl'::regclass AND contype='c'
      AND pg_get_constraintdef(oid) LIKE '%commission_adjusted_net_aud%'
  LOOP EXECUTE format('ALTER TABLE forex.demo_trade_pnl DROP CONSTRAINT %I',c.conname); END LOOP;
END $$;
CREATE UNIQUE INDEX IF NOT EXISTS demo_trade_pnl_capture_ticket_idx
ON forex.demo_trade_pnl(source_capture_id,deal_ticket);
CREATE TABLE IF NOT EXISTS forex.demo_trade_pnl_projection (
  capture_id TEXT PRIMARY KEY REFERENCES forex.demo_trade_pnl_capture(capture_id),
  calculation_version TEXT NOT NULL,
  projected_deal_count INTEGER NOT NULL,
  created_at_utc TIMESTAMPTZ NOT NULL DEFAULT now()
);
DROP TRIGGER IF EXISTS demo_trade_pnl_projection_immutable ON forex.demo_trade_pnl_projection;
CREATE TRIGGER demo_trade_pnl_projection_immutable BEFORE UPDATE OR DELETE ON forex.demo_trade_pnl_projection
FOR EACH ROW EXECUTE FUNCTION forex.reject_demo_audit_mutation();

CREATE OR REPLACE FUNCTION forex.project_m33_broker_pnl_capture(p_capture_id TEXT)
RETURNS INTEGER LANGUAGE plpgsql AS $$
DECLARE cap forex.demo_trade_pnl_capture%ROWTYPE; inserted INTEGER;
BEGIN
 SELECT * INTO STRICT cap FROM forex.demo_trade_pnl_capture WHERE capture_id=p_capture_id;
 PERFORM pg_advisory_xact_lock(hashtextextended(p_capture_id,0));
 IF EXISTS (SELECT 1 FROM forex.demo_trade_pnl_projection WHERE capture_id=p_capture_id) THEN
   RETURN cap.deal_count;
 END IF;
 IF cap.collection_version <> 'forex.m33.broker-pnl-journal.v2'
    OR cap.raw_history_text IS NULL
    OR cap.raw_history_text::jsonb <> cap.raw_history
    OR cap.raw_history->>'account_currency' <> 'AUD'
    OR (cap.raw_history->>'account_balance_before_aud')::numeric <> (cap.raw_history->>'account_balance_aud')::numeric
    OR jsonb_array_length(cap.raw_history->'deals') <> cap.deal_count
    OR jsonb_array_length(cap.raw_history->'raw_deals') <> cap.deal_count
 THEN RAISE EXCEPTION 'Unverified M33 broker P&L capture'; END IF;
 IF (SELECT count(DISTINCT (r->>'ticket')::bigint) FROM jsonb_array_elements(cap.raw_history->'deals') r) <> cap.deal_count THEN
   RAISE EXCEPTION 'Duplicate or absent broker deal tickets';
 END IF;
 -- Validate the normalized facts against the retained full broker objects.
 IF EXISTS (
   SELECT 1 FROM jsonb_array_elements(cap.raw_history->'deals') d
   LEFT JOIN jsonb_array_elements(cap.raw_history->'raw_deals') r ON r->>'ticket'=d->>'ticket'
   WHERE r IS NULL OR (d->>'ticket')::bigint <= 0
      OR (d->>'occurred_at_utc')::timestamptz > cap.captured_at_utc
      OR (d->>'broker_time_utc')::timestamptz <> to_timestamp(COALESCE((r->>'time_msc')::numeric/1000,(r->>'time')::numeric)::double precision)
      OR (d->>'occurred_at_utc')::timestamptz <> to_timestamp(COALESCE((r->>'time_msc')::numeric/1000,(r->>'time')::numeric)::double precision) - make_interval(secs => (cap.raw_history->>'broker_timestamp_offset_seconds')::integer)
      OR EXISTS (SELECT 1 FROM unnest(ARRAY['ticket','order','entry','type','volume','price','commission','fee','swap','profit','reason']) k
                 WHERE d->>k IS NULL OR r->>k IS NULL OR (d->>k)::numeric <> (r->>k)::numeric)
      OR d->>'symbol' IS DISTINCT FROM r->>'symbol'
      OR (d->>'position_identifier')::bigint IS DISTINCT FROM (r->>'position_id')::bigint
 ) THEN RAISE EXCEPTION 'Broker deal normalization differs from retained source'; END IF;
 -- The complete broker ledger must independently reconcile to the observed
 -- balance. Starting from balance minus history alone would be tautological.
 IF COALESCE((SELECT sum(round((d->>'profit')::numeric,2)+round((d->>'commission')::numeric,2)+round((d->>'fee')::numeric,2)+round((d->>'swap')::numeric,2))
              FROM jsonb_array_elements(cap.raw_history->'deals') d),0) <> cap.account_balance_aud
 THEN RAISE EXCEPTION 'Broker history does not reconcile to observed account balance'; END IF;
 WITH facts AS (
  SELECT d,
    (d->>'ticket')::bigint ticket, (d->>'occurred_at_utc')::timestamptz happened,
    round((d->>'profit')::numeric,2) profit, round((d->>'commission')::numeric,2) commission,
    round((d->>'fee')::numeric,2) fee, round((d->>'swap')::numeric,2) swap,
    (d->>'volume')::numeric volume, (d->>'type')::smallint type,
    (d->>'entry')::smallint entry
  FROM jsonb_array_elements(cap.raw_history->'deals') d
 ), money AS (
  SELECT *, profit+commission+fee+swap movement,
    CASE WHEN type IN (0,1) AND d->>'symbol'='EURUSD' THEN -round(3.00*volume,2)
         WHEN type NOT IN (0,1) THEN 0::numeric ELSE NULL END expected
  FROM facts
 ), balances AS (
  SELECT *, cap.account_balance_aud-sum(movement) OVER ()+
    sum(movement) OVER (ORDER BY happened,ticket ROWS UNBOUNDED PRECEDING) after
  FROM money
 )
 INSERT INTO forex.demo_trade_pnl (
   pnl_id,account_scope_sha256,deal_ticket,source_capture_id,source_deal_sha256,
   broker_time_utc,occurred_at_utc,entry_code,deal_type_code,event_kind,side,position_identifier,
   volume_lots,price,broker_commission_aud,broker_fee_aud,broker_swap_aud,trade_pnl_aud,
   net_movement_aud,expected_live_commission_aud,commission_adjusted_net_aud,
   balance_before_aud,balance_after_aud,account_currency,collection_version,observed_at_utc,
   calculation_version,commission_profile_version)
 SELECT p_capture_id||':'||ticket, cap.account_scope_sha256,ticket,p_capture_id,
   'sha256:'||encode(sha256(convert_to(d::text,'UTF8')),'hex'),
   (d->>'broker_time_utc')::timestamptz,happened,entry,type,
   CASE WHEN type IN (0,1) THEN CASE entry WHEN 0 THEN 'OPEN' WHEN 1 THEN 'CLOSE' WHEN 2 THEN 'INOUT' WHEN 3 THEN 'CLOSE_BY' ELSE 'OTHER' END
        WHEN type=2 THEN 'BALANCE' ELSE 'OTHER' END,
   CASE type WHEN 0 THEN 'BUY' WHEN 1 THEN 'SELL' ELSE NULL END,
   nullif((d->>'position_identifier')::bigint,0),volume,(d->>'price')::numeric,
   commission,fee,swap,profit,movement,expected,
   CASE WHEN expected IS NOT NULL THEN movement-commission+expected ELSE NULL END,
   after-movement,after,'AUD',cap.collection_version,cap.captured_at_utc,
   'forex.m33.broker-pnl-calculation.v2',
   CASE WHEN type IN (0,1) AND d->>'symbol'='EURUSD' THEN 'ASSUMED_GO_PLUS_AUD_3_PER_LOT_SIDE_V1' ELSE NULL END
 FROM balances;
 GET DIAGNOSTICS inserted = ROW_COUNT;
 IF inserted <> cap.deal_count THEN RAISE EXCEPTION 'Incomplete M33 broker P&L projection'; END IF;
 INSERT INTO forex.demo_trade_pnl_projection VALUES(p_capture_id,'forex.m33.broker-pnl-calculation.v2',inserted,now());
 RETURN inserted;
END $$;

-- An account's report always uses one entire validated snapshot. V1 rows remain
-- immutable evidence but are not trusted as a corrected projection.
CREATE OR REPLACE VIEW forex.demo_m33_current_trade_pnl AS
WITH latest AS (
 SELECT DISTINCT ON(c.account_scope_sha256) c.capture_id
 FROM forex.demo_trade_pnl_capture c
 JOIN forex.demo_trade_pnl_projection p USING(capture_id)
 ORDER BY c.account_scope_sha256,c.captured_at_utc DESC,c.capture_id DESC
)
SELECT pnl.* FROM forex.demo_trade_pnl pnl JOIN latest ON latest.capture_id=pnl.source_capture_id;
COMMIT;
