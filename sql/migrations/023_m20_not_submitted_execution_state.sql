-- A reservation that loses its current quote/M1 prerequisites before MT5 is
-- called is terminally auditable and is not broker exposure.  It remains an
-- execution attempt for conservative cumulative-cap accounting.
BEGIN;

DO $$ DECLARE n text; BEGIN
 SELECT conname INTO n FROM pg_constraint
 WHERE conrelid='forex.demo_position_event'::regclass AND contype='c'
   AND pg_get_constraintdef(oid) LIKE '%event_type%';
 IF n IS NOT NULL THEN EXECUTE format('ALTER TABLE forex.demo_position_event DROP CONSTRAINT %I', n); END IF;
END $$;
ALTER TABLE forex.demo_position_event
  ADD CONSTRAINT demo_position_event_type_check
  CHECK (event_type IN ('OPENED', 'UPDATED', 'CLOSED', 'REJECTED', 'FAILED', 'UNKNOWN', 'NOT_SUBMITTED'));

COMMIT;
