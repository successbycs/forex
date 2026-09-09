-- Preserve every breached Option B condition independently. Existing anchors
-- and resume history are untouched; the scalar remains a compatibility view.
BEGIN;
ALTER TABLE forex.demo_risk_policy_state
    ADD COLUMN IF NOT EXISTS pause_reasons TEXT[] NOT NULL DEFAULT '{}';
ALTER TABLE forex.demo_risk_policy_state
    ADD COLUMN IF NOT EXISTS account_scope_sha256 TEXT
    CHECK (account_scope_sha256 ~ '^[0-9a-f]{64}$');
ALTER TABLE forex.demo_risk_policy_state
    ADD COLUMN IF NOT EXISTS last_observed_equity NUMERIC(14,2),
    ADD COLUMN IF NOT EXISTS risk_observed_at_utc TIMESTAMPTZ;
UPDATE forex.demo_risk_policy_state
SET pause_reasons = ARRAY[pause_reason]
WHERE pause_reason IS NOT NULL AND cardinality(pause_reasons) = 0;

ALTER TABLE forex.demo_risk_policy_state
    DROP CONSTRAINT IF EXISTS demo_risk_pause_consistency;
ALTER TABLE forex.demo_risk_policy_state
    ADD CONSTRAINT demo_risk_pause_consistency CHECK (
        array_position(pause_reasons, NULL) IS NULL
        AND pause_reasons <@ ARRAY['DAILY_LOSS','WEEKLY_LOSS','PEAK_DRAWDOWN',
                                  'EXTERNAL_CASH_FLOW','UNKNOWN_ACCOUNT_STATE']::TEXT[]
        AND ((cardinality(pause_reasons) = 0 AND pause_reason IS NULL)
             OR (cardinality(pause_reasons) > 0 AND pause_reason IS NOT NULL
                 AND pause_reason = ANY(pause_reasons)))
    );
COMMIT;
