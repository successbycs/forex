from pathlib import Path

from scripts import postgres_pgvector_adapter


ROOT = Path(__file__).resolve().parents[2]


def test_m20_schema_is_demo_only_capped_and_append_only():
    schema = (ROOT / "sql/migrations/006_m20_demo_trading_audit.sql").read_text()
    for required in (
        "GOMarketsMU-Demo", "instrument TEXT NOT NULL CHECK (instrument = 'EURUSD')",
        "max_trades BETWEEN 1 AND 10", "INTERVAL '60 minutes'", "max_notional_usd <= 10000.00",
        "max_cumulative_notional_usd <= 100000.00", "max_open_positions = 1",
        "demo_trade_proposal", "demo_decision_snapshot", "demo_execution_attempt",
        "demo_position_event", "demo_trade_outcome", "M20 Demo trading audit rows are append-only",
    ):
        assert required in schema
    assert "GOMarketsMU-Live" not in schema


def test_m20_postgres_adapter_exposes_only_fixed_schema_and_audit_verification_operations():
    assert "forex-m20-apply-schema" in postgres_pgvector_adapter.MUTATING
    assert "forex-m20-audit-verify" in postgres_pgvector_adapter.READ_ONLY
    assert "m20_schema" in postgres_pgvector_adapter.ASSETS
    assert "m20_probe" not in postgres_pgvector_adapter.ASSETS


def test_m20_trade_ledger_is_a_read_only_profit_and_loss_projection():
    ledger = (ROOT / "sql/migrations/008_m20_account_currency_pnl.sql").read_text()
    assert "CREATE OR REPLACE VIEW forex.demo_trade_ledger" in ledger
    assert "account_currency" in ledger
    assert "PROFIT" in ledger and "LOSS" in ledger and "BREAKEVEN" in ledger
    assert "cumulative_pnl_recorded" in ledger
    assert "GOMarketsMU-Live" not in ledger
    assert "realized_pnl_account" in ledger
