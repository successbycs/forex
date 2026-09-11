from forex.event_quality import fixture_records, qualify_events


def test_m21_event_quality_controls_are_deterministic_and_fail_closed():
    result = qualify_events(fixture_records(), "2026-10-15T00:00:00Z")
    assert [item["event_id"] for item in result["accepted"]] == ["ecb-hicp-2026-10"]
    assert result["accepted"][0]["revision"] == 2
    assert result["accepted"][0]["scheduled_at_utc"] == "2026-10-25T02:30:00Z"
    reasons = {item["reason"] for item in result["quarantined"]}
    assert {"SUPERSEDED_REVISION", "CANCELLED", "TIME_PRECISION_INSUFFICIENT", "LOOKAHEAD", "DST_NONEXISTENT_LOCAL_TIME"} <= reasons
    assert result["result_sha256"].startswith("sha256:")


def test_m21_rejects_ambiguous_dst_times_without_explicit_fold():
    record = fixture_records()[0].copy()
    record["event_id"] = "ambiguous-without-fold"
    record.pop("local_fold")
    result = qualify_events([record], "2026-10-15T00:00:00Z")
    assert result["accepted"] == []
    assert result["quarantined"] == [{"event": "ambiguous-without-fold@1", "reason": "DST_AMBIGUOUS_LOCAL_TIME"}]


def test_m21_latest_cancellation_suppresses_an_older_schedule():
    scheduled = fixture_records()[0].copy()
    scheduled["event_id"] = "cancelled-after-schedule"
    scheduled["revision"] = 1
    cancelled = {**scheduled, "revision": 2, "status": "CANCELLED"}
    result = qualify_events([scheduled, cancelled], "2026-10-15T00:00:00Z")
    assert result["accepted"] == []
    assert {tuple(item.items()) for item in result["quarantined"]} == {
        (("event", "cancelled-after-schedule@1"), ("reason", "SUPERSEDED_REVISION")),
        (("event", "cancelled-after-schedule@2"), ("reason", "CANCELLED")),
    }
