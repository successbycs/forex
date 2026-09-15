WITH latest AS (
  SELECT max(bucket_time_utc) bucket FROM forex.gdelt_h1_aggregate
  WHERE query_definition_version = 'eurusd-context-terms.v2'
), aggregate AS (
  SELECT a.* FROM forex.gdelt_h1_aggregate a, latest l WHERE a.bucket_time_utc = l.bucket
), sources AS (
  SELECT r.payload_sha256, r.available_at_utc FROM forex.raw_observation r, latest l
  WHERE r.source_id = 'gdelt-sentiment-prototype' AND r.observation_id LIKE 'gdelt-gkg-v2-%'
    AND r.observed_at_utc >= l.bucket AND r.observed_at_utc < l.bucket + interval '1 hour'
)
SELECT 'FOREX_M11_V2_HOUR_VERIFY',
  'bucket=' || coalesce((SELECT bucket::text FROM latest), 'none'),
  'query=' || coalesce((SELECT query_definition_version FROM aggregate), 'none'),
  'source_count=' || (SELECT count(*) FROM sources),
  'source_hashes=' || coalesce((SELECT string_agg(payload_sha256, ',' ORDER BY payload_sha256) FROM sources), 'none'),
  'source_rows=' || coalesce((SELECT source_row_count::text FROM aggregate), 'none'),
  'relevant_documents=' || coalesce((SELECT article_count::text FROM aggregate), 'none'),
  'tone_samples=' || coalesce((SELECT tone_sample_count::text FROM aggregate), 'none'),
  'mean_tone=' || coalesce((SELECT mean_tone::text FROM aggregate), 'none'),
  'metrics_valid=' || coalesce((SELECT (source_row_count > 0 AND tone_sample_count <= article_count)::text FROM aggregate), 'false'),
  'hashes_present=' || coalesce((SELECT bool_and(payload_sha256 LIKE 'sha256:%')::text FROM sources), 'false'),
  'one_aggregate=' || ((SELECT count(*) FROM aggregate)=1),
  'lineage_ok=' || EXISTS (SELECT 1 FROM aggregate a JOIN forex.raw_observation r ON r.observation_id=a.observation_id WHERE r.observation_id LIKE 'gdelt-h1-v2-%'),
  'context_only=' || NOT EXISTS (SELECT 1 FROM aggregate WHERE uncertainty_label <> 'EXPERIMENTAL_CONTEXT_ONLY');
