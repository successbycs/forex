\set ON_ERROR_STOP on
WITH bounds AS (
  SELECT :'nz_date'::date AS nz_date
), rows AS (
  SELECT p.*
  FROM forex.demo_m33_current_trade_pnl p, bounds b
  WHERE (p.occurred_at_utc AT TIME ZONE 'Pacific/Auckland')::date=b.nz_date
), ordered AS (
  SELECT * FROM rows ORDER BY occurred_at_utc, deal_ticket
)
SELECT json_build_object(
  'date', (SELECT nz_date::text FROM bounds),
  'currency', 'AUD',
  'rows', COALESCE((SELECT json_agg(row_to_json(x) ORDER BY x.occurred_at_utc,x.deal_ticket) FROM (
    SELECT occurred_at_utc,broker_time_utc,deal_ticket,event_kind,side,volume_lots,price,
           broker_commission_aud,broker_fee_aud,broker_swap_aud,trade_pnl_aud,net_movement_aud,
           expected_live_commission_aud,commission_adjusted_net_aud,balance_before_aud,balance_after_aud,
           position_identifier,source_deal_sha256,collection_version
    FROM ordered
  ) x), '[]'::json),
  'deal_count', (SELECT count(*) FROM rows),
  'opening_balance_aud', (SELECT balance_before_aud FROM ordered LIMIT 1),
  'broker_balance_change_aud', COALESCE((SELECT sum(net_movement_aud) FROM rows),0),
  'closing_balance_aud', (SELECT balance_after_aud FROM ordered ORDER BY occurred_at_utc DESC,deal_ticket DESC LIMIT 1),
  'broker_commission_aud_total', COALESCE((SELECT sum(broker_commission_aud) FROM rows),0),
  'expected_live_commission_aud_total', COALESCE((SELECT sum(expected_live_commission_aud) FROM rows),0),
  'commission_adjusted_net_aud_total', COALESCE((SELECT sum(commission_adjusted_net_aud) FROM rows),0),
  'status', CASE WHEN EXISTS (SELECT 1 FROM rows) THEN 'AVAILABLE' ELSE 'UNAVAILABLE' END,
  'unavailable_reason', CASE WHEN EXISTS (SELECT 1 FROM rows) THEN NULL ELSE 'NO_RETAINED_BROKER_DEALS_FOR_DAY' END
);
