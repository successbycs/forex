-- M2 remediation: the raw observation underpinning a sealed snapshot is
-- immutable. Source registry metadata remains editable as a current catalog;
-- corrected historical data is represented by a new raw observation.

BEGIN;

CREATE OR REPLACE FUNCTION forex.reject_sealed_provenance_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_TABLE_NAME = 'raw_observation' THEN
        IF EXISTS (
            SELECT 1
            FROM forex.dataset_snapshot_observation link
            JOIN forex.dataset_snapshot snapshot ON snapshot.snapshot_id = link.snapshot_id
            WHERE link.observation_id = OLD.observation_id
              AND snapshot.sealed_at_utc IS NOT NULL
        ) THEN
            RAISE EXCEPTION 'sealed snapshot provenance is immutable';
        END IF;
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

COMMIT;
