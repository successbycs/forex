import json
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timedelta, timezone

import pytest

from forex.m31_scorecard import M31ScorecardInputError, build_scorecard, parse_completeness, parse_lifecycle, parse_protocol, render_terminal, scorecard_from_raw
from forex.m31_evidence import M31EvidenceError, verify_bundle


ROOT = Path(__file__).resolve().parents[2]
START = "2026-09-24T00:00:00Z"
END = "2026-09-24T01:00:00Z"


def protocol():
    return {"schema_version": "forex.m31.evaluation-protocol.v1", "interval": {"from_utc": START, "to_utc": END, "bounds": "inclusive/exclusive"},
            "baseline": {"kind": "NO_CHANGE", "trade_count": 0, "realized_pnl_aud": 0, "cost_aud": 0}, "server": "GOMarketsMU-Demo", "symbol": "EURUSD", "captured_at_utc": "2026-09-23T00:00:00Z"}


def completeness(records=None):
    value = {"schema_version": "forex.m1.postgres-completeness-summary.v1", "query_contract_version": "v1", "query_sha256": "sha256:" + "a" * 64,
             "interval": {"from_utc": START, "to_utc": END, "bounds": "inclusive/exclusive"},
             "records": records if records is not None else [{"proposal_id": "p-no", "decision_at_utc": "2026-09-24T00:01:00Z", "action": "NO_TRADE", "attempt_id": None, "status": None}, {"proposal_id": "p-buy", "decision_at_utc": "2026-09-24T00:02:00Z", "action": "BUY", "attempt_id": "a", "status": "SUBMITTED"}]}
    return {"operation": "forex_m1_postgres_completeness_summary", "result": {"ok": True, "stdout": json.dumps(value)}}


def lifecycle(rows=None):
    rows = rows if rows is not None else [{"proposal_id": "p-buy", "decision_at_utc": "2026-09-24T00:02:00Z", "action": "BUY", "status": "SUBMITTED", "trade_owner_strategy_id": "trend_pullback", "application_revision": "r1", "configuration_fingerprint": "sha256:" + "b" * 64, "closed_at_utc": "2026-09-24T00:04:00Z", "reconciliation_status": "MATCHED", "realized_pnl_account": 0.15, "commission_account": 0.0, "fee_account": 0.0, "swap_account": 0.0, "estimated_spread_cost_account": 0.2, "slippage_cost_account": None}]
    return {"operation": "forex_m20_lifecycle_summary", "result": {"ok": True, "stdout": json.dumps(rows)}}


def broker_history():
    inner = {"ok": True, "complete": True, "captured_at_utc": "2026-09-24T01:00:00Z", "from_utc": "2000-01-01T00:00:00Z", "query_to_server_clock_utc": "2026-09-24T04:00:00Z", "server": "GOMarketsMU-Demo", "currency": "AUD", "account_scope_sha256": "c" * 64, "balance": 1.0, "equity": 1.0, "credit": 0.0, "broker_timestamp_offset_seconds": 10800, "deal_count": 0, "order_count": 0, "deals": [], "orders": [], "error": None}
    return {"operation": "m20_all_demo_history_export", "approval_required": False, "approved": False, "result": {"stdout": json.dumps(inner)}, "ok": True, "tool_id": "forex_t480", "configuration_fingerprint": "sha256:" + "a" * 64, "adapter_configuration_fingerprint": "sha256:" + "b" * 64}


def test_scorecard_is_deterministic_and_has_no_execution_authority():
    result = scorecard_from_raw(protocol_raw=json.dumps(protocol()).encode(), completeness_raw=json.dumps(completeness()).encode(), lifecycle_raw=json.dumps(lifecycle()).encode())
    assert result["counts"] == {"decisions": 2, "no_trade": 1, "buy": 1, "sell": 0, "selected": 1, "joined_selected": 1, "reconciled_closed": 1}
    assert result["realized_pnl_aud"] == 0.15
    assert result["cost_field_coverage"] == {"PRESENT": 4, "UNKNOWN": 1}
    assert result["historical_comparator"] == "NON_COMPARABLE_CONTEXT"
    assert result["execution_authority"] is False
    text = render_terminal(result)
    assert "M31 DEMO SCORECARD" in text and "AUD 0.15" in text and "Execution authority: false" in text


