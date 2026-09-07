-- Rebuild the M20 ledger so fee completeness and reconciliation revisions are
-- evaluated together. Source outcomes remain immutable; a legacy outcome that
-- lacks a broker fee is visibly unresolved and contributes no realised P&L.
BEGIN;

DROP VIEW IF EXISTS forex.demo_trade_ledger;
CREATE VIEW forex.demo_trade_ledger AS
SELECT
    proposal.proposal_id, proposal.session_id, session.server, session.instrument,
    proposal.action, proposal.decision_at_utc, proposal.proposed_entry AS entry_price,
    CASE WHEN revision.disposition = 'REPAIRED' THEN revision.repaired_exit_price ELSE outcome.exit_price END AS exit_price,
    CASE WHEN revision.disposition = 'REPAIRED' THEN revision.repaired_closed_at_utc ELSE outcome.closed_at_utc END AS closed_at_utc,
    CASE WHEN outcome.fee_account IS NULL OR revision.disposition IN ('INVALIDATED', 'HISTORY_UNAVAILABLE') THEN NULL WHEN revision.disposition = 'REPAIRED' THEN revision.repaired_realized_pnl_account ELSE outcome.realized_pnl_account END AS realized_pnl_account,
    CASE WHEN outcome.fee_account IS NULL OR revision.disposition IN ('INVALIDATED', 'HISTORY_UNAVAILABLE') THEN NULL WHEN revision.disposition = 'REPAIRED' THEN revision.repaired_account_currency ELSE outcome.account_currency END AS account_currency,
    CASE WHEN outcome.fee_account IS NULL OR revision.disposition IN ('INVALIDATED', 'HISTORY_UNAVAILABLE') THEN 'RECONCILIATION_ERROR' WHEN revision.disposition = 'REPAIRED' THEN 'REPAIRED' ELSE outcome.reconciliation_status END AS reconciliation_status,
    CASE WHEN outcome.fee_account IS NULL THEN 'BROKER_FEE_UNAVAILABLE' WHEN revision.disposition IS NULL OR revision.disposition = 'REPAIRED' THEN outcome.close_reason ELSE revision.reason_code END AS close_reason,
    revision.disposition AS reconciliation_disposition, revision.reason_code AS reconciliation_reason,
    outcome.gross_price_pnl_account, outcome.commission_account, outcome.fee_account, outcome.swap_account,
    outcome.estimated_spread_cost_account, outcome.slippage_cost_account, outcome.estimated_total_cost_account,
    CASE WHEN outcome.fee_account IS NULL OR revision.disposition IN ('INVALIDATED', 'HISTORY_UNAVAILABLE') THEN 'UNAVAILABLE' ELSE 'RECORDED' END AS cost_attribution_status
FROM forex.demo_trade_outcome outcome
JOIN forex.demo_trade_proposal proposal ON proposal.proposal_id = outcome.proposal_id
JOIN forex.demo_trade_session session ON session.session_id = proposal.session_id
LEFT JOIN LATERAL (
    SELECT * FROM forex.demo_outcome_reconciliation_revision candidate
    WHERE candidate.proposal_id = outcome.proposal_id
    ORDER BY candidate.observed_at_utc DESC, candidate.created_at_utc DESC LIMIT 1
) revision ON true;

COMMIT;
