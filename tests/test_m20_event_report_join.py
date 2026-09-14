import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess

import pytest

SPEC = importlib.util.spec_from_file_location("m20_event_report", Path(__file__).resolve().parents[1] / "scripts/m20_replay_report.py")
CLI = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CLI)


def inputs(monkeypatch):
    import m1_event_sidecar as command
    from tests.test_m1_event_sidecar import operation_export, context, START, END
    from forex.m1_event_sidecar import build_m1_event_context_sidecar
    assessment = operation_export()
    raw = json.dumps(assessment).encode()
    digest = "sha256:" + hashlib.sha256(raw).hexdigest()
    report = context()
    monkeypatch.setattr(command, "_local_event_context", lambda *a, **k: report)
    expected = build_m1_event_context_sidecar(assessment, source_raw_sha256=digest,
        event_context=report, window_start_utc=START, window_end_utc=END)
    return assessment, raw, expected, dict(source_sha256=digest, store=Path("unused"), start=START, end=END)


def test_join_missing_attached_and_tampered_preserves_inputs(monkeypatch, tmp_path):
    assessment, raw, expected, kwargs = inputs(monkeypatch)
    before = copy.deepcopy(assessment)
    assert CLI.event_sidecar_status(assessment, sidecars=tmp_path, **kwargs)["status"] == "MISSING"
    assert list(tmp_path.iterdir()) == []
    path = tmp_path / (expected["sidecar_sha256"].removeprefix("sha256:") + ".json")
    path.write_text(json.dumps(expected))
    assert CLI.event_sidecar_status(assessment, sidecars=tmp_path, **kwargs)["status"] == "ATTACHED"
    expected["decision_at_utc"] = "2026-01-01T00:00:00Z"
    path.write_text(json.dumps(expected))
    assert CLI.event_sidecar_status(assessment, sidecars=tmp_path, **kwargs)["status"] == "INVALID"
    assert assessment == before


def test_optional_context_timeout_does_not_break_replay(monkeypatch, tmp_path, capsys):
    import m1_event_sidecar as command
    assessment, raw, expected, kwargs = inputs(monkeypatch)
    def timeout(*a, **k):
        raise subprocess.TimeoutExpired("local context", 30)
    monkeypatch.setattr(command, "_local_event_context", timeout)
    source = tmp_path / "assessment.json"
    source.write_bytes(raw)
    assert CLI.main([str(source), "--retained-export"]) == 0
    baseline = json.loads(capsys.readouterr().out)
    assert CLI.main([str(source), "--retained-export", "--event-store", str(tmp_path),
                     "--event-sidecars", str(tmp_path), "--event-window-start", kwargs["start"],
                     "--event-window-end", kwargs["end"]]) == 0
    joined = json.loads(capsys.readouterr().out)
    assert joined.pop("event_context_sidecar")["status"] == "UNAVAILABLE"
    assert baseline == joined
