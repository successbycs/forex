from __future__ import annotations

from datetime import datetime, timedelta, timezone
import importlib.util
import json
import subprocess
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "m1_event_batch.py"
SPEC = importlib.util.spec_from_file_location("m1_event_batch", SCRIPT)
CLI = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(CLI)

START = "2026-09-11T00:00:00Z"
END = "2026-09-11T23:59:59Z"


def valid_assessment() -> dict:
    from tests.test_m20_policy_kernel import bound_snapshot, stamp

    observed = datetime(2026, 9, 11, 6, 50, 30, tzinfo=timezone.utc)
    decision = observed + timedelta(seconds=9)
    snapshot = bound_snapshot(observed=observed, decision=decision)
    proposal = {"proposal_id": "proposal-batch", "session_id": "session-batch", "snapshot_id": "snapshot-1",
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


def test_timeout_is_reported_and_next_file_continues(monkeypatch, tmp_path):
    root = tmp_path / "inputs"
    root.mkdir()
    output = tmp_path / "output"
    output.mkdir()
    for name in ["a", "b"]:
        folder = root / name
        folder.mkdir()
        (folder / "demo-trading-operation.json").write_text(json.dumps(valid_assessment()))
    calls = []
    def local(store, *, decision_at_utc, **kwargs):
        calls.append(decision_at_utc)
        if len(calls) == 1:
            raise subprocess.TimeoutExpired("local context", 30)
        return context(decision_at_utc)
    monkeypatch.setattr(CLI.sidecar_cli, "_local_event_context", local)
    result = CLI.run_batch(assessment_root=root, store=tmp_path, output=output, window_start=START, window_end=END)
    assert result["total_count"] == 2 and result["attached_count"] == 1
    assert result["records"][0]["reason_code"] == "EVENT_CONTEXT_TIMEOUT"


def test_automatic_window_uses_decision_utc_day_not_host_today(monkeypatch, tmp_path):
    root = tmp_path / "inputs"
    folder = root / "a"
    folder.mkdir(parents=True)
    output = tmp_path / "output"
    output.mkdir()
    source = valid_assessment()
    payload = json.loads(source["result"]["stdout"])
    payload["proposal"]["decision_at_utc"] = "2026-09-11T23:30:00-04:00"
    source["result"]["stdout"] = json.dumps(payload)
    (folder / "demo-trading-operation.json").write_text(json.dumps(source))
    seen = []
    def local(store, *, decision_at_utc, window_start_utc, window_end_utc):
        from forex.event_quality import qualify_events
        from forex.event_annotations import event_annotation
        seen.append((window_start_utc, window_end_utc))
        q = qualify_events([], decision_at_utc)
        return {"schema_version": "forex.event-store-context-report.v1", "journal_sha256": "sha256:" + "2" * 64,
                "execution_authority": False, "qualification": q,
                "annotation": event_annotation(q, decision_at_utc=decision_at_utc,
                    window_start_utc=window_start_utc, window_end_utc=window_end_utc)}
    monkeypatch.setattr(CLI.sidecar_cli, "_local_event_context", local)
    result = CLI.run_batch(assessment_root=root, store=tmp_path, output=output,
                           window_start=None, window_end=None, window_mode="DECISION_UTC_DAY")
    assert seen == [("2026-09-12T00:00:00Z", "2026-09-12T23:59:59.999999Z")]
    assert result["attached_count"] == 1


def test_end_to_end_batch_keeps_invalid_row_and_is_idempotent(monkeypatch, tmp_path):
    root = tmp_path / "assessments"
    root.mkdir()
    valid = root / "a" / "demo-trading-operation.json"
    valid.parent.mkdir()
    valid.write_text(json.dumps(valid_assessment()))
    original = valid.read_bytes()
    invalid = root / "b" / "demo-trading-operation.json"
    invalid.parent.mkdir()
    invalid.write_text('{"result":{},"result":{}}')
    output = tmp_path / "sidecars"
    output.mkdir()
    calls = []

    def local(store, *, decision_at_utc, window_start_utc, window_end_utc):
        calls.append((store, decision_at_utc, window_start_utc, window_end_utc))
        return context(decision_at_utc)

    monkeypatch.setattr(CLI.sidecar_cli, "_local_event_context", local)
    first = CLI.run_batch(assessment_root=root, store=tmp_path / "store", output=output,
                          window_start=START, window_end=END)
    assert first["state"] == "COMPLETE"
    assert (first["total_count"], first["attached_count"], first["refused_count"]) == (2, 1, 1)
    assert [row["status"] for row in first["records"]] == ["ATTACHED", "INPUT_REFUSED"]
    assert first["records"][1]["reason_code"] == "INVALID_ASSESSMENT_JSON"
    assert valid.read_bytes() == original
    assert len(list(output.glob("*.json"))) == 1
    second = CLI.run_batch(assessment_root=root, store=tmp_path / "store", output=output,
                           window_start=START, window_end=END)
    assert second["records"][0]["publication"] == "EXISTING"
    assert len(list(output.glob("*.json"))) == 1
    assert calls[0][1:] == ("2026-09-11T06:50:39Z", START, END)


def test_one_level_discovery_empty_root_and_symlink_boundaries(monkeypatch, tmp_path):
    root = tmp_path / "empty"
    root.mkdir()
    output = tmp_path / "output"
    output.mkdir()
    empty = CLI.run_batch(assessment_root=root, store=tmp_path / "store", output=output,
                          window_start=START, window_end=END)
    assert empty["state"] == "NO_INPUTS"
    assert empty["records"] == []
    nested = root / "outer" / "inner"
    nested.mkdir(parents=True)
    (nested / "demo-trading-operation.json").write_text(json.dumps(valid_assessment()))
    assert CLI.run_batch(assessment_root=root, store=tmp_path / "store", output=output,
                         window_start=START, window_end=END)["total_count"] == 0
    link = tmp_path / "root-link"
    link.symlink_to(root, target_is_directory=True)
    try:
        CLI.run_batch(assessment_root=link, store=tmp_path / "store", output=output,
                      window_start=START, window_end=END)
    except ValueError as exc:
        assert "non-symlink" in str(exc)
    else:
        raise AssertionError("symlink assessment root was accepted")
    child = root / "direct"
    child.mkdir()
    (child / "demo-trading-operation.json").symlink_to(nested / "demo-trading-operation.json")
    report = CLI.run_batch(assessment_root=root, store=tmp_path / "store", output=output,
                           window_start=START, window_end=END)
    assert report["total_count"] == 1
    assert report["records"][0]["reason_code"] == "UNSAFE_ASSESSMENT_PATH"
