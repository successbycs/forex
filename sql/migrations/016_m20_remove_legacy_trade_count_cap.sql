-- Remove only the legacy Demo trade-count ceiling. All notional, loss,
-- one-position, Demo-server and append-only audit safeguards remain.
BEGIN;
ALTER TABLE forex.demo_execution_attempt
  DROP CONSTRAINT IF EXISTS demo_execution_attempt_session_id_slot_number_fkey;
ALTER TABLE forex.demo_execution_attempt ALTER COLUMN slot_number DROP NOT NULL;
ALTER TABLE forex.demo_execution_attempt
  ADD CONSTRAINT demo_execution_attempt_session_id_slot_number_fkey
  FOREIGN KEY (session_id, slot_number) REFERENCES forex.demo_trade_slot(session_id, slot_number);
ALTER TABLE forex.demo_trade_session ALTER COLUMN max_trades DROP NOT NULL;
DO $$ DECLARE n text; BEGIN
 SELECT conname INTO n FROM pg_constraint WHERE conrelid='forex.demo_trade_session'::regclass
   AND contype='c' AND pg_get_constraintdef(oid) LIKE '%max_trades%';
 IF n IS NOT NULL THEN EXECUTE format('ALTER TABLE forex.demo_trade_session DROP CONSTRAINT %I', n); END IF;
END $$;
COMMIT;
