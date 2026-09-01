-- M11-R1: hand-off between independent n8n workflows. No article content.
BEGIN;
CREATE TABLE IF NOT EXISTS forex.gdelt_hourly_stage (
    stage_id TEXT PRIMARY KEY,
    bucket_time_utc TIMESTAMPTZ NOT NULL UNIQUE,
    source_records JSONB NOT NULL,
    aggregate_sha256 TEXT NOT NULL CHECK (aggregate_sha256 LIKE 'sha256:%'),
    article_count INTEGER NOT NULL CHECK (article_count >= 0),
    mean_tone NUMERIC(12, 6) NOT NULL,
    query_definition_version TEXT NOT NULL,
    uncertainty_label TEXT NOT NULL CHECK (uncertainty_label = 'EXPERIMENTAL_CONTEXT_ONLY'),
    retrieved_at_utc TIMESTAMPTZ NOT NULL,
    imported_at_utc TIMESTAMPTZ NULL,
    CHECK (jsonb_typeof(source_records) = 'array')
);
CREATE INDEX IF NOT EXISTS gdelt_hourly_stage_pending_idx
ON forex.gdelt_hourly_stage (bucket_time_utc) WHERE imported_at_utc IS NULL;
COMMIT;
