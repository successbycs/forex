from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

from forex.delivery_harness import harness_status


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/delivery_harness_status.py"


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _inputs() -> tuple[dict, dict, dict, dict]:
    return (
        _json(ROOT / "docs/milestones/active-delivery-tasks.json"),
        _json(ROOT / "project_state.json"),
        _json(ROOT / "milestone_registry.json"),
        _json(ROOT / "runs/run_history.json"),
    )


def test_reports_task_metadata_formal_evidence_blockers_and_no_authority():
    plan, state, registry, history = _inputs()
    # Exercise the no-actionable-task case without depending on today's A1
    # execution status in the living task metadata.
    next(task for task in plan["tasks"] if task["id"] == "A1")["state"] = "BLOCKED_EXTERNAL_OBSERVATION"
    report = harness_status(task_plan=plan, state=state, registry=registry, history=history)
    assert report["execution_authority"] is False and report["read_only"] is True
    assert report["active_task"]["task_id"] == "M29"
    assert report["active_task"]["task_kind"] == "FORMAL_MILESTONE"
    assert report["demonstrated_result"]["formal_milestone_status"] == "BLOCKED"
    assert report["demonstrated_result"]["recorded_evidence_count"] == 0
    assert any(item.get("task_id") == "H5" and item["state"] == "BLOCKED_EXTERNAL_PLANE" for item in report["blockers"])
    assert any(item.get("task_id") == "A1" and item["state"] == "BLOCKED_EXTERNAL_OBSERVATION" for item in report["blockers"])
    assert report["next_action"]["state"] == "NO_ACTIVE_DELIVERY_TASK"
    assert report["unsupported_completion_claims"] == []


def test_actionable_a1_is_selected_despite_parked_plane_and_formal_proof():
    plan, state, registry, history = _inputs()
    next(task for task in plan["tasks"] if task["id"] == "A1")["state"] = "IN_PROGRESS"
    report = harness_status(task_plan=plan, state=state, registry=registry, history=history)
    assert report["active_task"]["task_id"] == "A1"
    assert report["next_action"]["state"] == "ACTIVE_TASK"
    assert report["demonstrated_result"]["formal_milestone_status"] == "BLOCKED"
    assert report["execution_authority"] is False


def test_canonical_active_plan_contains_harness_and_abc_tasks_and_parks_plane_h5():
    plan, _, _, _ = _inputs()
    assert plan["active_sequence"] == [
        "H1", "H2", "H3", "H4", "H5", "A1", "A2", "A3", "B1", "B2", "B3", "C1", "C2", "C3",
    ]
    by_id = {task["id"]: task for task in plan["tasks"]}
    assert by_id["H5"]["state"] == "BLOCKED_EXTERNAL_PLANE"
    assert all(task["formal_milestone"] == "M29" and task["execution_authority"] is False
               for task in plan["tasks"])
    assert all({"owned_paths", "acceptance_commands", "acceptance_results", "review_disposition", "evidence_class"} <= set(task)
               for task in plan["tasks"])
    assert {"H5", "A1"} == {task["id"] for task in plan["tasks"] if "symphony" in task}


def test_task_plan_refuses_unsafe_symphony_operation_policy():
    plan, _, _, _ = _inputs()
    broken = copy.deepcopy(plan)
    next(task for task in broken["tasks"] if task["id"] == "H5")["symphony"]["allowed_external_operations"] = ["mt5_demo_order"]
    with pytest.raises(ValueError, match="Symphony operation policy is unsafe"):
        harness_status(task_plan=broken, state=_inputs()[1], registry=_inputs()[2], history=_inputs()[3])


def test_refuses_an_active_task_with_an_unmet_prerequisite():
    plan, state, registry, history = _inputs()
    broken_plan = copy.deepcopy(plan)
    broken_plan["tasks"][0]["state"] = "PENDING"
    broken_plan["tasks"][5]["state"] = "PENDING"
    broken_plan["tasks"][1]["state"] = "IN_REVIEW"
    with pytest.raises(ValueError, match="unmet prerequisite"):
        harness_status(task_plan=broken_plan, state=state, registry=registry, history=history)


def test_detects_task_plan_mismatch_and_unsupported_completion_claim_without_repairing_it():
    plan, state, registry, history = _inputs()
    broken_plan = copy.deepcopy(plan)
    broken_plan["tasks"][0]["formal_milestone"] = "M999"
    broken_state = copy.deepcopy(state)
    broken_state["milestones"]["M29"]["status"] = "PROVEN"
    broken_state["milestones"]["M29"]["proven_at"] = None
    report = harness_status(task_plan=broken_plan, state=broken_state, registry=registry, history=history)
    assert report["task_plan_consistency"]["ok"] is False
    assert "TASK_PLAN_MISMATCH:H1:UNKNOWN_FORMAL_MILESTONE" in report["task_plan_consistency"]["issues"]
    assert "UNSUPPORTED_COMPLETION_CLAIM:M29:PROVEN_WITHOUT_PROVEN_AT" in report["unsupported_completion_claims"]


def test_cli_is_read_only_and_emits_machine_readable_harness_status(tmp_path):
    before = (ROOT / "project_state.json").read_bytes(), (ROOT / "runs/run_history.json").read_bytes()
    result = subprocess.run([sys.executable, str(SCRIPT)], text=True, capture_output=True, check=False)
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["schema_version"] == "forex.delivery-harness-status.v1"
    assert report["execution_authority"] is False
    assert before == ((ROOT / "project_state.json").read_bytes(), (ROOT / "runs/run_history.json").read_bytes())
