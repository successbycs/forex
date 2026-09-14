from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "h_slow_validate_preflight.py"
OFFSET_SECONDS = 10800


def _record() -> dict:
    captured = datetime(2026, 9, 13, tzinfo=UTC)
    return {
        "ok": True,
        "status": "PREFLIGHT_OK",
        "captured_at_utc": "2026-09-13T00:00:00Z",
        "account_label": "H1_demo",
        "account_scope_sha256": "sha256:" + "a" * 64,
        "server": "GOMarketsMU-Demo",
        "currency": "AUD",
        "symbol": "EURUSD",
        "bid": 1.1,
        "ask": 1.1001,
        "tick_time_msc": int((captured.timestamp() + OFFSET_SECONDS) * 1000),
        "broker_timestamp_offset_seconds": OFFSET_SECONDS,
        "tick_age_seconds": 0,
        "open_positions": 0,
        "symbol_specification": {
            "name": "EURUSD",
            "point": 0.00001,
            "trade_tick_size": 0.00001,
            "trade_tick_value_loss": 1.0,
            "trade_contract_size": 100000.0,
            "volume_min": 0.01,
            "volume_max": 1.0,
            "volume_step": 0.01,
            "trade_stops_level": 0,
            "trade_freeze_level": 0,
        },
    }


def _invoke(path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(path)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_validates_actual_operation_shape_with_governed_offset(tmp_path: Path):
    path = tmp_path / "preflight.json"
    source = _record()
    path.write_text(json.dumps(source), encoding="utf-8")

    result = _invoke(path)

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {
        "instrument": "EUR/USD",
        "preflight": source,
        "receipt_sha256": "sha256:243d539787991d8f002a57716f335e659f1f5e5deb34d0a0c5571cddddcc03ee",
    }
    assert path.read_text(encoding="utf-8") == json.dumps(source)


@pytest.mark.parametrize(
    "raw",
    [
        "{}",
        '{"ok":true,"ok":false}',
        '{"tick_age_seconds":NaN}',
        '{"tick_age_seconds":Infinity}',
        "[]",
    ],
)
def test_malformed_duplicate_and_nonfinite_records_refuse_without_stdout(tmp_path: Path, raw: str):
    path = tmp_path / "bad.json"
    path.write_text(raw, encoding="utf-8")

    result = _invoke(path)

    assert result.returncode == 2
    assert result.stdout == ""
    assert "Traceback" not in result.stderr


def test_oversized_tick_timestamp_and_duplicate_key_name_refuse_cleanly(tmp_path: Path):
    oversized = _record()
    oversized["tick_time_msc"] = 10 ** 400
    large_path = tmp_path / "oversized.json"
    large_path.write_text(json.dumps(oversized), encoding="utf-8")
    large = _invoke(large_path)
    assert large.returncode == 2
    assert large.stdout == ""
    assert "Traceback" not in large.stderr

    duplicate_path = tmp_path / "duplicate.json"
    duplicate_path.write_text('{"operator_secret_name":1,"operator_secret_name":2}', encoding="utf-8")
    duplicate = _invoke(duplicate_path)
    assert duplicate.returncode == 2
    assert duplicate.stdout == ""
    assert "duplicate JSON field" in duplicate.stderr
    assert "operator_secret_name" not in duplicate.stderr


def test_ancestor_symlink_input_path_refuses_without_reading_target(tmp_path: Path):
    target = tmp_path / "target"
    target.mkdir()
    (target / "preflight.json").write_text(json.dumps(_record()), encoding="utf-8")
    link = tmp_path / "link"
    link.symlink_to(target, target_is_directory=True)
    result = _invoke(link / "preflight.json")
    assert result.returncode == 2
    assert result.stdout == ""
    assert "Traceback" not in result.stderr


def test_governed_offset_mismatch_and_missing_input_refuse_without_stdout(tmp_path: Path):
    path = tmp_path / "wrong-offset.json"
    source = _record()
    source["broker_timestamp_offset_seconds"] = 0
    source["tick_time_msc"] -= OFFSET_SECONDS * 1000
    path.write_text(json.dumps(source), encoding="utf-8")

    mismatch = _invoke(path)
    missing = _invoke(tmp_path / "missing.json")

    assert mismatch.returncode == missing.returncode == 2
    assert mismatch.stdout == missing.stdout == ""
