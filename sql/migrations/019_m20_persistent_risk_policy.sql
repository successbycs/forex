-- Durable conservative-risk state. It is mutable operational state, separate
-- from the append-only execution ledger and evaluated before every entry.
BEGIN;

CREATE TABLE IF NOT EXISTS forex.demo_risk_policy_state (
    policy_version TEXT PRIMARY KEY CHECK (policy_version = 'forex.m20.conservative-risk.v1'),
    account_currency CHAR(3) NOT NULL CHECK (account_currency = 'AUD'),
    baseline_balance NUMERIC(14,2) NOT NULL,
    expected_balance NUMERIC(14,2) NOT NULL,
    peak_adjusted_equity NUMERIC(14,2) NOT NULL,
    daily_anchor_equity NUMERIC(14,2) NOT NULL,
    daily_anchor_date DATE NOT NULL,
    weekly_anchor_equity NUMERIC(14,2) NOT NULL,
    weekly_anchor_date DATE NOT NULL,
    pause_reason TEXT CHECK (pause_reason IN ('DAILY_LOSS', 'WEEKLY_LOSS', 'PEAK_DRAWDOWN', 'EXTERNAL_CASH_FLOW', 'UNKNOWN_ACCOUNT_STATE')),
    pause_until_date DATE,
    created_at_utc TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at_utc TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMIT;