def test_scorecard_rejects_duplicate_proposal_and_source_drift():
    duplicate = completeness()["result"]
    body = json.loads(duplicate["stdout"])
    body["records"].append(body["records"][0])
    duplicate["stdout"] = json.dumps(body)
    with pytest.raises(M31ScorecardInputError, match="duplicate"):
        scorecard_from_raw(protocol_raw=json.dumps(protocol()).encode(), completeness_raw=json.dumps({"operation": "forex_m1_postgres_completeness_summary", "result": duplicate}).encode(), lifecycle_raw=json.dumps(lifecycle()).encode())
    rows = json.loads(lifecycle()["result"]["stdout"])
    rows.append({**rows[0], "proposal_id": "p-sell", "decision_at_utc": "2026-09-24T00:03:00Z", "action": "SELL", "application_revision": "r2"})
    records = json.loads(completeness()["result"]["stdout"])["records"] + [{"proposal_id": "p-sell", "decision_at_utc": "2026-09-24T00:03:00Z", "action": "SELL"}]
    with pytest.raises(M31ScorecardInputError, match="drift"):
        build_scorecard(protocol=protocol(), completeness=parse_completeness(json.dumps(completeness(records))), lifecycle=parse_lifecycle(json.dumps(lifecycle(rows))))


def test_scorecard_rejects_out_of_interval_outcome_and_marks_missing_join():
    rows = json.loads(lifecycle()["result"]["stdout"])
    rows[0]["closed_at_utc"] = END
    with pytest.raises(M31ScorecardInputError, match="outside"):
        scorecard_from_raw(protocol_raw=json.dumps(protocol()).encode(), completeness_raw=json.dumps(completeness()).encode(), lifecycle_raw=json.dumps(lifecycle(rows)).encode())
    result = build_scorecard(protocol=protocol(), completeness=parse_completeness(json.dumps(completeness())), lifecycle=[])
    assert {"INCOMPLETE_SELECTED_LIFECYCLE_COVERAGE", "SELECTED_PROPOSAL_WITHOUT_LIFECYCLE:p-buy"} <= set(result["limitations"])


def test_no_trade_interval_discloses_missing_evaluation_evidence():
    records = [{"proposal_id": "no-trade", "action": "NO_TRADE", "decision_at_utc": "2026-09-24T00:02:00Z"}]
    result = build_scorecard(protocol=protocol(), completeness=parse_completeness(json.dumps(completeness(records))), lifecycle=[])
    assert set(result["limitations"]) == {
        "HISTORICAL_COMPARISON_UNQUALIFIED", "NO_RECONCILED_TRADE_OUTCOMES_IN_INTERVAL",
        "DECISION_VERSION_PROVENANCE_UNAVAILABLE", "NO_TRADE_REASONS_NOT_EXPORTED"}
    assert "formal M31 acceptance remains unproven" in render_terminal(result)


def test_no_trade_provenance_and_reasons_come_from_decisions():
    row = {"proposal_id": "p", "action": "NO_TRADE", "decision_at_utc": "2026-09-24T00:02:00Z",
           "application_revision": "r1", "configuration_fingerprint": "sha256:" + "b" * 64,
           "rationale": "Existing position"}
    result = build_scorecard(protocol=protocol(), completeness=parse_completeness(json.dumps(completeness([row]))), lifecycle=[])
    assert result["provenance"]["application_revision"] == "r1"
    assert result["no_trade_reasons"] == {"Existing position": 1}
    assert "DECISION_VERSION_PROVENANCE_UNAVAILABLE" not in result["limitations"]
    assert "NO_TRADE_REASONS_NOT_EXPORTED" not in result["limitations"]
    changed = dict(row, proposal_id="p2", application_revision="r2")
    with pytest.raises(M31ScorecardInputError, match="drift"):
        build_scorecard(protocol=protocol(), completeness=parse_completeness(json.dumps(completeness([row, changed]))), lifecycle=[])


