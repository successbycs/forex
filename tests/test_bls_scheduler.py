import json
from pathlib import Path

import pytest

from forex.bls_scheduler import BLSSchedulerError, run_schedule_once


POLICY = {"schema_version": "forex.bls-scheduler-policy.v1", "interval_seconds": 3600,
          "denial_backoff_seconds": 86400, "month_offsets": [0, 1], "execution_authority": False}


def collector(calls, *, outcome="SUCCESS", status_code=200):
    def call(**kwargs):
        calls.append(kwargs)
        value = {"schema_version": "forex.bls-collection-result.v1", "capture_id": kwargs["capture_id"],
                 "outcome": outcome, "status_code": status_code, "execution_authority": False,
                 "completed_at_utc": "2026-09-12T00:00:00Z", "observation_sha256": "sha256:" + "a" * 64,
                 "coverage_status": "UNKNOWN", "processing": "CAPTURE_RETAINED" if outcome == "SUCCESS" else "RETRIEVAL_FAILURE_RETAINED"}
        if outcome == "SUCCESS":
            value.update(journal_sha256="sha256:" + "b" * 64, parser_quarantined=[])
        return value
    return call


def test_claims_both_months_once_per_bucket_without_duplicate_fetch(tmp_path):
    calls = []
    first = run_schedule_once(tmp_path, now_utc="2026-09-12T00:10:00Z", policy=POLICY, collect=collector(calls))
    second = run_schedule_once(tmp_path, now_utc="2026-09-12T00:10:00Z", policy=POLICY, collect=collector(calls))
    third = run_schedule_once(tmp_path, now_utc="2026-09-12T00:10:00Z", policy=POLICY, collect=collector(calls))
    assert [item["state"] for item in (first, second, third)] == ["RUN_COMPLETE", "NOT_DUE", "NOT_DUE"]
    assert [(item["year"], item["month"], item["resume"]) for item in calls] == [(2026, 9, False), (2026, 10, False)]
    assert all(item["execution_authority"] is False for item in (first, second, third))


def test_pending_claim_uses_resume_only_and_blocks_other_months(tmp_path):
    calls = []

    def unavailable(**kwargs):
        calls.append(kwargs)
        raise RuntimeError("interrupted")

    first = run_schedule_once(tmp_path, now_utc="2026-09-12T00:10:00Z", policy=POLICY, collect=unavailable)
    second = run_schedule_once(tmp_path, now_utc="2026-09-12T01:10:00Z", policy=POLICY, collect=collector(calls))
    assert first["state"] == "RECOVERY_REQUIRED"
    assert second["state"] == "RUN_COMPLETE"
    assert calls[0]["resume"] is False
    assert calls[1]["resume"] is True
    assert calls[1]["month"] == 9


@pytest.mark.parametrize("outcome", ["HTTP_ERROR", "BODY_TOO_LARGE", "TRANSPORT_ERROR"])
def test_403_backoff_is_global_across_months_and_restart(tmp_path, outcome):
    calls = []
    run_schedule_once(tmp_path, now_utc="2026-09-12T00:10:00Z", policy=POLICY,
                      collect=collector(calls, outcome=outcome, status_code=403))
    blocked = run_schedule_once(tmp_path, now_utc="2026-09-12T03:10:00Z", policy=POLICY, collect=collector(calls))
    assert blocked["state"] == "BACKOFF"
    assert len(calls) == 1
    resumed = run_schedule_once(tmp_path, now_utc="2026-09-13T00:10:01Z", policy=POLICY, collect=collector(calls))
    assert resumed["state"] == "RUN_COMPLETE"
    assert [item["month"] for item in calls[-2:]] == [9, 10]


def test_invalid_collector_result_keeps_claim_and_refuses_new_fetch(tmp_path):
    calls = []
    bad = run_schedule_once(tmp_path, now_utc="2026-09-12T00:10:00Z", policy=POLICY,
                           collect=lambda **kwargs: {"capture_id": kwargs["capture_id"]})
    assert bad["state"] == "RECOVERY_REQUIRED"
    recovered = run_schedule_once(tmp_path, now_utc="2026-09-12T01:10:00Z", policy=POLICY, collect=collector(calls))
    assert recovered["state"] == "RUN_COMPLETE"
    assert calls == [{"year": 2026, "month": 9, "capture_id": calls[0]["capture_id"], "resume": True}]


@pytest.mark.parametrize("change", [
    {"interval_seconds": 3599}, {"interval_seconds": True}, {"denial_backoff_seconds": 604801},
    {"month_offsets": [1, 0]}, {"month_offsets": [False, True]}, {"execution_authority": True}, {"extra": 1},
])
def test_policy_is_strict(tmp_path, change):
    policy = {**POLICY, **change}
    with pytest.raises(BLSSchedulerError):
        run_schedule_once(tmp_path, now_utc="2026-09-12T00:10:00Z", policy=policy, collect=lambda **_: {})


def test_tampered_claim_refuses_and_symlink_root_is_unsafe(tmp_path):
    calls = []
    run_schedule_once(tmp_path, now_utc="2026-09-12T00:10:00Z", policy=POLICY, collect=collector(calls))
    path = next((tmp_path / "scheduler/claims").glob("*.json"))
    value = json.loads(path.read_text())
    value["month"] = 1
    path.write_text(json.dumps(value))
    with pytest.raises(BLSSchedulerError, match="hash mismatch"):
        run_schedule_once(tmp_path, now_utc="2026-09-12T01:10:00Z", policy=POLICY, collect=collector(calls))
    link = tmp_path.parent / "scheduler-link"
    link.symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(BLSSchedulerError, match="non-symlink"):
        run_schedule_once(link, now_utc="2026-09-12T01:10:00Z", policy=POLICY, collect=collector(calls))


