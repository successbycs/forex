from __future__ import annotations

from datetime import datetime, timedelta, timezone

from forex.data_contracts import build_dataset_snapshot
import pytest

from forex.event_annotations import event_annotation
from forex.event_quality import qualify_events
from forex.h_slow_decision import attach_event_context, evaluate_h_slow_snapshot


DECISION = "2026-09-01T12:00:00Z"


def monthly_snapshot() -> dict:
    source = {
        "contract_version": "forex.historical-data.v1", "source_id": "fixture", "owner": "test",
        "license": "test", "cost_model": "none", "api_version": "1", "endpoint_allowlist": [],
        "rate_limit": "none", "retention_rule": "test", "historical_depth": "test",
        "revision_support": "none", "timezone_policy": "UTC", "outage_policy": "fail",
        "approval_status": "DEMO_ONLY", "secrets_reference": "NONE", "provenance_note": "test",
    }
    observation = {
        "contract_version": "forex.historical-data.v1", "observation_id": "obs", "source_id": "fixture",
        "source_revision": "1", "observed_at_utc": "2025-08-01T00:00:00Z",
        "available_at_utc": "2025-08-01T00:00:00Z", "retrieved_at_utc": "2025-08-01T00:00:00Z",
        "timezone": "UTC", "payload_sha256": "sha256:test", "payload_path": "test", "redacted": False,
    }
    current = datetime(2025, 8, 1, tzinfo=timezone.utc)
    final = datetime(2026, 8, 31, tzinfo=timezone.utc)
    bars = []
    index = 0
    while current <= final:
        if current.weekday() < 5:
            close = 1.0 + index / 10000
            bars.append({"time_utc": current.isoformat().replace("+00:00", "Z"), "open": close,
                         "high": close + .001, "low": close - .001, "close": close, "volume": 1,
                         "raw_observation_id": "obs", "available_at_utc": (current + timedelta(days=1)).isoformat().replace("+00:00", "Z")})
            index += 1
        current += timedelta(days=1)
    return build_dataset_snapshot(snapshot_id="hslow-monthly", instrument="EUR/USD", timeframe="D1",
                                  decision_cutoff_utc=DECISION, created_at_utc=DECISION,
                                  source_registry=[source], raw_observations=[observation], price_bars=bars)


def test_binds_one_qualified_snapshot_to_a_deterministic_research_target_only():
    first = evaluate_h_slow_snapshot(monthly_snapshot(), decision_at_utc=DECISION)
    second = evaluate_h_slow_snapshot(monthly_snapshot(), decision_at_utc=DECISION)
    assert first["decision_sha256"] == second["decision_sha256"]
    assert first["record_status"] == "RESEARCH_TARGET_ONLY"
    assert first["execution_authority"] is False
    assert first["event_annotation_status"] == "NOT_ATTACHED"
    assert first["target"]["action"] == "BUY"
    assert first["target"]["research_only"] is True


def test_changed_snapshot_identity_changes_the_bound_decision_record():
    original = monthly_snapshot()
    changed = build_dataset_snapshot(
        snapshot_id="hslow-monthly-reissued", instrument=original["instrument"], timeframe=original["timeframe"],
        decision_cutoff_utc=original["decision_cutoff_utc"], created_at_utc=original["created_at_utc"],
        source_registry=original["source_registry"], raw_observations=original["raw_observations"],
        price_bars=original["price_bars"],
    )
    first = evaluate_h_slow_snapshot(original, decision_at_utc=DECISION)
    second = evaluate_h_slow_snapshot(changed, decision_at_utc=DECISION)
    assert first["snapshot_artifact_sha256"] != second["snapshot_artifact_sha256"]
    assert first["decision_sha256"] != second["decision_sha256"]


def test_attaches_only_a_digest_verified_matching_context_without_changing_target():
    decision = evaluate_h_slow_snapshot(monthly_snapshot(), decision_at_utc=DECISION)
    annotation = event_annotation(
        qualify_events([], DECISION), decision_at_utc=DECISION,
        window_start_utc="2026-08-31T12:00:00Z", window_end_utc="2026-09-02T12:00:00Z",
    )
    attached = attach_event_context(decision, annotation)
    assert attached["event_annotation_status"] == "ATTACHED_CONTEXT_ONLY"
    assert attached["event_annotation"] == annotation
    assert attached["target"] == decision["target"]
    assert attached["execution_authority"] is False

    mismatched = event_annotation(
        qualify_events([], "2026-09-02T12:00:00Z"), decision_at_utc="2026-09-02T12:00:00Z",
        window_start_utc="2026-09-01T12:00:00Z", window_end_utc="2026-09-03T12:00:00Z",
    )
    with pytest.raises(ValueError, match="matching context"):
        attach_event_context(decision, mismatched)
    decision["target"]["action"] = "TAMPERED"
    assert attached["target"]["action"] == "BUY"
