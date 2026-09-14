from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "m1_event_service.py"
SPEC = importlib.util.spec_from_file_location("m1_event_service", SCRIPT)
CLI = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(CLI)


POLICY = {"schema_version": "forex.m1-event-automation-policy.v1",
          "window_mode": "DECISION_UTC_DAY", "execution_authority": False}


def directories(tmp_path):
    values = {name: tmp_path / name for name in ("assessments", "store", "sidecars", "reports")}
    for value in values.values():
        value.mkdir()
    return values


def batch_result():
    return {"schema_version": "forex.m1-event-batch-report.v1", "state": "COMPLETE",
            "assessment_root": "assessment-root",
            "total_count": 2, "attached_count": 1, "refused_count": 1,
            "records": [{"status": "ATTACHED"}, {"status": "INPUT_REFUSED"}],
            "execution_authority": False}


def set_policy(monkeypatch, tmp_path, value=POLICY):
    path = tmp_path / "policy.json"
    path.write_text(json.dumps(value))
    monkeypatch.setattr(CLI, "POLICY_PATH", path)
    return path


@pytest.mark.parametrize("change", [{"records": []}, {"state": "NO_INPUTS"}, {"schema_version": "other"},
    {"records": [{"status": "ATTACHED"}, {"status": "ATTACHED"}]}])
def test_batch_count_labels_must_match_actual_rows(change):
    with pytest.raises(ValueError, match="rows"):
        CLI._validate_batch({**batch_result(), **change})


def test_clock_rollback_leaves_start_without_completion(monkeypatch, tmp_path):
    paths = directories(tmp_path)
    set_policy(monkeypatch, tmp_path)
    monkeypatch.setattr(CLI.batch, "run_batch", lambda **kwargs: batch_result())
    clock = iter(["2026-09-12T01:00:00Z", "2026-09-12T00:59:59Z"])
    monkeypatch.setattr(CLI, "_now", lambda: next(clock))
    with pytest.raises(ValueError, match="clock"):
        CLI.run_once(assessment_root=paths["assessments"], store=paths["store"], sidecars=paths["sidecars"], reports=paths["reports"])
    records = [json.loads(path.read_bytes()) for path in paths["reports"].glob("*.json")]
    assert len(records) == 1 and records[0]["schema_version"] == "forex.m1-event-service-start.v1"


