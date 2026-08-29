from __future__ import annotations

import json
from pathlib import Path
import shutil
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from forex.milestones import MilestoneStore, configuration_fingerprint, sha256_file, utc_now
from forex.review_handoff import (
    MAX_REVIEW_CYCLES,
    ReviewHandoffError,
    create_request,
    record_result,
    request_root,
    validate_result,
)
from forex.review_dispatcher import dispatch


ROOT = Path(__file__).resolve().parents[1]
REVISION = "a" * 40


def _root(tmp_path: Path) -> Path:
    state = json.loads((ROOT / "project_state.json").read_text(encoding="utf-8"))
    for relative in ("milestone_registry.json", "project_state.json", "runs/run_history.json", *state["governed_configuration_paths"]):
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, target)
    shutil.copytree(ROOT / "config" / "schemas", tmp_path / "config" / "schemas")
    state_path = tmp_path / "project_state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    m2 = state["milestones"]["M2"]
    m2.update(
        {
            "status": "AWAITING_REAL_WORLD_PROOF",
            "implementation_finished_at": utc_now(),
            "verification_passed_at": utc_now(),
            "verification": {
                "passed": True,
                "recorded_at": utc_now(),
                "git_revision": REVISION,
                "configuration_fingerprint": configuration_fingerprint(tmp_path, state),
                "commands": [],
            },
            "blockers": [],
        }
    )
    state["current_milestone"] = "M2"
    state["configuration_fingerprint"] = configuration_fingerprint(tmp_path, state)
    m2["verification"]["configuration_fingerprint"] = state["configuration_fingerprint"]
    state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    report = tmp_path / "docs" / "governance" / "fixture-builder-report.md"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text("# Fixture Builder report\n", encoding="utf-8")
    return tmp_path


def _request(root: Path) -> Path:
    with patch("forex.review_handoff.git_revision", return_value=REVISION), patch(
        "forex.review_handoff.material_worktree_changes", return_value=[]
    ):
        return create_request(root, "M2", root / "docs/governance/fixture-builder-report.md")


def _result(root: Path, request_path: Path, outcome: str) -> Path:
    request = json.loads(request_path.read_text(encoding="utf-8"))
    findings = []
    if outcome != "READY_FOR_EVIDENCE":
        findings = [
            {
                "finding_id": "GW-001",
                "severity": "HIGH",
                "title": "Fixture finding",
                "detail": "Synthetic test-only review finding.",
                "recommended_action": "Resolve in the fixture.",
            }
        ]
    result = {
        "schema_version": "forex.governance-review-result.v1",
        "request_id": request["request_id"],
        "milestone_id": "M2",
        "request_sha256": sha256_file(request_path),
        "git_revision": request["git_revision"],
        "configuration_fingerprint": request["configuration_fingerprint"],
        "milestone_contract_sha256": request["milestone_contract_sha256"],
        "review_cycle": request["review_cycle"],
        "reviewer": {"provider": "fixture", "model": "fixture", "session_id": "fresh-fixture-session"},
        "outcome": outcome,
        "summary": "Synthetic, read-only implementation review.",
        "required_findings": findings,
        "optional_observations": [],
        "attestations": {"read_only": True, "fresh_context": True, "did_not_modify_repository": True},
        "reviewed_at": utc_now(),
    }
    path = root / "fixture-result.json"
    path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return path


def _record(root: Path, request: Path, result: Path) -> Path:
    revision = json.loads(request.read_text(encoding="utf-8"))["git_revision"]
    with patch("forex.review_handoff.git_revision", return_value=revision), patch(
        "forex.review_handoff.material_worktree_changes", return_value=[]
    ):
        return record_result(root, request, result)


def test_ready_for_evidence_result_cannot_approve_or_prove_a_milestone(tmp_path: Path) -> None:
    root = _root(tmp_path)
    request = _request(root)
    result = _result(root, request, "READY_FOR_EVIDENCE")
    recorded = _record(root, request, result)

    state = MilestoneStore(root).state["milestones"]["M2"]
    assert recorded.is_file()
    assert state["status"] == "AWAITING_REAL_WORLD_PROOF"
    assert state["proven_at"] is None
    assert state["human_signoff"] is None
    assert state["review_workflow"]["outcome"] == "READY_FOR_EVIDENCE"


