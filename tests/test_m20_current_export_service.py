from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "render_m20_assessment_export_service.py"
SPEC = importlib.util.spec_from_file_location("render_m20_assessment_export_service", SCRIPT)
RENDERER = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(RENDERER)


def test_renderer_produces_read_only_fixed_operation_units(tmp_path):
    assessments, output = tmp_path / "assessments", tmp_path / "output"
    assessments.mkdir()
    output.mkdir()
    assert RENDERER.main(["--repository", str(Path.cwd()), "--python", "/usr/bin/python3",
                          "--assessments", str(assessments), "--output", str(output)]) == 0
    service = (output / "forex-m20-assessment-export.service").read_text()
    timer = (output / "forex-m20-assessment-export.timer").read_text()
    assert "m20_spool_page_export.py" in service
    assert "NoNewPrivileges=true" in service and "TimeoutStartSec=45s" in service
    assert "/mnt/c/Windows/System32/WindowsPowerShell/v1.0" in service
    assert "OnUnitActiveSec=2min" in timer and "Persistent=false" in timer
    assert "order_send" not in service + timer


def test_renderer_refuses_relative_or_nonempty_output(tmp_path):
    assessments = tmp_path / "assessments"
    assessments.mkdir()
    output = tmp_path / "output"
    output.mkdir()
    (output / "existing").write_text("x")
    assert RENDERER.main(["--repository", str(Path.cwd()), "--python", "/usr/bin/python3",
                          "--assessments", str(assessments), "--output", str(output)]) == 2
