-- M2 canonical historical-research persistence.  This migration stores
-- metadata and normalized OHLCV only; it deliberately has no broker, order,
-- credential, live-server, or network capability.

BEGIN;

CREATE SCHEMA IF NOT EXISTS forex;

CREATE TABLE forex.source_registry (
    source_id TEXT PRIMARY KEY,
    contract_version TEXT NOT NULL,
    owner TEXT NOT NULL,
    license TEXT NOT NULL,
    cost_model TEXT NOT NULL,
    api_version TEXT NOT NULL,
    endpoint_allowlist JSONB NOT NULL DEFAULT '[]'::jsonb,
    rate_limit TEXT NOT NULL,
    retention_rule TEXT NOT NULL,
    historical_depth TEXT NOT NULL,
    revision_support TEXT NOT NULL,
    timezone_policy TEXT NOT NULL CHECK (timezone_policy = 'UTC-normalised'),
    outage_policy TEXT NOT NULL,
    approval_status TEXT NOT NULL CHECK (approval_status IN ('DEMO_ONLY', 'PENDING_QUALIFICATION', 'APPROVED')),
    secrets_reference TEXT NOT NULL CHECK (secrets_reference = 'NONE' OR secrets_reference LIKE 'ENV:%'),
    provenance_note TEXT NOT NULL,
    created_at_utc TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE forex.raw_observation (
    observation_id TEXT PRIMARY KEY,
    contract_version TEXT NOT NULL,
    source_id TEXT NOT NULL REFERENCES forex.source_registry(source_id),
    source_revision TEXT NOT NULL,
    observed_at_utc TIMESTAMPTZ NOT NULL,
    available_at_utc TIMESTAMPTZ NOT NULL CHECK (available_at_utc >= observed_at_utc),
    retrieved_at_utc TIMESTAMPTZ NOT NULL CHECK (retrieved_at_utc >= observed_at_utc),
    timezone TEXT NOT NULL CHECK (timezone = 'UTC'),
    payload_sha256 TEXT NOT NULL CHECK (payload_sha256 ~ '^sha256:[0-9a-f]{64}$'),
    payload_path TEXT NOT NULL,
    redacted BOOLEAN NOT NULL,
    UNIQUE (source_id, source_revision, payload_sha256)
);

CREATE TABLE forex.dataset_snapshot (
    snapshot_id TEXT PRIMARY KEY,
    contract_version TEXT NOT NULL,
    instrument TEXT NOT NULL CHECK (instrument = 'EUR/USD'),
    timeframe TEXT NOT NULL CHECK (timeframe IN ('M15', 'H1', 'D1')),
    decision_cutoff_utc TIMESTAMPTZ NOT NULL,
    created_at_utc TIMESTAMPTZ NOT NULL CHECK (created_at_utc >= decision_cutoff_utc),
    artifact_sha256 TEXT NOT NULL UNIQUE CHECK (artifact_sha256 ~ '^sha256:[0-9a-f]{64}$'),
    no_lookahead BOOLEAN NOT NULL CHECK (no_lookahead),
    sealed_at_utc TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE forex.dataset_snapshot_observation (
    snapshot_id TEXT NOT NULL REFERENCES forex.dataset_snapshot(snapshot_id) ON DELETE RESTRICT,
    observation_id TEXT NOT NULL REFERENCES forex.raw_observation(observation_id) ON DELETE RESTRICT,
    PRIMARY KEY (snapshot_id, observation_id)
);

CREATE TABLE forex.price_bar (
    snapshot_id TEXT NOT NULL REFERENCES forex.dataset_snapshot(snapshot_id) ON DELETE RESTRICT,
    time_utc TIMESTAMPTZ NOT NULL,
    open NUMERIC(18,8) NOT NULL CHECK (open > 0),
    high NUMERIC(18,8) NOT NULL CHECK (high > 0),
    low NUMERIC(18,8) NOT NULL CHECK (low > 0),
    close NUMERIC(18,8) NOT NULL CHECK (close > 0),
    volume BIGINT NOT NULL CHECK (volume >= 0),
    raw_observation_id TEXT NOT NULL REFERENCES forex.raw_observation(observation_id) ON DELETE RESTRICT,
    available_at_utc TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (snapshot_id, time_utc),
    CHECK (high >= GREATEST(open, close) AND low <= LEAST(open, close))
);

CREATE INDEX price_bar_snapshot_available_idx ON forex.price_bar (snapshot_id, available_at_utc, time_utc);

CREATE FUNCTION forex.reject_snapshot_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'dataset snapshots are immutable once sealed';
END;
$$;

CREATE TRIGGER dataset_snapshot_immutable
BEFORE UPDATE OR DELETE ON forex.dataset_snapshot
FOR EACH ROW EXECUTE FUNCTION forex.reject_snapshot_mutation();

CREATE TRIGGER dataset_snapshot_observation_immutable
BEFORE UPDATE OR DELETE ON forex.dataset_snapshot_observation
FOR EACH ROW EXECUTE FUNCTION forex.reject_snapshot_mutation();

CREATE FUNCTION forex.enforce_snapshot_point_in_time() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE cutoff TIMESTAMPTZ;
BEGIN
    SELECT decision_cutoff_utc INTO cutoff FROM forex.dataset_snapshot WHERE snapshot_id = NEW.snapshot_id;
    IF NEW.available_at_utc > cutoff THEN
        RAISE EXCEPTION 'price bar availability exceeds snapshot decision cutoff';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER price_bar_point_in_time
BEFORE INSERT OR UPDATE ON forex.price_bar
FOR EACH ROW EXECUTE FUNCTION forex.enforce_snapshot_point_in_time();

CREATE TRIGGER price_bar_immutable
BEFORE UPDATE OR DELETE ON forex.price_bar
FOR EACH ROW EXECUTE FUNCTION forex.reject_snapshot_mutation();

CREATE FUNCTION forex.enforce_observation_point_in_time() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE cutoff TIMESTAMPTZ;
DECLARE available TIMESTAMPTZ;
BEGIN
    SELECT decision_cutoff_utc INTO cutoff FROM forex.dataset_snapshot WHERE snapshot_id = NEW.snapshot_id;
    SELECT available_at_utc INTO available FROM forex.raw_observation WHERE observation_id = NEW.observation_id;
    IF available > cutoff THEN
        RAISE EXCEPTION 'raw observation availability exceeds snapshot decision cutoff';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER snapshot_observation_point_in_time
BEFORE INSERT ON forex.dataset_snapshot_observation
FOR EACH ROW EXECUTE FUNCTION forex.enforce_observation_point_in_time();

COMMIT;
