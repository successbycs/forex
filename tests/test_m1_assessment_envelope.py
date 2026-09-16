import json

from forex.m1_assessment_envelope import SCHEMA, build_envelope


def assessment(*, action="NO_TRADE"):
    return {"operation": "m20_demo_trading_session", "server": "GOMarketsMU-Demo", "symbol": "EURUSD",
            "decision_snapshot": {"snapshot_id": "snapshot-1"},
            "proposal": {"proposal_id": "proposal-1", "snapshot_id": "snapshot-1", "action": action,
                         "decision_at_utc": "2026-09-16T00:00:00Z"}}


def test_terminal_decision_binds_exact_raw_bytes_without_authority():
    raw = json.dumps(assessment(), sort_keys=True).encode()
    envelope = build_envelope(raw, source_reference="retained/a.json")
    assert envelope["schema_version"] == SCHEMA
    assert envelope["terminal"] == {"disposition": "TERMINAL_DECISION", "action": "NO_TRADE"}
    assert envelope["source"]["reference"] == "retained/a.json"
    assert envelope["source"]["sha256"].startswith("sha256:")
    assert envelope["execution_authority"] is False


def test_legacy_invalid_bytes_and_missing_identity_are_explicit_refusals():
    invalid = build_envelope(b"not json", source_reference="retained/b.json")
    assert invalid["terminal"]["reason_code"] == "ASSESSMENT_OPERATION_OUTPUT_NOT_JSON"
    body = assessment()
    del body["proposal"]["proposal_id"]
    missing = build_envelope(json.dumps(body).encode(), source_reference="retained/c.json")
    assert missing["terminal"]["reason_code"] == "MISSING_REQUIRED_PROVENANCE"


def test_spool_clock_failure_is_retained_as_refusal():
    record = {"schema_version": "forex.m20.latest-assessment.v1", "listener_release_id": "a" * 16,
              "assessment_sequence": 1, "assessment_started_at_utc": "2026-09-16T00:01:00Z",
              "assessment_completed_at_utc": "2026-09-16T00:00:00Z", "assessment": assessment()}
    envelope = build_envelope(json.dumps(record).encode(), source_reference="spool/0001.json")
    assert envelope["terminal"]["reason_code"] == "ASSESSMENT_CLOCK_ORDER_INVALID"
