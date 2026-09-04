-- M20 market-regime, strategy-selection, ownership, and cost-coverage audit.
-- New data is append-only. Historical M20 rows remain untouched and are
-- deliberately not backfilled with inferred regimes or costs.

BEGIN;

CREATE TABLE IF NOT EXISTS forex.demo_strategy_selection (
    proposal_id TEXT PRIMARY KEY REFERENCES forex.demo_trade_proposal(proposal_id) ON DELETE RESTRICT,
    market_regime TEXT NOT NULL CHECK (market_regime IN (
        'UNSAFE_OR_UNTRADEABLE', 'COMPRESSION_BREAKOUT', 'TREND_PULLBACK',
        'RANGE_REVERSION', 'LIQUID_SESSION_BREAKOUT', 'MOMENTUM_BREAKOUT',
        'NO_CLEAR_REGIME'
    )),
    market_regime_reason TEXT NOT NULL,
    selected_strategy_id TEXT CHECK (selected_strategy_id IN (
        'momentum_breakout', 'compression_breakout', 'trend_pullback',
        'range_reversion', 'session_breakout'
    )),
    strategy_rule_version TEXT,
    selection_status TEXT NOT NULL CHECK (selection_status IN (
        'SELECTED_EXECUTABLE', 'SELECTED_SHADOW', 'NO_SELECTION'
    )),
    trade_owner_id TEXT NOT NULL,
    trade_owner_strategy_id TEXT CHECK (trade_owner_strategy_id IN (
        'momentum_breakout', 'compression_breakout', 'trend_pullback',
        'range_reversion', 'session_breakout'
    )),
    estimated_round_trip_cost_aud NUMERIC(14,2),
    minimum_net_profit_aud NUMERIC(14,2),
    expected_net_profit_at_take_profit_aud NUMERIC(14,2),
    cost_coverage_status TEXT NOT NULL CHECK (cost_coverage_status IN (
        'FEASIBLE', 'NOT_FEASIBLE', 'NOT_APPLICABLE'
    )),
    created_at_utc TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (trade_owner_id = proposal_id),
    CHECK ((selection_status = 'NO_SELECTION') = (selected_strategy_id IS NULL
        AND strategy_rule_version IS NULL AND trade_owner_strategy_id IS NULL)),
    CHECK ((selection_status <> 'NO_SELECTION') = (selected_strategy_id IS NOT NULL
        AND strategy_rule_version IS NOT NULL AND trade_owner_strategy_id = selected_strategy_id)),
    CHECK ((cost_coverage_status = 'NOT_APPLICABLE') = (estimated_round_trip_cost_aud IS NULL
        AND minimum_net_profit_aud IS NULL AND expected_net_profit_at_take_profit_aud IS NULL)),
    CHECK (cost_coverage_status = 'NOT_APPLICABLE' OR (
        estimated_round_trip_cost_aud >= 0 AND minimum_net_profit_aud > 0
        AND expected_net_profit_at_take_profit_aud IS NOT NULL
    ))
);

CREATE TABLE IF NOT EXISTS forex.demo_strategy_signal (
    proposal_id TEXT NOT NULL REFERENCES forex.demo_trade_proposal(proposal_id) ON DELETE RESTRICT,
    strategy_id TEXT NOT NULL CHECK (strategy_id IN (
        'momentum_breakout', 'compression_breakout', 'trend_pullback',
        'range_reversion', 'session_breakout'
    )),
    signal TEXT NOT NULL CHECK (signal IN ('BUY', 'SELL', 'NO_TRADE')),
    eligible_for_execution BOOLEAN NOT NULL,
    reason TEXT NOT NULL,
    observed_at_utc TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (proposal_id, strategy_id)
);

DROP TRIGGER IF EXISTS demo_strategy_selection_immutable ON forex.demo_strategy_selection;
CREATE TRIGGER demo_strategy_selection_immutable BEFORE UPDATE OR DELETE ON forex.demo_strategy_selection
FOR EACH ROW EXECUTE FUNCTION forex.reject_demo_audit_mutation();

DROP TRIGGER IF EXISTS demo_strategy_signal_immutable ON forex.demo_strategy_signal;
CREATE TRIGGER demo_strategy_signal_immutable BEFORE UPDATE OR DELETE ON forex.demo_strategy_signal
FOR EACH ROW EXECUTE FUNCTION forex.reject_demo_audit_mutation();

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
    COALESCE((SELECT event.payload->>'actual_entry_price'
              FROM forex.demo_position_event event
              JOIN forex.demo_execution_attempt attempt ON attempt.attempt_id = event.attempt_id
              WHERE attempt.proposal_id = proposal.proposal_id AND event.event_type = 'OPENED'
              ORDER BY event.observed_at_utc DESC LIMIT 1), '') AS actual_entry_price,
    selection.market_regime,
    selection.market_regime_reason,
    selection.selected_strategy_id,
    selection.strategy_rule_version,
    selection.selection_status,
    selection.trade_owner_id,
    selection.trade_owner_strategy_id,
    selection.estimated_round_trip_cost_aud,
    selection.minimum_net_profit_aud,
    selection.expected_net_profit_at_take_profit_aud,
    selection.cost_coverage_status,
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
LEFT JOIN forex.demo_strategy_selection selection ON selection.proposal_id = proposal.proposal_id
LEFT JOIN LATERAL (
    SELECT * FROM forex.demo_outcome_reconciliation_revision candidate
    WHERE candidate.proposal_id = outcome.proposal_id
    ORDER BY candidate.observed_at_utc DESC, candidate.created_at_utc DESC
    LIMIT 1
) revision ON true;

COMMIT;
