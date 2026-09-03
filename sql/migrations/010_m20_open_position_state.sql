-- Durable, mutable projection of the one permitted active M20 Demo position.
-- Append-only events remain the audit record; this table supports restart-safe
-- monitoring and is removed only after a verified closed outcome is recorded.
BEGIN;

CREATE TABLE IF NOT EXISTS forex.demo_open_position_state (
    proposal_id TEXT PRIMARY KEY REFERENCES forex.demo_trade_proposal(proposal_id) ON DELETE RESTRICT,
    attempt_id TEXT NOT NULL UNIQUE REFERENCES forex.demo_execution_attempt(attempt_id) ON DELETE RESTRICT,
    position_ticket BIGINT NOT NULL UNIQUE CHECK (position_ticket > 0),
    action TEXT NOT NULL CHECK (action IN ('BUY', 'SELL')),
    opened_at_utc TIMESTAMPTZ NOT NULL,
    observed_at_utc TIMESTAMPTZ NOT NULL,
    entry_price NUMERIC(16,8) NOT NULL CHECK (entry_price > 0),
    stop_loss NUMERIC(16,8) NOT NULL CHECK (stop_loss > 0),
    take_profit NUMERIC(16,8) NOT NULL CHECK (take_profit > 0),
    break_even_applied BOOLEAN NOT NULL DEFAULT FALSE,
    status TEXT NOT NULL CHECK (status IN ('OPEN', 'MONITORING')),
    updated_at_utc TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS demo_open_position_state_active_idx
    ON forex.demo_open_position_state (status, observed_at_utc);

COMMIT;
