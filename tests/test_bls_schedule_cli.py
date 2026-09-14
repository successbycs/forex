import importlib.util
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace

import pytest


SPEC = importlib.util.spec_from_file_location("bls_schedule_cli", Path(__file__).resolve().parents[1] / "scripts/bls_schedule.py")
CLI = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CLI)


def summary():
    return {"schema_version": "forex.bls-collection-result.v1", "capture_id": "test-capture",
            "outcome": "SUCCESS", "execution_authority": False}


@pytest.mark.parametrize("resume", [False, True])
def test_fixed_command_and_local_resume(monkeypatch, tmp_path, resume):
    import forex.bls_collection as collection
    monkeypatch.setattr(collection, "resume_collection", lambda *a, **k: summary())
    calls = []
    def run(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=0, stdout=json.dumps(summary()))
    monkeypatch.setattr(CLI.subprocess, "run", run)
    assert CLI.collect_once(tmp_path, year=2026, month=9, capture_id="test-capture", resume=resume) == summary()
    command, kwargs = calls[0]
    assert command[:2] == [CLI.sys.executable, str(CLI.ROOT / "scripts/bls_collect.py")]
    assert ("--resume" in command) is resume
    assert kwargs == dict(capture_output=True, text=True, timeout=90, check=False)
    assert len(calls) == 1


def test_child_summary_must_match_retained_bytes(monkeypatch, tmp_path):
    import forex.bls_collection as collection
    monkeypatch.setattr(collection, "resume_collection", lambda *a, **k: {**summary(), "status_code": 403})
    monkeypatch.setattr(CLI.subprocess, "run", lambda *a, **k: SimpleNamespace(returncode=0, stdout=json.dumps(summary())))
    with pytest.raises(ValueError, match="retained observation"):
        CLI.collect_once(tmp_path, year=2026, month=9, capture_id="test-capture", resume=False)


@pytest.mark.parametrize("code,body", [(2, "{}"), (0, "{}"), (3, json.dumps(summary())),
    (0, '{"capture_id":"a","capture_id":"b"}'), (0, '{"value":NaN}')])
def test_invalid_child_response_refused(monkeypatch, tmp_path, code, body):
    monkeypatch.setattr(CLI.subprocess, "run", lambda *a, **k: SimpleNamespace(returncode=code, stdout=body))
    with pytest.raises(ValueError):
        CLI.collect_once(tmp_path, year=2026, month=9, capture_id="test-capture", resume=False)


def test_timeout_never_retries(monkeypatch, tmp_path):
    calls = []
    def run(*args, **kwargs):
        calls.append(args)
        raise subprocess.TimeoutExpired(args[0], 90)
    monkeypatch.setattr(CLI.subprocess, "run", run)
    with pytest.raises(subprocess.TimeoutExpired):
        CLI.collect_once(tmp_path, year=2026, month=9, capture_id="test-capture", resume=False)
    assert len(calls) == 1


def test_main_uses_current_clock_and_canonical_policy(monkeypatch, tmp_path, capsys):
    import forex.bls_scheduler as scheduler
    def run(root, *, now_utc, policy, collect):
        assert root == tmp_path
        assert CLI.datetime.fromisoformat(now_utc).tzinfo is not None
        assert policy == json.loads((CLI.ROOT / "config/bls_scheduler.json").read_bytes())
        return {"state": "NOT_DUE", "execution_authority": False}
    monkeypatch.setattr(scheduler, "run_schedule_once", run)
    assert CLI.main(["--store", str(tmp_path)]) == 0
    assert json.loads(capsys.readouterr().out)["state"] == "NOT_DUE"


def test_scheduler_recovers_real_retained_capture_through_resume_subprocess(tmp_path):
    from forex.bls_scheduler import run_schedule_once
    from forex.bls_collection import retain_response
    from tests.test_bls_collection import response
    policy = json.loads((CLI.ROOT / "config/bls_scheduler.json").read_bytes())
    def interrupted(**kwargs):
        retain_response(tmp_path, capture_id=kwargs["capture_id"], year=kwargs["year"], month=kwargs["month"],
                        raw=response(completed_at_utc="2026-09-12T00:10:01Z"))
        raise RuntimeError("crash after capture publication")
    first = run_schedule_once(tmp_path, now_utc="2026-09-12T00:10:00Z", policy=policy, collect=interrupted)
    assert first["state"] == "RECOVERY_REQUIRED"
    before = {str(path.relative_to(tmp_path)): path.read_bytes() for folder in ["raw", "metadata", "journals", "acquisitions"]
              for path in (tmp_path / folder).rglob("*") if path.is_file()}
    def resume(**kwargs):
        assert kwargs["resume"] is True  # No new publisher request is permitted.
        return CLI.collect_once(tmp_path, **kwargs)
    recovered = run_schedule_once(tmp_path, now_utc="2026-09-12T00:11:00Z", policy=policy, collect=resume)
    assert recovered["state"] == "RUN_COMPLETE"
    assert len(recovered["results"]) == 1
    assert recovered["results"][0]["collector_result"]["processing"] == "CAPTURE_RETAINED"
    after = {str(path.relative_to(tmp_path)): path.read_bytes() for folder in ["raw", "metadata", "journals", "acquisitions"]
             for path in (tmp_path / folder).rglob("*") if path.is_file()}
    assert before == after
