from forex.quality import normalise


def test_m12_normalises_and_quarantines_bad_historical_observations():
    record = {"observation_id":"ok","source_id":"fixture","observed_at_utc":"2026-01-01T00:00:00Z","available_at_utc":"2026-01-01T00:15:00Z","payload_sha256":"sha256:" + "a" * 64}
    accepted, quarantined = normalise([record, record, {**record, "observation_id":"late", "available_at_utc":"2026-01-01T02:00:00Z"}, {"observation_id":"bad"}], "2026-01-01T01:00:00Z")
    assert len(accepted) == 1
    assert {item["reason"] for item in quarantined} == {"DUPLICATE", "LATE_OR_LOOKAHEAD", "MISSING_REQUIRED_FIELD"}
