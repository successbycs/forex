import hashlib
import json
from pathlib import Path

import pytest

from forex.m20_retained_export import RetainedExportInputError, adapt_retained_m20_export, load_and_adapt_retained_m20_export


def operation_export():
    snapshot = {"snapshot_id": "snapshot-1", "payload_sha256": "sha256:" + "a" * 64,
                "observed_at_utc": "2026-09-11T01:00:00Z", "captured_at_utc": "2026-09-11T01:00:01Z",
                "bid": 1.1, "ask": 1.1001, "spread_points": 10, "freshness_seconds": 1,
                "m1_closed_bars": [], "m5_closed_bars": []}
    proposal = {"proposal_id": "proposal-1", "snapshot_id": "snapshot-1",
                "decision_snapshot_sha256": snapshot["payload_sha256"], "decision_at_utc": "2026-09-11T01:00:02Z"}
    return {"operation": "m20_demo_trading_session", "result": {"stdout": json.dumps({"decision_snapshot": snapshot, "proposal": proposal, "reconciliation": {"status": "MATCHED"}})}}


def test_adapts_real_operation_envelope_without_repairing_snapshot_or_inventing_outcome():
    adapted = adapt_retained_m20_export(operation_export())
    record = adapted["records"][0]
    assert adapted["provenance"]["source_shape"] == "T480_RESULT_STDOUT_JSON"
    assert record["snapshot"]["payload_sha256"] == "sha256:" + "a" * 64
    assert record["proposal"]["decision_snapshot_sha256"] == "sha256:" + "a" * 64
    assert "outcome" not in record
    assert adapted["retained_export_coverage"]["replayable_pair_count"] == 1
    assert adapted["execution_authority"] is False


def test_adapts_fixed_latest_listener_assessment_export_with_transport_provenance():
    base = json.loads(operation_export()["result"]["stdout"])
    latest = {
        "observation": "AVAILABLE",
        "listener_release_id": "a" * 16,
        "assessment_started_at_utc": "2026-09-11T01:00:00Z",
        "assessment_completed_at_utc": "2026-09-11T01:00:03Z",
        "raw_sha256": "sha256:" + "c" * 64,
        "assessment": {
            **base,
            "server": "GOMarketsMU-Demo",
            "symbol": "EURUSD",
        },
    }
    adapted = adapt_retained_m20_export({
        "operation": "m20_listener_latest_assessment",
        "result": {"stdout": json.dumps(latest)},
    })
    assert adapted["provenance"]["source_shape"] == "M20_LISTENER_LATEST_ASSESSMENT"
    assert adapted["provenance"]["listener_release_id"] == "a" * 16
    assert adapted["provenance"]["raw_sha256"] == "sha256:" + "c" * 64
    assert adapted["records"][0]["snapshot"]["snapshot_id"] == "snapshot-1"


def test_refuses_an_absent_latest_listener_assessment_without_creating_a_replay_record():
    with pytest.raises(RetainedExportInputError, match="not available"):
        adapt_retained_m20_export({"observation": "LATEST_ASSESSMENT_ABSENT", "assessment": None})


def test_lifecycle_rows_are_coverage_only_and_keep_actual_fields_unmodified():
    row = {"proposal_id": "p1", "snapshot_id": "s1", "decision_snapshot_sha256": "sha256:" + "b" * 64,
           "gross_price_pnl_account": 1.0, "commission_account": 0.0, "fee_account": None,
           "swap_account": 0.0, "realized_pnl_account": 1.0, "account_currency": "AUD",
           "reconciliation_status": "MATCHED"}
    adapted = adapt_retained_m20_export({"operation": "forex_m20_lifecycle_summary", "result": {"stdout": json.dumps([row, row])}})
    assert adapted["records"] == []
    assert adapted["retained_export_coverage"]["coverage_only_row_count"] == 2
    assert adapted["retained_export_coverage"]["duplicate_proposal_id_count"] == 1
    retained = adapted["coverage_only_records"][0]["identifiers"]["outcome_fields_retained_without_replay_pair"]
    assert retained["fee_account"] is None
    assert retained["commission_account"] == 0.0


def test_lineage_outcome_is_coverage_only_not_a_synthetic_replay_pair():
    lineage = {"lineage": [{"proposal_id": "p1", "snapshot_id": "s1", "outcome": {"proposal_id": "p1", "fee_account": 0.0}}]}
    adapted = adapt_retained_m20_export({"operation": "forex_m20_current_lineage_summary", "result": {"stdout": json.dumps(lineage)}})
    assert adapted["records"] == []
    assert adapted["coverage_only_records"][0]["identifiers"]["outcome"]["fee_account"] == 0.0


def test_loader_hashes_raw_input_and_rejects_ambiguous_json(tmp_path):
    source = tmp_path / "operation.json"
    raw = json.dumps(operation_export()).encode()
    source.write_bytes(raw)
    adapted = load_and_adapt_retained_m20_export(source)
    assert adapted["provenance"]["source_sha256"] == "sha256:" + hashlib.sha256(raw).hexdigest()
    source.write_text('{"result":{},"result":{}}')
    with pytest.raises(RetainedExportInputError, match="duplicate JSON field"):
        load_and_adapt_retained_m20_export(source)


def test_nested_stdout_json_rejects_duplicate_fields():
    with pytest.raises(RetainedExportInputError):
        adapt_retained_m20_export({"result": {"stdout": '{"lineage":[],"lineage":[null]}'}})


def test_cli_retains_coverage_only_rows(tmp_path):
    import subprocess
    import sys
    source = tmp_path / "lineage.json"
    source.write_text(json.dumps({"lineage": [{"proposal_id": "p1"}]}))
    script = Path(__file__).resolve().parents[1] / "scripts/m20_replay_report.py"
    result = subprocess.run([sys.executable, str(script), "--retained-export", str(source)],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["retained_export_coverage"]["coverage_only_row_count"] == 1
    assert report["record_count"] == 0
