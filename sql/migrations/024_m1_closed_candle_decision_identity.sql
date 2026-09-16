-- Package D MVP: one terminal Demo M1 decision per closed candle.
-- Additive only; existing immutable rows are retained without a new key.
BEGIN;
ALTER TABLE forex.demo_trade_proposal
  ADD COLUMN IF NOT EXISTS decision_key TEXT,
  ADD COLUMN IF NOT EXISTS decision_candle_closed_at_utc TIMESTAMPTZ;
CREATE UNIQUE INDEX IF NOT EXISTS demo_trade_proposal_m1_decision_key_unique
  ON forex.demo_trade_proposal (decision_key)
  WHERE decision_key IS NOT NULL;
COMMIT;
