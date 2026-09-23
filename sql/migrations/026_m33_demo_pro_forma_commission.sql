-- M33: immutable commission-only comparison for closed, attributable Demo
-- trades. It deliberately leaves broker outcomes and the existing ledger view
-- unchanged. GO_PLUS_AUD_V1 is an assumed comparison schedule, not the MT5
-- account's discovered profile and not a Live P&L claim.

BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS forex.demo_pricing_profile (
    profile_version_id TEXT PRIMARY KEY,
    scenario_id TEXT NOT NULL,
    account_currency TEXT NOT NULL CHECK (account_currency = 'AUD'),
    instrument TEXT NOT NULL CHECK (instrument = 'EURUSD'),
    commission_aud_per_standard_lot_per_side NUMERIC(14, 4) NOT NULL CHECK (commission_aud_per_standard_lot_per_side >= 0),
    standard_lot_units INTEGER NOT NULL CHECK (standard_lot_units = 100000),
    source_url TEXT NOT NULL,
    source_retrieved_at_utc TIMESTAMPTZ NOT NULL,
    source_content_sha256 TEXT NOT NULL CHECK (source_content_sha256 ~ '^sha256:[0-9a-f]{64}$'),
    publisher_entity TEXT NOT NULL,
    jurisdiction TEXT NOT NULL,
    assumed_or_verified TEXT NOT NULL CHECK (assumed_or_verified IN ('ASSUMED', 'VERIFIED')),
    created_at_utc TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS forex.demo_trade_pro_forma_pnl (
    projection_id TEXT PRIMARY KEY,
    proposal_id TEXT NOT NULL REFERENCES forex.demo_trade_proposal(proposal_id) ON DELETE RESTRICT,
    profile_version_id TEXT NOT NULL REFERENCES forex.demo_pricing_profile(profile_version_id) ON DELETE RESTRICT,
    volume_lots NUMERIC(12, 4) NOT NULL CHECK (volume_lots > 0),
    actual_broker_commission_aud NUMERIC(14, 2) NOT NULL,
    estimated_open_commission_aud NUMERIC(14, 2) NOT NULL CHECK (estimated_open_commission_aud <= 0),
    estimated_close_commission_aud NUMERIC(14, 2) NOT NULL CHECK (estimated_close_commission_aud <= 0),
    estimated_round_trip_commission_aud NUMERIC(14, 2) NOT NULL CHECK (estimated_round_trip_commission_aud = estimated_open_commission_aud + estimated_close_commission_aud),
    gross_price_pnl_aud NUMERIC(14, 2) NOT NULL,
    broker_fee_aud NUMERIC(14, 2) NOT NULL,
    broker_swap_aud NUMERIC(14, 2) NOT NULL,
    actual_broker_net_aud NUMERIC(14, 2) NOT NULL,
    pro_forma_live_pnl_aud NUMERIC(14, 2) NOT NULL,
    source_reconciliation_id TEXT NOT NULL,
    canonical_source_fingerprint TEXT NOT NULL CHECK (canonical_source_fingerprint ~ '^sha256:[0-9a-f]{64}$'),
    calculation_version TEXT NOT NULL,
    calculated_at_utc TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (proposal_id, profile_version_id, calculation_version, canonical_source_fingerprint),
    CHECK (pro_forma_live_pnl_aud = actual_broker_net_aud - actual_broker_commission_aud + estimated_round_trip_commission_aud)
);

DROP TRIGGER IF EXISTS demo_pricing_profile_immutable ON forex.demo_pricing_profile;
CREATE TRIGGER demo_pricing_profile_immutable BEFORE UPDATE OR DELETE ON forex.demo_pricing_profile
FOR EACH ROW EXECUTE FUNCTION forex.reject_demo_audit_mutation();
DROP TRIGGER IF EXISTS demo_trade_pro_forma_pnl_immutable ON forex.demo_trade_pro_forma_pnl;
CREATE TRIGGER demo_trade_pro_forma_pnl_immutable BEFORE UPDATE OR DELETE ON forex.demo_trade_pro_forma_pnl
FOR EACH ROW EXECUTE FUNCTION forex.reject_demo_audit_mutation();

INSERT INTO forex.demo_pricing_profile (
    profile_version_id, scenario_id, account_currency, instrument,
    commission_aud_per_standard_lot_per_side, standard_lot_units, source_url,
    source_retrieved_at_utc, source_content_sha256, publisher_entity,
    jurisdiction, assumed_or_verified
) VALUES (
    'GO_PLUS_AUD_V1', 'GO_PLUS_AUD', 'AUD', 'EURUSD', 3.0000, 100000,
    'https://www.gomarkets.com/en-au/accounts-and-pricing/spreads-and-fees',
    '2026-09-23T03:40:00Z',
    'sha256:423c196efe9e32b747171816a316faa77f2f4cf0eff37f18ac79f546bec7ae9c',
    'GO Markets',
    'Australia pricing page; not proof of the current Mauritius Demo account terms',
    'ASSUMED'
) ON CONFLICT (profile_version_id) DO NOTHING;

-- A source row is eligible only when the un-repaired broker outcome is complete,
-- a single full opening fill records the complete volume, and all actual signed
-- cost components reconcile exactly to broker net. Repaired/partial/unknown
-- rows are intentionally absent rather than simulated.
CREATE OR REPLACE VIEW forex.demo_m33_closed_trade_source AS
SELECT
    proposal.proposal_id,
    opening.volume_lots,
    outcome.commission_account AS actual_broker_commission_aud,
    outcome.gross_price_pnl_account AS gross_price_pnl_aud,
    outcome.fee_account AS broker_fee_aud,
    outcome.swap_account AS broker_swap_aud,
    outcome.realized_pnl_account AS actual_broker_net_aud,
    'BASE_OUTCOME_V1'::TEXT AS source_reconciliation_id,
    'sha256:' || encode(digest(concat_ws('|',
        proposal.proposal_id,
        opening.volume_lots::TEXT,
        outcome.closed_at_utc::TEXT,
        outcome.gross_price_pnl_account::TEXT,
        outcome.commission_account::TEXT,
        outcome.fee_account::TEXT,
        outcome.swap_account::TEXT,
        outcome.realized_pnl_account::TEXT,
        opening.payload_sha256
    ), 'sha256'), 'hex') AS canonical_source_fingerprint
FROM forex.demo_trade_outcome outcome
JOIN forex.demo_trade_proposal proposal ON proposal.proposal_id = outcome.proposal_id
JOIN forex.demo_trade_session session ON session.session_id = proposal.session_id
JOIN forex.demo_execution_attempt attempt ON attempt.proposal_id = proposal.proposal_id
JOIN LATERAL (
    SELECT (event.payload->>'volume')::NUMERIC(12, 4) AS volume_lots,
           event.payload_sha256,
           event.payload
    FROM forex.demo_position_event event
    WHERE event.attempt_id = attempt.attempt_id AND event.event_type = 'OPENED'
    ORDER BY event.observed_at_utc, event.event_id
    LIMIT 1
) opening ON true
LEFT JOIN LATERAL (
    SELECT revision.disposition
    FROM forex.demo_outcome_reconciliation_revision revision
    WHERE revision.proposal_id = proposal.proposal_id
    ORDER BY revision.observed_at_utc DESC, revision.created_at_utc DESC
    LIMIT 1
) latest_revision ON true
WHERE session.server = 'GOMarketsMU-Demo'
  AND session.instrument = 'EURUSD'
  AND proposal.action IN ('BUY', 'SELL')
  AND outcome.reconciliation_status = 'MATCHED'
  AND latest_revision.disposition IS NULL
  AND opening.payload->>'fill_status' = 'FULL'
  AND outcome.account_currency = 'AUD'
  AND outcome.gross_price_pnl_account IS NOT NULL
  AND outcome.commission_account IS NOT NULL
  AND outcome.fee_account IS NOT NULL
  AND outcome.swap_account IS NOT NULL
  AND outcome.realized_pnl_account IS NOT NULL
  AND outcome.realized_pnl_account = outcome.gross_price_pnl_account
      + outcome.commission_account + outcome.fee_account + outcome.swap_account;

INSERT INTO forex.demo_trade_pro_forma_pnl (
    projection_id, proposal_id, profile_version_id, volume_lots,
    actual_broker_commission_aud, estimated_open_commission_aud,
    estimated_close_commission_aud, estimated_round_trip_commission_aud,
    gross_price_pnl_aud, broker_fee_aud, broker_swap_aud, actual_broker_net_aud,
    pro_forma_live_pnl_aud, source_reconciliation_id,
    canonical_source_fingerprint, calculation_version
)
SELECT
    'M33-' || source.proposal_id || '-' || profile.profile_version_id || '-' || substring(source.canonical_source_fingerprint FROM 8),
    source.proposal_id, profile.profile_version_id, source.volume_lots,
    source.actual_broker_commission_aud,
    -ROUND(profile.commission_aud_per_standard_lot_per_side * source.volume_lots, 2),
    -ROUND(profile.commission_aud_per_standard_lot_per_side * source.volume_lots, 2),
    -ROUND(profile.commission_aud_per_standard_lot_per_side * source.volume_lots, 2)
      + -ROUND(profile.commission_aud_per_standard_lot_per_side * source.volume_lots, 2),
    source.gross_price_pnl_aud, source.broker_fee_aud, source.broker_swap_aud,
    source.actual_broker_net_aud,
    source.actual_broker_net_aud - source.actual_broker_commission_aud
      + (-ROUND(profile.commission_aud_per_standard_lot_per_side * source.volume_lots, 2)
      + -ROUND(profile.commission_aud_per_standard_lot_per_side * source.volume_lots, 2)),
    source.source_reconciliation_id, source.canonical_source_fingerprint,
    'forex.m33.pro-forma-commission.v1'
FROM forex.demo_m33_closed_trade_source source
JOIN forex.demo_pricing_profile profile ON profile.profile_version_id = 'GO_PLUS_AUD_V1'
ON CONFLICT (proposal_id, profile_version_id, calculation_version, canonical_source_fingerprint) DO NOTHING;

CREATE OR REPLACE VIEW forex.demo_m33_pro_forma_ledger AS
SELECT
    source.proposal_id, projection.profile_version_id,
    profile.assumed_or_verified, profile.commission_aud_per_standard_lot_per_side,
    projection.volume_lots, projection.actual_broker_commission_aud,
    projection.estimated_open_commission_aud,
    projection.estimated_close_commission_aud,
    projection.estimated_round_trip_commission_aud,
    projection.actual_broker_net_aud, projection.pro_forma_live_pnl_aud,
    projection.source_reconciliation_id, projection.canonical_source_fingerprint,
    projection.calculation_version, projection.calculated_at_utc
FROM forex.demo_m33_closed_trade_source source
JOIN forex.demo_trade_pro_forma_pnl projection
  ON projection.proposal_id = source.proposal_id
 AND projection.canonical_source_fingerprint = source.canonical_source_fingerprint
 AND projection.calculation_version = 'forex.m33.pro-forma-commission.v1'
JOIN forex.demo_pricing_profile profile
  ON profile.profile_version_id = projection.profile_version_id
WHERE projection.profile_version_id = 'GO_PLUS_AUD_V1';

COMMIT;
