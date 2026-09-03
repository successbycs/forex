-- M20: bounded Demo-only trading audit.  This is intentionally separate from
-- M19's immutable historical research lineage, which remains non-executing.

BEGIN;

CREATE TABLE IF NOT EXISTS forex.demo_trade_session (
    session_id TEXT PRIMARY KEY,
    operator_label TEXT NOT NULL,
    server TEXT NOT NULL CHECK (server = 'GOMarketsMU-Demo'),
    instrument TEXT NOT NULL CHECK (instrument = 'EURUSD'),
    starts_at_utc TIMESTAMPTZ NOT NULL,
    expires_at_utc TIMESTAMPTZ NOT NULL CHECK (expires_at_utc > starts_at_utc),
    max_trades INTEGER NOT NULL CHECK (max_trades BETWEEN 1 AND 10),
    max_notional_usd NUMERIC(12,2) NOT NULL CHECK (max_notional_usd > 0 AND max_notional_usd <= 100.00),
    max_cumulative_notional_usd NUMERIC(12,2) NOT NULL CHECK (max_cumulative_notional_usd > 0 AND max_cumulative_notional_usd <= 1000.00),
    max_open_positions INTEGER NOT NULL DEFAULT 1 CHECK (max_open_positions = 1),
    status TEXT NOT NULL CHECK (status IN ('ACTIVE', 'PAUSED', 'EXPIRED', 'CLOSED')),
    strategy_version TEXT NOT NULL,
    application_revision TEXT NOT NULL,
    configuration_fingerprint TEXT NOT NULL CHECK (configuration_fingerprint ~ '^sha256:[0-9a-f]{64}$'),
    created_at_utc TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (expires_at_utc <= starts_at_utc + INTERVAL '60 minutes')
);

CREATE TABLE IF NOT EXISTS forex.demo_trade_slot (
    session_id TEXT NOT NULL REFERENCES forex.demo_trade_session(session_id) ON DELETE RESTRICT,
    slot_number INTEGER NOT NULL CHECK (slot_number BETWEEN 1 AND 10),
    claimed_at_utc TIMESTAMPTZ,
    proposal_id TEXT,
    PRIMARY KEY (session_id, slot_number),
    UNIQUE (proposal_id)
);

CREATE TABLE IF NOT EXISTS forex.demo_trade_proposal (
    proposal_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES forex.demo_trade_session(session_id) ON DELETE RESTRICT,
    decision_at_utc TIMESTAMPTZ NOT NULL,
    expires_at_utc TIMESTAMPTZ NOT NULL CHECK (expires_at_utc >= decision_at_utc),
    selected_timeframe TEXT NOT NULL CHECK (selected_timeframe IN ('M1', 'M5')),
    action TEXT NOT NULL CHECK (action IN ('BUY', 'SELL', 'NO_TRADE')),
    proposed_entry NUMERIC(16,8),
    stop_loss NUMERIC(16,8),
    take_profit NUMERIC(16,8),
    notional_usd NUMERIC(12,2) CHECK (notional_usd > 0 AND notional_usd <= 100.00),
    confidence NUMERIC(5,2) NOT NULL CHECK (confidence BETWEEN 0 AND 100),
    rationale TEXT NOT NULL,
    decision_snapshot_sha256 TEXT NOT NULL CHECK (decision_snapshot_sha256 ~ '^sha256:[0-9a-f]{64}$'),
    strategy_version TEXT NOT NULL,
    application_revision TEXT NOT NULL,
    configuration_fingerprint TEXT NOT NULL CHECK (configuration_fingerprint ~ '^sha256:[0-9a-f]{64}$'),
    created_at_utc TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK ((action = 'NO_TRADE' AND proposed_entry IS NULL AND stop_loss IS NULL AND take_profit IS NULL AND notional_usd IS NULL)
        OR (action IN ('BUY', 'SELL') AND proposed_entry IS NOT NULL AND stop_loss IS NOT NULL AND take_profit IS NOT NULL AND notional_usd IS NOT NULL))
);

CREATE TABLE IF NOT EXISTS forex.demo_decision_snapshot (
    snapshot_id TEXT PRIMARY KEY,
    proposal_id TEXT NOT NULL UNIQUE REFERENCES forex.demo_trade_proposal(proposal_id) ON DELETE RESTRICT,
    observed_at_utc TIMESTAMPTZ NOT NULL,
    captured_at_utc TIMESTAMPTZ NOT NULL,
    bid NUMERIC(16,8) NOT NULL CHECK (bid > 0),
    ask NUMERIC(16,8) NOT NULL CHECK (ask >= bid),
    spread_points NUMERIC(16,4) NOT NULL CHECK (spread_points >= 0),
    m1_closed_bars JSONB NOT NULL,
    m5_closed_bars JSONB NOT NULL,
    news_context JSONB NOT NULL DEFAULT '{}'::jsonb,
    freshness_seconds INTEGER NOT NULL CHECK (freshness_seconds >= 0),
    payload_sha256 TEXT NOT NULL CHECK (payload_sha256 ~ '^sha256:[0-9a-f]{64}$'),
    CHECK (jsonb_typeof(m1_closed_bars) = 'array'),
    CHECK (jsonb_typeof(m5_closed_bars) = 'array'),
    CHECK (jsonb_typeof(news_context) = 'object')
);

