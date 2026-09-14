import importlib.util
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

from forex.m20_spool_drain import SpoolDrainError, _canonical, _load_cursor, _store_cursor, drain


SOURCE = Path("t480/m20_demo_listener_service.py")
ROOT = Path(__file__).resolve().parents[1]


def listener_module():
    spec = importlib.util.spec_from_file_location("m20_listener_drain", SOURCE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def source_output(sequence: int) -> dict:
    return {"marker": "FOREX_M20_DEMO_TRADING_OPERATION_OK", "schema_version": "forex.m20.demo-trading-operation.v1",
            "operation": "m20_demo_trading_session", "server": "GOMarketsMU-Demo", "symbol": "EURUSD",
            "captured_at_utc": "2026-09-12T00:00:01Z", "configuration_fingerprint": "sha256:" + "a" * 64,
            "tick_timestamp_offset_seconds": 0, "decision_snapshot": {"snapshot_id": f"s{sequence}"},
            "proposal": {"proposal_id": f"p{sequence}"}}


def spool(tmp_path, monkeypatch, sequences=(1, 2)):
    module = listener_module()
    root = tmp_path / "spool"
    monkeypatch.setattr(module, "ASSESSMENT_SPOOL_PATH", root)
    monkeypatch.setattr(module, "ROOT", Path("a" * 16))
    for sequence in sequences:
        assert module._write_assessment_spool(source_output(sequence), assessment_started_at_utc="2026-09-12T00:00:00Z",
                                              assessment_completed_at_utc="2026-09-12T00:00:02Z",
                                              assessment_sequence=sequence) == "SPOOLED_IMMUTABLE"
    return root


def test_drain_copies_all_sources_then_advances_cursor(monkeypatch, tmp_path):
    source = spool(tmp_path, monkeypatch)
    captures = tmp_path / "captures"; captures.mkdir()
    first = drain(spool_root=source, capture_root=captures, listener_release_id="a" * 16)
    assert first["retained_count"] == 2
    assert first["acknowledgement"] == "LOCAL_CURSOR_ADVANCED_AFTER_IMMUTABLE_RETENTION"
    assert not (source / "00000000000000000001.json").is_symlink()
    target = Path(first["retained"][0]["capture_path"])
    assert set(item.name for item in target.iterdir()) == {"listener-spool-record.json", "receipt.json", "demo-trading-operation.json"}
    assert json.loads((target / "receipt.json").read_text())["assessment_sequence"] == 1
    before = {path.name: path.read_bytes() for path in source.iterdir()}
    second = drain(spool_root=source, capture_root=captures, listener_release_id="a" * 16)
    assert second["retained_count"] == 0
    assert {path.name: path.read_bytes() for path in source.iterdir()} == before


def test_drain_never_advances_cursor_after_conflicting_or_incomplete_capture(monkeypatch, tmp_path):
    source = spool(tmp_path, monkeypatch, sequences=(1,))
    captures = tmp_path / "captures"; captures.mkdir()
    prefix = hashlib.sha256((source / "00000000000000000001.json").read_bytes()).hexdigest()[:16]
    conflict = captures / ("a" * 16 + "-00000000000000000001-" + prefix)
    conflict.mkdir()
    (conflict / "receipt.json").write_text("different")
    with pytest.raises(SpoolDrainError, match="incomplete"):
        drain(spool_root=source, capture_root=captures, listener_release_id="a" * 16)
    assert not (captures / ".m20-spool-drain-cursor.json").exists()


def test_drain_cli_emits_json(monkeypatch, tmp_path):
    source = spool(tmp_path, monkeypatch, sequences=(1,))
    captures = tmp_path / "captures"; captures.mkdir()
    result = subprocess.run([sys.executable, "scripts/m20_spool_drain.py", "--spool-root", str(source),
                             "--capture-root", str(captures), "--listener-release-id", "a" * 16],
                            cwd=ROOT, text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["retained_count"] == 1


def test_matching_cursor_staging_recovers_after_interrupted_local_publish(tmp_path):
    captures = tmp_path / "captures"
    captures.mkdir()
    release = "a" * 16
    first = "sha256:" + "1" * 64
    second = "sha256:" + "2" * 64
    _store_cursor(captures, release=release, sequence=1, source_sha256=first)
    raw = _canonical({"schema_version": "forex.m20.spool-drain-cursor.v1",
                      "listener_release_id": release, "assessment_sequence": 2,
                      "source_sha256": second})
    staging = captures / ".m20-spool-drain-cursor.tmp"
    staging.write_bytes(raw)
    _store_cursor(captures, release=release, sequence=2, source_sha256=second)
    assert not staging.exists()
    assert _load_cursor(captures)["assessment_sequence"] == 2


def test_conflicting_cursor_staging_remains_a_fail_closed_investigation_stop(tmp_path):
    captures = tmp_path / "captures"
    captures.mkdir()
    (captures / ".m20-spool-drain-cursor.tmp").write_bytes(b"partial")
    with pytest.raises(SpoolDrainError, match="temporary path is unsafe"):
        _store_cursor(captures, release="a" * 16, sequence=1, source_sha256="sha256:" + "1" * 64)
