from pathlib import Path
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import m30_evidence_contract as contract
from test_m20 import fixture as m20_fixture, write


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


def fixture(tmp_path):
    root, prior = m20_fixture(tmp_path)
    bundle = root / "runs/evidence/M30/fixture"
    bundle.mkdir(parents=True)
    for name in contract.REQUIRED - {"manifest.json", "summary.txt", "m30-audit.json"}:
        (bundle / name).write_bytes((prior / name).read_bytes())
    wrapper = json.loads((bundle / "demo-trading-operation.json").read_text())
    payload = json.loads(wrapper["result"]["stdout"])
    payload["operation"] = "m20_demo_trading_session"
    at = payload["decision_snapshot"]["observed_at_utc"]
    snapshot = payload["decision_snapshot"]
    snapshot.update(captured_at_utc=at, freshness_seconds=0)
    proposal = payload["proposal"]
    proposal.update(action="BUY", decision_at_utc=at, notional_usd=100,
                    proposed_entry=1.1001, stop_loss=1.099, take_profit=1.101)
    proposal["expires_at_utc"] = (datetime.fromisoformat(at.replace("Z", "+00:00")) + timedelta(minutes=5)).isoformat()
    selection = payload["strategy_selection"]
    selection.update(selected_strategy_id="momentum_breakout", trade_owner_strategy_id="momentum_breakout",
                     selection_status="SELECTED_EXECUTABLE", cost_coverage_status="FEASIBLE")
    payload["execution"] = {"status": "ACCEPTED", "attempt_id": "attempt-1", "proposal_id": proposal["proposal_id"],
                            "session_id": payload["session"]["session_id"], "idempotency_key": "attempt-1-key",
                            "submitted_at_utc": at, "open_positions_before": 0, "cumulative_notional_before_usd": 0,
                            "monitor_job_scheduled": True}
    payload["reconciliation"] = {"status": "OPEN_MONITORING", "position_ticket": 99}
    payload["postgres_audit"]["execution_attempt_id"] = "attempt-1"
    wrapper["result"]["stdout"] = json.dumps(payload)
    write(bundle / "demo-trading-operation.json", wrapper)
    wrapper = json.loads((bundle / "lifecycle-summary.json").read_text())
    row = json.loads(wrapper["result"]["stdout"])[0]
    row.update(proposal_id=proposal["proposal_id"], attempt_id="attempt-1", snapshot_id=proposal["snapshot_id"],
               proposal_expires_at_utc=proposal["expires_at_utc"], close_reason="BROKER_SIDE_CLOSE")
    row["opening_context"]["position_ticket"] = 99
    row["closing_context"].update(position_ticket=99, close_reason="BROKER_SIDE_CLOSE")
    wrapper["result"]["stdout"] = json.dumps([row])
    write(bundle / "lifecycle-summary.json", wrapper)
    contract.capture(bundle, root)
    return root, bundle


def verify(root, bundle):
    return subprocess.run([sys.executable, str(ROOT / "scripts/m30_evidence_contract.py"), "verify", "--root", str(root), "--bundle", str(bundle)],
                          capture_output=True, text=True, env={**os.environ, "PYTHONOPTIMIZE": "1"})


def rehash(bundle):
    manifest = json.loads((bundle / "manifest.json").read_text())
    manifest["artifacts"] = contract.artifacts(bundle)
    write(bundle / "manifest.json", manifest)


def mutate_payload(bundle, change):
    wrapper = json.loads((bundle / "demo-trading-operation.json").read_text())
    value = json.loads(wrapper["result"]["stdout"])
    change(value)
    wrapper["result"]["stdout"] = json.dumps(value)
    write(bundle / "demo-trading-operation.json", wrapper)
    rehash(bundle)


def mutate_lifecycle(bundle, change):
    wrapper = json.loads((bundle / "lifecycle-summary.json").read_text())
    rows = json.loads(wrapper["result"]["stdout"])
    change(rows)
    wrapper["result"]["stdout"] = json.dumps(rows)
    write(bundle / "lifecycle-summary.json", wrapper)
    rehash(bundle)


def test_m30_accepts_real_executor_async_shape_with_exact_closed_broker_lifecycle(tmp_path):
    root, bundle = fixture(tmp_path)
    result = verify(root, bundle)
    assert result.returncode == 0, result.stderr
    assert contract.MARKER in result.stdout
    registry = json.loads((ROOT / "milestone_registry.json").read_text())
    assert contract.SURFACE == next(row for row in registry["milestones"] if row["milestone_id"] == "M30")["real_world_proof"]["surface"]


@pytest.mark.parametrize("mutation, message", [
    (lambda p: p["proposal"].update(action="NO_TRADE", notional_usd=None), "actionable"),
    (lambda p: p.update(server="GOMarketsMU-Live"), "Live-server"),
    (lambda p: p["execution"].update(status="REJECTED"), "accepted"),
    (lambda p: p["execution"].update(monitor_job_scheduled=False), "scheduled monitor"),
    (lambda p: p["reconciliation"].update(position_ticket=100), "position ticket mismatch"),
    (lambda p: p["decision_snapshot"]["safety_gates"].update(fresh_quote=False), "failed safety gate"),
])
def test_m30_rejects_invalid_entry_even_after_rehash(tmp_path, mutation, message):
    root, bundle = fixture(tmp_path)
    mutate_payload(bundle, mutation)
    result = verify(root, bundle)
    assert result.returncode == 2
    assert message in result.stderr


