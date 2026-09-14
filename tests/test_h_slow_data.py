from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from forex.data_contracts import build_dataset_snapshot
from forex.h_slow_data import HSlowDataInputError, h_slow_daily_input


DECISION = "2026-09-01T12:00:00Z"


def snapshot(*, timeframe: str = "D1", instrument: str = "EUR/USD", late: bool = False) -> dict:
    source = {
        "contract_version": "forex.historical-data.v1", "source_id": "fixture", "owner": "test",
        "license": "test", "cost_model": "none", "api_version": "1", "endpoint_allowlist": [],
        "rate_limit": "none", "retention_rule": "test", "historical_depth": "test",
        "revision_support": "none", "timezone_policy": "UTC", "outage_policy": "fail",
        "approval_status": "DEMO_ONLY", "secrets_reference": "NONE", "provenance_note": "test",
    }
    observation = {
        "contract_version": "forex.historical-data.v1", "observation_id": "obs", "source_id": "fixture",
        "source_revision": "1", "observed_at_utc": "2026-08-01T00:00:00Z",
        "available_at_utc": "2026-08-01T00:00:00Z", "retrieved_at_utc": "2026-08-01T00:00:00Z",
        "timezone": "UTC", "payload_sha256": "sha256:test", "payload_path": "test", "redacted": False,
    }
    first = datetime(2026, 8, 3, tzinfo=timezone.utc)
    bars = []
    for number in range(3):
        opened = first + timedelta(days=number)
        available = opened + timedelta(days=1, hours=1)
        bars.append({"time_utc": opened.isoformat().replace("+00:00", "Z"), "open": 1.1, "high": 1.2,
                     "low": 1.0, "close": 1.1 + number / 100, "volume": 1, "raw_observation_id": "obs",
                     "available_at_utc": ("2026-09-02T00:00:00Z" if late and number == 2 else available.isoformat().replace("+00:00", "Z"))})
    return build_dataset_snapshot(snapshot_id="hslow-d1", instrument=instrument, timeframe=timeframe,
                                  decision_cutoff_utc=DECISION, created_at_utc=DECISION,
                                  source_registry=[source], raw_observations=[observation], price_bars=bars)


def test_converts_completed_d1_snapshot_with_bound_deterministic_input():
    first = h_slow_daily_input(snapshot(), decision_at_utc=DECISION)
    second = h_slow_daily_input(snapshot(), decision_at_utc=DECISION)
    assert first["input_sha256"] == second["input_sha256"]
    assert first["research_only"] is True and first["execution_authority"] is False
    assert first["daily_bars"][0] == {"opened_at_utc": "2026-08-03T00:00:00Z", "closed_at_utc": "2026-08-04T00:00:00Z", "available_at_utc": "2026-08-04T01:00:00Z", "close": 1.1}
    assert first["snapshot_artifact_sha256"] == snapshot()["artifact_sha256"]


@pytest.mark.parametrize(("kwargs", "message"), [
    ({"timeframe": "H1"}, "EUR/USD D1"),
    ({"instrument": "GBP/USD"}, "invalid dataset snapshot"),
])
def test_rejects_wrong_snapshot_scope(kwargs: dict, message: str):
    with pytest.raises(HSlowDataInputError, match=message):
        h_slow_daily_input(snapshot(**kwargs), decision_at_utc=DECISION)


def test_rejects_cutoff_mismatch_and_unavailable_completed_bar():
    with pytest.raises(HSlowDataInputError, match="must equal"):
        h_slow_daily_input(snapshot(), decision_at_utc="2026-09-01T12:01:00Z")
    with pytest.raises(HSlowDataInputError, match="invalid dataset snapshot"):
        h_slow_daily_input(snapshot(late=True), decision_at_utc=DECISION)


def test_rejects_non_midnight_or_pre_close_available_d1_bar():
    non_midnight = snapshot()
    non_midnight["price_bars"][0]["time_utc"] = "2026-08-03T01:00:00Z"
    # Rebuild the artifact rather than asking the adapter to accept a tampered
    # snapshot: the source contract permits a D1 label, while H_SLOW does not.
    rebuilt = build_dataset_snapshot(
        snapshot_id=non_midnight["snapshot_id"], instrument=non_midnight["instrument"],
        timeframe=non_midnight["timeframe"], decision_cutoff_utc=non_midnight["decision_cutoff_utc"],
        created_at_utc=non_midnight["created_at_utc"], source_registry=non_midnight["source_registry"],
        raw_observations=non_midnight["raw_observations"], price_bars=non_midnight["price_bars"],
    )
    with pytest.raises(HSlowDataInputError, match="UTC midnight"):
        h_slow_daily_input(rebuilt, decision_at_utc=DECISION)

    pre_close = snapshot()
    pre_close["price_bars"][0]["available_at_utc"] = "2026-08-03T12:00:00Z"
    rebuilt = build_dataset_snapshot(
        snapshot_id=pre_close["snapshot_id"], instrument=pre_close["instrument"],
        timeframe=pre_close["timeframe"], decision_cutoff_utc=pre_close["decision_cutoff_utc"],
        created_at_utc=pre_close["created_at_utc"], source_registry=pre_close["source_registry"],
        raw_observations=pre_close["raw_observations"], price_bars=pre_close["price_bars"],
    )
    with pytest.raises(HSlowDataInputError, match="unavailable as a completed"):
        h_slow_daily_input(rebuilt, decision_at_utc=DECISION)
