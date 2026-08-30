from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("forex_ptr", ROOT / "scripts" / "ptr.py")
assert SPEC and SPEC.loader
ptr = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ptr)


def test_ptr_launches_one_fresh_read_only_codex_review() -> None:
    observed: list[str] = []

    def fake_run(command: list[str], **kwargs: object) -> SimpleNamespace:
        observed.extend(command)
        assert "Forex Reviewer" in str(kwargs["input"])
        output_index = command.index("--output-last-message") + 1
        Path(command[output_index]).write_text("Outcome: READY\n", encoding="utf-8")
        return SimpleNamespace(returncode=0)

    with patch.object(ptr.shutil, "which", return_value="/usr/bin/codex"), patch.object(
        ptr.subprocess, "run", side_effect=fake_run
    ):
        assert ptr.main() == 0

    assert observed[0:4] == ["codex", "exec", "--sandbox", "read-only"]
    assert "--ephemeral" in observed
    assert "--output-last-message" in observed
    assert "--cd" in observed
