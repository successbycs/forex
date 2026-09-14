from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "render_m20_history_capture_service.py"
SPEC = importlib.util.spec_from_file_location("render_m20_history_capture_service", SCRIPT)
RENDERER = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(RENDERER)


def test_renderer_produces_fixed_read_only_daily_units(tmp_path):
    captures, output = tmp_path / "captures", tmp_path / "output"
    captures.mkdir()
    output.mkdir()
    assert RENDERER.main([
        "--repository", str(Path.cwd()), "--python", "/usr/bin/python3",
        "--captures", str(captures), "--output", str(output),
    ]) == 0
    service = (output / "forex-m20-history-capture.service").read_text()
    timer = (output / "forex-m20-history-capture.timer").read_text()
    assert "m20_all_history_capture.py" in service
    assert "NoNewPrivileges=true" in service and "TimeoutStartSec=150s" in service
    assert "/mnt/c/Windows/System32/WindowsPowerShell/v1.0" in service
    assert "OnCalendar=*-*-* 17:05:00" in timer and "Persistent=false" in timer
    assert "order_send" not in service + timer


def test_renderer_refuses_relative_or_nonempty_output(tmp_path):
    captures, output = tmp_path / "captures", tmp_path / "output"
    captures.mkdir()
    output.mkdir()
    (output / "existing").write_text("x")
    assert RENDERER.main([
        "--repository", str(Path.cwd()), "--python", "/usr/bin/python3",
        "--captures", str(captures), "--output", str(output),
    ]) == 2
