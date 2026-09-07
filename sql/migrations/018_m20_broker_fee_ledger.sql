-- Record the MT5 DEAL_FEE component separately from commission and swap.
-- It is part of broker net P&L and must not be hidden in an execution estimate.
BEGIN;

DROP VIEW IF EXISTS forex.demo_trade_ledger;

ALTER TABLE forex.demo_trade_outcome
    ADD COLUMN fee_account NUMERIC(14,2);

CREATE OR REPLACE VIEW forex.demo_trade_ledger AS
SELECT
    outcome.proposal_id,
    proposal.session_id,
    session.server,
    session.instrument,
    proposal.selected_timeframe,
    proposal.strategy_version,
    proposal.action,
    proposal.proposed_entry AS entry_price,
    outcome.exit_price,
    outcome.closed_at_utc,
    outcome.gross_price_pnl_account,
    outcome.commission_account,
    outcome.fee_account,
    outcome.swap_account,
    outcome.estimated_spread_cost_account,
    outcome.slippage_cost_account,
    outcome.estimated_total_cost_account,
    CASE WHEN outcome.estimated_total_cost_account IS NULL THEN 'UNAVAILABLE'
         ELSE 'RECORDED' END AS cost_attribution_status,
    outcome.realized_pnl_account,
    outcome.account_currency,
    CASE WHEN outcome.realized_pnl_account > 0 THEN 'PROFIT'
         WHEN outcome.realized_pnl_account < 0 THEN 'LOSS'
         ELSE 'BREAKEVEN' END AS pnl_classification,
    outcome.close_reason,
    SUM(outcome.realized_pnl_account) OVER (
        PARTITION BY outcome.account_currency
        ORDER BY outcome.closed_at_utc, outcome.proposal_id
    ) AS cumulative_pnl_recorded,
    SUM(COALESCE(outcome.estimated_total_cost_account, 0)) OVER (
        PARTITION BY outcome.account_currency
        ORDER BY outcome.closed_at_utc, outcome.proposal_id
    ) AS cumulative_estimated_cost_recorded
FROM forex.demo_trade_outcome outcome
JOIN forex.demo_trade_proposal proposal ON proposal.proposal_id = outcome.proposal_id
JOIN forex.demo_trade_session session ON session.session_id = proposal.session_id;

COMMIT;
