-- M33 daily coverage: every closed Demo outcome is visible; only complete inputs
-- receive an assumed commission comparison. Broker evidence remains immutable.
BEGIN;

CREATE TABLE IF NOT EXISTS forex.demo_trade_commission_coverage (
    coverage_id TEXT PRIMARY KEY,
    proposal_id TEXT NOT NULL REFERENCES forex.demo_trade_proposal(proposal_id) ON DELETE RESTRICT,
    profile_version_id TEXT NOT NULL REFERENCES forex.demo_pricing_profile(profile_version_id) ON DELETE RESTRICT,
    closed_at_utc TIMESTAMPTZ NOT NULL,
    actual_broker_net_aud NUMERIC(14,2),
    actual_broker_commission_aud NUMERIC(14,2),
    broker_fee_aud NUMERIC(14,2),
    broker_swap_aud NUMERIC(14,2),
    volume_lots NUMERIC(12,4),
    expected_round_trip_commission_aud NUMERIC(14,2),
    commission_adjusted_pnl_aud NUMERIC(14,2),
    coverage_status TEXT NOT NULL CHECK (coverage_status IN ('APPLIED','UNAVAILABLE')),
    unavailable_reason TEXT CHECK (unavailable_reason IN ('NOT_MATCHED','UNATTRIBUTED','VOLUME_MISSING_OR_PARTIAL','COST_COMPONENT_MISSING','COST_RECONCILIATION_FAILED','REPAIRED_SOURCE','UNSUPPORTED_CURRENCY')),
    source_fingerprint TEXT NOT NULL CHECK (source_fingerprint ~ '^sha256:[0-9a-f]{64}$'),
    calculation_version TEXT NOT NULL,
    calculated_at_utc TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (proposal_id, profile_version_id, calculation_version, source_fingerprint),
    CHECK ((coverage_status = 'APPLIED' AND unavailable_reason IS NULL AND volume_lots > 0 AND expected_round_trip_commission_aud IS NOT NULL AND commission_adjusted_pnl_aud IS NOT NULL)
        OR (coverage_status = 'UNAVAILABLE' AND unavailable_reason IS NOT NULL AND expected_round_trip_commission_aud IS NULL AND commission_adjusted_pnl_aud IS NULL))
);

DROP TRIGGER IF EXISTS demo_trade_commission_coverage_immutable ON forex.demo_trade_commission_coverage;
CREATE TRIGGER demo_trade_commission_coverage_immutable BEFORE UPDATE OR DELETE ON forex.demo_trade_commission_coverage
FOR EACH ROW EXECUTE FUNCTION forex.reject_demo_audit_mutation();

CREATE OR REPLACE VIEW forex.demo_m33_daily_coverage_source AS
WITH base AS (
 SELECT outcome.proposal_id, outcome.closed_at_utc, outcome.reconciliation_status,
        outcome.realized_pnl_account, outcome.commission_account, outcome.fee_account,
        outcome.swap_account, outcome.gross_price_pnl_account, outcome.account_currency,
        session.server, session.instrument,
        attempt.attempt_id,
        (SELECT count(*) FROM forex.demo_position_event e WHERE e.attempt_id=attempt.attempt_id AND e.event_type='OPENED') AS opened_count,
        (SELECT min(e.payload->>'fill_status') FROM forex.demo_position_event e WHERE e.attempt_id=attempt.attempt_id AND e.event_type='OPENED') AS fill_status,
        (SELECT min(CASE WHEN e.payload->>'volume' ~ '^[0-9]{1,8}(\\.[0-9]{1,4})?$' THEN (e.payload->>'volume')::numeric(12,4) END) FROM forex.demo_position_event e WHERE e.attempt_id=attempt.attempt_id AND e.event_type='OPENED') AS volume_lots,
        (SELECT disposition FROM forex.demo_outcome_reconciliation_revision r WHERE r.proposal_id=outcome.proposal_id ORDER BY r.observed_at_utc DESC,r.created_at_utc DESC LIMIT 1) AS disposition
 FROM forex.demo_trade_outcome outcome
 JOIN forex.demo_trade_proposal proposal ON proposal.proposal_id=outcome.proposal_id
 JOIN forex.demo_trade_session session ON session.session_id=proposal.session_id
 LEFT JOIN forex.demo_execution_attempt attempt ON attempt.proposal_id=proposal.proposal_id
 WHERE session.server='GOMarketsMU-Demo' AND session.instrument='EURUSD'
), classified AS (
 SELECT *, CASE
  WHEN reconciliation_status <> 'MATCHED' THEN 'NOT_MATCHED'
  WHEN attempt_id IS NULL THEN 'UNATTRIBUTED'
  WHEN opened_count <> 1 OR fill_status <> 'FULL' OR volume_lots IS NULL OR volume_lots <= 0 THEN 'VOLUME_MISSING_OR_PARTIAL'
  WHEN disposition IS NOT NULL THEN 'REPAIRED_SOURCE'
  WHEN account_currency <> 'AUD' THEN 'UNSUPPORTED_CURRENCY'
  WHEN realized_pnl_account IS NULL OR commission_account IS NULL OR fee_account IS NULL OR swap_account IS NULL OR gross_price_pnl_account IS NULL THEN 'COST_COMPONENT_MISSING'
  WHEN realized_pnl_account <> gross_price_pnl_account + commission_account + fee_account + swap_account THEN 'COST_RECONCILIATION_FAILED'
  ELSE NULL END AS unavailable_reason
 FROM base
)
SELECT *, 'sha256:'||encode(digest(concat_ws('|',proposal_id,closed_at_utc::text,reconciliation_status,coalesce(realized_pnl_account::text,''),coalesce(commission_account::text,''),coalesce(fee_account::text,''),coalesce(swap_account::text,''),coalesce(volume_lots::text,''),coalesce(unavailable_reason,'')),'sha256'),'hex') AS source_fingerprint
FROM classified;