def test_protocol_rejects_live_identity_and_cli_uses_local_files_only(tmp_path):
    invalid = protocol()
    invalid["server"] = "GOMarketsMU-Live"
    with pytest.raises(M31ScorecardInputError, match="Demo identity"):
        parse_protocol(json.dumps(invalid))
    paths = {name: tmp_path / f"{name}.json" for name in ("protocol", "completeness", "lifecycle")}
    paths["protocol"].write_text(json.dumps(protocol()))
    paths["completeness"].write_text(json.dumps(completeness()))
    paths["lifecycle"].write_text(json.dumps(lifecycle()))
    process = subprocess.run([sys.executable, "scripts/m31_scorecard.py", "--protocol", str(paths["protocol"]), "--completeness", str(paths["completeness"]), "--lifecycle", str(paths["lifecycle"])], cwd=ROOT, text=True, capture_output=True, check=False)
    assert process.returncode == 0, process.stderr
    assert "M31 DEMO SCORECARD" in process.stdout


def evidence_bundle(tmp_path):
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    raw = {"protocol.json": json.dumps(protocol()).encode(), "completeness.json": json.dumps(completeness()).encode(), "lifecycle.json": json.dumps(lifecycle()).encode(), "broker-history.json": json.dumps(broker_history()).encode(), "revision.txt": b"a" * 40 + b"\n"}
    import hashlib
    raw["protocol-receipt.json"] = json.dumps({"schema_version": "forex.m31.protocol-receipt.v1", "declared_at_utc": "2026-09-23T00:00:00Z", "git_revision": "a" * 40, "protocol_sha256": "sha256:" + hashlib.sha256(raw["protocol.json"]).hexdigest(), "execution_authority": False}).encode()
    scorecard = scorecard_from_raw(protocol_raw=raw["protocol.json"], completeness_raw=raw["completeness.json"], lifecycle_raw=raw["lifecycle.json"])
    raw["scorecard.json"] = json.dumps(scorecard, sort_keys=True).encode()
    for name, content in raw.items():
        (bundle / name).write_bytes(content)
    manifest = {"schema_version": "forex.m31.evidence-bundle.v1", "milestone_id": "M31", "observed_result": "FOREX_M31_EVIDENCE_CAPTURED", "git_revision": "a" * 40,
                "artifacts": [{"path": name, "sha256": "sha256:" + hashlib.sha256(content).hexdigest()} for name, content in raw.items()]}
    (bundle / "manifest.json").write_text(json.dumps(manifest))
    return bundle


def test_evidence_verifier_binds_hashes_revision_and_scorecard(tmp_path):
    bundle = evidence_bundle(tmp_path)
    verified = verify_bundle(bundle, expected_revision="a" * 40)
    assert verified["marker"] == "FOREX_M31_EVIDENCE_VERIFIED"
    assert verified["decision_count"] == 2
    (bundle / "scorecard.json").write_text("{}")
    with pytest.raises(M31EvidenceError, match="digest"):
        verify_bundle(bundle)


def test_evidence_verifier_cli_checks_broker_history_binding(tmp_path):
    bundle = evidence_bundle(tmp_path)
    process = subprocess.run(["bash", "scripts/verify_m31_evidence.sh", str(bundle)], cwd=ROOT, text=True, capture_output=True, check=False)
    assert process.returncode == 0, process.stderr
    assert "FOREX_M31_EVIDENCE_VERIFIED" in process.stdout
    history = json.loads((bundle / "broker-history.json").read_text())
    history["result"]["stdout"] = json.dumps({"ok": True, "complete": True, "server": "GOMarketsMU-Live"})
    (bundle / "broker-history.json").write_text(json.dumps(history))
    process = subprocess.run(["bash", "scripts/verify_m31_evidence.sh", str(bundle)], cwd=ROOT, text=True, capture_output=True, check=False)
    assert process.returncode != 0


@pytest.fixture
def dirty_git(tmp_path, monkeypatch):
    # This condition belongs to the fixture, not the developer's worktree.
    import os
    executable = tmp_path / "git"
    executable.write_text('#!/bin/sh\n[ "$1" = "status" ] || exit 99\nprintf " M tracked.py\\n"\n')
    executable.chmod(0o755)
    monkeypatch.setenv("PATH", str(tmp_path) + os.pathsep + os.environ["PATH"])


