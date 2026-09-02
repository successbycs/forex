-- M19: immutable research lineage for one bounded local-model observation.
-- These tables deliberately preserve research inputs and outputs only. They
-- contain no account, credential, broker-server, order or execution fields.

BEGIN;

CREATE TABLE IF NOT EXISTS forex.model_inference_lineage (
    inference_id TEXT PRIMARY KEY,
    snapshot_id TEXT NOT NULL REFERENCES forex.dataset_snapshot(snapshot_id) ON DELETE RESTRICT,
    source_label TEXT NOT NULL CHECK (source_label = 'DEMO_ONLY_HISTORICAL'),
    model_id TEXT NOT NULL CHECK (model_id = 'qwen2.5:3b'),
    model_definition_sha256 TEXT NOT NULL CHECK (model_definition_sha256 ~ '^sha256:[0-9a-f]{64}$'),
    prompt_template_version TEXT NOT NULL,
    prompt_sha256 TEXT NOT NULL CHECK (prompt_sha256 ~ '^sha256:[0-9a-f]{64}$'),
    input_sha256 TEXT NOT NULL CHECK (input_sha256 ~ '^sha256:[0-9a-f]{64}$'),
    output_sha256 TEXT NOT NULL CHECK (output_sha256 ~ '^sha256:[0-9a-f]{64}$'),
    input_payload JSONB NOT NULL,
    output_payload JSONB NOT NULL,
    validation_result TEXT NOT NULL CHECK (validation_result = 'PASS'),
    research_only BOOLEAN NOT NULL CHECK (research_only),
    order_capability BOOLEAN NOT NULL CHECK (order_capability IS FALSE),
    application_revision TEXT NOT NULL,
    configuration_fingerprint TEXT NOT NULL CHECK (configuration_fingerprint ~ '^sha256:[0-9a-f]{64}$'),
    created_at_utc TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (input_sha256, output_sha256),
    CHECK (jsonb_typeof(input_payload) = 'object'),
    CHECK (jsonb_typeof(output_payload) = 'object')
);

CREATE TABLE IF NOT EXISTS forex.research_decision_lineage (
    decision_id TEXT PRIMARY KEY,
    inference_id TEXT NOT NULL REFERENCES forex.model_inference_lineage(inference_id) ON DELETE RESTRICT,
    hypothesis_id TEXT NOT NULL CHECK (hypothesis_id = 'eurusd-h1-historical-sentiment-observation'),
    hypothesis_text TEXT NOT NULL,
    decision_state TEXT NOT NULL CHECK (decision_state = 'RESEARCH_ONLY'),
    validation_result TEXT NOT NULL CHECK (validation_result = 'PASS'),
    created_at_utc TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS model_inference_lineage_snapshot_idx
ON forex.model_inference_lineage (snapshot_id, created_at_utc DESC);

CREATE FUNCTION forex.reject_m19_lineage_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'M19 model and decision lineage is immutable';
END;
$$;

DROP TRIGGER IF EXISTS model_inference_lineage_immutable ON forex.model_inference_lineage;
CREATE TRIGGER model_inference_lineage_immutable
BEFORE UPDATE OR DELETE ON forex.model_inference_lineage
FOR EACH ROW EXECUTE FUNCTION forex.reject_m19_lineage_mutation();

DROP TRIGGER IF EXISTS research_decision_lineage_immutable ON forex.research_decision_lineage;
CREATE TRIGGER research_decision_lineage_immutable
BEFORE UPDATE OR DELETE ON forex.research_decision_lineage
FOR EACH ROW EXECUTE FUNCTION forex.reject_m19_lineage_mutation();

COMMIT;
