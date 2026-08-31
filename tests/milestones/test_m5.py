from pathlib import Path


def test_m5_fixed_adapter_has_idempotent_snapshot_guard():
    text=(Path(__file__).parents[2]/'scripts/postgres_pgvector_adapter.py').read_text()
    assert 'FOREX_M2_IMPORT_ALREADY_PRESENT' in text
    assert 'artifact_sha256' in text
    assert 'forex-m2-import' in text
