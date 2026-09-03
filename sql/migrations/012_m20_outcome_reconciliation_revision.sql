-- M20 remediation: retain immutable source outcomes, but never let a known
-- contaminated MT5 history query appear as broker-verified trade P&L.
-- A later exact-position repair is appended as a new reconciliation revision;
-- no audit event or source outcome is updated or deleted.
BEGIN;

CREATE TABLE IF NOT EXISTS forex.demo_outcome_reconciliation_revision (
    revision_id TEXT PRIMARY KEY,
    proposal_id TEXT NOT NULL REFERENCES forex.demo_trade_proposal(proposal_id) ON DELETE RESTRICT,
    disposition TEXT NOT NULL CHECK (disposition IN ('INVALIDATED', 'HISTORY_UNAVAILABLE', 'REPAIRED')),
    observed_at_utc TIMESTAMPTZ NOT NULL,
    reason_code TEXT NOT NULL,
    original_outcome JSONB NOT NULL CHECK (jsonb_typeof(original_outcome) = 'object'),
    broker_position_id BIGINT,
    broker_deals JSONB,
    broker_deals_sha256 TEXT,
    repaired_closed_at_utc TIMESTAMPTZ,
    repaired_exit_price NUMERIC(16,8),
    repaired_gross_price_pnl_account NUMERIC(14,2),
    repaired_commission_account NUMERIC(14,2),
    repaired_swap_account NUMERIC(14,2),
    repaired_realized_pnl_account NUMERIC(14,2),
    repaired_account_currency CHAR(3),
    created_at_utc TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK ((disposition = 'REPAIRED') = (broker_position_id IS NOT NULL
        AND broker_deals IS NOT NULL AND broker_deals_sha256 ~ '^sha256:[0-9a-f]{64}$'
        AND repaired_closed_at_utc IS NOT NULL AND repaired_exit_price > 0
        AND repaired_gross_price_pnl_account IS NOT NULL AND repaired_commission_account IS NOT NULL
        AND repaired_swap_account IS NOT NULL AND repaired_realized_pnl_account IS NOT NULL
        AND repaired_account_currency = 'AUD')),
    CHECK (disposition <> 'REPAIRED' OR jsonb_typeof(broker_deals) = 'array')
);

CREATE UNIQUE INDEX IF NOT EXISTS demo_outcome_reconciliation_revision_once_idx
    ON forex.demo_outcome_reconciliation_revision (proposal_id, disposition);

DROP TRIGGER IF EXISTS demo_outcome_reconciliation_revision_immutable
    ON forex.demo_outcome_reconciliation_revision;
CREATE TRIGGER demo_outcome_reconciliation_revision_immutable
BEFORE UPDATE OR DELETE ON forex.demo_outcome_reconciliation_revision
FOR EACH ROW EXECUTE FUNCTION forex.reject_demo_audit_mutation();

-- These source rows were created by the now-removed mixed range/position
-- history overload.  Their +100000.18 AUD amount is a Demo deposit, not a
-- trade result.  Keep the original row as JSON evidence and append this
-- explicit invalidation rather than modifying the immutable outcome.
INSERT INTO forex.demo_outcome_reconciliation_revision
    (revision_id, proposal_id, disposition, observed_at_utc, reason_code, original_outcome)
SELECT
    'legacy-history-contamination:' || outcome.proposal_id,
    outcome.proposal_id,
    'INVALIDATED',
    now(),
    'LEGACY_MIXED_RANGE_POSITION_HISTORY_QUERY',
    to_jsonb(outcome)
FROM forex.demo_trade_outcome outcome
WHERE outcome.reconciliation_status = 'MATCHED'
  AND outcome.account_currency = 'AUD'
  AND outcome.realized_pnl_account = 100000.18
ON CONFLICT (revision_id) DO NOTHING;

DROP VIEW IF EXISTS forex.demo_trade_ledger;
CREATE VIEW forex.demo_trade_ledger AS
SELECT
    proposal.proposal_id,
    proposal.session_id,
    session.server,
    session.instrument,
    proposal.action,
    proposal.decision_at_utc,
    proposal.proposed_entry AS entry_price,
    CASE WHEN revision.disposition = 'REPAIRED' THEN revision.repaired_exit_price ELSE outcome.exit_price END AS exit_price,
    CASE WHEN revision.disposition = 'REPAIRED' THEN revision.repaired_closed_at_utc ELSE outcome.closed_at_utc END AS closed_at_utc,
    CASE WHEN revision.disposition IN ('INVALIDATED', 'HISTORY_UNAVAILABLE') THEN NULL
         WHEN revision.disposition = 'REPAIRED' THEN revision.repaired_realized_pnl_account
         ELSE outcome.realized_pnl_account END AS realized_pnl_account,
    CASE WHEN revision.disposition IN ('INVALIDATED', 'HISTORY_UNAVAILABLE') THEN NULL
         WHEN revision.disposition = 'REPAIRED' THEN revision.repaired_account_currency
         ELSE outcome.account_currency END AS account_currency,
    CASE WHEN revision.disposition IN ('INVALIDATED', 'HISTORY_UNAVAILABLE') THEN 'RECONCILIATION_ERROR'
         WHEN revision.disposition = 'REPAIRED' THEN 'REPAIRED'
         ELSE outcome.reconciliation_status END AS reconciliation_status,
    CASE WHEN revision.disposition IS NULL THEN outcome.close_reason
         WHEN revision.disposition = 'REPAIRED' THEN outcome.close_reason
         ELSE revision.reason_code END AS close_reason,
    revision.disposition AS reconciliation_disposition,
    revision.reason_code AS reconciliation_reason,
    CASE WHEN revision.disposition IN ('INVALIDATED', 'HISTORY_UNAVAILABLE') THEN 'UNAVAILABLE'
         ELSE 'RECORDED' END AS cost_attribution_status
FROM forex.demo_trade_outcome outcome
JOIN forex.demo_trade_proposal proposal ON proposal.proposal_id = outcome.proposal_id
JOIN forex.demo_trade_session session ON session.session_id = proposal.session_id
LEFT JOIN LATERAL (
    SELECT *
    FROM forex.demo_outcome_reconciliation_revision candidate
    WHERE candidate.proposal_id = outcome.proposal_id
    ORDER BY candidate.observed_at_utc DESC, candidate.created_at_utc DESC
    LIMIT 1
) revision ON true;

COMMIT;
