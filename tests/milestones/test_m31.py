import json
from pathlib import Path
import subprocess
import sys

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
    assert result["limitations"] == ["INCOMPLETE_SELECTED_LIFECYCLE_COVERAGE", "SELECTED_PROPOSAL_WITHOUT_LIFECYCLE:p-buy"]


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


def test_capture_refuses_dirty_checkout_before_creating_bundle(tmp_path):
    target = tmp_path / "new-bundle"
    process = subprocess.run(["bash", "scripts/capture_m31_evidence.sh", str(target), str(tmp_path / "protocol")], cwd=ROOT, text=True, capture_output=True, check=False)
    assert process.returncode == 2
    assert "clean, committed checkout" in process.stderr
    assert not target.exists()


def test_protocol_declaration_refuses_dirty_checkout_before_creating_directory(tmp_path):
    target = tmp_path / "protocol"
    process = subprocess.run([sys.executable, "scripts/declare_m31_protocol.py", "--directory", str(target), "--from-utc", "2026-09-24T00:00:00Z", "--to-utc", "2026-09-24T01:00:00Z"], cwd=ROOT, text=True, capture_output=True, check=False)
    assert process.returncode == 2
    assert "clean committed checkout" in process.stderr
    assert not target.exists()
