-- Fixed M14 T480 historical regime probe.  It classifies the last six closed
-- EUR/USD H1 bars in the retained Demo-only snapshot; it has no order surface.
WITH bars AS (
  SELECT time_utc, open, high, low, close
  FROM forex.price_bar
  WHERE snapshot_id='m2-m1-eurusd-h1-720'
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
 'event_window=NO_SCHEDULED_EVENT_BLACKOUT',
 'session=08:00Z-20:00Z', 'daylight_saving=UTC_FIXED'
FROM stats;
