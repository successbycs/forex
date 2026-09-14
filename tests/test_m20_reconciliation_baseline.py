import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from forex.m20_reconciliation_baseline import (
    ReconciliationBaselineError,
    assessment_identity,
    reconcile,
)


ROOT = Path(__file__).resolve().parents[1]


def history(*ids):
    return {"schema_version": "forex.m20.history-report.v1", "server": "GOMarketsMU-Demo", "currency": "AUD",
            "source_sha256": "sha256:" + "a" * 64, "closed_positions": [
                {"position_id": position_id, "entry_ticket": position_id + 1, "exit_ticket": position_id + 2,
                 "net_realized_aud": -0.1, "exit_reason": 4, "stop_loss_like_exit": True} for position_id in ids]}


def operation(proposal_id="proposal-1", snapshot_id="snapshot-1", position=100, *, outcome=True):
    value = {"server": "GOMarketsMU-Demo", "symbol": "EURUSD",
             "decision_snapshot": {"snapshot_id": snapshot_id},
             "proposal": {"proposal_id": proposal_id, "snapshot_id": snapshot_id},
             "execution": {"status": "ACCEPTED", "position_identifier": position}}
    if outcome:
        value["outcome"] = {"proposal_id": proposal_id}
    return value


def identity(value):
    return assessment_identity(value, source_sha256="sha256:" + hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest())


def test_reconciliation_uses_only_explicit_position_identity_and_links_all_identities():
    report = reconcile(history_report=history(100, 200), assessments=[identity(operation(position=100))])
    assert report["assessment_rows"][0]["reconciliation_status"] == "MATCHED"
    assert report["assessment_rows"][0]["proposal_id"] == "proposal-1"
    assert report["assessment_rows"][0]["snapshot_id"] == "snapshot-1"
    assert report["assessment_rows"][0]["outcome_proposal_id"] == "proposal-1"
    assert report["broker_rows"][0]["reconciliation_status"] == "MATCHED"
    assert report["broker_rows"][1]["reconciliation_status"] == "UNMATCHED_MT5_HISTORY"
    assert report["execution_authority"] is False


def test_missing_position_or_outcome_evidence_is_not_inferred_from_other_trade_fields():
    no_position = operation(position=None)
    no_position["execution"].update({"position_ticket": 100, "broker_comment": "forex-m20-demo"})
    no_outcome = operation(proposal_id="proposal-2", snapshot_id="snapshot-2", position=200, outcome=False)
    report = reconcile(history_report=history(100, 200), assessments=[identity(no_position), identity(no_outcome)])
    assert [row["reconciliation_status"] for row in report["assessment_rows"]] == ["MISSING_EVIDENCE", "MISSING_EVIDENCE"]
    assert [row["reconciliation_status"] for row in report["broker_rows"]] == ["UNMATCHED_MT5_HISTORY", "MISSING_EVIDENCE"]
    assert "No time, price, side" in report["limitations"][1]


def test_rejected_or_not_submitted_execution_cannot_match_a_stray_position_identifier():
    rejected = operation(position=100)
    rejected["execution"]["status"] = "REJECTED"
    report = reconcile(history_report=history(100), assessments=[identity(rejected)])
    assert report["assessment_rows"][0]["reconciliation_status"] == "MISSING_EVIDENCE"
    assert report["broker_rows"][0]["reconciliation_status"] == "UNMATCHED_MT5_HISTORY"


def test_duplicate_position_and_duplicate_decision_are_explicitly_ambiguous():
    first = identity(operation(proposal_id="same", snapshot_id="a", position=100))
    second = identity(operation(proposal_id="other", snapshot_id="b", position=100))
    report = reconcile(history_report=history(100), assessments=[first, second])
    assert report["broker_rows"][0]["reconciliation_status"] == "AMBIGUOUS_POSITION_IDENTITY"
    assert {row["reconciliation_status"] for row in report["assessment_rows"]} == {"AMBIGUOUS_POSITION_IDENTITY"}
    duplicate_decision = reconcile(history_report=history(100), assessments=[first, {**first, "assessment_source_sha256": "sha256:" + "c" * 64}])
    assert duplicate_decision["assessment_rows"][0]["reconciliation_status"] == "AMBIGUOUS_DECISION_IDENTITY"


@pytest.mark.parametrize("field, value", [
    ("assessment_source_sha256", "sha256:not-a-digest"),
    ("snapshot_id", 4),
    ("outcome_proposal_id", "another-proposal"),
    ("position_identifier", True),
])
def test_reconcile_revalidates_hand_constructed_public_api_identities(field, value):
    item = identity(operation())
    item[field] = value
    with pytest.raises(ReconciliationBaselineError, match="identity shape is invalid"):
        reconcile(history_report=history(100), assessments=[item])


@pytest.mark.parametrize("mutator, message", [
    (lambda value: value["proposal"].update({"snapshot_id": "wrong"}), "does not bind its snapshot"),
    (lambda value: value["execution"].update({"position_identifier": True}), "position identifier is invalid"),
    (lambda value: value.update({"server": "GOMarketsMU-Live"}), "not a Demo EURUSD operation"),
])
def test_assessment_identity_refuses_unbound_or_live_evidence(mutator, message):
    value = operation(); mutator(value)
    with pytest.raises(ReconciliationBaselineError, match=message):
        identity(value)


def test_cli_has_no_mt5_or_transport_route_and_refuses_no_assessment_history(tmp_path):
    # A valid history capture is deliberately required; the baseline cannot
    # treat an arbitrary summary as broker evidence.
    source = ROOT / "scripts/m20_reconciliation_baseline.py"
    text = source.read_text()
    assert "t480_adapter" not in text and "MetaTrader5" not in text and "subprocess" not in text
    path = tmp_path / "not-history.json"; path.write_text("{}")
    run = subprocess.run([sys.executable, str(source), "--history", str(path)], cwd=ROOT, text=True, capture_output=True)
    assert run.returncode == 2
    assert run.stdout == ""
