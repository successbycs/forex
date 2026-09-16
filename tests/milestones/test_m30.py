from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]


def test_m30_contract_is_autonomous_demo_only_and_names_its_artifacts():
    result = subprocess.run([sys.executable, "scripts/forex_milestones.py", "show", "--id", "M30"], cwd=ROOT, capture_output=True, text=True, check=True)
    assert "bounded autonomous GOMarketsMU-Demo" in result.stdout
    assert "GOMarketsMU-Live" in result.stdout
    assert "docs/milestones/M30-proof.md" in result.stdout
    assert "tests/milestones/test_m30.py" in result.stdout


def test_m30_verifier_refuses_a_missing_bundle():
    result = subprocess.run(["bash", "scripts/verify_m30_evidence.sh", "runs/evidence/M30/missing"], cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 2
    assert "M30 evidence verification failed" in result.stderr


def test_m30_capture_and_verifier_are_bound_to_fixed_demo_operation():
    source = (ROOT / "scripts" / "m30_evidence_contract.py").read_text(encoding="utf-8")
    capture = (ROOT / "scripts" / "capture_m30_evidence.sh").read_text(encoding="utf-8")
    assert "m20_demo_trading_session" in source
    assert "GOMarketsMU-Demo" in source
    assert "ensure_no_live_reference" in source
    assert "m20_demo_trading_session" in capture
    assert "m20_listener_disable_maintenance_hold" not in capture