def test_capture_refuses_dirty_checkout_before_creating_bundle(tmp_path, dirty_git):
    target = tmp_path / "new-bundle"
    process = subprocess.run(["bash", "scripts/capture_m31_evidence.sh", str(target), str(tmp_path / "protocol")], cwd=ROOT, text=True, capture_output=True, check=False)
    assert process.returncode == 2
    assert "clean, committed checkout" in process.stderr
    assert not target.exists()


def test_protocol_declaration_refuses_dirty_checkout_before_creating_directory(tmp_path, dirty_git):
    target = tmp_path / "protocol"
    start = (datetime.now(timezone.utc) + timedelta(days=1)).replace(microsecond=0)
    end = start + timedelta(minutes=10)
    process = subprocess.run([sys.executable, "scripts/declare_m31_protocol.py", "--directory", str(target), "--from-utc", start.isoformat().replace("+00:00", "Z"), "--to-utc", end.isoformat().replace("+00:00", "Z")], cwd=ROOT, text=True, capture_output=True, check=False)
    assert process.returncode == 2
    assert "clean committed checkout" in process.stderr
    assert not target.exists()


def supplement_inputs():
    import hashlib
    row = {"proposal_id": "p", "action": "NO_TRADE", "decision_at_utc": "2026-09-24T00:02:00Z", "attempt_id": None}
    enriched = dict(row, application_revision="a" * 40,
                    selected_timeframe="M1", server="GOMarketsMU-Demo", instrument="EURUSD", session_id="session",
                    strategy_version="strategy.v1",
                    configuration_fingerprint="sha256:" + "b" * 64, rationale="No selected actionable M1 strategy.")
    original_wrapper = completeness([row])
    enriched_wrapper = completeness([enriched])
    lifecycle_wrapper = lifecycle([])
    history_wrapper = broker_history()
    for wrapper in (original_wrapper, enriched_wrapper, lifecycle_wrapper, history_wrapper):
        wrapper["ok"] = True
        wrapper["result"].update(ok=True, exit_code=0)
    prior = {"marker": "FOREX_M16_WALK_FORWARD_PROBE_OK", "snapshot": "m2-m1-eurusd-h1-720",
             "evaluation": {"evaluation_version": "eurusd-walk-forward.v1", "availability_policy": "RETROSPECTIVE_H1_BAR_CLOSE_ASSUMPTION",
                "overall": {"no_change": {"sessions": 12, "actionable_sessions": 0, "total_net_return": 0, "mean_net_return": 0}},
                "windows": [{"last_test_day": "2026-08-28", "no_change": {"actionable_sessions": 0, "total_net_return": 0}}]}}
    protocol_raw = json.dumps(protocol()).encode()
    receipt = {"schema_version": "forex.m31.protocol-receipt.v1", "git_revision": "a" * 40,
               "protocol_sha256": "sha256:" + hashlib.sha256(protocol_raw).hexdigest(),
               "declared_at_utc": protocol()["captured_at_utc"], "execution_authority": False}
    return {"protocol_raw": protocol_raw, "receipt_raw": json.dumps(receipt).encode(),
            "original_raw": json.dumps(original_wrapper).encode(), "enriched_raw": json.dumps(enriched_wrapper).encode(),
            "lifecycle_raw": json.dumps(lifecycle_wrapper).encode(), "broker_raw": json.dumps(history_wrapper).encode(),
            "historical_raw": json.dumps({"operation": "forex_m16_walk_forward_probe", "ok": True,
                "result": {"ok": True, "exit_code": 0, "stdout": json.dumps(prior)}}).encode()}


