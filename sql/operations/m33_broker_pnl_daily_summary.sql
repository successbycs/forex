\set ON_ERROR_STOP on
WITH bounds AS (
 SELECT :'nz_date'::date nz_date
), scope AS (
 SELECT count(DISTINCT account_scope_sha256) accounts FROM forex.demo_trade_pnl_capture
), snapshot AS (
 SELECT c.* FROM forex.demo_trade_pnl_capture c
 JOIN forex.demo_trade_pnl_projection p USING(capture_id)
 WHERE (SELECT accounts FROM scope)=1
 ORDER BY c.captured_at_utc DESC,c.capture_id DESC LIMIT 1
), all_rows AS (
 SELECT p.* FROM forex.demo_m33_current_trade_pnl p
 WHERE (SELECT accounts FROM scope)=1
), rows AS (
 SELECT p.* FROM all_rows p,bounds b
 WHERE (p.occurred_at_utc AT TIME ZONE 'Pacific/Auckland')::date=b.nz_date
) , latest_receipt AS (
 SELECT capture_id FROM forex.demo_trade_pnl_capture
 ORDER BY captured_at_utc DESC,capture_id DESC LIMIT 1
), validity AS (
 SELECT CASE WHEN (SELECT accounts FROM scope)>1 THEN 'AMBIGUOUS_ACCOUNT_SCOPE'
 WHEN NOT EXISTS(SELECT 1 FROM snapshot) THEN 'NO_VERIFIED_BROKER_CAPTURE'
 WHEN NOT EXISTS(SELECT 1 FROM forex.demo_trade_pnl_projection p JOIN latest_receipt r USING(capture_id)) THEN 'LATEST_CAPTURE_NOT_RECONCILED'
 WHEN (SELECT captured_at_utc AT TIME ZONE 'Pacific/Auckland' FROM snapshot)::date < (SELECT nz_date FROM bounds)
 THEN 'DAY_AFTER_LATEST_CAPTURE'
 WHEN NOT EXISTS(SELECT 1 FROM all_rows,bounds WHERE (occurred_at_utc AT TIME ZONE 'Pacific/Auckland')::date<=nz_date)
 THEN 'DAY_BEFORE_RETAINED_HISTORY'
 ELSE NULL END reason
)
SELECT json_build_object(
 'date',(SELECT nz_date::text FROM bounds),'currency','AUD',
 'status',CASE WHEN (SELECT reason FROM validity) IS NULL THEN 'AVAILABLE' ELSE 'UNAVAILABLE' END,
 'unavailable_reason',(SELECT reason FROM validity),
 'captured_at_utc',(SELECT captured_at_utc FROM snapshot),
 'account_scope_sha256',(SELECT account_scope_sha256 FROM snapshot),
 'rows',COALESCE((SELECT json_agg(row_to_json(r) ORDER BY occurred_at_utc,deal_ticket) FROM rows r),'[]'::json),
 'deal_count',(SELECT count(*) FROM rows),
 'opening_balance_aud',(SELECT account_balance_aud FROM snapshot)-COALESCE((SELECT sum(net_movement_aud) FROM all_rows,bounds WHERE (occurred_at_utc AT TIME ZONE 'Pacific/Auckland')::date>=nz_date),0),
 'broker_balance_change_aud',COALESCE((SELECT sum(net_movement_aud) FROM rows),0),
 'closing_balance_aud',(SELECT account_balance_aud FROM snapshot)-COALESCE((SELECT sum(net_movement_aud) FROM all_rows,bounds WHERE (occurred_at_utc AT TIME ZONE 'Pacific/Auckland')::date>nz_date),0),
 'broker_commission_aud_total',COALESCE((SELECT sum(broker_commission_aud) FROM rows),0),
 'expected_live_commission_aud_total',CASE WHEN EXISTS(SELECT 1 FROM rows WHERE expected_live_commission_aud IS NULL) THEN NULL ELSE COALESCE((SELECT sum(expected_live_commission_aud) FROM rows),0) END,
 'commission_adjusted_net_aud_total',CASE WHEN EXISTS(SELECT 1 FROM rows WHERE commission_adjusted_net_aud IS NULL) THEN NULL ELSE COALESCE((SELECT sum(commission_adjusted_net_aud) FROM rows),0) END,
 'total_trade_pnl_aud',COALESCE((SELECT sum(net_movement_aud) FROM all_rows WHERE deal_type_code IN(0,1)),0),
 'total_commission_adjusted_trade_pnl_aud',CASE WHEN EXISTS(SELECT 1 FROM all_rows WHERE deal_type_code IN(0,1) AND commission_adjusted_net_aud IS NULL) THEN NULL ELSE COALESCE((SELECT sum(commission_adjusted_net_aud) FROM all_rows WHERE deal_type_code IN(0,1)),0) END
);
