import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import subprocess

from forex.ollama_evaluation import EXPERIMENT_SESSIONS, action_from_sentiment, evaluate
from scripts import postgres_pgvector_adapter
from scripts.m20_ollama_evaluation_probe import retrospective_close


def response(sentiment: str, abstain: bool = False) -> dict:
    return {"sentiment": sentiment, "abstain": abstain, "research_only": True, "order_capability": False}


def experiments() -> list[dict]:
    return [
        {
            "decision_at_utc": f"2026-07-{day:02d}T09:00:00+00:00", "entry_at_utc": f"2026-07-{day:02d}T09:00:00+00:00",
            "exit_at_utc": f"2026-07-{day:02d}T20:00:00+00:00", "entry_close": 1.10, "exit_close": 1.11 if day % 2 else 1.09,
            "context_bar_count": 12, "model_output_sha256": f"sha256:{day:064x}",
            "model_response_valid": True,
            "invocation_metadata": {"input_context_sha256": f"sha256:{day:064x}", "prompt_sha256": f"sha256:{day + 3:064x}", "response_schema_sha256": f"sha256:{day + 6:064x}"},
            "response": response("POSITIVE" if day % 2 else "NEGATIVE"), "price_only_action": "BUY",
        }
        for day in range(1, EXPERIMENT_SESSIONS + 1)
    ]


def test_m20_evaluation_is_fixed_chronological_and_research_only():
    result = evaluate(experiments())
    assert result["marker"] == "FOREX_M20_EVALUATION_OK"
    assert result["predeclared_controls"]["sessions"] == 3
    assert result["predeclared_controls"]["random_shuffling_used"] is False
    assert len(result["rows"]) == 3
    assert result["valid_model_response_count"] == 3
    assert all("invocation_metadata" in row for row in result["rows"])
    assert result["comparison"]["no_change"]["actionable_sessions"] == 0
    assert result["research_only"] is True and result["order_capability"] is False


def test_m20_rejects_decisions_after_the_recorded_entry_bar():
    rows = experiments()
    rows[0]["decision_at_utc"] = "2026-07-01T10:00:00+00:00"
    try:
        evaluate(rows)
    except ValueError as exc:
        assert "no later than the entry" in str(exc)
    else:
        raise AssertionError("M20 accepted a decision after its entry bar")


def test_m20_abstention_is_evaluation_no_trade_and_rejects_order_surface():
    assert action_from_sentiment(response("ABSTAIN", True)) == "NO_TRADE"
    unsafe = response("POSITIVE")
    unsafe["order_capability"] = True
    try:
        action_from_sentiment(unsafe)
    except ValueError as exc:
        assert "research-only" in str(exc)
    else:
        raise AssertionError("M20 accepted an order-capable response")


def test_m20_adapter_exposes_one_fixed_read_only_probe():
    assert "forex-m20-ollama-evaluation-probe" in postgres_pgvector_adapter.READ_ONLY
    assert "m20_probe" in postgres_pgvector_adapter.ASSETS
    assert "forex-m20-ollama-evaluation-probe" not in postgres_pgvector_adapter.MUTATING


def test_m20_uses_declared_h1_bar_close_assumption_for_historical_decisions():
    assert retrospective_close("2026-07-01 08:00:00+00") == "2026-07-01T09:00:00Z"


def test_m20_evidence_verifier_remains_fail_closed_with_python_optimization(tmp_path: Path):
    root = tmp_path
    script = root / "scripts" / "verify_m20_evidence.sh"
    script.parent.mkdir()
    script.write_bytes((Path(__file__).resolve().parents[2] / "scripts" / "verify_m20_evidence.sh").read_bytes())
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "M20 test"], cwd=root, check=True)
    subprocess.run(["git", "commit", "--allow-empty", "-qm", "fixture"], cwd=root, check=True)
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    bundle = root / "runs" / "evidence" / "M20" / "fixture"
    bundle.mkdir(parents=True)
    summary = bundle / "summary.txt"
    summary.write_text("FOREX_M20_PROOF_OK\n", encoding="utf-8")
    digest = "sha256:" + "a" * 64
    row = {"decision_at_utc": "2026-01-01T00:00:00Z", "entry_at_utc": "2026-01-01T00:00:00Z", "exit_at_utc": "2026-01-01T01:00:00Z", "invocation_metadata": {key: digest for key in ("input_context_sha256", "prompt_sha256", "response_schema_sha256")}}
    evaluation = {"marker": "FOREX_M20_EVALUATION_OK", "model": "qwen2.5:3b", "rows": [row, row, row], "valid_model_response_count": 3, "predeclared_controls": {"chronological_only": True, "random_shuffling_used": False}, "research_only": True, "order_capability": False}
    probe = {"ok": True, "result": {"stdout": json.dumps({"marker": "FOREX_M20_OLLAMA_EVALUATION_PROBE_OK", "source": "DEMO_ONLY_HISTORICAL", "order_capability": False, "live_trading_capability": False, "ollama_provenance": {"runtime_version": "test", "model_inventory": "test", "model_details": "test", "model_inventory_sha256": digest, "model_details_sha256": digest}, "evaluation": evaluation})}}
    probe_path = bundle / "evaluation-probe.json"
    probe_path.write_text(json.dumps(probe), encoding="utf-8")
    manifest = {"milestone_id": "M20", "dirty_worktree": False, "git_revision": revision, "captured_at": datetime.now(timezone.utc).isoformat(), "external_dependencies": [{"ok": True, "clean_worktree": True, "actual_git_revision": revision, "expected_git_revision": revision}], "artifacts": [{"path": "summary.txt", "sha256": hashlib.sha256(summary.read_bytes()).hexdigest()}, {"path": "evaluation-probe.json", "sha256": hashlib.sha256(probe_path.read_bytes()).hexdigest()}]}
    (bundle / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    environment = {**os.environ, "PYTHONOPTIMIZE": "1"}
    passed = subprocess.run(["bash", str(script), str(bundle)], cwd=root, env=environment, text=True, capture_output=True)
    assert passed.returncode == 0, passed.stderr
    summary.write_text("tampered\n", encoding="utf-8")
    failed = subprocess.run(["bash", str(script), str(bundle)], cwd=root, env=environment, text=True, capture_output=True)
    assert failed.returncode != 0
