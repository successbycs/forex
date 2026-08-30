-- M2 remediation: provenance records that underpin a sealed snapshot are
-- immutable. This migration is idempotent so the fixed T480 operation can
-- safely apply it after the initial M2 schema already exists.

BEGIN;

CREATE OR REPLACE FUNCTION forex.reject_sealed_provenance_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_TABLE_NAME = 'raw_observation' AND EXISTS (
        SELECT 1
        FROM forex.dataset_snapshot_observation link
        JOIN forex.dataset_snapshot snapshot ON snapshot.snapshot_id = link.snapshot_id
        WHERE link.observation_id = OLD.observation_id
          AND snapshot.sealed_at_utc IS NOT NULL
    ) THEN
        RAISE EXCEPTION 'sealed snapshot provenance is immutable';
    END IF;

    IF TG_TABLE_NAME = 'source_registry' AND EXISTS (
        SELECT 1
        FROM forex.raw_observation observation
        JOIN forex.dataset_snapshot_observation link ON link.observation_id = observation.observation_id
        JOIN forex.dataset_snapshot snapshot ON snapshot.snapshot_id = link.snapshot_id
        WHERE observation.source_id = OLD.source_id
          AND snapshot.sealed_at_utc IS NOT NULL
    ) THEN
        RAISE EXCEPTION 'sealed snapshot provenance is immutable';
    END IF;

    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS raw_observation_sealed_provenance_immutable ON forex.raw_observation;
CREATE TRIGGER raw_observation_sealed_provenance_immutable
BEFORE UPDATE OR DELETE ON forex.raw_observation
FOR EACH ROW EXECUTE FUNCTION forex.reject_sealed_provenance_mutation();

DROP TRIGGER IF EXISTS source_registry_sealed_provenance_immutable ON forex.source_registry;
CREATE TRIGGER source_registry_sealed_provenance_immutable
BEFORE UPDATE OR DELETE ON forex.source_registry
FOR EACH ROW EXECUTE FUNCTION forex.reject_sealed_provenance_mutation();

COMMIT;
