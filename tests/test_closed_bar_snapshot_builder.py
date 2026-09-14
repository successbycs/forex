from __future__ import annotations

from copy import deepcopy

import pytest

from forex.closed_bar_snapshot_builder import ClosedBarSnapshotError, build_closed_eurusd_snapshot
from forex.data_contracts import validate_dataset_snapshot


RAW = b"already observed EURUSD H1 payload"
DIGEST = "sha256:77af79203369421f6206ad9c6b1a1d1656e5a68d83569ea3620e7775e25e0c5e"


def source():
    return {"contract_version": "forex.historical-data.v1", "source_id": "retained-demo-source", "owner": "operator", "license": "demo", "cost_model": "none", "api_version": "retained", "endpoint_allowlist": [], "rate_limit": "not-applicable", "retention_rule": "immutable local raw", "historical_depth": "unknown", "revision_support": "source revision", "timezone_policy": "UTC-normalised", "outage_policy": "not-applicable", "approval_status": "DEMO_ONLY", "secrets_reference": "NONE", "provenance_note": "already observed"}


def bars():
    return [{"time_utc": "2026-09-01T00:00:00Z", "open": 1.1, "high": 1.2, "low": 1.0, "close": 1.15, "volume": 10, "available_at_utc": "2026-09-01T02:00:00Z"}, {"time_utc": "2026-09-01T01:00:00Z", "open": 1.15, "high": 1.25, "low": 1.1, "close": 1.2, "volume": 11, "available_at_utc": "2026-09-01T02:00:00Z"}]


def build(**changes):
    values = {"snapshot_id": "eurusd-h1", "timeframe": "H1", "decision_cutoff_utc": "2026-09-01T03:00:00Z", "capture_available_at_utc": "2026-09-01T02:00:00Z", "source_registry_entry": source(), "source_revision": "capture-1", "raw_payload": RAW, "payload_sha256": DIGEST, "parsed_bars": bars()}
    values.update(changes)
    return build_closed_eurusd_snapshot(**values)


def test_builds_content_addressed_closed_h1_snapshot_accepted_by_contract():
    snapshot = build()
    assert validate_dataset_snapshot(snapshot) == snapshot
    assert snapshot["timeframe"] == "H1"
    assert snapshot["raw_observations"][0]["payload_sha256"] == DIGEST
    assert all(bar["raw_observation_id"] == snapshot["raw_observations"][0]["observation_id"] for bar in snapshot["price_bars"])


@pytest.mark.parametrize("changes", [
    {"timeframe": "M1"}, {"payload_sha256": "sha256:" + "0" * 64},
    {"capture_available_at_utc": "2026-09-01T04:00:00Z"},
    {"capture_available_at_utc": "2026-09-01T01:00:00Z"},
    {"parsed_bars": [{**bars()[0], "time_utc": "2026-09-01T00:30:00Z"}]},
    {"parsed_bars": [{**bars()[0], "available_at_utc": "2026-09-01T00:30:00Z"}]},
    {"parsed_bars": [bars()[1], bars()[0]]},
    {"parsed_bars": [{**bars()[0], "close": float("nan")}]},
    {"parsed_bars": [{**bars()[0], "time_utc": "2026-09-01T00:00:00+01:00"}]},
    {"source_registry_entry": {**source(), "timezone_policy": "UTC"}},
])
def test_refuses_unclosed_misaligned_future_or_invalid_input(changes):
    with pytest.raises(ClosedBarSnapshotError): build(**changes)


def test_d1_requires_midnight_open_and_rejects_non_eurusd_by_construction():
    daily = {**bars()[0], "time_utc": "2026-08-31T00:00:00Z", "available_at_utc": "2026-09-01T02:00:00Z"}
    snapshot = build(snapshot_id="eurusd-d1", timeframe="D1", parsed_bars=[daily])
    assert snapshot["instrument"] == "EUR/USD" and snapshot["timeframe"] == "D1"
    with pytest.raises(ClosedBarSnapshotError):
        build(timeframe="D1", parsed_bars=[{**daily, "time_utc": "2026-08-31T01:00:00Z"}])
