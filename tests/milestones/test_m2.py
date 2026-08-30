from pathlib import Path
import subprocess
import sys

import pytest

from forex.data_contracts import ContractError, bars_available_before, build_dataset_snapshot, validate_dataset_snapshot


def source():
    return {"contract_version": "forex.historical-data.v1", "source_id": "mt5-demo-eurusd-h1", "owner": "GO Markets Mauritius", "license": "UNQUALIFIED_BROKER_TERMINAL_DATA", "cost_model": "account-access", "api_version": "MT5-terminal", "endpoint_allowlist": [], "rate_limit": "terminal-governed", "retention_rule": "retain-redacted-metadata-and-hashes", "historical_depth": "terminal-dependent", "revision_support": "not-provided", "timezone_policy": "UTC-normalised", "outage_policy": "record-missing-observation", "approval_status": "DEMO_ONLY", "secrets_reference": "NONE", "provenance_note": "M1 fixed Demo-only historical observation; not externally source-qualified."}


def observation():
    return {"contract_version": "forex.historical-data.v1", "observation_id": "obs-001", "source_id": "mt5-demo-eurusd-h1", "source_revision": "M1-720-bars:d6adf58a", "observed_at_utc": "2026-08-28T23:00:00Z", "available_at_utc": "2026-08-28T23:00:00Z", "retrieved_at_utc": "2026-08-29T06:42:04Z", "timezone": "UTC", "payload_sha256": "sha256:d6adf58a448d203a7ff68152c00d5548bd1fc3075d3c16be8dfad3d66607efe7", "payload_path": "runs/evidence/M1/20260829T064204Z/capture.stdout.json", "redacted": True}


def snapshot():
    obs = observation()
    bars = [
        {"time_utc": "2026-08-28T20:00:00Z", "open": 1.1587, "high": 1.15893, "low": 1.15778, "close": 1.15804, "volume": 5093, "raw_observation_id": "obs-001", "available_at_utc": "2026-08-28T23:00:00Z"},
        {"time_utc": "2026-08-28T21:00:00Z", "open": 1.15804, "high": 1.15849, "low": 1.15776, "close": 1.15807, "volume": 4318, "raw_observation_id": "obs-001", "available_at_utc": "2026-08-28T23:00:00Z"},
        {"time_utc": "2026-08-28T22:00:00Z", "open": 1.15803, "high": 1.1588, "low": 1.15796, "close": 1.15858, "volume": 3752, "raw_observation_id": "obs-001", "available_at_utc": "2026-08-28T23:00:00Z"},
    ]
    return build_dataset_snapshot(snapshot_id="m2-eurusd-h1-20260828", instrument="EUR/USD", timeframe="H1", decision_cutoff_utc="2026-08-28T23:00:00Z", created_at_utc="2026-08-29T06:42:04Z", source_registry=[source()], raw_observations=[obs], price_bars=bars)


def test_m2_snapshot_is_canonical_and_hash_addressed():
    result = snapshot()
    assert validate_dataset_snapshot(result) == result
    assert result["artifact_sha256"].startswith("sha256:")


def test_m2_snapshot_rejects_future_availability_as_lookahead():
    result = snapshot()
    result["price_bars"][0]["available_at_utc"] = "2026-08-29T00:00:00Z"
    with pytest.raises(ContractError, match="unavailable"):
        validate_dataset_snapshot(result)


def test_m2_snapshot_rejects_tampered_content_hash():
    result = snapshot()
    result["price_bars"][0]["close"] = 1.1585
    with pytest.raises(ContractError, match="artifact hash"):
        validate_dataset_snapshot(result)


def test_m2_replay_never_exceeds_snapshot_cutoff():
    result = snapshot()
    assert len(bars_available_before(result, "2026-08-28T23:00:00Z")) == 3
    with pytest.raises(ContractError, match="exceeds"):
        bars_available_before(result, "2026-08-29T00:00:00Z")


def test_m2_postgres_migration_preserves_lineage_immutability_and_no_lookahead():
    migration = Path("sql/migrations/001_m2_historical_data.sql").read_text()
    for table in ("source_registry", "raw_observation", "dataset_snapshot", "dataset_snapshot_observation", "price_bar"):
        assert f"CREATE TABLE forex.{table}" in migration
    assert "REFERENCES forex.source_registry" in migration
    assert "payload_sha256" in migration
    assert "dataset snapshots are immutable once sealed" in migration
    assert "price bar availability exceeds snapshot decision cutoff" in migration
    assert "raw observation availability exceeds snapshot decision cutoff" in migration
    assert "CREATE TRIGGER price_bar_immutable" in migration
    assert "CREATE TRIGGER dataset_snapshot_observation_immutable" in migration
    assert "order_send" not in migration.lower()
    assert "gomarketsmu-live" not in migration.lower()


def test_m2_postgres_migration_static_validation_passes():
    result = subprocess.run(["python3", "scripts/check_m2_schema.py", "--root", "."], text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    assert "FOREX_M2_POSTGRES_SCHEMA_VALID" in result.stdout


def test_m2_fixed_postgres_import_contains_exact_retained_m1_bar_count():
    result = subprocess.run(["python3", "scripts/build_m2_postgres_import.py"], text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout.count("INSERT INTO forex.price_bar") == 720
    assert "VALUES ('m2-m1-eurusd-h1-720', '2026-07-17T23:00:00Z'" in result.stdout
    assert "m2-m1-eurusd-h1-720" in result.stdout
    assert "FOREX_M2_POSTGRES_IMPORT_OK" in result.stdout
    assert "GOMarketsMU-Live" not in result.stdout


def test_m2_capture_uses_only_fixed_shared_adapter_operations():
    capture = Path("scripts/capture_m2_evidence.sh").read_text()
    assert "postgres_pgvector_adapter.py" in capture
    for operation in ("preflight", "forex-m2-apply-schema --approve", "forex-m2-import --approve", "forex-m2-verify"):
        assert operation in capture
    assert "import_m2_postgres.sh" not in capture
