import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

from forex.m20_assessment_spool import AssessmentSpoolError, read_immutable_spool


SOURCE = Path("t480/m20_demo_listener_service.py")


def listener_module():
    spec = importlib.util.spec_from_file_location("m20_listener_spool", SOURCE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def output(sequence: int) -> dict:
    return {"marker": "FOREX_M20_DEMO_TRADING_OPERATION_OK", "schema_version": "forex.m20.demo-trading-operation.v1",
            "operation": "m20_demo_trading_session", "server": "GOMarketsMU-Demo", "symbol": "EURUSD",
            "captured_at_utc": "2026-09-12T00:00:01Z", "configuration_fingerprint": "sha256:" + "a" * 64,
            "tick_timestamp_offset_seconds": 0, "decision_snapshot": {"snapshot_id": f"s{sequence}"},
            "proposal": {"proposal_id": f"p{sequence}"}}


def test_reader_accepts_listener_immutable_records_and_binds_raw_bytes(tmp_path, monkeypatch):
    module = listener_module()
    monkeypatch.setattr(module, "ASSESSMENT_SPOOL_PATH", tmp_path / "spool")
    monkeypatch.setattr(module, "ROOT", Path("a" * 16))
    for sequence in (4, 5):
        assert module._write_assessment_spool(output(sequence), assessment_started_at_utc="2026-09-12T00:00:00Z",
                                              assessment_completed_at_utc="2026-09-12T00:00:02Z",
                                              assessment_sequence=sequence) == "SPOOLED_IMMUTABLE"
    result = read_immutable_spool(tmp_path / "spool", listener_release_id="a" * 16)
    assert result["coverage_status"] == "BASELINE_CONTIGUOUS"
    assert [row["assessment_sequence"] for row in result["records"]] == [4, 5]
    assert result["records"][0]["source_sha256"].startswith("sha256:")
    assert result["execution_authority"] is False


def test_reader_refuses_gaps_staging_or_wrong_release(tmp_path, monkeypatch):
    module = listener_module()
    monkeypatch.setattr(module, "ASSESSMENT_SPOOL_PATH", tmp_path / "spool")
    monkeypatch.setattr(module, "ROOT", Path("a" * 16))
    for sequence in (4, 6):
        module._write_assessment_spool(output(sequence), assessment_started_at_utc="2026-09-12T00:00:00Z",
                                       assessment_completed_at_utc="2026-09-12T00:00:02Z", assessment_sequence=sequence)
    with pytest.raises(AssessmentSpoolError, match="gap"):
        read_immutable_spool(tmp_path / "spool", listener_release_id="a" * 16)
    (tmp_path / "spool" / "00000000000000000006.json").unlink()
    (tmp_path / "spool" / "x.pending").write_text("unfinished")
    with pytest.raises(AssessmentSpoolError, match="unfinished"):
        read_immutable_spool(tmp_path / "spool", listener_release_id="a" * 16)


def test_cli_is_read_only_and_emits_inspection(tmp_path, monkeypatch):
    module = listener_module()
    spool = tmp_path / "spool"
    monkeypatch.setattr(module, "ASSESSMENT_SPOOL_PATH", spool)
    monkeypatch.setattr(module, "ROOT", Path("a" * 16))
    module._write_assessment_spool(output(1), assessment_started_at_utc="2026-09-12T00:00:00Z",
                                   assessment_completed_at_utc="2026-09-12T00:00:02Z", assessment_sequence=1)
    before = {path.name: path.read_bytes() for path in spool.iterdir()}
    command = [sys.executable, "scripts/m20_assessment_spool.py", "--root", str(spool),
               "--listener-release-id", "a" * 16]
    result = subprocess.run(command, cwd=Path(__file__).resolve().parents[1], text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["last_assessment_sequence"] == 1
    assert {path.name: path.read_bytes() for path in spool.iterdir()} == before
