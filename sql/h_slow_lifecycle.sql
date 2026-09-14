-- Disabled H_SLOW lifecycle intent persistence.  This schema stores only
-- opaque isolation labels and non-operational intents; it contains no account
-- number, credential, route, lease, size, price, or broker command surface.
-- Apply only through a separately approved local PostgreSQL migration path.
BEGIN;

CREATE TABLE IF NOT EXISTS forex.h_slow_lifecycle_intent (
    action_id TEXT PRIMARY KEY CHECK (action_id ~ '^sha256:[0-9a-f]{64}$'),
    stream_id TEXT NOT NULL CHECK (stream_id = 'H_SLOW'),
    account_scope TEXT NOT NULL CHECK (account_scope ~ '^[a-z][a-z0-9_-]{2,127}$'),
    terminal_instance TEXT NOT NULL CHECK (terminal_instance ~ '^[a-z][a-z0-9_-]{2,127}$'),
    isolation_registry_fingerprint TEXT NOT NULL CHECK (isolation_registry_fingerprint ~ '^sha256:[0-9a-f]{64}$'),
    decision_sha256 TEXT NOT NULL CHECK (decision_sha256 ~ '^sha256:[0-9a-f]{64}$'),
    action_kind TEXT NOT NULL CHECK (action_kind IN ('OPEN', 'CLOSE')),
    ticket_id TEXT,
    direction TEXT CHECK (direction IN ('BUY', 'SELL')),
    valid_until_utc TIMESTAMPTZ,
    claim_status TEXT NOT NULL DEFAULT 'PENDING'
        CHECK (claim_status IN ('PENDING', 'CLAIMED', 'SUBMISSION_UNKNOWN', 'TERMINAL_RECONCILED', 'EXPIRED_NOT_SUBMITTED')),
    terminal_status TEXT CHECK (terminal_status IN
        ('OPEN_CONFIRMED', 'OPEN_REJECTED', 'CLOSE_CONFIRMED', 'CLOSE_REJECTED', 'NOT_SUBMITTED')),
    terminal_reference TEXT,
    created_at_utc TIMESTAMPTZ NOT NULL DEFAULT now(),
    claimed_at_utc TIMESTAMPTZ,
    reconciled_at_utc TIMESTAMPTZ,
    expired_at_utc TIMESTAMPTZ,
    CHECK ((action_kind = 'OPEN' AND ticket_id IS NULL AND direction IS NOT NULL AND direction IN ('BUY', 'SELL'))
        OR (action_kind = 'CLOSE' AND ticket_id IS NOT NULL AND length(ticket_id) > 0 AND direction IS NULL)),
    CHECK ((claim_status = 'PENDING' AND claimed_at_utc IS NULL AND terminal_status IS NULL)
        OR (claim_status = 'CLAIMED' AND claimed_at_utc IS NOT NULL AND terminal_status IS NULL)
        OR (claim_status = 'SUBMISSION_UNKNOWN' AND claimed_at_utc IS NOT NULL AND terminal_status IS NULL)
        OR (claim_status = 'TERMINAL_RECONCILED' AND claimed_at_utc IS NOT NULL
            AND reconciled_at_utc IS NOT NULL AND terminal_status IS NOT NULL)
        OR (claim_status = 'EXPIRED_NOT_SUBMITTED' AND action_kind = 'OPEN' AND claimed_at_utc IS NULL
            AND reconciled_at_utc IS NULL AND terminal_status = 'NOT_SUBMITTED' AND expired_at_utc IS NOT NULL)),
    CHECK ((action_kind = 'OPEN' AND terminal_status IN ('OPEN_CONFIRMED', 'OPEN_REJECTED', 'NOT_SUBMITTED'))
        OR (action_kind = 'CLOSE' AND terminal_status IN ('CLOSE_CONFIRMED', 'CLOSE_REJECTED', 'NOT_SUBMITTED'))
        OR terminal_status IS NULL)
);

-- Existing installations may already have been initialized from the original
-- create-only schema.  Add the nullable deadline and terminal expiry time
-- without assigning a deadline to legacy unresolved records.
ALTER TABLE forex.h_slow_lifecycle_intent
    ADD COLUMN IF NOT EXISTS valid_until_utc TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS expired_at_utc TIMESTAMPTZ;

-- Replace the original unnamed state check, if present, so the explicit
-- non-submission expiry state is valid on an upgraded database as well.
DO $$
DECLARE state_constraint RECORD;
BEGIN
    FOR state_constraint IN
        SELECT conname FROM pg_constraint
        WHERE conrelid = 'forex.h_slow_lifecycle_intent'::regclass
          AND contype = 'c'
          AND conname IN ('h_slow_lifecycle_intent_claim_status_check',
                          'h_slow_lifecycle_intent_check1',
                          'h_slow_lifecycle_intent_state_check')
    LOOP
        EXECUTE format('ALTER TABLE forex.h_slow_lifecycle_intent DROP CONSTRAINT %I', state_constraint.conname);
    END LOOP;
