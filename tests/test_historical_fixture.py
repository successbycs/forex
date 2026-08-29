import pytest
import json
from pathlib import Path

from forex.historical_fixture import replay_before, validate_fixture


def fixture():
    return {"kind": "HISTORICAL_FIXTURE", "symbol": "EURUSD", "bars": [
        {"time_utc": "2026-08-21T00:00:00Z", "open": 1.1, "high": 1.2, "low": 1.0, "close": 1.15, "volume": 1},
        {"time_utc": "2026-08-21T01:00:00Z", "open": 1.15, "high": 1.2, "low": 1.1, "close": 1.18, "volume": 2},
    ]}


def test_replay_excludes_future_bar():
    assert len(replay_before(fixture(), "2026-08-21T01:00:00Z")) == 1


def test_fixture_rejects_unlabelled_input():
    payload = fixture(); payload["kind"] = "LIVE"
    with pytest.raises(ValueError, match="HISTORICAL_FIXTURE"):
        validate_fixture(payload)


def test_exported_mt5_fixture_replays_without_lookahead():
    path = Path(__file__).parent / "fixtures" / "eurusd_h1_historical_fixture.json"
    payload = json.loads(path.read_text())
    assert len(replay_before(payload, "2026-08-28T22:00:00Z")) == 2
