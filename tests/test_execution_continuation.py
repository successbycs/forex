from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

from forex.execution_continuation import ExecutionWorkError, evaluate_work_plan, validate_work_plan
from forex.execution_selection import ExecutionSelectionError, load_active_execution_work


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/check_execution_continuation.py"


def _item(item_id: str, state: str, *, requires: list[str] | None = None, evidence: list[str] | None = None, blocker: dict | None = None) -> dict:
    return {"id": item_id, "title": item_id + " title", "state": state, "requires": requires or [], "evidence": evidence or [], "blocker": blocker}


def _blocked(source: str = "platform") -> dict:
    return {"source": source, "reason": "unavailable", "unblock_action": "restore access"}


def _plan(items: list[dict]) -> dict:
    return {"schema_version": "forex.execution-work.v1", "task_id": "A1", "authorization": "Chris authorized local implementation scope", "markdown_plan": "docs/plans/example.md", "items": items}


def _write(path: Path, value: dict) -> bytes:
    raw = json.dumps(value, separators=(",", ":")).encode()
    path.write_bytes(raw)
    return raw


def _invoke(path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(SCRIPT), "--work-plan", str(path)], cwd=ROOT, capture_output=True, text=True, check=False)


def test_independent_preparation_continues_while_deploy_is_blocked():
    plan = _plan([
        _item("deploy", "BLOCKED", blocker=_blocked()),
        _item("prepare-review", "PENDING"),
        _item("dependent", "PENDING", requires=["deploy"]),
    ])
    result = evaluate_work_plan(plan, work_plan_sha256="sha256:" + "a" * 64)
    assert result["outcome"] == "CONTINUE"
    assert result["next_item"]["id"] == "prepare-review"
    assert result["stop_allowed"] is False
    assert result["execution_authority"] is False
    assert result["enforcement"] == "ADVISORY_REQUIRES_CALLER"


def test_known_blocked_dependency_returns_terminal_blocker():
    plan = _plan([_item("access", "BLOCKED", blocker=_blocked("n8n")), _item("deploy", "PENDING", requires=["access"])])
    result = evaluate_work_plan(plan, work_plan_sha256="sha256:" + "b" * 64)
    assert result["outcome"] == "BLOCKED"
    assert result["stop_allowed"] is True
    assert result["terminal_blockers"] == [{"id": "access", "title": "access title", "blocker": _blocked("n8n")}]


@pytest.mark.parametrize("plan", [
    _plan([]),
    _plan([_item("done", "DONE")]),
    _plan([_item("later", "PENDING", requires=["missing"])]),
    _plan([_item("first", "PENDING"), _item("second", "PENDING", requires=["first", "first"])]),
    _plan([_item("first", "PENDING"), _item("active", "IN_PROGRESS", requires=["first"])]),
])
def test_empty_dag_and_done_evidence_errors_are_rejected(plan: dict):
    with pytest.raises(ExecutionWorkError):
        validate_work_plan(plan)


def test_complete_plan_is_advisory_complete():
    result = evaluate_work_plan(_plan([_item("done", "DONE", evidence=["tests passed"])]), work_plan_sha256="sha256:" + "c" * 64)
    assert result["outcome"] == "COMPLETE"
    assert result["next_item"] is None


def test_cli_statuses_hash_and_read_only_input(tmp_path: Path):
    continuing = tmp_path / "continue.json"
    raw = _write(continuing, _plan([_item("prep", "PENDING")]))
    before = continuing.read_bytes()
    result = _invoke(continuing)
    assert result.returncode == 2
    assert continuing.read_bytes() == before

    blocked = tmp_path / "blocked.json"
    _write(blocked, _plan([_item("access", "BLOCKED", blocker=_blocked()), _item("deploy", "PENDING", requires=["access"])]))
    assert _invoke(blocked).returncode == 2

    complete = tmp_path / "complete.json"
    _write(complete, _plan([_item("done", "DONE", evidence=["proof"])]))
    assert _invoke(complete).returncode == 2


@pytest.mark.parametrize("raw", ["{", '{"schema_version":"forex.execution-work.v1","schema_version":"x"}', '{"schema_version":NaN}'])
def test_cli_refuses_malformed_duplicate_and_nonfinite_input(tmp_path: Path, raw: str):
    path = tmp_path / "bad.json"
    path.write_text(raw)
    result = _invoke(path)
    assert result.returncode == 2
    assert result.stdout == ""
    assert "Traceback" not in result.stderr


def test_cli_refuses_deeply_nested_json_without_ambiguous_continue_status(tmp_path: Path):
    path = tmp_path / "deep.json"
    path.write_text("[" * 10_000 + "0" + "]" * 10_000)
    result = _invoke(path)
    assert result.returncode == 2
    assert result.stdout == ""
    assert "Traceback" not in result.stderr


def test_active_selector_binds_h5_to_one_plan_below_docs_plans(tmp_path: Path):
    (tmp_path / "config").mkdir(); (tmp_path / "docs" / "plans").mkdir(parents=True)
    target = tmp_path / "docs" / "plans" / "h5.json"; target.write_text("{}")
    (tmp_path / "config" / "execution-continuation.json").write_text(
        '{"schema_version":"forex.active-execution-work.v1","task_id":"H5","work_plan":"docs/plans/h5.json"}'
    )
    with pytest.raises(ExecutionSelectionError, match="projection"):
        load_active_execution_work(tmp_path)
    (tmp_path / "config" / "execution-continuation.json").write_text(
        '{"schema_version":"forex.active-execution-work.v1","task_id":"H5","work_plan":"../outside.json"}'
    )
    with pytest.raises(ExecutionSelectionError, match="unsafe"):
        load_active_execution_work(tmp_path)
