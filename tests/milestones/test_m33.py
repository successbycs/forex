from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _commission(volume: str) -> tuple[Decimal, Decimal, Decimal]:
    side = -(Decimal("3.00") * Decimal(volume)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return side, side, side + side


def test_m33_commission_examples_replace_actual_commission_once():
    assert _commission("0.01") == (Decimal("-0.03"), Decimal("-0.03"), Decimal("-0.06"))
    assert _commission("1.00") == (Decimal("-3.00"), Decimal("-3.00"), Decimal("-6.00"))
    actual_net = Decimal("0.45")
    actual_commission = Decimal("0.00")
    assert actual_net - actual_commission + _commission("0.01")[2] == Decimal("0.39")
    assert Decimal("0.45") - Decimal("-0.02") + _commission("0.01")[2] == Decimal("0.41")


def test_m33_migration_is_additive_source_bound_and_excludes_open_positions():
    source = (ROOT / "sql/migrations/026_m33_demo_pro_forma_commission.sql").read_text()
    for required in (
        "CREATE TABLE IF NOT EXISTS forex.demo_pricing_profile",
        "CREATE TABLE IF NOT EXISTS forex.demo_trade_pro_forma_pnl",
        "GO_PLUS_AUD_V1", "ASSUMED", "canonical_source_fingerprint",
        "demo_m33_closed_trade_source", "fill_status' = 'FULL'",
        "outcome.reconciliation_status = 'MATCHED'", "latest_revision.disposition IS NULL",
        "pro_forma_live_pnl_aud = actual_broker_net_aud - actual_broker_commission_aud + estimated_round_trip_commission_aud",
        "ON CONFLICT (proposal_id, profile_version_id, calculation_version, canonical_source_fingerprint) DO NOTHING",
    ):
        assert required in source
    assert "demo_open_position_state" not in source
    assert "UPDATE forex.demo_trade_outcome" not in source
    assert "DELETE FROM forex.demo_trade_outcome" not in source


def test_m33_refresh_rejects_multiple_or_invalid_opening_fills_and_projects_new_closes():
    source = (ROOT / "sql/migrations/027_m33_refresh_pro_forma_commission.sql").read_text()
    for required in ("COUNT(*) = 1", "fill_status') = 'FULL'", "volume' ~", "volume_lots, 2)",
                     "refresh_demo_m33_pro_forma_commission", "AFTER INSERT ON forex.demo_trade_outcome",
                     "ON CONFLICT (proposal_id, profile_version_id, calculation_version,"):
        assert required in source
    assert "ORDER BY event.observed_at_utc, event.event_id\n    LIMIT 1" not in source


def test_m33_terminal_ledger_uses_an_explicit_assumption_label():
    source = (ROOT / "scripts/m20_trade_ledger_dashboard.py").read_text()
    assert "Commission-adjusted Demo P&L — GO Plus+ AUD assumption" in source
    assert "Actual broker P&L" in source
    assert "('commission_account', 'fee_account', 'swap_account')" in source


def test_m33_proof_surface_has_fixed_capture_and_offline_verification():
    capture = (ROOT / "scripts/capture_m33_evidence.sh").read_text()
    verify = (ROOT / "scripts/verify_m33_evidence.sh").read_text()
    collector = (ROOT / "scripts/m33_pro_forma_evidence.py").read_text()
    proof = (ROOT / "docs/milestones/M33-proof.md").read_text()
    assert "m33_pro_forma_evidence.py capture" in capture
    assert "m33_pro_forma_evidence.py verify" in verify
    for required in ("FOREX_M33_PRO_FORMA_COMMISSION_OK", "m33-projection.json", "terminal-ledger.txt", "open_position_overlap=", "refresh_trigger=true", "m20-lifecycle.json", '"schema_version": "1.0.0"', '"dirty_worktree": False'):
        assert required in collector
    assert "Decimal(str(value))" in collector
    assert 'git", "status", "--porcelain"' in collector
    assert "GO_PLUS_AUD_V1" in proof and "Demo-only" in proof
