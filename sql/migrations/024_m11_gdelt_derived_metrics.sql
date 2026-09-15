-- GDELT V2 derived-metric transparency. Existing V1 placeholder rows remain
-- untouched and have NULL metrics; every V2 staged/final row supplies both.
BEGIN;

ALTER TABLE forex.gdelt_hourly_stage
    ADD COLUMN IF NOT EXISTS source_row_count INTEGER
        CHECK (source_row_count >= 0),
    ADD COLUMN IF NOT EXISTS tone_sample_count INTEGER
        CHECK (tone_sample_count >= 0 AND tone_sample_count <= article_count);

ALTER TABLE forex.gdelt_h1_aggregate
    ADD COLUMN IF NOT EXISTS source_row_count INTEGER
        CHECK (source_row_count >= 0),
    ADD COLUMN IF NOT EXISTS tone_sample_count INTEGER
        CHECK (tone_sample_count >= 0 AND tone_sample_count <= article_count);

COMMIT;