CREATE TABLE IF NOT EXISTS forex.demo_execution_attempt (
    attempt_id TEXT PRIMARY KEY,
    proposal_id TEXT NOT NULL UNIQUE REFERENCES forex.demo_trade_proposal(proposal_id) ON DELETE RESTRICT,
    session_id TEXT NOT NULL REFERENCES forex.demo_trade_session(session_id) ON DELETE RESTRICT,
    slot_number INTEGER NOT NULL,
    idempotency_key TEXT NOT NULL UNIQUE,
    submitted_at_utc TIMESTAMPTZ NOT NULL,
    acknowledged_at_utc TIMESTAMPTZ,
    status TEXT NOT NULL CHECK (status IN ('SUBMITTED', 'ACCEPTED', 'REJECTED', 'FAILED')),
    broker_order_reference TEXT,
    redacted_result TEXT NOT NULL,
    FOREIGN KEY (session_id, slot_number) REFERENCES forex.demo_trade_slot(session_id, slot_number)
);

CREATE TABLE IF NOT EXISTS forex.demo_position_event (
    event_id TEXT PRIMARY KEY,
    attempt_id TEXT NOT NULL REFERENCES forex.demo_execution_attempt(attempt_id) ON DELETE RESTRICT,
    event_type TEXT NOT NULL CHECK (event_type IN ('OPENED', 'UPDATED', 'CLOSED', 'REJECTED', 'FAILED')),
    observed_at_utc TIMESTAMPTZ NOT NULL,
    price NUMERIC(16,8),
    payload_sha256 TEXT NOT NULL CHECK (payload_sha256 ~ '^sha256:[0-9a-f]{64}$'),
    payload JSONB NOT NULL CHECK (jsonb_typeof(payload) = 'object')
);

CREATE TABLE IF NOT EXISTS forex.demo_trade_outcome (
    proposal_id TEXT PRIMARY KEY REFERENCES forex.demo_trade_proposal(proposal_id) ON DELETE RESTRICT,
    closed_at_utc TIMESTAMPTZ NOT NULL,
    exit_price NUMERIC(16,8) NOT NULL CHECK (exit_price > 0),
    realized_pnl_usd NUMERIC(14,2) NOT NULL,
    close_reason TEXT NOT NULL,
    reconciliation_status TEXT NOT NULL CHECK (reconciliation_status IN ('MATCHED', 'MISMATCH', 'PENDING')),
    created_at_utc TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE OR REPLACE FUNCTION forex.reject_demo_audit_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'M20 Demo trading audit rows are append-only';
END;
$$;

DROP TRIGGER IF EXISTS demo_trade_proposal_immutable ON forex.demo_trade_proposal;
CREATE TRIGGER demo_trade_proposal_immutable BEFORE UPDATE OR DELETE ON forex.demo_trade_proposal
FOR EACH ROW EXECUTE FUNCTION forex.reject_demo_audit_mutation();
DROP TRIGGER IF EXISTS demo_decision_snapshot_immutable ON forex.demo_decision_snapshot;
CREATE TRIGGER demo_decision_snapshot_immutable BEFORE UPDATE OR DELETE ON forex.demo_decision_snapshot
FOR EACH ROW EXECUTE FUNCTION forex.reject_demo_audit_mutation();
DROP TRIGGER IF EXISTS demo_execution_attempt_immutable ON forex.demo_execution_attempt;
CREATE TRIGGER demo_execution_attempt_immutable BEFORE UPDATE OR DELETE ON forex.demo_execution_attempt
FOR EACH ROW EXECUTE FUNCTION forex.reject_demo_audit_mutation();
DROP TRIGGER IF EXISTS demo_position_event_immutable ON forex.demo_position_event;
CREATE TRIGGER demo_position_event_immutable BEFORE UPDATE OR DELETE ON forex.demo_position_event
FOR EACH ROW EXECUTE FUNCTION forex.reject_demo_audit_mutation();
DROP TRIGGER IF EXISTS demo_trade_outcome_immutable ON forex.demo_trade_outcome;
CREATE TRIGGER demo_trade_outcome_immutable BEFORE UPDATE OR DELETE ON forex.demo_trade_outcome
FOR EACH ROW EXECUTE FUNCTION forex.reject_demo_audit_mutation();

COMMIT;
