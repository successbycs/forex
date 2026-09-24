-- M33 broker-wide P&L journal.  Raw history snapshots and deal observations are
-- append-only.  The selected-day view uses the newest observed revision per MT5 deal.
BEGIN;

CREATE TABLE IF NOT EXISTS forex.demo_trade_pnl_capture (
    capture_id TEXT PRIMARY KEY,
    account_scope_sha256 TEXT NOT NULL CHECK (account_scope_sha256 ~ '^sha256:[0-9a-f]{64}$'),
    captured_at_utc TIMESTAMPTZ NOT NULL,
    account_balance_aud NUMERIC(14,2) NOT NULL,
    account_currency TEXT NOT NULL CHECK (account_currency='AUD'),
    deal_count INTEGER NOT NULL CHECK (deal_count >= 0 AND deal_count <= 10000),
    source_history_sha256 TEXT NOT NULL CHECK (source_history_sha256 ~ '^sha256:[0-9a-f]{64}$'),
    collection_version TEXT NOT NULL,
    raw_history JSONB NOT NULL,
    created_at_utc TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (account_scope_sha256, source_history_sha256)
);
DROP TRIGGER IF EXISTS demo_trade_pnl_capture_immutable ON forex.demo_trade_pnl_capture;
CREATE TRIGGER demo_trade_pnl_capture_immutable BEFORE UPDATE OR DELETE ON forex.demo_trade_pnl_capture
FOR EACH ROW EXECUTE FUNCTION forex.reject_demo_audit_mutation();

CREATE TABLE IF NOT EXISTS forex.demo_trade_pnl (
    pnl_id TEXT PRIMARY KEY,
    account_scope_sha256 TEXT NOT NULL CHECK (account_scope_sha256 ~ '^sha256:[0-9a-f]{64}$'),
    deal_ticket BIGINT NOT NULL CHECK (deal_ticket > 0),
    source_capture_id TEXT NOT NULL REFERENCES forex.demo_trade_pnl_capture(capture_id) ON DELETE RESTRICT,
    source_deal_sha256 TEXT NOT NULL CHECK (source_deal_sha256 ~ '^sha256:[0-9a-f]{64}$'),
    broker_time_utc TIMESTAMPTZ NOT NULL,
    occurred_at_utc TIMESTAMPTZ NOT NULL,
    entry_code SMALLINT NOT NULL,
    deal_type_code SMALLINT NOT NULL,
    event_kind TEXT NOT NULL CHECK (event_kind IN ('OPEN','CLOSE','INOUT','CLOSE_BY','BALANCE','OTHER')),
    side TEXT CHECK (side IN ('BUY','SELL')),
    position_identifier BIGINT,
    volume_lots NUMERIC(12,4) NOT NULL CHECK (volume_lots >= 0),
    price NUMERIC(14,5) NOT NULL CHECK (price >= 0),
    broker_commission_aud NUMERIC(14,2) NOT NULL,
    broker_fee_aud NUMERIC(14,2) NOT NULL,
    broker_swap_aud NUMERIC(14,2) NOT NULL,
    trade_pnl_aud NUMERIC(14,2) NOT NULL,
    net_movement_aud NUMERIC(14,2) NOT NULL,
    expected_live_commission_aud NUMERIC(14,2),
    commission_adjusted_net_aud NUMERIC(14,2),
    balance_before_aud NUMERIC(14,2) NOT NULL,
    balance_after_aud NUMERIC(14,2) NOT NULL,
    account_currency TEXT NOT NULL CHECK (account_currency='AUD'),
    collection_version TEXT NOT NULL,
    observed_at_utc TIMESTAMPTZ NOT NULL,
    created_at_utc TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (account_scope_sha256, deal_ticket, source_deal_sha256),
    CHECK (balance_after_aud = balance_before_aud + net_movement_aud),
    CHECK ((expected_live_commission_aud IS NULL AND commission_adjusted_net_aud IS NULL)
        OR (expected_live_commission_aud IS NOT NULL AND commission_adjusted_net_aud = net_movement_aud + expected_live_commission_aud))
);
DROP TRIGGER IF EXISTS demo_trade_pnl_immutable ON forex.demo_trade_pnl;
CREATE TRIGGER demo_trade_pnl_immutable BEFORE UPDATE OR DELETE ON forex.demo_trade_pnl
FOR EACH ROW EXECUTE FUNCTION forex.reject_demo_audit_mutation();

CREATE INDEX IF NOT EXISTS demo_trade_pnl_current_day_idx
ON forex.demo_trade_pnl (account_scope_sha256, occurred_at_utc, observed_at_utc DESC, deal_ticket);

CREATE OR REPLACE VIEW forex.demo_m33_current_trade_pnl AS
SELECT DISTINCT ON (account_scope_sha256, deal_ticket)
    pnl.*
FROM forex.demo_trade_pnl pnl
ORDER BY account_scope_sha256, deal_ticket, observed_at_utc DESC, created_at_utc DESC;
COMMIT;
