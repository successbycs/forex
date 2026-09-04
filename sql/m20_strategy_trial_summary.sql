-- Read-only M20.11 v2 strategy scoreboard. Each source is aggregated once so
-- growing assessment history does not multiply rows in the terminal query.
WITH trial_proposals AS (
  SELECT proposal_id FROM forex.demo_trade_proposal
  WHERE strategy_version = 'forex.m20.11.m1-five-strategy-trial.v2'
), signal_stats AS (
  SELECT g.strategy_id, count(*) FILTER (WHERE g.signal IN ('BUY','SELL')) AS signal_count
  FROM forex.demo_strategy_signal g JOIN trial_proposals p USING (proposal_id)
  GROUP BY g.strategy_id
), selection_stats AS (
  SELECT s.selected_strategy_id AS strategy_id,
         count(*) FILTER (WHERE s.selection_status = 'SELECTED_EXECUTABLE') AS selected_count
  FROM forex.demo_strategy_selection s JOIN trial_proposals p USING (proposal_id)
  WHERE s.selected_strategy_id IS NOT NULL GROUP BY s.selected_strategy_id
), attempt_events AS (
  SELECT e.attempt_id, bool_or(e.event_type = 'OPENED') AS opened,
         bool_or(e.event_type = 'REJECTED') AS rejected
  FROM forex.demo_position_event e GROUP BY e.attempt_id
), attempt_stats AS (
  SELECT s.selected_strategy_id AS strategy_id, count(DISTINCT a.attempt_id) AS attempt_count,
         count(DISTINCT a.attempt_id) FILTER (WHERE ev.opened) AS opened_count,
         count(DISTINCT a.attempt_id) FILTER (WHERE ev.rejected) AS rejected_count
  FROM forex.demo_strategy_selection s JOIN trial_proposals p USING (proposal_id)
  LEFT JOIN forex.demo_execution_attempt a USING (proposal_id)
  LEFT JOIN attempt_events ev USING (attempt_id)
  WHERE s.selected_strategy_id IS NOT NULL GROUP BY s.selected_strategy_id
), outcome_stats AS (
  SELECT l.trade_owner_strategy_id AS strategy_id,
         count(*) FILTER (WHERE l.reconciliation_status IN ('MATCHED','REPAIRED') AND l.realized_pnl_account IS NOT NULL) AS verified_closed_count,
         count(*) FILTER (WHERE l.realized_pnl_account > 0) AS win_count,
         count(*) FILTER (WHERE l.realized_pnl_account < 0) AS loss_count,
         COALESCE(sum(l.realized_pnl_account) FILTER (WHERE l.reconciliation_status IN ('MATCHED','REPAIRED')), 0) AS net_realized_pnl_aud
  FROM forex.demo_trade_ledger l JOIN trial_proposals p USING (proposal_id)
  WHERE l.trade_owner_strategy_id IS NOT NULL GROUP BY l.trade_owner_strategy_id
), strategy_ids AS (
  SELECT strategy_id FROM signal_stats UNION SELECT strategy_id FROM selection_stats
  UNION SELECT strategy_id FROM attempt_stats UNION SELECT strategy_id FROM outcome_stats
)
SELECT COALESCE(json_agg(row_to_json(x) ORDER BY x.strategy_id)::text, '[]')
FROM (
  SELECT ids.strategy_id, COALESCE(si.signal_count,0) AS signal_count,
    COALESCE(se.selected_count,0) AS selected_count, COALESCE(at.attempt_count,0) AS attempt_count,
    COALESCE(at.opened_count,0) AS opened_count, COALESCE(at.rejected_count,0) AS rejected_count,
    COALESCE(ou.verified_closed_count,0) AS verified_closed_count, COALESCE(ou.win_count,0) AS win_count,
    COALESCE(ou.loss_count,0) AS loss_count, COALESCE(ou.net_realized_pnl_aud,0) AS net_realized_pnl_aud
  FROM strategy_ids ids LEFT JOIN signal_stats si USING(strategy_id)
  LEFT JOIN selection_stats se USING(strategy_id) LEFT JOIN attempt_stats at USING(strategy_id)
  LEFT JOIN outcome_stats ou USING(strategy_id)
) x;
