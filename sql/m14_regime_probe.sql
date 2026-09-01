-- Fixed M14 T480 historical regime probe.  It classifies the last six closed
-- EUR/USD H1 bars in the retained Demo-only snapshot; it has no order surface.
WITH session_contract AS (
  SELECT '2026-08-28T08:00:00Z'::timestamptz AS decision_at_utc,
         '2026-08-28T20:00:00Z'::timestamptz AS flat_by_utc, 60::integer AS blackout_minutes
), declared_event AS (
  SELECT '2026-08-28T08:30:00Z'::timestamptz AS scheduled_at_utc
), bars AS (
  SELECT time_utc, open, high, low, close
  FROM forex.price_bar, session_contract
  WHERE snapshot_id='m2-m1-eurusd-h1-720'
    AND time_utc <= decision_at_utc AND available_at_utc <= decision_at_utc
  ORDER BY time_utc DESC LIMIT 6
), ordered AS (
  SELECT * FROM bars ORDER BY time_utc
), stats AS (
  SELECT count(*) AS n, (array_agg(close ORDER BY time_utc))[1] AS first_close,
         (array_agg(close ORDER BY time_utc DESC))[1] AS last_close,
         avg(high-low) AS average_range FROM ordered
)
SELECT 'FOREX_M14_REGIME_PROBE_OK', 'bars=' || n,
 'regime=' || CASE WHEN n<2 THEN 'INSUFFICIENT_HISTORY'
                   WHEN average_range/last_close >= 0.003 THEN 'HIGH_VOLATILITY'
                   WHEN abs(last_close/first_close-1) >= 0.002 THEN 'TRENDING'
                   ELSE 'RANGE_BOUND' END,
 'event_window=' || CASE WHEN EXISTS (SELECT 1 FROM declared_event, session_contract WHERE abs(extract(epoch FROM scheduled_at_utc-decision_at_utc)) <= blackout_minutes*60) THEN 'EVENT_BLACKOUT' ELSE 'NO_SCHEDULED_EVENT_BLACKOUT' END,
 'decision_at=' || (SELECT decision_at_utc::text FROM session_contract),
 'flat_by=' || (SELECT flat_by_utc::text FROM session_contract), 'daylight_saving=UTC_FIXED'
FROM stats;
