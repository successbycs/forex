-- Append-only record for a fixed operator resume request.  A request clears
-- only a manual pause marker; the next account check re-applies every current
-- Option B loss and drawdown limit before another entry can be reserved.
BEGIN;

ALTER TABLE forex.demo_risk_policy_state
    ADD COLUMN IF NOT EXISTS cash_flow_review_approved BOOLEAN NOT NULL DEFAULT FALSE;

CREATE TABLE IF NOT EXISTS forex.demo_risk_policy_resume (
    resume_id UUID PRIMARY KEY,
    policy_version TEXT NOT NULL REFERENCES forex.demo_risk_policy_state(policy_version),
    previous_pause_reason TEXT NOT NULL CHECK (previous_pause_reason IN ('WEEKLY_LOSS', 'PEAK_DRAWDOWN', 'EXTERNAL_CASH_FLOW', 'UNKNOWN_ACCOUNT_STATE')),
    requested_at_utc TIMESTAMPTZ NOT NULL DEFAULT now(),
    operator_action TEXT NOT NULL CHECK (operator_action = 'm20_listener_resume_risk_policy')
);

CREATE OR REPLACE FUNCTION forex.reject_demo_risk_policy_resume_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'demo risk-policy resume records are append-only';
END;
$$;

DROP TRIGGER IF EXISTS demo_risk_policy_resume_immutable ON forex.demo_risk_policy_resume;
CREATE TRIGGER demo_risk_policy_resume_immutable
BEFORE UPDATE OR DELETE ON forex.demo_risk_policy_resume
FOR EACH ROW EXECUTE FUNCTION forex.reject_demo_risk_policy_resume_mutation();

COMMIT;
