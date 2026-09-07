-- Preserve broker-reported execution that cannot yet be matched to a terminal
-- position. It remains an unresolved, entry-blocking audit state; it is never
-- silently converted into a rejection or a fabricated close.
BEGIN;

DO $$ DECLARE n text; BEGIN
 SELECT conname INTO n FROM pg_constraint
 WHERE conrelid='forex.demo_position_event'::regclass AND contype='c'
   AND pg_get_constraintdef(oid) LIKE '%event_type%';
 IF n IS NOT NULL THEN EXECUTE format('ALTER TABLE forex.demo_position_event DROP CONSTRAINT %I', n); END IF;
END $$;
ALTER TABLE forex.demo_position_event
  ADD CONSTRAINT demo_position_event_type_check
  CHECK (event_type IN ('OPENED', 'UPDATED', 'CLOSED', 'REJECTED', 'FAILED', 'UNKNOWN'));

COMMIT;
