-- M33 repair: project each newly inserted immutable Demo outcome as soon as it
-- is eligible. Existing broker evidence remains append-only; the projection
-- table remains immutable and source-versioned.
BEGIN;

-- Replace the initial backfill source view with the ongoing-safe version.
-- Exactly one FULL opening event with a parseable positive volume is required;
-- partial, multiple or malformed fills are unavailable rather than errors.
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
    'sha256:' || encode(digest(concat_ws('|', proposal.proposal_id,
        opening.volume_lots::TEXT, outcome.closed_at_utc::TEXT,
        outcome.gross_price_pnl_account::TEXT, outcome.commission_account::TEXT,
        outcome.fee_account::TEXT, outcome.swap_account::TEXT,
        outcome.realized_pnl_account::TEXT, opening.payload_sha256), 'sha256'), 'hex')
      AS canonical_source_fingerprint
FROM forex.demo_trade_outcome outcome
JOIN forex.demo_trade_proposal proposal ON proposal.proposal_id = outcome.proposal_id
JOIN forex.demo_trade_session session ON session.session_id = proposal.session_id
JOIN forex.demo_execution_attempt attempt ON attempt.proposal_id = proposal.proposal_id
JOIN LATERAL (
    SELECT
        MAX(CASE WHEN event.payload->>'volume' ~ '^[0-9]+(\.[0-9]{1,4})?$'
                 THEN (event.payload->>'volume')::NUMERIC(12, 4) END) AS volume_lots,
        MIN(event.payload_sha256) AS payload_sha256
    FROM forex.demo_position_event event
    WHERE event.attempt_id = attempt.attempt_id AND event.event_type = 'OPENED'
    HAVING COUNT(*) = 1
       AND MIN(event.payload->>'fill_status') = 'FULL'
       AND MIN(event.payload->>'volume') ~ '^[0-9]+(\.[0-9]{1,4})?$'
       AND MAX(CASE WHEN event.payload->>'volume' ~ '^[0-9]+(\.[0-9]{1,4})?$'
                    THEN (event.payload->>'volume')::NUMERIC(12, 4) END) > 0
) opening ON true
LEFT JOIN LATERAL (
    SELECT revision.disposition
    FROM forex.demo_outcome_reconciliation_revision revision
    WHERE revision.proposal_id = proposal.proposal_id
    ORDER BY revision.observed_at_utc DESC, revision.created_at_utc DESC LIMIT 1
) latest_revision ON true
WHERE session.server = 'GOMarketsMU-Demo' AND session.instrument = 'EURUSD'
  AND proposal.action IN ('BUY', 'SELL') AND outcome.reconciliation_status = 'MATCHED'
  AND latest_revision.disposition IS NULL AND outcome.account_currency = 'AUD'
  AND outcome.gross_price_pnl_account IS NOT NULL AND outcome.commission_account IS NOT NULL
  AND outcome.fee_account IS NOT NULL AND outcome.swap_account IS NOT NULL
  AND outcome.realized_pnl_account IS NOT NULL
  AND outcome.realized_pnl_account = outcome.gross_price_pnl_account
      + outcome.commission_account + outcome.fee_account + outcome.swap_account;

CREATE OR REPLACE FUNCTION forex.refresh_demo_m33_pro_forma_commission()
RETURNS void LANGUAGE plpgsql AS $$
BEGIN
    INSERT INTO forex.demo_trade_pro_forma_pnl (
        projection_id, proposal_id, profile_version_id, volume_lots,
        actual_broker_commission_aud, estimated_open_commission_aud,
        estimated_close_commission_aud, estimated_round_trip_commission_aud,
        gross_price_pnl_aud, broker_fee_aud, broker_swap_aud,
        actual_broker_net_aud, pro_forma_live_pnl_aud,
        source_reconciliation_id, canonical_source_fingerprint,
        calculation_version
    )
    SELECT
        'M33-' || source.proposal_id || '-' || profile.profile_version_id || '-'
            || substring(source.canonical_source_fingerprint FROM 8),
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
    JOIN forex.demo_pricing_profile profile
      ON profile.profile_version_id = 'GO_PLUS_AUD_V1'
    ON CONFLICT (proposal_id, profile_version_id, calculation_version,
                 canonical_source_fingerprint) DO NOTHING;
END;
$$;

CREATE OR REPLACE FUNCTION forex.refresh_demo_m33_pro_forma_commission_trigger()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    PERFORM forex.refresh_demo_m33_pro_forma_commission();
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS demo_trade_outcome_m33_pro_forma_refresh
    ON forex.demo_trade_outcome;
CREATE TRIGGER demo_trade_outcome_m33_pro_forma_refresh
AFTER INSERT ON forex.demo_trade_outcome
FOR EACH STATEMENT EXECUTE FUNCTION forex.refresh_demo_m33_pro_forma_commission_trigger();

SELECT forex.refresh_demo_m33_pro_forma_commission();

COMMIT;
