from pathlib import Path

from scripts import postgres_pgvector_adapter


ROOT = Path(__file__).resolve().parents[2]


def test_m19_schema_persists_hashed_model_and_research_decision_lineage_only():
    schema = (ROOT / "sql/migrations/005_m19_decision_model_lineage.sql").read_text()
    for required in (
        "forex.model_inference_lineage", "forex.research_decision_lineage", "input_payload JSONB",
        "output_payload JSONB", "model_definition_sha256", "prompt_sha256", "input_sha256", "output_sha256",
        "validation_result = 'PASS'", "research_only", "order_capability IS FALSE", "RESEARCH_ONLY",
        "M19 model and decision lineage is immutable",
    ):
        assert required in schema


def test_m19_adapter_exposes_only_named_schema_persistence_and_replay_operations():
    assert "forex-m19-apply-schema" in postgres_pgvector_adapter.MUTATING
    assert "forex-m19-lineage-probe" in postgres_pgvector_adapter.MUTATING
    assert "forex-m19-lineage-verify" in postgres_pgvector_adapter.READ_ONLY
    assert "m19_schema" in postgres_pgvector_adapter.ASSETS
    assert "m19_probe" in postgres_pgvector_adapter.ASSETS


def test_m19_fixed_probe_has_no_caller_supplied_argument_or_trade_surface():
    source = (ROOT / "scripts/m19_lineage_probe.py").read_text()
    assert "argparse" not in source
    assert 'MODEL = "qwen2.5:3b"' in source
    assert "GOMarketsMU-Live" not in source
    assert '"order_capability": False' in source
