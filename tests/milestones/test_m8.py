import pytest
from pathlib import Path

from forex.fred_vintage import VintageDataError, normalise_payload, observation_url


def payload():
    return {
        "realtime_start": "2024-02-01",
        "realtime_end": "2024-02-01",
        "observations": [{"realtime_start": "2024-02-01", "realtime_end": "2024-02-01", "date": "2024-01-01", "value": "309.685"}],
    }


def test_m8_uses_one_declared_series_and_requested_vintage_cutoff():
    url = observation_url("2024-02-01", "test-key")
    assert "series_id=CPIAUCSL" in url
    assert "realtime_start=2024-02-01" in url
    assert "realtime_end=2024-02-01" in url
    assert "observation_end=2024-02-01" in url


def test_m8_normalises_only_information_available_at_cutoff():
    result = normalise_payload(payload(), "2024-02-01")
    assert result["observations"][0]["value"] == 309.685
    future = payload(); future["observations"][0]["date"] = "2024-02-02"
    with pytest.raises(VintageDataError, match="future"):
        normalise_payload(future, "2024-02-01")


def test_m8_rejects_unbound_response_vintage():
    invalid = payload(); invalid["realtime_end"] = "2024-02-02"
    with pytest.raises(VintageDataError, match="vintage"):
        normalise_payload(invalid, "2024-02-01")


def test_m8_capture_reads_only_the_declared_ignored_secret_key():
    capture = (Path(__file__).parents[2] / "scripts/capture_m8_evidence.sh").read_text()
    assert "FRED_API_KEY" in capture
    assert "source .env" not in capture