def test_changes_required_transitions_only_to_existing_needs_fix(tmp_path: Path) -> None:
    root = _root(tmp_path)
    request = _request(root)
    _record(root, request, _result(root, request, "CHANGES_REQUIRED"))

    state = MilestoneStore(root).state["milestones"]["M2"]
    assert state["status"] == "NEEDS_FIX"
    assert "GW-001" in state["blockers"][-1]["reason"]
    assert state["proven_at"] is None


def test_result_binding_mismatch_is_rejected(tmp_path: Path) -> None:
    root = _root(tmp_path)
    request = _request(root)
    result = _result(root, request, "READY_FOR_EVIDENCE")
    value = json.loads(result.read_text(encoding="utf-8"))
    value["git_revision"] = "b" * 40
    result.write_text(json.dumps(value), encoding="utf-8")

    with pytest.raises(ReviewHandoffError, match="binding mismatch"):
        validate_result(root, request, result)


def test_fourth_review_request_is_rejected(tmp_path: Path) -> None:
    root = _root(tmp_path)
    request_dir = request_root(root, "M2")
    request_dir.mkdir(parents=True)
    for cycle in range(1, MAX_REVIEW_CYCLES + 1):
        fixture = {
            "schema_version": "forex.governance-review-request.v1",
            "request_id": f"fixture-{cycle}",
            "milestone_id": "M2",
            "purpose": "IMPLEMENTATION_READINESS",
            "created_at": utc_now(),
            "git_revision": REVISION,
            "configuration_fingerprint": MilestoneStore(root).state["configuration_fingerprint"],
            "milestone_contract_sha256": "c" * 64,
            "verification_recorded_at": utc_now(),
            "builder_report_path": "docs/governance/fixture-builder-report.md",
            "builder_report_sha256": sha256_file(root / "docs/governance/fixture-builder-report.md"),
            "review_cycle": cycle,
        }
        (request_dir / f"fixture-{cycle}.request.json").write_text(json.dumps(fixture), encoding="utf-8")
    with patch("forex.review_handoff.git_revision", return_value=REVISION), patch(
        "forex.review_handoff.material_worktree_changes", return_value=[]
    ), pytest.raises(ReviewHandoffError, match="cycle cap"):
        create_request(root, "M2", root / "docs/governance/fixture-builder-report.md")


def test_dummy_review_fix_and_rereview_workflow_is_test_only(tmp_path: Path) -> None:
    root = _root(tmp_path)
    first_request = _request(root)
    _record(root, first_request, _result(root, first_request, "CHANGES_REQUIRED"))
    state_path = root / "project_state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    m2 = state["milestones"]["M2"]
    m2["status"] = "AWAITING_REAL_WORLD_PROOF"
    m2["blockers"] = []
    m2["implementation_finished_at"] = utc_now()
    m2["verification"].update({"git_revision": "b" * 40, "recorded_at": utc_now()})
    state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    with patch("forex.review_handoff.git_revision", return_value="b" * 40), patch(
        "forex.review_handoff.material_worktree_changes", return_value=[]
    ):
        second_request = create_request(root, "M2", root / "docs/governance/fixture-builder-report.md")
    _record(root, second_request, _result(root, second_request, "READY_FOR_EVIDENCE"))

    final = MilestoneStore(root).state["milestones"]["M2"]
    assert final["review_workflow"]["cycle"] == 2
    assert final["review_workflow"]["outcome"] == "READY_FOR_EVIDENCE"
    assert final["status"] == "AWAITING_REAL_WORLD_PROOF"
    assert final["proven_at"] is None


def test_dispatcher_uses_fixed_read_only_codex_invocation(tmp_path: Path) -> None:
    root = _root(tmp_path)
    request = _request(root)
    fixture_result = _result(root, request, "READY_FOR_EVIDENCE")
    observed: list[str] = []

    def fake_run(command: list[str], **_: object) -> SimpleNamespace:
        observed.extend(command)
        output = Path(command[command.index("--output-last-message") + 1])
        output.write_text(fixture_result.read_text(encoding="utf-8"), encoding="utf-8")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    with patch("forex.review_dispatcher.shutil.which", return_value="/usr/bin/codex"), patch(
        "forex.review_dispatcher.subprocess.run", side_effect=fake_run
    ), patch("forex.review_handoff.git_revision", return_value=REVISION), patch(
        "forex.review_handoff.material_worktree_changes", return_value=[]
    ):
        recorded = dispatch(root, request)

    assert recorded.is_file()
    assert observed[0:4] == ["codex", "exec", "--sandbox", "read-only"]
    assert "--ephemeral" in observed
