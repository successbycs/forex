-- M20.12: immutable, read-only M5/H1 context captured alongside each M1
-- proposal.  This intentionally does not alter a proposal, selection, order,
-- position, or outcome.  Historical proposals are deliberately not inferred
-- or backfilled.

BEGIN;

CREATE TABLE IF NOT EXISTS forex.demo_multi_timeframe_context (
    context_id TEXT PRIMARY KEY,
    proposal_id TEXT NOT NULL UNIQUE REFERENCES forex.demo_trade_proposal(proposal_id) ON DELETE RESTRICT,
    selected_m1_action TEXT NOT NULL CHECK (selected_m1_action IN ('BUY', 'SELL', 'NO_TRADE')),
    overall_alignment TEXT NOT NULL CHECK (overall_alignment IN ('ALIGNED', 'NEUTRAL', 'OPPOSED', 'UNAVAILABLE', 'NOT_APPLICABLE')),
    context_disposition TEXT NOT NULL CHECK (context_disposition IN ('OBSERVE_ONLY', 'NEUTRAL', 'HARD_CONFLICT')),
    reason TEXT NOT NULL,
    rule_version TEXT NOT NULL,
    retrieved_at_utc TIMESTAMPTZ NOT NULL,
    source_inputs_sha256 TEXT NOT NULL CHECK (source_inputs_sha256 ~ '^sha256:[0-9a-f]{64}$'),
    created_at_utc TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (context_disposition <> 'HARD_CONFLICT' OR overall_alignment = 'OPPOSED')
);

CREATE TABLE IF NOT EXISTS forex.demo_multi_timeframe_context_bar (
    context_id TEXT NOT NULL REFERENCES forex.demo_multi_timeframe_context(context_id) ON DELETE RESTRICT,
    timeframe TEXT NOT NULL CHECK (timeframe IN ('M5', 'H1')),
    closed_at_utc TIMESTAMPTZ,
    data_age_seconds INTEGER CHECK (data_age_seconds >= 0),
    integrity_status TEXT NOT NULL CHECK (integrity_status IN ('VALID', 'STALE', 'UNAVAILABLE', 'INVALID')),
    market_state TEXT NOT NULL CHECK (market_state IN ('BULLISH', 'BEARISH', 'RANGE', 'MIXED', 'UNKNOWN')),
    volatility_state TEXT NOT NULL CHECK (volatility_state IN ('LOW', 'NORMAL', 'HIGH', 'UNKNOWN')),
    liquidity_state TEXT NOT NULL CHECK (liquidity_state IN ('LIQUID', 'THIN', 'UNKNOWN')),
    alignment TEXT NOT NULL CHECK (alignment IN ('ALIGNED', 'NEUTRAL', 'OPPOSED', 'UNAVAILABLE', 'NOT_APPLICABLE')),
    reason TEXT NOT NULL,
    source_inputs JSONB NOT NULL CHECK (jsonb_typeof(source_inputs) = 'object'),
    PRIMARY KEY (context_id, timeframe),
    CHECK (
        (integrity_status IN ('VALID', 'STALE') AND closed_at_utc IS NOT NULL AND data_age_seconds IS NOT NULL)
        OR (integrity_status IN ('UNAVAILABLE', 'INVALID') AND closed_at_utc IS NULL AND data_age_seconds IS NULL)
    ),
    CHECK (
        (integrity_status IN ('UNAVAILABLE', 'INVALID') AND market_state = 'UNKNOWN'
            AND volatility_state = 'UNKNOWN' AND liquidity_state = 'UNKNOWN'
            AND alignment = 'UNAVAILABLE')
        OR integrity_status IN ('VALID', 'STALE')
    )
);

CREATE OR REPLACE FUNCTION forex.reject_demo_multi_timeframe_context_cardinality()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF (SELECT count(*) FROM forex.demo_multi_timeframe_context_bar
        WHERE context_id = NEW.context_id) <> 2 THEN
        RAISE EXCEPTION 'M20.12 context requires exactly M5 and H1 rows';
    END IF;
    IF (SELECT action FROM forex.demo_trade_proposal WHERE proposal_id = NEW.proposal_id)
        <> NEW.selected_m1_action THEN
        RAISE EXCEPTION 'M20.12 context cannot alter the linked M1 proposal action';
    END IF;
    RETURN NEW;
END;
$$;

-- The parent is inserted before its two immutable rows by the fixed bridge,
-- so enforce cardinality at transaction commit rather than halfway through
-- the append-only write.
DROP TRIGGER IF EXISTS demo_multi_timeframe_context_cardinality ON forex.demo_multi_timeframe_context;
CREATE CONSTRAINT TRIGGER demo_multi_timeframe_context_cardinality
AFTER INSERT ON forex.demo_multi_timeframe_context
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION forex.reject_demo_multi_timeframe_context_cardinality();

DROP TRIGGER IF EXISTS demo_multi_timeframe_context_immutable ON forex.demo_multi_timeframe_context;
CREATE TRIGGER demo_multi_timeframe_context_immutable
BEFORE UPDATE OR DELETE ON forex.demo_multi_timeframe_context
FOR EACH ROW EXECUTE FUNCTION forex.reject_demo_audit_mutation();

DROP TRIGGER IF EXISTS demo_multi_timeframe_context_exactly_m5_h1 ON forex.demo_multi_timeframe_context;
CREATE CONSTRAINT TRIGGER demo_multi_timeframe_context_exactly_m5_h1
AFTER INSERT ON forex.demo_multi_timeframe_context
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION forex.reject_demo_multi_timeframe_context_cardinality();

DROP TRIGGER IF EXISTS demo_multi_timeframe_context_bar_immutable ON forex.demo_multi_timeframe_context_bar;
CREATE TRIGGER demo_multi_timeframe_context_bar_immutable
BEFORE UPDATE OR DELETE ON forex.demo_multi_timeframe_context_bar
FOR EACH ROW EXECUTE FUNCTION forex.reject_demo_audit_mutation();

COMMIT;
