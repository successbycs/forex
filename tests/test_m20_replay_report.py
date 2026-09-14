import hashlib
import json
import subprocess
import sys
import pytest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from forex.m20_replay_report import build_replay_report, load_and_build_replay_report, ReplayReportInputError


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("raw", ['{"records":[],"records":[null]}', '{"records":[],"x":NaN}'])
def test_loader_refuses_ambiguous_or_nonfinite_json(tmp_path, raw):
    path = tmp_path / "records.json"
    path.write_text(raw)
    with pytest.raises(ReplayReportInputError):
        load_and_build_replay_report(path)


def stamp(value):
    return value.isoformat().replace("+00:00", "Z")


def snapshot_and_proposal(*, snapshot_id="snapshot-1", proposal_id="proposal-1"):
    observed = datetime(2026, 9, 11, 9, 0, tzinfo=timezone.utc)
    bars = []
    for offset in range(12):
        opened = observed - timedelta(minutes=12 - offset)
        closed = opened + timedelta(minutes=1)
        bars.append({"opened_at_utc": stamp(opened), "closed_at_utc": stamp(closed),
                     "available_at_utc": stamp(observed), "open": 1.10000 + offset * .00001,
                     "high": 1.10010 + offset * .00001, "low": 1.09990 + offset * .00001,
                     "close": 1.10005 + offset * .00001})
    body = {"observed_at_utc": stamp(observed), "captured_at_utc": stamp(observed),
            "bid": 1.10010, "ask": 1.10020, "spread_points": 10, "freshness_seconds": 1,
            "m1_closed_bars": bars, "m5_closed_bars": [],
            "safety_gates": {"fresh_quote": True, "completed_m1": True, "normal_spread": True,
                             "no_existing_position": True, "demo_lease_active": True,
                             "news_blackout_inactive": True, "abnormal_volatility_inactive": True},
            "market_context": {}, "strategy_assessments": []}
    digest = "sha256:" + hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return ({"snapshot_id": snapshot_id, "payload_sha256": digest, **body},
            {"proposal_id": proposal_id, "snapshot_id": snapshot_id,
             "decision_snapshot_sha256": digest, "decision_at_utc": stamp(observed)})


def outcome(proposal_id):
    return {"proposal_id": proposal_id, "reconciliation_status": "MATCHED", "account_currency": "AUD",
            "gross_price_pnl_account": 1.25, "commission_account": -0.10, "fee_account": -0.05,
            "swap_account": 0, "estimated_spread_cost_account": 0.08,
            "slippage_cost_account": 0.03, "estimated_total_cost_account": 0.11,
            "realized_pnl_account": 1.10}


def test_report_classifies_linked_retained_records_and_preserves_missing_outcome():
    snapshot, proposal = snapshot_and_proposal()
    report = build_replay_report({"provenance": {"source_id": "retained-m20", "revision": "r1"}, "records": [
        {"record_id": "with-outcome", "snapshot": snapshot, "proposal": proposal, "outcome": outcome("proposal-1")},
        {"record_id": "missing-outcome", "snapshot": snapshot_and_proposal(snapshot_id="snapshot-2", proposal_id="proposal-2")[0],
         "proposal": snapshot_and_proposal(snapshot_id="snapshot-2", proposal_id="proposal-2")[1]},
    ]})
    assert report["valid_record_count"] == 2
    assert report["records"][0]["classification"]["proposal_bound"] is True
    assert report["records"][0]["cost"]["actual_cost_status"] == "COMPLETE"
    assert report["records"][1]["limitations"] == ["linked broker outcome is absent"]
    assert report["broker_outcome_coverage"]["outcome_count"] == 1
    assert report["execution_authority"] is False
    assert report["input_provenance"]["declared_provenance_status"] == "NOT_INDEPENDENTLY_VERIFIED"


def test_report_rejects_duplicate_and_unlinked_outcomes_from_aggregate():
    first_snapshot, first_proposal = snapshot_and_proposal()
    duplicate_snapshot, duplicate_proposal = snapshot_and_proposal()
    other_snapshot, other_proposal = snapshot_and_proposal(snapshot_id="snapshot-2", proposal_id="proposal-2")
    report = build_replay_report({"records": [
        {"snapshot": first_snapshot, "proposal": first_proposal, "outcome": outcome("proposal-1")},
        {"snapshot": duplicate_snapshot, "proposal": duplicate_proposal, "outcome": outcome("proposal-1")},
        {"snapshot": other_snapshot, "proposal": other_proposal, "outcome": outcome("wrong-proposal")},
    ]})
    assert report["valid_record_count"] == 1
    assert report["error_record_count"] == 2
    assert "duplicate snapshot_id" in report["records"][1]["errors"]
    assert "outcome proposal_id does not link to proposal_id" in report["records"][2]["errors"]
    assert report["broker_outcome_coverage"]["outcome_count"] == 1
    assert report["records"][1]["included_in_aggregates"] is False


@pytest.mark.parametrize("digest", ["sha256:not-a-digest", "sha256:" + "A" * 64,
                                    "sha256:" + "a" * 63, "md5:" + "a" * 64])
def test_report_refuses_malformed_supplied_source_digest(digest):
    with pytest.raises(ReplayReportInputError, match="lowercase SHA-256"):
        build_replay_report({"records": []}, source_sha256=digest)


def test_cli_outputs_json_and_does_not_modify_input(tmp_path):
    snapshot, proposal = snapshot_and_proposal()
    source = tmp_path / "retained.json"
    source.write_text(json.dumps({"records": [{"snapshot": snapshot, "proposal": proposal, "outcome": outcome("proposal-1")}]}), encoding="utf-8")
    before = source.read_bytes()
    process = subprocess.run([sys.executable, "scripts/m20_replay_report.py", str(source)], cwd=ROOT, text=True, capture_output=True, check=False)
    assert process.returncode == 0, process.stderr
    report = json.loads(process.stdout)
    assert source.read_bytes() == before
    assert report["input_provenance"]["source_sha256"] == "sha256:" + hashlib.sha256(before).hexdigest()
    assert report["broker_outcome_coverage"]["outcome_count"] == 1
    assert report["profitability_conclusion"] == "NOT_EVALUATED"


def test_cli_rejects_invalid_document_with_no_json_stdout(tmp_path):
    source = tmp_path / "invalid.json"
    source.write_text("[]", encoding="utf-8")
    process = subprocess.run([sys.executable, "scripts/m20_replay_report.py", str(source)], cwd=ROOT, text=True, capture_output=True, check=False)
    assert process.returncode == 2
    assert process.stdout == ""
    assert "input document must be a JSON object" in process.stderr
