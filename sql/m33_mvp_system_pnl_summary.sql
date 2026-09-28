-- Fixed read-only M33.5 system-owned Demo journal and Auckland P&L summary.
-- This deliberately excludes account deposits, withdrawals, manual/broker-only
-- history, open positions, and non-reconciled outcomes. The web console renders
-- these returned totals; it never computes money values in the browser.
WITH clock AS (
  SELECT now() AT TIME ZONE 'Pacific/Auckland' AS auckland_now
), candidates AS (
  SELECT
    p.proposal_id,
    a.attempt_id,
    p.action,
    p.application_revision,
    p.configuration_fingerprint,
    p.strategy_version,
    p.decision_at_utc,
    p.proposed_entry,
    p.stop_loss,
    p.take_profit,
    a.submitted_at_utc,
    s.selected_strategy_id,
    s.trade_owner_strategy_id,
    l.closed_at_utc,
    l.exit_price,
    l.gross_price_pnl_account,
    l.commission_account,
    l.fee_account,
    l.swap_account,
    l.realized_pnl_account,
    l.account_currency,
    l.close_reason,
    l.reconciliation_status,
    l.reconciliation_disposition,
    l.reconciliation_reason,
    opening.payload->>'actual_entry_price' AS actual_entry_price,
    opening.payload->>'volume' AS volume_lots,
    (l.closed_at_utc AT TIME ZONE 'Pacific/Auckland') AS closed_at_auckland,
    CASE
      WHEN l.reconciliation_status IN ('MATCHED', 'REPAIRED')
       AND l.realized_pnl_account IS NOT NULL
       AND l.account_currency IS NOT NULL THEN true
      ELSE false
    END AS broker_matched
  FROM forex.demo_trade_proposal p
  JOIN forex.demo_execution_attempt a ON a.proposal_id = p.proposal_id
  JOIN forex.demo_trade_session trade_session ON trade_session.session_id = p.session_id
  JOIN forex.demo_strategy_selection s ON s.proposal_id = p.proposal_id
  LEFT JOIN forex.demo_trade_ledger l ON l.proposal_id = p.proposal_id
  LEFT JOIN LATERAL (
    SELECT e.payload
    FROM forex.demo_position_event e
    WHERE e.attempt_id = a.attempt_id AND e.event_type = 'OPENED'
    ORDER BY e.observed_at_utc, e.event_id
    LIMIT 1
  ) opening ON true
  WHERE trade_session.server = 'GOMarketsMU-Demo'
    AND p.action IN ('BUY', 'SELL')
    AND s.trade_owner_strategy_id IS NOT NULL
), periods AS (
  SELECT 'today'::text AS period, date_trunc('day', auckland_now) AS starts_at, auckland_now AS ends_at FROM clock
  UNION ALL
  SELECT 'week', date_trunc('week', auckland_now), auckland_now FROM clock
  UNION ALL
  SELECT 'month', date_trunc('month', auckland_now), auckland_now FROM clock
), period_summary AS (
  SELECT
    p.period,
    p.starts_at,
    p.ends_at,
    count(c.proposal_id) FILTER (WHERE c.closed_at_auckland >= p.starts_at AND c.closed_at_auckland <= p.ends_at) AS candidate_closed_count,
    count(c.proposal_id) FILTER (WHERE c.closed_at_auckland >= p.starts_at AND c.closed_at_auckland <= p.ends_at AND c.broker_matched) AS matched_closed_count,
    count(c.proposal_id) FILTER (WHERE c.closed_at_auckland >= p.starts_at AND c.closed_at_auckland <= p.ends_at AND NOT c.broker_matched) AS excluded_closed_count,
    COALESCE(sum(c.realized_pnl_account) FILTER (WHERE c.closed_at_auckland >= p.starts_at AND c.closed_at_auckland <= p.ends_at AND c.broker_matched), 0) AS actual_net_pnl_account,
    COALESCE(json_agg(DISTINCT c.account_currency) FILTER (WHERE c.closed_at_auckland >= p.starts_at AND c.closed_at_auckland <= p.ends_at AND c.broker_matched), '[]'::json) AS account_currencies
  FROM periods p
  LEFT JOIN candidates c ON c.closed_at_auckland IS NOT NULL
  GROUP BY p.period, p.starts_at, p.ends_at
), journal AS (
  SELECT *
  FROM candidates
  WHERE closed_at_utc IS NOT NULL AND broker_matched
  ORDER BY closed_at_utc DESC, proposal_id DESC
  LIMIT 50
), excluded_journal AS (
  SELECT proposal_id, attempt_id, action, strategy_version, trade_owner_strategy_id,
         closed_at_utc, reconciliation_status, reconciliation_disposition,
         reconciliation_reason,
         CASE
           WHEN reconciliation_status NOT IN ('MATCHED', 'REPAIRED') THEN 'UNRECONCILED'
           WHEN realized_pnl_account IS NULL THEN 'ACTUAL_NET_PNL_UNAVAILABLE'
           WHEN account_currency IS NULL THEN 'ACCOUNT_CURRENCY_UNAVAILABLE'
           ELSE 'EXCLUDED'
         END AS exclusion_reason
  FROM candidates
  WHERE closed_at_utc IS NOT NULL AND NOT broker_matched
  ORDER BY closed_at_utc DESC, proposal_id DESC
  LIMIT 50
)
SELECT json_build_object(
  'schema_version', 'forex.m33.5.system-pnl-summary.v1',
  'timezone', 'Pacific/Auckland',
  'generated_at_utc', to_char(now() AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'),
  'periods', COALESCE((SELECT json_agg(row_to_json(p) ORDER BY CASE p.period WHEN 'today' THEN 1 WHEN 'week' THEN 2 ELSE 3 END) FROM period_summary p), '[]'::json),
  'journal', COALESCE((SELECT json_agg(row_to_json(j) ORDER BY j.closed_at_utc DESC, j.proposal_id DESC) FROM journal j), '[]'::json),
  'excluded_journal', COALESCE((SELECT json_agg(row_to_json(x) ORDER BY x.closed_at_utc DESC, x.proposal_id DESC) FROM excluded_journal x), '[]'::json),
  'unclosed_system_attempt_count', (SELECT count(*) FROM candidates WHERE closed_at_utc IS NULL)
)::text;
