from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

from forex.m20_current_export import CurrentAssessmentExportError, parse_adapter_result, retain


def adapter_raw(*, observation: str = "AVAILABLE", sequence: int = 1) -> bytes:
    assessment = {
        "decision_snapshot": {"snapshot_id": "snapshot-1", "payload_sha256": "sha256:" + "a" * 64},
        "proposal": {"proposal_id": "proposal-1", "snapshot_id": "snapshot-1",
                     "decision_snapshot_sha256": "sha256:" + "a" * 64},
    }
    stdout = {
        "observation": observation,
        "listener_release_id": "b" * 16,
        "assessment_sequence": sequence,
        "assessment_started_at_utc": "2026-09-12T01:00:00Z",
        "assessment_completed_at_utc": "2026-09-12T01:00:03Z",
        "raw_sha256": "sha256:" + "c" * 64,
        "assessment": assessment if observation == "AVAILABLE" else None,
    }
    return json.dumps({"operation": "m20_listener_latest_assessment", "ok": True,
                       "result": {"stdout": json.dumps(stdout)}}).encode()


def test_parses_exact_adapter_envelope_and_preserves_raw_hashes():
    raw = adapter_raw()
    record = parse_adapter_result(raw)
    assert record["state"] == "AVAILABLE"
    assert record["assessment_raw_sha256"] == "sha256:" + hashlib.sha256(record["assessment_raw"]).hexdigest()
    assert record["adapter_response_raw"] == raw
    assert record["execution_authority"] is False


def test_absence_is_explicit_and_is_not_a_synthetic_assessment():
    record = parse_adapter_result(adapter_raw(observation="LATEST_ASSESSMENT_ABSENT"))
    assert record == {"state": "ASSESSMENT_ABSENT", "observation": "LATEST_ASSESSMENT_ABSENT", "execution_authority": False}


def test_retention_is_immutable_and_assessment_file_is_last(monkeypatch, tmp_path):
    record = parse_adapter_result(adapter_raw())
    calls = []
    from forex import m20_current_export
    original = m20_current_export._write_new

    def tracked(path, raw):
        calls.append(path.name)
        original(path, raw)

    monkeypatch.setattr(m20_current_export, "_write_new", tracked)
    root = tmp_path / "captures"
    root.mkdir()
    path, publication = retain(root, record)
    assert publication == "CREATED"
    assert calls[:3] == ["adapter-operation.json", "receipt.json", "demo-trading-operation.json"]
    assert calls[3] == ".m20-current-assessment-export-cursor.tmp"
    assert json.loads((path / "receipt.json").read_text())["assessment_raw_sha256"] == record["assessment_raw_sha256"]
    assert (path / "adapter-operation.json").read_bytes() == adapter_raw()
    assert retain(root, record) == (path, "EXISTING")


def test_cursor_reports_exact_gap_without_claiming_full_coverage(tmp_path):
    root = tmp_path / "captures"
    root.mkdir()
    first = parse_adapter_result(adapter_raw(sequence=10))
    first_path, _ = retain(root, first)
    first_receipt = json.loads((first_path / "receipt.json").read_text())
    assert first_receipt["coverage_status"] == "BASELINE_UNVERIFIED"
    second = parse_adapter_result(adapter_raw(sequence=13))
    second_path, _ = retain(root, second)
    second_receipt = json.loads((second_path / "receipt.json").read_text())
    assert second_receipt["coverage_status"] == "GAP_OBSERVED"
    assert second_receipt["missed_assessment_count"] == 2
    assert second_receipt["previous_assessment_sequence"] == 10


def test_conflicting_or_incomplete_existing_capture_refuses_without_overwrite(tmp_path):
    record = parse_adapter_result(adapter_raw())
    root = tmp_path / "captures"
    root.mkdir()
    path, _ = retain(root, record)
    source = path / "demo-trading-operation.json"
    source.write_text("different")
    with pytest.raises(CurrentAssessmentExportError, match="conflicts"):
        retain(root, record)
    assert source.read_text() == "different"


def test_cli_uses_only_the_fixed_operation(monkeypatch, tmp_path, capsys):
    source = Path("scripts/m20_current_assessment_export.py")
    spec = importlib.util.spec_from_file_location("m20_current_assessment_export", source)
    assert spec and spec.loader
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
    calls = []

    class Completed:
        returncode = 0
        stdout = adapter_raw()

    def run(command, **kwargs):
        calls.append((command, kwargs))
        return Completed()

    monkeypatch.setattr(cli.subprocess, "run", run)
    root = tmp_path / "captures"
    root.mkdir()
    assert cli.main(["--root", str(root)]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["state"] == "RETAINED"
    assert calls[0][0][-1] == "m20_listener_latest_assessment"
    assert "--operation" in calls[0][0]
