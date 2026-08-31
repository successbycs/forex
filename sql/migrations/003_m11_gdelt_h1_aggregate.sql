-- M11 experimental GDELT context aggregates. Derived records only: no article
-- text, URL, account, trading decision, model score, or order surface.

BEGIN;

CREATE TABLE IF NOT EXISTS forex.gdelt_h1_aggregate (
    aggregate_id TEXT PRIMARY KEY,
    observation_id TEXT NOT NULL REFERENCES forex.raw_observation(observation_id) ON DELETE RESTRICT,
    bucket_time_utc TIMESTAMPTZ NOT NULL,
    available_at_utc TIMESTAMPTZ NOT NULL,
    article_count INTEGER NOT NULL CHECK (article_count >= 0),
    mean_tone NUMERIC(12, 6) NOT NULL,
    query_definition_version TEXT NOT NULL,
    uncertainty_label TEXT NOT NULL CHECK (uncertainty_label = 'EXPERIMENTAL_CONTEXT_ONLY'),
    created_at_utc TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (observation_id, bucket_time_utc),
    CHECK (available_at_utc >= bucket_time_utc)
);

CREATE INDEX IF NOT EXISTS gdelt_h1_aggregate_alignment_idx
ON forex.gdelt_h1_aggregate (bucket_time_utc, available_at_utc);

COMMIT;