CREATE OR REPLACE FUNCTION forex.refresh_demo_m33_daily_commission_coverage()
RETURNS void LANGUAGE plpgsql AS $$
BEGIN
 INSERT INTO forex.demo_trade_commission_coverage (
  coverage_id,proposal_id,profile_version_id,closed_at_utc,actual_broker_net_aud,actual_broker_commission_aud,broker_fee_aud,broker_swap_aud,volume_lots,expected_round_trip_commission_aud,commission_adjusted_pnl_aud,coverage_status,unavailable_reason,source_fingerprint,calculation_version)
 SELECT 'M33C-'||source.proposal_id||'-'||substring(source.source_fingerprint FROM 8),source.proposal_id,profile.profile_version_id,source.closed_at_utc,
  source.realized_pnl_account,source.commission_account,source.fee_account,source.swap_account,source.volume_lots,
  CASE WHEN source.unavailable_reason IS NULL THEN -round(profile.commission_aud_per_standard_lot_per_side*source.volume_lots,2)-round(profile.commission_aud_per_standard_lot_per_side*source.volume_lots,2) END,
  CASE WHEN source.unavailable_reason IS NULL THEN source.realized_pnl_account-source.commission_account-round(profile.commission_aud_per_standard_lot_per_side*source.volume_lots,2)-round(profile.commission_aud_per_standard_lot_per_side*source.volume_lots,2) END,
  CASE WHEN source.unavailable_reason IS NULL THEN 'APPLIED' ELSE 'UNAVAILABLE' END,source.unavailable_reason,source.source_fingerprint,'forex.m33.daily-coverage.v1'
 FROM forex.demo_m33_daily_coverage_source source JOIN forex.demo_pricing_profile profile ON profile.profile_version_id='GO_PLUS_AUD_V1'
 ON CONFLICT (proposal_id,profile_version_id,calculation_version,source_fingerprint) DO NOTHING;
END $$;

DROP TRIGGER IF EXISTS demo_trade_outcome_m33_daily_coverage_refresh ON forex.demo_trade_outcome;
CREATE OR REPLACE FUNCTION forex.refresh_demo_m33_daily_commission_coverage_trigger()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 PERFORM forex.refresh_demo_m33_daily_commission_coverage();
 RETURN NEW;
END $$;
CREATE TRIGGER demo_trade_outcome_m33_daily_coverage_refresh AFTER INSERT ON forex.demo_trade_outcome
FOR EACH STATEMENT EXECUTE FUNCTION forex.refresh_demo_m33_daily_commission_coverage_trigger();
SELECT forex.refresh_demo_m33_daily_commission_coverage();

CREATE OR REPLACE VIEW forex.demo_m33_daily_commission_coverage AS
SELECT DISTINCT ON (source.proposal_id) source.proposal_id,source.closed_at_utc,source.server,source.instrument,
 coverage.actual_broker_net_aud,coverage.actual_broker_commission_aud,coverage.broker_fee_aud,coverage.broker_swap_aud,
 coverage.volume_lots,coverage.expected_round_trip_commission_aud,coverage.commission_adjusted_pnl_aud,
 coverage.coverage_status,coverage.unavailable_reason,coverage.profile_version_id,coverage.calculation_version,coverage.calculated_at_utc
FROM forex.demo_m33_daily_coverage_source source
JOIN forex.demo_trade_commission_coverage coverage ON coverage.proposal_id=source.proposal_id AND coverage.source_fingerprint=source.source_fingerprint AND coverage.calculation_version='forex.m33.daily-coverage.v1'
ORDER BY source.proposal_id,coverage.calculated_at_utc DESC;
COMMIT;