END;
$$;
ALTER TABLE forex.h_slow_lifecycle_intent
    ADD CONSTRAINT h_slow_lifecycle_intent_claim_status_check CHECK
    (claim_status IN ('PENDING', 'CLAIMED', 'SUBMISSION_UNKNOWN', 'TERMINAL_RECONCILED', 'EXPIRED_NOT_SUBMITTED')),
    ADD CONSTRAINT h_slow_lifecycle_intent_state_check CHECK
    ((claim_status = 'PENDING' AND claimed_at_utc IS NULL AND terminal_status IS NULL)
        OR (claim_status = 'CLAIMED' AND claimed_at_utc IS NOT NULL AND terminal_status IS NULL)
        OR (claim_status = 'SUBMISSION_UNKNOWN' AND claimed_at_utc IS NOT NULL AND terminal_status IS NULL)
        OR (claim_status = 'TERMINAL_RECONCILED' AND claimed_at_utc IS NOT NULL
            AND reconciled_at_utc IS NOT NULL AND terminal_status IS NOT NULL)
        OR (claim_status = 'EXPIRED_NOT_SUBMITTED' AND action_kind = 'OPEN' AND claimed_at_utc IS NULL
            AND reconciled_at_utc IS NULL AND terminal_status IS NOT NULL AND terminal_status = 'NOT_SUBMITTED'
            AND valid_until_utc IS NOT NULL AND expired_at_utc IS NOT NULL AND expired_at_utc >= valid_until_utc));

CREATE INDEX IF NOT EXISTS h_slow_lifecycle_pending_scope_idx
    ON forex.h_slow_lifecycle_intent (stream_id, account_scope, terminal_instance, claim_status);

-- Different decisions must not bypass the single unresolved action per
-- isolated account. A registry revision also cannot reset an existing claim.
CREATE UNIQUE INDEX IF NOT EXISTS h_slow_lifecycle_unresolved_account_idx
    ON forex.h_slow_lifecycle_intent (account_scope)
    WHERE claim_status IN ('CLAIMED', 'SUBMISSION_UNKNOWN');

-- This is append-only evidence of a terminal reconciliation conclusion.  It
-- cannot turn an ambiguous submission into a retryable claim.
CREATE TABLE IF NOT EXISTS forex.h_slow_lifecycle_reconciliation (
    reconciliation_id BIGSERIAL PRIMARY KEY,
    action_id TEXT NOT NULL REFERENCES forex.h_slow_lifecycle_intent(action_id) ON DELETE RESTRICT,
    terminal_status TEXT NOT NULL CHECK (terminal_status IN
        ('OPEN_CONFIRMED', 'OPEN_REJECTED', 'CLOSE_CONFIRMED', 'CLOSE_REJECTED', 'NOT_SUBMITTED')),
    terminal_reference TEXT NOT NULL,
    observed_at_utc TIMESTAMPTZ NOT NULL,
    created_at_utc TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (action_id)
);

-- Expiry is not broker evidence: it records that a dated OPEN was never
-- submitted.  A separate append-only row prevents it being confused with a
-- terminal reconciliation or rewritten after the fact.
CREATE TABLE IF NOT EXISTS forex.h_slow_lifecycle_expiry (
    expiry_id BIGSERIAL PRIMARY KEY,
    action_id TEXT NOT NULL UNIQUE REFERENCES forex.h_slow_lifecycle_intent(action_id) ON DELETE RESTRICT,
    expiry_reason TEXT NOT NULL CHECK (expiry_reason = 'OPEN_INTENT_EXPIRED_BEFORE_SUBMISSION'),
    expired_at_utc TIMESTAMPTZ NOT NULL,
    created_at_utc TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE OR REPLACE FUNCTION forex.reject_h_slow_reconciliation_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'H_SLOW terminal reconciliation rows are append-only';
END;
$$;
DROP TRIGGER IF EXISTS h_slow_lifecycle_reconciliation_immutable
    ON forex.h_slow_lifecycle_reconciliation;
CREATE TRIGGER h_slow_lifecycle_reconciliation_immutable
BEFORE UPDATE OR DELETE ON forex.h_slow_lifecycle_reconciliation
FOR EACH ROW EXECUTE FUNCTION forex.reject_h_slow_reconciliation_mutation();

CREATE OR REPLACE FUNCTION forex.reject_h_slow_expiry_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'H_SLOW expiry rows are append-only';
END;
$$;
DROP TRIGGER IF EXISTS h_slow_lifecycle_expiry_immutable
    ON forex.h_slow_lifecycle_expiry;
CREATE TRIGGER h_slow_lifecycle_expiry_immutable
BEFORE UPDATE OR DELETE ON forex.h_slow_lifecycle_expiry
FOR EACH ROW EXECUTE FUNCTION forex.reject_h_slow_expiry_mutation();

COMMIT;
