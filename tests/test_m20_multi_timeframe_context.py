import importlib.util
from pathlib import Path

import pytest

from scripts import postgres_pgvector_adapter


ROOT = Path(__file__).resolve().parents[1]


def _bridge():
    spec = importlib.util.spec_from_file_location("m20_mtf_context_bridge", ROOT / "t480" / "m20_postgres_audit_bridge.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _context(*, action: str = "BUY") -> dict:
    inputs = {
        "selected_m1_owner": "momentum_breakout",
        "pre_context_m1_candidate": {"action": action, "strategy_id": "momentum_breakout"},
        "final_m1_action": action,
    }
    return {
        "context_id": "context-1", "proposal_id": "proposal-1", "selected_m1_action": action,
        "overall_alignment": "UNAVAILABLE", "context_disposition": "NEUTRAL",
        "reason": "M5 and H1 are unavailable; M1 remains unchanged.",
        "rule_version": "forex.m20.12.mtf-context.v1",
        "retrieved_at_utc": "2026-09-04T00:10:02Z",
        "source_inputs_sha256": "sha256:" + "a" * 64,
        "contexts": [
            {"timeframe": "M5", "closed_at_utc": None, "data_age_seconds": None,
             "integrity_status": "UNAVAILABLE", "market_state": "UNKNOWN",
             "volatility_state": "UNKNOWN", "liquidity_state": "UNKNOWN",
             "alignment": "UNAVAILABLE", "reason": "No completed native M5 candle.", "source_inputs": inputs},
            {"timeframe": "H1", "closed_at_utc": None, "data_age_seconds": None,
             "integrity_status": "UNAVAILABLE", "market_state": "UNKNOWN",
             "volatility_state": "UNKNOWN", "liquidity_state": "UNKNOWN",
             "alignment": "UNAVAILABLE", "reason": "No completed native H1 candle.", "source_inputs": inputs},
        ],
    }


def test_m20_mtf_schema_is_immutable_and_preserves_only_m5_h1_observations():
    schema = (ROOT / "sql/migrations/015_m20_multi_timeframe_context.sql").read_text(encoding="utf-8")
    for required in (
        "demo_multi_timeframe_context", "demo_multi_timeframe_context_bar",
        "timeframe IN ('M5', 'H1')", "context_disposition IN ('OBSERVE_ONLY', 'NEUTRAL', 'HARD_CONFLICT')",
        "selected_m1_action", "source_inputs_sha256", "demo_multi_timeframe_context_immutable",
        "demo_multi_timeframe_context_bar_immutable", "exactly M5 and H1 rows",
    ):
        assert required in schema
    assert "GOMarketsMU-Live" not in schema
    # It is a purely additive staged migration: it neither rewrites legacy
    # ledger evidence nor backfills inferred historical context.
    for forbidden in ("UPDATE forex.demo_", "DELETE FROM forex.demo_", "ALTER TABLE forex.demo_trade_", "INSERT INTO forex.demo_trade_"):
        assert forbidden not in schema


def test_m20_mtf_context_accepts_visible_neutral_unavailability_without_changing_m1_action():
    bridge = _bridge()
    proposal = {"proposal_id": "proposal-1", "action": "BUY"}
    value = bridge._multi_timeframe_context({"multi_timeframe_context": _context()}, proposal)
    assert value["context_disposition"] == "NEUTRAL"
    assert [row["timeframe"] for row in value["contexts"]] == ["M5", "H1"]


def test_m20_mtf_context_rejects_a_context_that_changes_the_pre_context_m1_candidate():
    bridge = _bridge()
    value = _context()
    value["contexts"][1]["source_inputs"] = {**value["contexts"][1]["source_inputs"], "final_m1_action": "SELL"}
    with pytest.raises(SystemExit, match="cannot alter the M1 proposal action"):
        bridge._multi_timeframe_context({"multi_timeframe_context": value}, {"proposal_id": "proposal-1", "action": "BUY"})


def test_m20_mtf_context_adapter_is_fixed_stage_apply_and_read_only_summary_only():
    assert postgres_pgvector_adapter.ASSETS["m20_multi_timeframe_context_schema"] == "sql/migrations/015_m20_multi_timeframe_context.sql"
    assert "forex-m20-stage-mtf-context-schema" in postgres_pgvector_adapter.MUTATING
    assert "forex-m20-apply-mtf-context-schema" in postgres_pgvector_adapter.MUTATING
    assert "forex-m20-mtf-context-verify" in postgres_pgvector_adapter.READ_ONLY
    assert "forex-m20-mtf-context-summary" in postgres_pgvector_adapter.READ_ONLY


def test_m20_mtf_summary_keeps_costs_pnl_holding_time_and_mae_mfe_limit_visible(monkeypatch):
    monkeypatch.setattr(postgres_pgvector_adapter, "remote", lambda command: {"ok": True, "command": command})
    command = postgres_pgvector_adapter.m20_multi_timeframe_context_summary()["result"]["command"]
    for field in ("realized_pnl_account", "commission_account", "fee_account", "estimated_total_cost_account", "holding_seconds", "NOT_RETAINED_IN_M20_12"):
        assert field in command
