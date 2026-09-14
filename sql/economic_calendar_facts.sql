-- Manual migration: canonical projections of already-retained calendar facts.
-- This file is deliberately not auto-applied by any Python module or script.
CREATE SCHEMA IF NOT EXISTS forex;

CREATE TABLE IF NOT EXISTS forex.economic_calendar_event_fact (
    fact_sha256 TEXT PRIMARY KEY CHECK (fact_sha256 ~ '^sha256:[0-9a-f]{64}$'),
    source_family TEXT NOT NULL,
    source_url TEXT NOT NULL,
    capture_completed_at_utc TIMESTAMPTZ NOT NULL,
    raw_sha256 TEXT NOT NULL CHECK (raw_sha256 ~ '^sha256:[0-9a-f]{64}$'),
    receipt_sha256 TEXT NOT NULL CHECK (receipt_sha256 ~ '^sha256:[0-9a-f]{64}$'),
    event_identifier TEXT NOT NULL,
    scheduled_at_utc TIMESTAMPTZ NULL,
    event_title TEXT NOT NULL,
    country_code TEXT NULL CHECK (country_code IS NULL OR country_code ~ '^[A-Z]{2}$'),
    currency_code TEXT NULL CHECK (currency_code IS NULL OR currency_code ~ '^[A-Z]{3}$'),
    impact TEXT NULL CHECK (impact IS NULL OR impact IN ('LOW','MEDIUM','HIGH','UNKNOWN')),
    qualification_state TEXT NOT NULL CHECK (qualification_state IN ('QUALIFIED','QUARANTINED','UNQUALIFIED','UNKNOWN')),
    qualification_reason TEXT NULL,
    source_revision INTEGER NOT NULL CHECK (source_revision >= 1),
    event_payload JSONB CHECK (event_payload IS NULL OR jsonb_typeof(event_payload) = 'object'),
    recorded_at_utc TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

-- The first reviewed projection was not deployed when this migration was
-- prepared. This explicit alteration keeps a controlled manual application
-- safe if an operator had already created its earlier table shape. Existing
-- rows cannot be inferred or rewritten: an incomplete legacy row is rejected
-- by the adapter and must be reprojected from immutable evidence.
ALTER TABLE forex.economic_calendar_event_fact
    ADD COLUMN IF NOT EXISTS event_payload JSONB;
ALTER TABLE forex.economic_calendar_event_fact
    DROP CONSTRAINT IF EXISTS economic_calendar_event_fact_event_payload_check;
ALTER TABLE forex.economic_calendar_event_fact
    ADD CONSTRAINT economic_calendar_event_fact_event_payload_check
    CHECK (event_payload IS NULL OR jsonb_typeof(event_payload) = 'object');

-- A source can be re-qualified (or quarantined) without its publisher bytes
-- changing.  ``fact_sha256`` is therefore the sole idempotency key: it binds
-- the full fact including qualification state and reason, rather than losing
-- a later qualification conclusion to a raw-payload uniqueness collision.
CREATE INDEX IF NOT EXISTS economic_calendar_event_fact_lookup_idx
    ON forex.economic_calendar_event_fact
       (source_family, event_identifier, source_revision, capture_completed_at_utc DESC);