def test_result_hash_binds_collector_and_late_clock_refuses(tmp_path):
    calls = []
    run_schedule_once(tmp_path, now_utc="2026-09-12T02:10:00Z", policy=POLICY, collect=collector(calls))
    result = next((tmp_path / "scheduler/results").glob("*.json"))
    value = json.loads(result.read_text())
    value["collector_result"]["outcome"] = "SUCCESS_CHANGED"
    result.write_text(json.dumps(value))
    with pytest.raises(BLSSchedulerError, match="result hash mismatch"):
        run_schedule_once(tmp_path, now_utc="2026-09-12T03:10:00Z", policy=POLICY, collect=collector(calls))
    # Restore a new clean root to exercise immutable-clock order separately.
    clean = tmp_path.parent / "clean-scheduler"
    clean.mkdir()
    run_schedule_once(clean, now_utc="2026-09-12T02:10:00Z", policy=POLICY, collect=collector([]))
    late = run_schedule_once(clean, now_utc="2026-09-12T00:10:00Z", policy=POLICY, collect=collector([]))
    assert late["state"] == "RECOVERY_REQUIRED"


def test_collector_completion_extends_denial_backoff_and_must_be_aware(tmp_path):
    calls = []

    def denied(**kwargs):
        return {**collector(calls, outcome="HTTP_ERROR", status_code=429)(**kwargs),
                "completed_at_utc": "2026-09-12T01:00:00Z"}

    result = run_schedule_once(tmp_path, now_utc="2026-09-12T00:10:00Z", policy=POLICY, collect=denied)
    assert result["results"][0]["completed_at_utc"] == "2026-09-12T01:00:00Z"
    assert run_schedule_once(tmp_path, now_utc="2026-09-13T00:30:00Z", policy=POLICY,
                             collect=collector(calls))["state"] == "BACKOFF"
    bad = tmp_path.parent / "bad-completion"
    bad.mkdir()
    assert run_schedule_once(bad, now_utc="2026-09-12T00:10:00Z", policy=POLICY,
                             collect=lambda **kwargs: {**collector([])(**kwargs),
                                                        "completed_at_utc": "2026-09-12T00:00:00"})["state"] == "RECOVERY_REQUIRED"


@pytest.mark.parametrize("change", [{"outcome": "UNKNOWN"}, {"status_code": 403},
    {"observation_sha256": "invalid"}, {"completed_at_utc": None}, {"coverage_status": "COMPLETE"},
    {"processing": "TRANSPORT_FAILURE_RETAINED"}, {"parser_quarantined": 0}])
def test_contradictory_summary_keeps_unresolved_claim(tmp_path, change):
    result = run_schedule_once(tmp_path, now_utc="2026-09-12T00:10:00Z", policy=POLICY,
                              collect=lambda **kwargs: {**collector([])(**kwargs), **change})
    assert result["state"] == "RECOVERY_REQUIRED"
    assert len(list((tmp_path / "scheduler/claims").glob("*.json"))) == 1
    assert not list((tmp_path / "scheduler/results").glob("*.json"))


def test_out_of_range_next_month_refuses_before_claim_or_callback(tmp_path):
    calls = []
    result = run_schedule_once(tmp_path, now_utc="2099-12-01T00:00:00Z", policy=POLICY, collect=collector(calls))
    assert result["state"] == "RECOVERY_REQUIRED"
    assert calls == []
    assert list((tmp_path / "scheduler/claims").glob("*.json")) == []


def test_intrabucket_clock_rollback_does_not_poison_pending_claim(tmp_path):
    def interrupted(**kwargs):
        raise RuntimeError("interrupted")
    run_schedule_once(tmp_path, now_utc="2026-09-12T00:50:00Z", policy=POLICY, collect=interrupted)
    calls = []
    result = run_schedule_once(tmp_path, now_utc="2026-09-12T00:10:00Z", policy=POLICY, collect=collector(calls))
    assert result["state"] == "RECOVERY_REQUIRED"
    assert calls == []
    assert not list((tmp_path / "scheduler/results").glob("*.json"))
    assert run_schedule_once(tmp_path, now_utc="2026-09-12T00:51:00Z", policy=POLICY,
                             collect=collector(calls))["state"] == "RUN_COMPLETE"
    assert calls[0]["resume"] is True


def test_symlink_ancestor_refuses_before_ledger_creation(tmp_path):
    target = tmp_path / "real"
    target.mkdir()
    (target / "store").mkdir()
    link = tmp_path / "alias"
    link.symlink_to(target, target_is_directory=True)
    with pytest.raises(BLSSchedulerError, match="symlink"):
        run_schedule_once(link / "store", now_utc="2026-09-12T00:10:00Z", policy=POLICY,
                          collect=collector([]))
    assert not (target / "store/scheduler").exists()


@pytest.mark.parametrize("old_interval,new_interval", [(86400, 3600), (3600, 86400)])
def test_interval_change_uses_elapsed_time_not_incomparable_buckets(tmp_path, old_interval, new_interval):
    calls = []
    old = {**POLICY, "interval_seconds": old_interval}
    new = {**POLICY, "interval_seconds": new_interval}
    run_schedule_once(tmp_path, now_utc="2026-09-12T00:10:00Z", policy=old, collect=collector(calls))
    assert run_schedule_once(tmp_path, now_utc="2026-09-12T00:10:00Z", policy=new,
                             collect=collector(calls))["state"] == "NOT_DUE"
    assert len(calls) == 2
    assert run_schedule_once(tmp_path, now_utc="2026-09-13T00:11:00Z", policy=new,
                             collect=collector(calls))["state"] == "RUN_COMPLETE"
    assert len(calls) == 4
