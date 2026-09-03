-- M20: simple read-only ledger for closed Demo trades.
-- The account currency is retained explicitly at session level by the
-- operator-facing ledger query; realized P&L is the immutable broker result.

BEGIN;

ALTER TABLE forex.demo_trade_session
    DROP CONSTRAINT IF EXISTS demo_trade_session_max_notional_usd_check,
    DROP CONSTRAINT IF EXISTS demo_trade_session_max_cumulative_notional_usd_check;
ALTER TABLE forex.demo_trade_session
    ADD CONSTRAINT demo_trade_session_max_notional_usd_check CHECK (max_notional_usd > 0 AND max_notional_usd <= 10000.00),
    ADD CONSTRAINT demo_trade_session_max_cumulative_notional_usd_check CHECK (max_cumulative_notional_usd > 0 AND max_cumulative_notional_usd <= 100000.00);
ALTER TABLE forex.demo_trade_proposal
    DROP CONSTRAINT IF EXISTS demo_trade_proposal_notional_usd_check;
ALTER TABLE forex.demo_trade_proposal
    ADD CONSTRAINT demo_trade_proposal_notional_usd_check CHECK (notional_usd IS NULL OR (notional_usd > 0 AND notional_usd <= 10000.00));

CREATE OR REPLACE VIEW forex.demo_trade_ledger AS
SELECT
    outcome.proposal_id,
    proposal.session_id,
    session.server,
    session.instrument,
    proposal.action,
    proposal.decision_at_utc,
    attempt.submitted_at_utc,
    proposal.proposed_entry AS entry_price,
    outcome.exit_price,
    outcome.closed_at_utc,
    outcome.realized_pnl_usd AS realized_pnl_recorded,
    CASE WHEN outcome.realized_pnl_usd > 0 THEN 'PROFIT'
         WHEN outcome.realized_pnl_usd < 0 THEN 'LOSS'
         ELSE 'BREAKEVEN' END AS result,
    outcome.close_reason,
    SUM(outcome.realized_pnl_usd) OVER (
        PARTITION BY proposal.session_id ORDER BY outcome.closed_at_utc, outcome.proposal_id
    ) AS cumulative_pnl_recorded
FROM forex.demo_trade_outcome outcome
JOIN forex.demo_trade_proposal proposal ON proposal.proposal_id = outcome.proposal_id
JOIN forex.demo_trade_session session ON session.session_id = proposal.session_id
JOIN forex.demo_execution_attempt attempt ON attempt.proposal_id = proposal.proposal_id
WHERE outcome.reconciliation_status = 'MATCHED';

COMMIT;
