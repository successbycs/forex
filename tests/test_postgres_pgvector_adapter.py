from unittest import mock

from scripts import postgres_pgvector_adapter


def test_adapter_exposes_only_fixed_m2_operations():
    assert postgres_pgvector_adapter.READ_ONLY | postgres_pgvector_adapter.MUTATING == {
        "preflight", "inspect", "vector-probe", "forex-m2-apply-schema", "forex-m2-import", "forex-m2-verify", "forex-m2-provenance-negative-control"
    }


def test_schema_application_is_hash_bound_and_rerunnable():
    with mock.patch.object(postgres_pgvector_adapter, "asset", side_effect=[("sql/migrations/001_m2_historical_data.sql", "a" * 64), ("sql/migrations/002_m2_sealed_provenance.sql", "b" * 64)]), mock.patch.object(postgres_pgvector_adapter, "remote", return_value={"ok": True}) as remote:
        assert postgres_pgvector_adapter.apply_schema()["ok"]
    assert "sha256sum" in remote.call_args.args[0]
    assert "FOREX_M2_SCHEMA_ALREADY_APPLIED" in remote.call_args.args[0]


def test_import_is_hash_bound():
    with mock.patch.object(postgres_pgvector_adapter, "asset", return_value=("scripts/build_m2_postgres_import.py", "b" * 64)), mock.patch.object(postgres_pgvector_adapter, "remote", return_value={"ok": True}) as remote:
        assert postgres_pgvector_adapter.import_snapshot()["ok"]
    assert "sha256sum" in remote.call_args.args[0]
    assert "FOREX_M2_IMPORT_ALREADY_PRESENT" in remote.call_args.args[0]


def test_verification_query_checks_m2_lineage_and_point_in_time_controls():
    with mock.patch.object(postgres_pgvector_adapter, "remote", return_value={"ok": True}) as remote:
        assert postgres_pgvector_adapter.verify_snapshot()["ok"]
    query = remote.call_args.args[0]
    for required in ("source_status", "snapshot=", "lineage_ok", "bar_availability_ok", "price_bar_point_in_time", "snapshot_observation_point_in_time", "sealed_provenance_triggers"):
        assert required in query


def test_provenance_negative_control_attempts_both_sealed_mutations():
    with mock.patch.object(postgres_pgvector_adapter, "remote", return_value={"ok": True}) as remote:
        assert postgres_pgvector_adapter.provenance_negative_control()["ok"]
    query = remote.call_args.args[0]
    assert "UPDATE forex.raw_observation" in query
    assert "UPDATE forex.source_registry" in query
    assert "FOREX_M2_SEALED_PROVENANCE_NEGATIVE_CONTROL_OK" in query