def test_one_pass_retains_hash_bound_partial_batch_report(monkeypatch, tmp_path, capsys):
    paths = directories(tmp_path)
    policy_path = set_policy(monkeypatch, tmp_path)
    calls = []

    def run_batch(**kwargs):
        calls.append(kwargs)
        return batch_result()

    monkeypatch.setattr(CLI.batch, "run_batch", run_batch)
    clock = iter(["2026-09-12T00:00:00.000Z", "2026-09-12T00:00:01.000Z"])
    monkeypatch.setattr(CLI, "_now", lambda: next(clock))
    argv = ["--assessment-root", str(paths["assessments"]), "--store", str(paths["store"]),
            "--sidecars", str(paths["sidecars"]), "--reports", str(paths["reports"])]
    assert CLI.main(argv) == 0
    command = json.loads(capsys.readouterr().out)
    assert command["execution_authority"] is False
    assert (command["total_count"], command["attached_count"], command["refused_count"]) == (2, 1, 1)
    assert calls == [{"assessment_root": paths["assessments"], "store": paths["store"],
                      "output": paths["sidecars"], "window_start": None, "window_end": None,
                      "window_mode": "DECISION_UTC_DAY"}]
    report_path = Path(command["report_path"])
    report = json.loads(report_path.read_text())
    assert report["policy_sha256"] == "sha256:" + hashlib.sha256(policy_path.read_bytes()).hexdigest()
    assert report["result"]["assessment_roots"] == ["assessment-root"]
    assert report["result"]["records"] == batch_result()["records"]
    start_path = next(paths["reports"].glob("m1-event-service-start-*.json"))
    start = json.loads(start_path.read_text())
    assert start["started_at_utc"] == report["started_at_utc"]
    assert start["policy_sha256"] == report["policy_sha256"]
    assert start["assessment_roots"] == [str(paths["assessments"])]
    assert report["start_record_sha256"] == start["start_record_sha256"]
    content = {key: value for key, value in report.items() if key != "report_sha256"}
    assert report["report_sha256"] == "sha256:" + hashlib.sha256(
        json.dumps(content, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


@pytest.mark.parametrize("change", [
    {"window_mode": "DEFAULT"}, {"execution_authority": True}, {"extra": 1},
])
def test_policy_is_exact_and_batch_is_not_called(monkeypatch, tmp_path, change):
    paths = directories(tmp_path)
    set_policy(monkeypatch, tmp_path, {**POLICY, **change})
    monkeypatch.setattr(CLI.batch, "run_batch", lambda **kwargs: pytest.fail("batch must not run"))
    with pytest.raises(ValueError, match="policy"):
        CLI.run_once(assessment_root=paths["assessments"], store=paths["store"],
                     sidecars=paths["sidecars"], reports=paths["reports"])


def test_identical_repeat_is_idempotent_and_symlink_lock_refuses(monkeypatch, tmp_path):
    paths = directories(tmp_path)
    set_policy(monkeypatch, tmp_path)
    monkeypatch.setattr(CLI.batch, "run_batch", lambda **kwargs: batch_result())
    monkeypatch.setattr(CLI, "_now", lambda: "2026-09-12T00:00:00.000Z")
    first, path, created = CLI.run_once(assessment_root=paths["assessments"], store=paths["store"],
                                        sidecars=paths["sidecars"], reports=paths["reports"])
    second, repeated, created_again = CLI.run_once(assessment_root=paths["assessments"], store=paths["store"],
                                                    sidecars=paths["sidecars"], reports=paths["reports"])
    assert first == second and path == repeated and created and not created_again
    lock = paths["reports"] / ".m1-event-service.lock"
    lock.unlink()
    lock.symlink_to(tmp_path / "elsewhere")
    with pytest.raises(ValueError, match="lock"):
        CLI.run_once(assessment_root=paths["assessments"], store=paths["store"],
                     sidecars=paths["sidecars"], reports=paths["reports"])


def test_invalid_batch_retains_unfinished_start_and_trusted_directory_refuses(monkeypatch, tmp_path):
    paths = directories(tmp_path)
    set_policy(monkeypatch, tmp_path)
    monkeypatch.setattr(CLI.batch, "run_batch", lambda **kwargs: {"execution_authority": False,
                                                                    "total_count": 1, "attached_count": 1,
                                                                    "refused_count": 0, "records": "wrong"})
    with pytest.raises(ValueError, match="records"):
        CLI.run_once(assessment_root=paths["assessments"], store=paths["store"],
                     sidecars=paths["sidecars"], reports=paths["reports"])
    assert list(paths["reports"].glob("m1-event-service-report-*.json")) == []
    starts = list(paths["reports"].glob("m1-event-service-start-*.json"))
    assert len(starts) == 1
    assert json.loads(starts[0].read_text())["schema_version"] == "forex.m1-event-service-start.v1"
    link = tmp_path / "bad-reports"
    link.symlink_to(paths["reports"], target_is_directory=True)
    with pytest.raises(ValueError, match="reports"):
        CLI.run_once(assessment_root=paths["assessments"], store=paths["store"],
                     sidecars=paths["sidecars"], reports=link)


def test_additional_assessment_root_is_batched_separately_and_reported(monkeypatch, tmp_path):
    paths = directories(tmp_path)
    extra = tmp_path / "current-assessments"
    extra.mkdir()
    set_policy(monkeypatch, tmp_path)
    seen = []

    def run_batch(**kwargs):
        seen.append(kwargs["assessment_root"])
        return {**batch_result(), "assessment_root": str(kwargs["assessment_root"])}

    monkeypatch.setattr(CLI.batch, "run_batch", run_batch)
    report, _, _ = CLI.run_once(assessment_root=paths["assessments"], store=paths["store"],
                                 sidecars=paths["sidecars"], reports=paths["reports"],
                                 additional_assessment_roots=(extra,))
    assert seen == [paths["assessments"], extra]
    assert report["result"]["assessment_roots"] == [str(paths["assessments"]), str(extra)]
    assert report["result"]["total_count"] == 4
