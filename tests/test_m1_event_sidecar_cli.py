from __future__ import annotations

from datetime import datetime, timedelta, timezone
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "m1_event_sidecar.py"
SPEC = importlib.util.spec_from_file_location("m1_event_sidecar_cli", SCRIPT)
CLI = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(CLI)


START = "2026-09-11T09:00:00Z"
END = "2026-09-11T11:00:00Z"


def assessment() -> dict:
    from tests.test_m20_policy_kernel import bound_snapshot, stamp

    observed = datetime(2026, 9, 11, 10, 0, tzinfo=timezone.utc)
    decision = observed + timedelta(seconds=7)
    snapshot = bound_snapshot(observed=observed, decision=decision)
    proposal = {"proposal_id": "proposal-1", "session_id": "session-1", "snapshot_id": "snapshot-1",
                "decision_at_utc": stamp(decision), "expires_at_utc": stamp(decision + timedelta(minutes=5)),
                "selected_timeframe": "M1", "action": "NO_TRADE", "proposed_entry": None,
                "stop_loss": None, "take_profit": None, "notional_usd": None, "confidence": 100,
                "rationale": "fixture", "decision_snapshot_sha256": snapshot["payload_sha256"],
                "strategy_version": "fixture"}
    return {"operation": "m20_demo_trading_session",
            "result": {"stdout": json.dumps({"decision_snapshot": snapshot, "proposal": proposal})}}


def context(decision: str) -> dict:
    from forex.event_annotations import event_annotation
    from forex.event_quality import qualify_events

    qualification = qualify_events([], decision)
    return {"schema_version": "forex.event-store-context-report.v1",
            "journal_sha256": "sha256:" + "2" * 64,
            "qualification": qualification,
            "annotation": event_annotation(qualification, decision_at_utc=decision,
                                             window_start_utc=START, window_end_utc=END),
            "execution_authority": False}


def test_symlink_ancestor_output_refuses_before_processing(monkeypatch, tmp_path):
    real = tmp_path / "real"
    real.mkdir()
    (real / "out").mkdir()
    alias = tmp_path / "alias"
    alias.symlink_to(real, target_is_directory=True)
    source = tmp_path / "assessment.json"
    source.write_text(json.dumps(assessment()))
    def forbidden(*args, **kwargs):
        raise AssertionError("must refuse before subprocess")
    monkeypatch.setattr(CLI.subprocess, "run", forbidden)
    assert CLI.main(["--assessment", str(source), "--store", str(tmp_path), "--window-start", START,
                     "--window-end", END, "--output", str(alias / "out")]) == 2
    assert not list((real / "out").iterdir())


def test_local_context_then_exclusive_content_addressed_publication(monkeypatch, tmp_path, capsys):
    source = tmp_path / "assessment.json"
    source.write_text(json.dumps(assessment()))
    output = tmp_path / "sidecars"
    output.mkdir()
    seen = []

    def run(command, **kwargs):
        seen.append((command, kwargs))
        decision = command[command.index("--decision-at") + 1]
        return SimpleNamespace(returncode=0, stdout=json.dumps(context(decision)), stderr="")

    monkeypatch.setattr(CLI.subprocess, "run", run)
    args = ["--assessment", str(source), "--store", str(tmp_path / "store"),
            "--window-start", START, "--window-end", END, "--output", str(output)]
    assert CLI.main(args) == 0
    first = json.loads(capsys.readouterr().out)
    assert first["publication"] == "CREATED"
    assert first["execution_authority"] is False
    path = Path(first["sidecar_path"])
    assert path.parent == output and path.name == first["sidecar_sha256"].removeprefix("sha256:") + ".json"
    assert json.loads(path.read_text())["sidecar_sha256"] == first["sidecar_sha256"]
    command, kwargs = seen[0]
    assert command[:2] == [CLI.sys.executable, str(CLI.ROOT / "scripts" / "event_context.py")]
    assert command[2:] == ["--store", str(tmp_path / "store"), "--decision-at", "2026-09-11T10:00:07Z",
                           "--window-start", START, "--window-end", END]
    assert kwargs == {"cwd": CLI.ROOT, "capture_output": True, "text": True, "timeout": 30, "check": False}
    assert CLI.main(args) == 0
    assert json.loads(capsys.readouterr().out)["publication"] == "EXISTING"
    assert len(seen) == 2


def test_strict_assessment_and_unsafe_output_refuse_before_local_subprocess(monkeypatch, tmp_path, capsys):
    source = tmp_path / "ambiguous.json"
    source.write_text('{"result":{},"result":{}}')
    output = tmp_path / "output"
    output.mkdir()
    calls = []
    monkeypatch.setattr(CLI.subprocess, "run", lambda *args, **kwargs: calls.append(args))
    args = ["--assessment", str(source), "--store", str(tmp_path / "store"),
            "--window-start", START, "--window-end", END, "--output", str(output)]
    assert CLI.main(args) == 2
    assert calls == []
    assert "refused" in capsys.readouterr().err
    good = tmp_path / "good.json"
    good.write_text(json.dumps(assessment()))
    link = tmp_path / "output-link"
    link.symlink_to(output, target_is_directory=True)
    args[1] = str(good)
    args[-1] = str(link)
    assert CLI.main(args) == 2
    assert calls == []


def test_existing_digest_path_with_different_bytes_refuses(monkeypatch, tmp_path, capsys):
    source = tmp_path / "assessment.json"
    raw = json.dumps(assessment()).encode()
    source.write_bytes(raw)
    output = tmp_path / "output"
    output.mkdir()
    decision = "2026-09-11T10:00:07Z"
    supplied_context = context(decision)
    from forex.m1_event_sidecar import build_m1_event_context_sidecar
    import hashlib
    sidecar = build_m1_event_context_sidecar(assessment(), source_raw_sha256="sha256:" + hashlib.sha256(raw).hexdigest(),
                                             event_context=supplied_context, window_start_utc=START, window_end_utc=END)
    (output / (sidecar["sidecar_sha256"].removeprefix("sha256:") + ".json")).write_bytes(b"conflict")
    monkeypatch.setattr(CLI.subprocess, "run", lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout=json.dumps(supplied_context)))
    assert CLI.main(["--assessment", str(source), "--store", str(tmp_path / "store"),
                     "--window-start", START, "--window-end", END, "--output", str(output)]) == 2
    assert "conflicts" in capsys.readouterr().err