def test_supplement_is_additive_and_does_not_claim_formal_proof():
    from forex.m31_supplement import evaluate_no_trade_supplement
    raw = supplement_inputs()
    report = evaluate_no_trade_supplement(**raw)
    assert report == evaluate_no_trade_supplement(**raw)
    assert report["scorecard"]["provenance"]["application_revision"] == "a" * 40
    assert report["broker_crosscheck"]["interval_eurusd_deals"] == 0
    assert report["historical_reference"]["bound_after_observation"] is True
    assert report["comparison"]["account_pnl_or_flatness_claim"] is False
    assert report["formal_m31_proven"] is False
    assert len(report["input_sha256"]) == 7


@pytest.mark.parametrize("change", ["original_changed", "failed_source", "early_history", "early_query_end", "missing_provenance", "new_attempt", "late_declaration", "nonzero_baseline", "wrong_timeframe", "wrong_server", "missing_strategy", "strategy_drift"])
def test_supplement_refuses_unsupported_evidence(change):
    from forex.m31_supplement import evaluate_no_trade_supplement
    raw = supplement_inputs()
    key = {"early_history": "broker_raw", "early_query_end": "broker_raw", "late_declaration": "receipt_raw", "nonzero_baseline": "historical_raw"}.get(change, "enriched_raw")
    wrapper = json.loads(raw[key])
    inner = json.loads(wrapper["result"]["stdout"]) if "result" in wrapper else wrapper
    if change == "original_changed": inner["records"][0]["decision_at_utc"] = "2026-09-24T00:03:00Z"
    elif change == "failed_source": wrapper["ok"] = False
    elif change == "early_history": inner["captured_at_utc"] = START
    elif change == "early_query_end": inner["query_to_server_clock_utc"] = END
    elif change == "missing_provenance": inner["records"][0].pop("application_revision")
    elif change == "new_attempt": inner["records"][0]["attempt_id"] = "unexpected"
    elif change == "late_declaration": inner["declared_at_utc"] = START
    elif change == "nonzero_baseline": inner["evaluation"]["overall"]["no_change"]["total_net_return"] = 1
    elif change == "wrong_timeframe": inner["records"][0]["selected_timeframe"] = "M5"
    elif change == "wrong_server": inner["records"][0]["server"] = "GOMarketsMU-Live"
    elif change == "missing_strategy": inner["records"][0].pop("strategy_version")
    elif change == "strategy_drift":
        inner["records"].append(dict(inner["records"][0], proposal_id="p2", strategy_version="other"))
        original = json.loads(raw["original_raw"])
        original_inner = json.loads(original["result"]["stdout"])
        original_inner["records"].append(dict(original_inner["records"][0], proposal_id="p2"))
        original["result"]["stdout"] = json.dumps(original_inner)
        raw["original_raw"] = json.dumps(original).encode()
    if "result" in wrapper: wrapper["result"]["stdout"] = json.dumps(inner)
    raw[key] = json.dumps(wrapper).encode()
    with pytest.raises(M31ScorecardInputError):
        evaluate_no_trade_supplement(**raw)


def test_supplement_checks_original_manifest_before_enrichment(tmp_path):
    from forex.m31_supplement import verify_original_hashes
    bundle = evidence_bundle(tmp_path)
    manifest = json.loads((bundle / "manifest.json").read_text())
    manifest["captured_at_utc"] = END
    (bundle / "manifest.json").write_text(json.dumps(manifest))
    assert verify_original_hashes(bundle)["completeness.json"] == (bundle / "completeness.json").read_bytes()
    (bundle / "completeness.json").write_text("{}")
    with pytest.raises(M31ScorecardInputError, match="digest"):
        verify_original_hashes(bundle)


