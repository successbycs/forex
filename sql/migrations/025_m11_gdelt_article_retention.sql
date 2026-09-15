-- M11 V3 publisher article retention.  GDELT identifies eligible publisher
-- URLs; this table retains bounded, normalised publisher text.  A duplicate
-- must never replace a body that was already retained.
BEGIN;

CREATE TABLE IF NOT EXISTS forex.gdelt_article (
    content_sha256 TEXT PRIMARY KEY CHECK (content_sha256 ~ '^sha256:[0-9a-f]{64}$'),
    title TEXT NOT NULL CHECK (length(title) BETWEEN 1 AND 500),
    body TEXT NOT NULL CHECK (length(body) BETWEEN 1 AND 100000),
    retrieved_at_utc TIMESTAMPTZ NOT NULL,
    content_type TEXT NOT NULL CHECK (content_type IN ('text/html', 'application/xhtml+xml'))
);

-- URLs are observations, not identities.  A publisher can legitimately change
-- a page, and syndicated copies can share one normalized body.
CREATE TABLE IF NOT EXISTS forex.gdelt_article_url (
    content_sha256 TEXT NOT NULL REFERENCES forex.gdelt_article(content_sha256) ON DELETE RESTRICT,
    canonical_url TEXT NOT NULL CHECK (length(canonical_url) <= 2048 AND canonical_url ~ '^https://'),
    first_retrieved_at_utc TIMESTAMPTZ NOT NULL,
    last_retrieved_at_utc TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (content_sha256, canonical_url),
    CHECK (last_retrieved_at_utc >= first_retrieved_at_utc)
);

CREATE INDEX IF NOT EXISTS gdelt_article_url_canonical_idx
ON forex.gdelt_article_url (canonical_url, last_retrieved_at_utc DESC);

-- This ledger deliberately has no title or body column.  Every selected URL
-- produces one attempt, including redirects and rejected responses.
CREATE TABLE IF NOT EXISTS forex.gdelt_article_retrieval_attempt (
    attempt_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    canonical_url TEXT NOT NULL CHECK (length(canonical_url) <= 2048 AND canonical_url ~ '^https://'),
    retrieved_at_utc TIMESTAMPTZ NOT NULL,
    result_status TEXT NOT NULL CHECK (result_status IN ('RETAINED', 'FAILED')),
    failure_reason TEXT NULL CHECK (failure_reason IS NULL OR length(failure_reason) <= 128),
    http_status INTEGER NULL CHECK (http_status BETWEEN 100 AND 599),
    content_sha256 TEXT NULL CHECK (content_sha256 IS NULL OR content_sha256 ~ '^sha256:[0-9a-f]{64}$'),
    content_type TEXT NULL CHECK (content_type IS NULL OR content_type IN ('text/html', 'application/xhtml+xml')),
    CHECK ((result_status = 'RETAINED' AND content_sha256 IS NOT NULL AND failure_reason IS NULL)
        OR (result_status = 'FAILED' AND content_sha256 IS NULL AND failure_reason IS NOT NULL))
);

CREATE INDEX IF NOT EXISTS gdelt_article_retrieval_attempt_url_idx
ON forex.gdelt_article_retrieval_attempt (canonical_url, retrieved_at_utc DESC);

-- The egress receipt is metadata only; response content is never copied here.
ALTER TABLE forex.gdelt_article_retrieval_attempt
    ADD COLUMN IF NOT EXISTS final_url TEXT NULL CHECK (final_url IS NULL OR length(final_url) <= 2048),
    ADD COLUMN IF NOT EXISTS redirect_chain JSONB NULL,
    ADD COLUMN IF NOT EXISTS pinned_ip TEXT NULL,
    ADD COLUMN IF NOT EXISTS byte_count INTEGER NULL CHECK (byte_count IS NULL OR byte_count BETWEEN 0 AND 1048576),
    ADD COLUMN IF NOT EXISTS payload_sha256 TEXT NULL CHECK (payload_sha256 IS NULL OR payload_sha256 ~ '^sha256:[0-9a-f]{64}$');

CREATE TABLE IF NOT EXISTS forex.gdelt_article_source (
    content_sha256 TEXT NOT NULL REFERENCES forex.gdelt_article(content_sha256) ON DELETE RESTRICT,
    source_observation_id TEXT NOT NULL REFERENCES forex.raw_observation(observation_id) ON DELETE RESTRICT,
    gdelt_document_id TEXT NOT NULL CHECK (length(gdelt_document_id) BETWEEN 1 AND 512),
    bucket_time_utc TIMESTAMPTZ NOT NULL,
    source_tone NUMERIC(12, 6) NULL,
    created_at_utc TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (content_sha256, source_observation_id, gdelt_document_id, bucket_time_utc)
);

CREATE INDEX IF NOT EXISTS gdelt_article_source_bucket_idx
ON forex.gdelt_article_source (bucket_time_utc, content_sha256);

COMMIT;
