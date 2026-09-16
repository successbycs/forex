import json

from forex.m1_assessment_envelope import build_envelope
from forex.m1_postgres_completeness import SCHEMA, build_report


def envelope(action="NO_TRADE"):
    body = {"operation": "m20_demo_trading_session", "server": "GOMarketsMU-Demo", "symbol": "EURUSD",
            "decision_snapshot": {"snapshot_id": "s"},
            "proposal": {"proposal_id": "p", "snapshot_id": "s", "action": action}}
    return build_envelope(json.dumps(body).encode(), source_reference="retained/p.json")


def test_report_matches_declared_identity_and_preserves_refusal():
    refused = build_envelope(b"bad", source_reference="retained/bad.json")
    summary = {"schema_version": "forex.m1.postgres-completeness-summary.v1", "query_contract_version": "v1",
               "query_sha256": "sha256:" + "a" * 64, "interval": {"from_utc": "2026-09-16T00:00:00Z", "to_utc": "2026-09-16T01:00:00Z"},
               "records": [{"proposal_id": "p", "status": "ACCEPTED"}]}
    report = build_report([envelope(), refused], postgres_raw=json.dumps(summary).encode(), postgres_reference="capture/db.json")
    assert report["schema_version"] == SCHEMA
    assert report["joins"]["raw_to_projection_matched"] == 1
    assert report["counts"]["operational_refusals"] == 1
    assert report["execution_authority"] is False


def test_report_marks_missing_database_input_unknown():
    report = build_report([envelope()], postgres_raw=None)
    assert report["counts"]["backlog"] == "UNKNOWN"
    assert report["limitations"] == ["POSTGRES_SUMMARY_UNAVAILABLE"]
