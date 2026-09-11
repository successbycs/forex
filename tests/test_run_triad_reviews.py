from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "run_triad_reviews.py"


def _runner_module():
    spec = importlib.util.spec_from_file_location("run_triad_reviews", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _cycle(root: Path) -> Path:
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, check=True, text=True, capture_output=True
    ).stdout.strip()
    manifest = root / "runs/evidence/M20/20260911T084133Z/manifest.json"
    cycle = root / "runs/triad/test-runner-snapshot"
    (cycle / "packets").mkdir(parents=True)
    (cycle / "templates").mkdir()
    (cycle / "submissions").mkdir()
    (cycle / "packets/ai_engineer.md").write_text("Bound packet\n", encoding="utf-8")
    (cycle / "templates/ai_engineer.json").write_text("{}\n", encoding="utf-8")
    (cycle / "request.json").write_text(
        json.dumps(
            {
                "git_revision": revision,
                "evidence_manifest_path": str(manifest.relative_to(root)),
                "evidence_manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
            }
        ),
        encoding="utf-8",
    )
    return cycle


def test_reviewer_uses_clean_bound_snapshot_and_compact_failure_logs(monkeypatch) -> None:
    runner = _runner_module()
    cycle = _cycle(ROOT)
    real_run = runner.subprocess.run
    calls: list[tuple[list[str], Path]] = []
    snapshot: dict[str, bool] = {}

    def fake_run(command, **kwargs):
        if command[0] == "git":
            return real_run(command, **kwargs)
        calls.append((command, kwargs["cwd"]))
        cwd = kwargs["cwd"]
        snapshot["no_git"] = not (cwd / ".git").exists()
        snapshot["handoff"] = (cwd / ".triad-review/request.json").is_file()
        snapshot["evidence"] = (cwd / "runs/evidence/M20/20260911T084133Z/manifest.json").is_file()
        snapshot["current_state"] = (cwd / "project_state.json").read_bytes() == (ROOT / "project_state.json").read_bytes()
        snapshot["current_history"] = (cwd / "runs/run_history.json").read_bytes() == (ROOT / "runs/run_history.json").read_bytes()
        return subprocess.CompletedProcess(command, 1, "ordinary output", "x" * 10000)

    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    try:
        ok, events = runner.review_role(cycle, "AI_ENGINEER", 1)
        assert not ok
        command, cwd = calls[0]
        assert command[command.index("-C") + 1] == str(cwd)
        assert cwd != ROOT
        assert snapshot == {"no_git": True, "handoff": True, "evidence": True, "current_state": True, "current_history": True}
        assert events[0]["stderr"]["bytes"] == 10000
        assert "x" * 1000 not in json.dumps(events[0])
        assert Path(ROOT / events[0]["stderr"]["path"]).is_file()
        assert not cwd.exists()
    finally:
        shutil.rmtree(cycle)


def test_attempt_is_validated_only_after_canonical_staging(monkeypatch) -> None:
    runner = _runner_module()
    cycle = _cycle(ROOT)
    real_run = runner.subprocess.run
    validated: list[Path] = []

    def fake_subprocess(command, **kwargs):
        if command[0] == "git":
            return real_run(command, **kwargs)
        output = Path(command[command.index("-o") + 1])
        output.write_text("{}\n", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, "", "")

    def fake_validation(argv):
        review = Path(argv[argv.index("--review") + 1])
        validated.append(review)
        assert review.name == "ai_engineer.json"
        assert review.is_file()
        return subprocess.CompletedProcess(argv, 0, "valid", "")

    monkeypatch.setattr(runner.subprocess, "run", fake_subprocess)
    monkeypatch.setattr(runner, "run", fake_validation)
    try:
        ok, events = runner.review_role(cycle, "AI_ENGINEER", 1)
        assert ok
        assert len(validated) == 1
        assert events[0]["validation"] == "valid"
        assert (cycle / "submissions/ai_engineer.json").is_file()
    finally:
        shutil.rmtree(cycle)