@pytest.fixture
def formal_bundle(tmp_path, monkeypatch):
    import hashlib
    import importlib
    from argparse import Namespace
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    formal = importlib.import_module("m31_retained_evidence")
    raw = supplement_inputs()
    # Place the fixture's observation in the present so freshness is tested
    # independently of the wall-clock date on which this suite runs.
    now = datetime.now(timezone.utc).replace(microsecond=0)
    start = now - timedelta(minutes=10)
    end = now - timedelta(minutes=5)
    replace = {START: start.isoformat(), END: end.isoformat(),
        "2026-09-24T00:02:00Z": (start + timedelta(minutes=2)).isoformat(),
        "2026-09-23T00:00:00Z": (start - timedelta(minutes=5)).isoformat(),
        "2026-09-24T04:00:00Z": (end + timedelta(hours=3)).isoformat()}
    for name in raw:
        content = raw[name].decode()
        for old, new in replace.items(): content = content.replace(old, new)
        raw[name] = content.encode()
    receipt = json.loads(raw["receipt_raw"])
    receipt["protocol_sha256"] = "sha256:" + hashlib.sha256(raw["protocol_raw"]).hexdigest()
    raw["receipt_raw"] = json.dumps(receipt).encode()
    original = tmp_path / "original-source"
    original.mkdir()
    mapping = {"protocol.json": "protocol_raw", "protocol-receipt.json": "receipt_raw", "completeness.json": "original_raw", "lifecycle.json": "lifecycle_raw", "broker-history.json": "broker_raw"}
    files = {name: raw[key] for name, key in mapping.items()}
    files.update({"revision.txt": b"a" * 40, "scorecard.json": b"{}"})
    for name, value in files.items(): (original / name).write_bytes(value)
    (original / "manifest.json").write_text(json.dumps({"schema_version": "forex.m31.evidence-bundle.v1", "milestone_id": "M31",
        "observed_result": "FOREX_M31_EVIDENCE_CAPTURED", "git_revision": "a" * 40, "captured_at_utc": end.isoformat(),
        "artifacts": [{"path": name, "sha256": "sha256:" + hashlib.sha256(value).hexdigest()} for name, value in files.items()]}))
    enriched, historical = tmp_path / "enriched.json", tmp_path / "historical.json"
    enriched.write_bytes(raw["enriched_raw"])
    historical.write_bytes(raw["historical_raw"])
    monkeypatch.setattr(formal, "ROOT", tmp_path)
    monkeypatch.setattr(formal, "clean", lambda: None)
    monkeypatch.setattr(formal, "current_revision", lambda: "a" * 40)
    monkeypatch.setattr(formal.m20, "project_fingerprint", lambda root: "sha256:" + "b" * 64)
    monkeypatch.setattr(formal.subprocess, "run", lambda command, **kwargs: subprocess.CompletedProcess(command, 0,
        stdout="51 passed\n" if "pytest" in command else "milestone governance valid\n"))
    (tmp_path / "project_state.json").write_text(json.dumps({"configuration_fingerprint": "sha256:" + "b" * 64,
        "runtime_mode": "DEMO_TRADING", "live_trading_enabled": False, "permitted_mt5_server": "GOMarketsMU-Demo"}))
    bundle = tmp_path / "formal"
    formal.capture(Namespace(bundle=bundle, original_bundle=original, enriched_completeness=enriched, historical_reference=historical))
    return formal, bundle


def test_formal_retained_evaluation_does_not_close_milestone(formal_bundle):
    formal, bundle = formal_bundle
    result = formal.verify(bundle)
    assert result["marker"] == "FOREX_M31_PROOF_OK"
    assert result["formal_closeout"] is False
    assert result["execution_authority"] is False


@pytest.mark.parametrize("change", ["digest", "stale", "revision", "runtime", "fingerprint", "duplicate", "dirty", "live"])
def test_formal_retained_evaluation_refuses_invalid_binding(formal_bundle, change):
    formal, bundle = formal_bundle
    manifest_path = bundle / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    if change == "digest": (bundle / "evaluation.json").write_text("{}")
    elif change == "stale": manifest["captured_at"] = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    elif change == "revision": manifest["git_revision"] = "b" * 40
    elif change == "runtime": manifest["runtime_revision"] = "b" * 40
    elif change == "fingerprint": manifest["configuration_fingerprint"] = "sha256:" + "c" * 64
    elif change == "duplicate": manifest["artifacts"].append(manifest["artifacts"][0])
    elif change == "dirty": manifest["dirty_worktree"] = True
    elif change == "live":
        state_path = bundle.parent / "project_state.json"
        state = json.loads(state_path.read_text())
        state["live_trading_enabled"] = True
        state_path.write_text(json.dumps(state))
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(M31ScorecardInputError): formal.verify(bundle)
