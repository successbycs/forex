-- M20 accounts are AUD-denominated.  P&L must be stored with its actual
-- account currency rather than mislabelled as USD merely because EUR/USD
-- notionals are expressed in USD.
BEGIN;

DROP VIEW IF EXISTS forex.demo_trade_ledger;

ALTER TABLE forex.demo_trade_outcome
    RENAME COLUMN realized_pnl_usd TO realized_pnl_account;

ALTER TABLE forex.demo_trade_outcome
    ADD COLUMN account_currency CHAR(3) NOT NULL DEFAULT 'AUD',
    ADD CONSTRAINT demo_trade_outcome_account_currency_check
        CHECK (account_currency = 'AUD');

CREATE OR REPLACE VIEW forex.demo_trade_ledger AS
SELECT
    outcome.proposal_id,
    proposal.session_id,
    session.server,
    session.instrument,
    proposal.action,
    proposal.proposed_entry AS entry_price,
    outcome.exit_price,
    outcome.closed_at_utc,
    outcome.realized_pnl_account,
    outcome.account_currency,
    CASE WHEN outcome.realized_pnl_account > 0 THEN 'PROFIT'
         WHEN outcome.realized_pnl_account < 0 THEN 'LOSS'
         ELSE 'BREAKEVEN' END AS pnl_classification,
    outcome.close_reason,
    SUM(outcome.realized_pnl_account) OVER (
        PARTITION BY outcome.account_currency
        ORDER BY outcome.closed_at_utc, outcome.proposal_id
    ) AS cumulative_pnl_recorded
FROM forex.demo_trade_outcome outcome
JOIN forex.demo_trade_proposal proposal ON proposal.proposal_id = outcome.proposal_id
JOIN forex.demo_trade_session session ON session.session_id = proposal.session_id;

COMMIT;