@pytest.mark.parametrize("field, value, message", [
    ("proposal_id", "different-proposal", "exact operation"),
    ("attempt_id", "different-attempt", "exact operation"),
    ("snapshot_id", "different-snapshot", "snapshot_id mismatch"),
    ("lifecycle", "OPEN_MONITORING", "no broker-matched"),
    ("reconciliation_status", "UNRESOLVED", "no broker-matched"),
    ("application_revision", "0" * 40, "no broker-matched"),
    ("close_reason", "MANUAL", "owner exit contract"),
])
def test_m30_rejects_wrong_or_incomplete_lifecycle(tmp_path, field, value, message):
    root, bundle = fixture(tmp_path)
    mutate_lifecycle(bundle, lambda rows: rows[0].update({field: value}))
    result = verify(root, bundle)
    assert result.returncode == 2
    assert message in result.stderr


def test_m30_ignores_other_closed_trades_in_the_same_continuous_lease(tmp_path):
    root, bundle = fixture(tmp_path)
    mutate_lifecycle(bundle, lambda rows: rows.append({**rows[0], "proposal_id": "unrelated", "attempt_id": "other"}))
    result = verify(root, bundle)
    assert result.returncode == 0, result.stderr


def test_m30_rejects_duplicate_matching_lifecycles(tmp_path):
    root, bundle = fixture(tmp_path)
    mutate_lifecycle(bundle, lambda rows: rows.append(rows[0]))
    assert "one lifecycle" in verify(root, bundle).stderr


def test_m30_rejects_broker_exit_after_configured_cutoff(tmp_path):
    root, bundle = fixture(tmp_path)
    # Move submission/decision and opening deal into the past while keeping
    # the retained close recent. Rehash all changed bytes to test semantics.
    delta = timedelta(minutes=11)
    def shift(value):
        return (datetime.fromisoformat(value.replace("Z", "+00:00")) - delta).isoformat()
    def entry(payload):
        for field in ("decision_at_utc", "expires_at_utc"):
            payload["proposal"][field] = shift(payload["proposal"][field])
        payload["execution"]["submitted_at_utc"] = shift(payload["execution"]["submitted_at_utc"])
        payload["session"]["starts_at_utc"] = shift(payload["session"]["starts_at_utc"])
        snapshot = payload["decision_snapshot"]
        for field in ("observed_at_utc", "captured_at_utc"):
            snapshot[field] = shift(snapshot[field])
        for bar in snapshot["m1_closed_bars"]:
            for field in ("opened_at_utc", "closed_at_utc", "available_at_utc"):
                bar[field] = shift(bar[field])
    mutate_payload(bundle, entry)
    def lifecycle(rows):
        row = rows[0]
        for field in ("decision_at_utc", "proposal_expires_at_utc", "submitted_at_utc", "snapshot_captured_at_utc"):
            row[field] = shift(row[field])
        history = row["closing_context"]["broker_history"]
        history["broker_deals"][0]["time_utc"] = shift(history["broker_deals"][0]["time_utc"])
        history["broker_deals_sha256"] = "sha256:" + hashlib.sha256(json.dumps(history["broker_deals"], sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    mutate_lifecycle(bundle, lifecycle)
    result = verify(root, bundle)
    assert result.returncode == 2
    assert "configured owner cutoff" in result.stderr


def test_m30_rejects_tampering_and_refuses_to_overwrite_evidence(tmp_path):
    root, bundle = fixture(tmp_path)
    before = {path.name: path.read_bytes() for path in bundle.iterdir()}
    with pytest.raises(contract.m20.VerificationError, match="never overwrite"):
        contract.capture(bundle, root)
    assert before == {path.name: path.read_bytes() for path in bundle.iterdir()}
    (bundle / "summary.txt").write_text("tampered")
    assert "digest mismatch" in verify(root, bundle).stderr


def test_m30_wait_observes_exact_attempt_without_repeating_entry(tmp_path, monkeypatch):
    root, bundle = fixture(tmp_path)
    final_bytes = (bundle / "lifecycle-summary.json").read_text()
    (bundle / "lifecycle-summary.json").unlink()
    open_wrapper = json.loads(final_bytes)
    rows = json.loads(open_wrapper["result"]["stdout"])
    rows[0]["lifecycle"] = "OPEN_MONITORING"
    open_wrapper["result"]["stdout"] = json.dumps(rows)
    replies = iter([json.dumps(open_wrapper), final_bytes])
    calls = []
    def observe(argv, **kwargs):
        calls.append(argv)
        return subprocess.CompletedProcess(argv, 0, next(replies), "")
    monkeypatch.setattr(contract.m20, "project_fingerprint", lambda root: "sha256:" + "a" * 64)
    monkeypatch.setattr(contract.subprocess, "run", observe)
    monkeypatch.setattr(contract.time, "sleep", lambda seconds: None)
    contract.wait_for_close(bundle, root)
    assert len(calls) == 2
    assert all(call[-1] == "forex-m20-lifecycle-summary" for call in calls)
    assert (bundle / "lifecycle-summary.json").read_text() == final_bytes
    assert len(list(bundle.glob("lifecycle-observation-*.json"))) == 2
