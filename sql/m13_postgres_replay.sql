-- Fixed M13 T480 read-only daily alignment and replay query.
WITH cutoff AS (
    SELECT '2026-09-01T08:00:00Z'::timestamptz AS value
),
price AS (
    SELECT bar.*, raw.source_id
    FROM forex.price_bar bar
    JOIN forex.raw_observation raw ON raw.observation_id = bar.raw_observation_id,
         cutoff
    WHERE bar.snapshot_id = 'm2-m1-eurusd-h1-720'
      AND bar.available_at_utc <= cutoff.value
      AND bar.time_utc <= cutoff.value
),
context AS (
    SELECT aggregate.*, raw.source_id, raw.source_revision, raw.payload_sha256
    FROM forex.gdelt_h1_aggregate aggregate
    JOIN forex.raw_observation raw ON raw.observation_id = aggregate.observation_id,
         cutoff
    WHERE aggregate.available_at_utc <= cutoff.value
      AND aggregate.bucket_time_utc <= cutoff.value
),
price_daily AS (
    SELECT date_trunc('day', time_utc) AS day_utc, count(*) AS bar_count, max(time_utc) AS latest_bar_utc
    FROM price GROUP BY 1
),
context_daily AS (
    SELECT date_trunc('day', bucket_time_utc) AS day_utc, count(*) AS context_count
    FROM context GROUP BY 1
),
aligned AS (
    SELECT price_daily.day_utc, price_daily.bar_count, price_daily.latest_bar_utc,
           coalesce(context_daily.context_count, 0) AS context_count
    FROM price_daily LEFT JOIN context_daily USING (day_utc)
),
future_price AS (
    SELECT count(*) AS count FROM forex.price_bar, cutoff
    WHERE snapshot_id = 'm2-m1-eurusd-h1-720'
      AND (available_at_utc > cutoff.value OR time_utc > cutoff.value)
),
future_context AS (
    SELECT count(*) AS count FROM forex.gdelt_h1_aggregate, cutoff
    WHERE available_at_utc > cutoff.value OR bucket_time_utc > cutoff.value
)
SELECT 'FOREX_M13_POSTGRES_REPLAY_OK',
       'cutoff=2026-09-01T08:00:00Z',
       'snapshot=m2-m1-eurusd-h1-720',
       'bars=' || (SELECT count(*) FROM price),
       'contexts=' || (SELECT count(*) FROM context),
       'replay_days=' || (SELECT count(*) FROM aligned),
       'aligned_context_days=' || (SELECT count(*) FROM aligned WHERE context_count > 0),
       'price_lineage_ok=' || ((SELECT count(*) FROM price) = (
           SELECT count(*) FROM forex.price_bar bar
           JOIN forex.dataset_snapshot_observation link
             ON link.snapshot_id = bar.snapshot_id AND link.observation_id = bar.raw_observation_id
           WHERE bar.snapshot_id = 'm2-m1-eurusd-h1-720')),
       'context_lineage_ok=' || NOT EXISTS (
           SELECT 1 FROM context
           WHERE source_id <> 'gdelt-sentiment-prototype'
              OR source_revision = '' OR payload_sha256 !~ '^sha256:'),
       'future_price_records=' || (SELECT count FROM future_price),
       'future_context_records=' || (SELECT count FROM future_context);
