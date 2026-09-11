-- Fixed read-only M20 lifecycle evidence and operator-ledger extract.
-- The query is staged by hash before execution so Windows command-line limits
-- cannot truncate its evidence fields. It reads append-only audit data only.
SELECT COALESCE(json_agg(row_to_json(x) ORDER BY x.submitted_at_utc)::text, '[]')
FROM (
  SELECT
    p.session_id,
    p.proposal_id,
    a.attempt_id,
    p.action,
    a.status,
    a.submitted_at_utc,
    p.proposed_entry,
    p.stop_loss,
    p.take_profit,
    opening.payload->>'actual_entry_price' AS actual_entry_price,
    opening.payload->>'volume' AS volume_lots,
    selection.selected_strategy_id,
    selection.trade_owner_strategy_id,
    ledger.closed_at_utc,
    ledger.exit_price,
    ledger.gross_price_pnl_account,
    ledger.commission_account,
    ledger.fee_account,
    ledger.swap_account,
    ledger.estimated_spread_cost_account,
    ledger.slippage_cost_account,
    ledger.estimated_total_cost_account,
    ledger.realized_pnl_account,
    ledger.account_currency,
    ledger.close_reason,
    ledger.reconciliation_status,
    ledger.reconciliation_disposition,
    ledger.reconciliation_reason,
    rejection.payload AS rejection_context,
    COALESCE(events.event_types, '[]'::json)::text AS events,
    CASE
      WHEN ledger.reconciliation_status IN ('MATCHED', 'REPAIRED') THEN 'CLOSED_MATCHED'
      WHEN ledger.reconciliation_status = 'RECONCILIATION_ERROR' THEN 'CLOSED_RECONCILIATION_ERROR'
      WHEN open_state.attempt_id IS NOT NULL THEN 'OPEN_MONITORING'
      WHEN events.has_not_submitted THEN 'TERMINAL_NOT_SUBMITTED'
      WHEN rejection.attempt_id IS NOT NULL THEN 'TERMINAL_REJECTED'
      WHEN events.has_failed THEN 'TERMINAL_FAILED'
      ELSE 'PENDING'
    END AS lifecycle
  FROM forex.demo_execution_attempt a
  JOIN forex.demo_trade_proposal p ON p.proposal_id = a.proposal_id
  LEFT JOIN forex.demo_trade_ledger ledger ON ledger.proposal_id = p.proposal_id
  LEFT JOIN forex.demo_open_position_state open_state ON open_state.attempt_id = a.attempt_id
  LEFT JOIN forex.demo_strategy_selection selection ON selection.proposal_id = p.proposal_id
  LEFT JOIN LATERAL (
    SELECT e.payload
    FROM forex.demo_position_event e
    WHERE e.attempt_id = a.attempt_id AND e.event_type = 'OPENED'
    ORDER BY e.observed_at_utc, e.event_id
    LIMIT 1
  ) opening ON true
  LEFT JOIN LATERAL (
    SELECT e.attempt_id, e.payload
    FROM forex.demo_position_event e
    WHERE e.attempt_id = a.attempt_id AND e.event_type = 'REJECTED'
    ORDER BY e.observed_at_utc DESC, e.event_id DESC
    LIMIT 1
  ) rejection ON true
  LEFT JOIN LATERAL (
    SELECT
      json_agg(e.event_type ORDER BY e.observed_at_utc, e.event_id) AS event_types,
      bool_or(e.event_type = 'NOT_SUBMITTED') AS has_not_submitted,
      bool_or(e.event_type = 'FAILED') AS has_failed
    FROM forex.demo_position_event e
    WHERE e.attempt_id = a.attempt_id
  ) events ON true
) x;
