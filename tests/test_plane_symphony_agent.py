from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("plane_symphony_agent", ROOT / "t480" / "plane_symphony_agent.py")
assert SPEC and SPEC.loader
agent = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(agent)


def test_status_record_is_minimal_and_does_not_retain_prompt(tmp_path: Path):
    status = tmp_path / "run.json"
    agent.write_status(status, "FAILED", "run-1")
    assert status.read_text(encoding="utf-8") == '{"run_id": "run-1", "status": "FAILED"}\n'


def test_worker_environment_is_fixed_and_does_not_inherit_plane_or_broker_values(monkeypatch):
    monkeypatch.setenv("FOREX_PLANE_TOKEN", "must-not-reach-worker")
    monkeypatch.setenv("MT5_PATH", "must-not-reach-worker")
    environment = agent.worker_environment(Path("/home/worker"))
    assert environment == {
        "HOME": "/home/worker", "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8",
        "PATH": "/home/worker/.local/bin:/usr/local/bin:/usr/bin:/bin",
    }
