from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "m20_spool_page_export.py"
SPEC = importlib.util.spec_from_file_location("m20_spool_page_export", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def test_nonzero_fixed_operation_is_a_safe_structured_refusal(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(MODULE.subprocess, "run", lambda *args, **kwargs: subprocess.CompletedProcess(args, 1, b"secret raw", b""))
    assert MODULE.main(["--capture-root", str(tmp_path)]) == 2
    captured = capsys.readouterr()
    assert not captured.out
    error = json.loads(captured.err)
    assert error == {"schema_version": "forex.m20.spool-page-export-error.v1", "state": "REFUSED",
                     "reason": "FIXED_OPERATION_NONZERO", "execution_authority": False}


def test_timeout_is_a_safe_structured_refusal(tmp_path, monkeypatch, capsys):
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(args[0], kwargs["timeout"])
    monkeypatch.setattr(MODULE.subprocess, "run", timeout)
    assert MODULE.main(["--capture-root", str(tmp_path)]) == 2
    captured = capsys.readouterr()
    assert not captured.out
    error = json.loads(captured.err)
    assert error["reason"] == "FIXED_OPERATION_TIMEOUT"
    assert "secret" not in json.dumps(error)
