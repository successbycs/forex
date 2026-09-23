-- Chris approved this exact Demo-only, loss-preserving correction on 2026-09-23.
-- Fixed adapter requires fresh held/flat broker checks before this transaction.
BEGIN;
SET LOCAL lock_timeout = '5s';
SELECT pg_advisory_xact_lock(hashtextextended('forex.m20.conservative-risk.v1',0));
CREATE TABLE IF NOT EXISTS forex.demo_account_incident (
 incident_id TEXT PRIMARY KEY,
 account_scope_sha256 TEXT NOT NULL CHECK (account_scope_sha256 ~ '^[0-9a-f]{64}$'),
 server TEXT NOT NULL CHECK (server='GOMarketsMU-Demo'),
 currency TEXT NOT NULL CHECK (currency='AUD'),
 source_sha256 TEXT NOT NULL CHECK (source_sha256 ~ '^[0-9a-f]{64}$'),
 source_deals JSONB NOT NULL,
 broker_timestamp_offset_seconds INTEGER NOT NULL,
 actual_net_aud NUMERIC(14,2) NOT NULL,
 before_risk JSONB NOT NULL,
 applied_at_utc TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS forex.demo_account_incident_deal (
 account_scope_sha256 TEXT NOT NULL,
 deal_ticket BIGINT NOT NULL,
 incident_id TEXT NOT NULL REFERENCES forex.demo_account_incident(incident_id),
 position_id BIGINT NOT NULL,
 occurred_at_utc TIMESTAMPTZ NOT NULL,
 attribution TEXT NOT NULL CHECK (attribution IN ('UNKNOWN_ORIGIN','OPERATOR_CONFIRMED_CLOSE')),
 raw_deal JSONB NOT NULL,
 PRIMARY KEY(account_scope_sha256,deal_ticket)
);
DROP TRIGGER IF EXISTS demo_account_incident_immutable ON forex.demo_account_incident;
CREATE TRIGGER demo_account_incident_immutable BEFORE UPDATE OR DELETE ON forex.demo_account_incident
 FOR EACH ROW EXECUTE FUNCTION forex.reject_demo_audit_mutation();
DROP TRIGGER IF EXISTS demo_account_incident_deal_immutable ON forex.demo_account_incident_deal;
CREATE TRIGGER demo_account_incident_deal_immutable BEFORE UPDATE OR DELETE ON forex.demo_account_incident_deal
 FOR EACH ROW EXECUTE FUNCTION forex.reject_demo_audit_mutation();
DO $repair$
DECLARE
 scope CONSTANT TEXT := '4b12a2cebac68fadc4009c52f46e1cda20bd3c731ef94428ed2b47a2d29faabf';
 source CONSTANT TEXT := '068bb6d05046fbf018362c22fcd35cbdc6920f3b520948d0a57d8f5096dbcf18';
 incident CONSTANT TEXT := 'demo-20260923-four-unattributed-positions';
 deals CONSTANT JSONB := '[{"comment":"","commission":0.0,"entry":0,"external_id":"","fee":0.0,"magic":0,"order":43135808,"position_id":43135808,"price":1.14518,"profit":0.0,"reason":0,"swap":0.0,"symbol":"EURUSD","ticket":35649111,"time":1790124764,"time_msc":1790124764679,"type":0,"volume":0.02},{"comment":"","commission":0.0,"entry":0,"external_id":"","fee":0.0,"magic":0,"order":43135809,"position_id":43135809,"price":1.14518,"profit":0.0,"reason":0,"swap":0.0,"symbol":"EURUSD","ticket":35649112,"time":1790124764,"time_msc":1790124764679,"type":0,"volume":0.02},{"comment":"","commission":0.0,"entry":0,"external_id":"","fee":0.0,"magic":0,"order":43135810,"position_id":43135810,"price":1.14518,"profit":0.0,"reason":0,"swap":0.0,"symbol":"EURUSD","ticket":35649113,"time":1790124764,"time_msc":1790124764679,"type":0,"volume":0.02},{"comment":"","commission":0.0,"entry":0,"external_id":"","fee":0.0,"magic":0,"order":43135811,"position_id":43135811,"price":1.14518,"profit":0.0,"reason":0,"swap":0.0,"symbol":"EURUSD","ticket":35649114,"time":1790124764,"time_msc":1790124764679,"type":0,"volume":0.02},{"comment":"","commission":0.0,"entry":1,"external_id":"","fee":0.0,"magic":0,"order":43157012,"position_id":43135808,"price":1.14265,"profit":-7.12,"reason":0,"swap":0.0,"symbol":"EURUSD","ticket":35667306,"time":1790150380,"time_msc":1790150380478,"type":1,"volume":0.02},{"comment":"","commission":0.0,"entry":1,"external_id":"","fee":0.0,"magic":0,"order":43157014,"position_id":43135809,"price":1.14266,"profit":-7.1,"reason":0,"swap":0.0,"symbol":"EURUSD","ticket":35667308,"time":1790150385,"time_msc":1790150385015,"type":1,"volume":0.02},{"comment":"","commission":0.0,"entry":1,"external_id":"","fee":0.0,"magic":0,"order":43157015,"position_id":43135810,"price":1.14262,"profit":-7.21,"reason":0,"swap":0.0,"symbol":"EURUSD","ticket":35667309,"time":1790150388,"time_msc":1790150388910,"type":1,"volume":0.02},{"comment":"","commission":0.0,"entry":1,"external_id":"","fee":0.0,"magic":0,"order":43157016,"position_id":43135811,"price":1.14262,"profit":-7.21,"reason":0,"swap":0.0,"symbol":"EURUSD","ticket":35667310,"time":1790150392,"time_msc":1790150392409,"type":1,"volume":0.02}]'::jsonb;
 state forex.demo_risk_policy_state%ROWTYPE;
 prior forex.demo_account_incident%ROWTYPE;
 remaining TEXT[];
BEGIN
 SELECT * INTO STRICT state FROM forex.demo_risk_policy_state
 WHERE policy_version='forex.m20.conservative-risk.v1' FOR UPDATE;
 IF state.account_scope_sha256 IS DISTINCT FROM scope OR state.account_currency <> 'AUD' THEN
   RAISE EXCEPTION 'Incident account mismatch';
 END IF;
 SELECT * INTO prior FROM forex.demo_account_incident WHERE incident_id=incident;
 IF FOUND THEN
   IF prior.account_scope_sha256<>scope OR prior.source_sha256<>source OR prior.source_deals<>deals
      OR prior.actual_net_aud<>-28.64 OR
      (SELECT count(*) FROM forex.demo_account_incident_deal WHERE incident_id=incident)<>8 THEN
     RAISE EXCEPTION 'Conflicting incident replay';
   END IF;
   RAISE NOTICE 'FOREX_INCIDENT_ALREADY_APPLIED';
   RETURN;
 END IF;
 IF state.expected_balance<>100989.45 OR state.baseline_balance<>100995.51
    OR state.peak_adjusted_equity<>100995.17 OR state.daily_anchor_equity<>100989.45
    OR state.weekly_anchor_equity<>100988.91 OR state.daily_anchor_date<>DATE '2026-09-23'
    OR state.weekly_anchor_date<>DATE '2026-09-21' OR state.cash_flow_review_approved
    OR NOT ('EXTERNAL_CASH_FLOW'=ANY(state.pause_reasons)) THEN
   RAISE EXCEPTION 'Incident risk precondition differs';
 END IF;
 IF EXISTS (SELECT 1 FROM forex.demo_open_position_state)
    OR EXISTS (SELECT 1 FROM forex.demo_execution_attempt WHERE broker_order_reference IN
       ('43135808','43135809','43135810','43135811','43157012','43157014','43157015','43157016'))
    OR EXISTS (SELECT 1 FROM forex.demo_execution_attempt a
       LEFT JOIN forex.demo_trade_outcome o ON o.proposal_id=a.proposal_id
       WHERE o.proposal_id IS NULL AND NOT EXISTS
       (SELECT 1 FROM forex.demo_position_event e WHERE e.attempt_id=a.attempt_id
        AND e.event_type IN ('REJECTED','NOT_SUBMITTED')))
    OR EXISTS (SELECT 1 FROM forex.demo_position_event e WHERE
       e.payload->>'position_ticket' IN ('43135808','43135809','43135810','43135811')
       OR e.payload->>'position_identifier' IN ('43135808','43135809','43135810','43135811')
       OR e.payload->>'broker_order_reference' IN
       ('43135808','43135809','43135810','43135811','43157012','43157014','43157015','43157016')) THEN
   RAISE EXCEPTION 'Open, pending or already attributed incident state';
 END IF;
 IF jsonb_array_length(deals)<>8 OR
    (SELECT sum((d->>'profit')::numeric+(d->>'commission')::numeric+
                (d->>'swap')::numeric+(d->>'fee')::numeric) FROM jsonb_array_elements(deals) d)<>-28.64 THEN
   RAISE EXCEPTION 'Incident deal total differs';
 END IF;
 INSERT INTO forex.demo_account_incident VALUES
 (incident,scope,'GOMarketsMU-Demo','AUD',source,deals,10800,-28.64,to_jsonb(state),now());
 INSERT INTO forex.demo_account_incident_deal
 SELECT scope,(d->>'ticket')::bigint,incident,(d->>'position_id')::bigint,
        to_timestamp((d->>'time_msc')::numeric/1000-10800),
        CASE WHEN (d->>'entry')::integer=0 THEN 'UNKNOWN_ORIGIN' ELSE 'OPERATOR_CONFIRMED_CLOSE' END,d
 FROM jsonb_array_elements(deals) d;
 remaining := array_remove(state.pause_reasons,'EXTERNAL_CASH_FLOW');
 UPDATE forex.demo_risk_policy_state SET expected_balance=expected_balance-28.64,
   pause_reasons=remaining,pause_reason=remaining[1],cash_flow_review_approved=false,
   risk_observed_at_utc=NULL,updated_at_utc=now()
 WHERE policy_version=state.policy_version;
 RAISE NOTICE 'FOREX_INCIDENT_RECONCILED_LOSS_28_64';
END $repair$;
COMMIT;
