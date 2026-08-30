from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("forex_ptr", ROOT / "scripts" / "ptr.py")
assert SPEC and SPEC.loader
ptr = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ptr)


def _cycle(root: Path, milestone_id: str = "M2") -> Path:
    cycle = root / "runs" / "triad" / milestone_id / f"{milestone_id}-fixture"
    (cycle / "packets").mkdir(parents=True)
    (cycle / "templates").mkdir()
    (cycle / "request.json").write_text("{}", encoding="utf-8")
    (cycle / "packets" / "solution_architect.md").write_text("packet", encoding="utf-8")
    (cycle / "templates" / "solution_architect.json").write_text("{}", encoding="utf-8")
    return cycle


def test_ptr_emits_one_bound_role_prompt(tmp_path: Path, monkeypatch, capsys) -> None:
    (tmp_path / "project_state.json").write_text(
        json.dumps({"current_milestone": "M2"}), encoding="utf-8"
    )
    _cycle(tmp_path)
    monkeypatch.setattr(ptr, "ROOT", tmp_path)

    assert ptr.main(["--role", "solution_architect"]) == 0
    output = capsys.readouterr().out

    assert "Forex Solution Architect Reviewer" in output
    assert "M2-fixture/request.json" in output
    assert "M2-fixture/packets/solution_architect.md" in output
    assert "M2-fixture/submissions/solution_architect.json" in output
    assert "read other reviewers' submissions" in output


def test_ptr_requires_a_prepared_cycle(tmp_path: Path, monkeypatch, capsys) -> None:
    (tmp_path / "project_state.json").write_text(
        json.dumps({"current_milestone": "M2"}), encoding="utf-8"
    )
    monkeypatch.setattr(ptr, "ROOT", tmp_path)

    assert ptr.main(["--role", "solution_architect"]) == 2
    assert "no prepared Triad cycle" in capsys.readouterr().err


def test_sequence_skips_valid_submissions_and_stops_on_first_failure(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    cycle = _cycle(tmp_path)
    monkeypatch.setattr(ptr, "ROOT", tmp_path)
    seen: list[str] = []

    def already_valid(_: Path, role: str) -> bool:
        return role == "ai_engineer"

    def run_once(_: Path, role: str, __: int) -> bool:
        seen.append(role)
        return role == "solution_architect"

    monkeypatch.setattr(ptr, "_submission_is_valid", already_valid)
    monkeypatch.setattr(ptr, "_run_role", run_once)

    assert ptr.run_sequence(cycle, 30) == 1
    output = capsys.readouterr()
    assert "PTR_SKIP_VALID role=AI Engineer" in output.out
    assert seen == ["solution_architect", "senior_software_developer"]
    assert "PTR_STOPPED next_role=Senior Software Developer" in output.err
