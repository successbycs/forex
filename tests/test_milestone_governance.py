from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import subprocess

import pytest

from forex.milestones import (
    GovernanceError,
    MilestoneStore,
    configuration_fingerprint,
    _gate_errors,
    git_revision,
    main,
    utc_now,
    validate_evidence_bundle,
    validate_registry,
)


ROOT = Path(__file__).resolve().parents[1]


def _copy_governance(tmp_path: Path) -> Path:
    source_state = json.loads((ROOT / "project_state.json").read_text(encoding="utf-8"))
    for relative in (
        "milestone_registry.json",
        "project_state.json",
        "runs/run_history.json",
        *source_state["governed_configuration_paths"],
    ):
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, destination)
    schemas = tmp_path / "config" / "schemas"
    shutil.copytree(ROOT / "config" / "schemas", schemas)
    state_path = tmp_path / "project_state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    m0 = state["milestones"]["M0"]
    m0.update(
        {
            "status": "READY",
            "started_at": None,
            "implementation_finished_at": None,
            "verification_passed_at": None,
            "real_world_proof_captured_at": None,
            "human_signed_off_at": None,
            "first_proven_at": None,
            "proven_at": None,
            "last_validated_at": None,
            "checks": {},
            "evidence": [],
            "verification": None,
            "human_signoff": None,
            "blockers": [],
        }
    )
    m0["work_packages"] = {
        "M0.1": {"status": "IN_PROGRESS", "started_at": utc_now(), "verified_at": None},
        **{
            f"M0.{index}": {"status": "PLANNED", "started_at": None, "verified_at": None}
            for index in range(2, 8)
        },
    }
    state["configuration_fingerprint"] = configuration_fingerprint(tmp_path, state)
    state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    return tmp_path


def test_registry_defines_contiguous_real_world_transition_contracts() -> None:
    registry = json.loads((ROOT / "milestone_registry.json").read_text(encoding="utf-8"))
    validate_registry(registry)
    assert [item["milestone_id"] for item in registry["milestones"]] == [f"M{i}" for i in range(33)]
    assert all(item["real_world_proof"]["real_world_execution"] is True for item in registry["milestones"])
    assert all(
        item["real_world_proof"]["provenance_assurance"] == "SELF_ATTESTED_INTEGRITY"
        for item in registry["milestones"]
    )
    assert all("status" not in item for item in registry["milestones"])


def test_repository_governance_files_validate() -> None:
    MilestoneStore(ROOT).validate()


def test_closeout_refuses_a_proof_free_milestone(tmp_path: Path) -> None:
    root = _copy_governance(tmp_path)
    assert main(["--root", str(root), "start", "--id", "M0"]) == 0
    assert main(["--root", str(root), "prove", "--id", "M0"]) == 2
    state = json.loads((root / "project_state.json").read_text(encoding="utf-8"))
    assert state["milestones"]["M0"]["status"] == "IN_PROGRESS"
    assert state["milestones"]["M0"]["proven_at"] is None


def test_closeout_reports_current_material_worktree_changes(tmp_path: Path) -> None:
    root = _copy_governance(tmp_path)
    source = root / "implementation.py"
    source.write_text("BOUND = True\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Forex Test",
            "-c",
            "user.email=forex-test@example.invalid",
            "commit",
            "-qm",
            "bound fixture",
        ],
        cwd=root,
        check=True,
    )
    source.write_text("BOUND = False\n", encoding="utf-8")
    errors = _gate_errors(MilestoneStore(root), "M0")
    assert any("current worktree has material changes" in error for error in errors)
    assert any("implementation.py" in error for error in errors)


def test_dependency_prevents_starting_a_future_milestone(tmp_path: Path) -> None:
    root = _copy_governance(tmp_path)
    assert main(["--root", str(root), "ready", "--id", "M1"]) == 2
    state = json.loads((root / "project_state.json").read_text(encoding="utf-8"))
    assert state["milestones"]["M1"]["status"] == "PLANNED"


def test_evidence_hash_tampering_is_rejected(tmp_path: Path) -> None:
    root = _copy_governance(tmp_path)
    store = MilestoneStore(root)
    bundle = root / "runs" / "evidence" / "M0" / "test-run"
    bundle.mkdir(parents=True)
    raw = bundle / "summary.txt"
    raw.write_text("FOREX_M0_PROOF_OK\n", encoding="utf-8")
    manifest = {
        "schema_version": "1.0.0",
        "milestone_id": "M0",
        "captured_at": utc_now(),
        "git_revision": git_revision(root),
        "dirty_worktree": True,
        "configuration_fingerprint": configuration_fingerprint(root, store.state),
        "surface": "fresh temporary Python environment",
        "operation": "negative-control fixture",
        "expected_result": "A retained marker with a valid hash.",
        "observed_result": "Fixture passed before tampering.",
        "exit_code": 0,
        "redactions": [],
        "summary": "Inspectable negative-control evidence.",
        "artifacts": [{"path": "summary.txt", "sha256": hashlib.sha256(raw.read_bytes()).hexdigest()}],
    }
    manifest_path = bundle / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    validate_evidence_bundle(root, store.state, store.milestone("M0"), manifest_path, run_external_verifier=False)
    raw.write_text("tampered\n", encoding="utf-8")
    with pytest.raises(GovernanceError, match="hash mismatch"):
        validate_evidence_bundle(root, store.state, store.milestone("M0"), manifest_path, run_external_verifier=False)


def test_signoff_requires_explicit_review_confirmations(tmp_path: Path) -> None:
    root = _copy_governance(tmp_path)
    result = main(
        [
            "--root",
            str(root),
            "signoff",
            "--id",
            "M0",
            "--operator",
            "test-operator",
            "--decision",
            "approve",
            "--note",
            "fixture",
        ]
    )
    assert result == 2
    state = json.loads((root / "project_state.json").read_text(encoding="utf-8"))
    assert state["milestones"]["M0"]["human_signoff"] is None


def test_target_date_is_not_a_completion_timestamp() -> None:
    registry = json.loads((ROOT / "milestone_registry.json").read_text(encoding="utf-8"))
    state = json.loads((ROOT / "project_state.json").read_text(encoding="utf-8"))
    assert all(item["target_date_owner"] == "HUMAN_OPERATOR" for item in registry["milestones"])
    assert state["milestones"]["M0"]["proven_at"] is None


def test_json_schema_validation_rejects_registry_shape_drift(tmp_path: Path) -> None:
    root = _copy_governance(tmp_path)
    registry_path = root / "milestone_registry.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    registry["unexpected"] = True
    registry_path.write_text(json.dumps(registry, indent=2) + "\n", encoding="utf-8")
    with pytest.raises(GovernanceError, match="JSON Schema"):
        MilestoneStore(root).validate()


def test_work_package_dependency_is_enforced(tmp_path: Path) -> None:
    root = _copy_governance(tmp_path)
    assert main(["--root", str(root), "start-package", "--id", "M0.2"]) == 2
    state = json.loads((root / "project_state.json").read_text(encoding="utf-8"))
    assert state["milestones"]["M0"]["work_packages"]["M0.2"]["status"] == "PLANNED"


def test_interrupted_two_file_save_is_recovered(tmp_path: Path) -> None:
    root = _copy_governance(tmp_path)
    state = json.loads((root / "project_state.json").read_text(encoding="utf-8"))
    history = json.loads((root / "runs" / "run_history.json").read_text(encoding="utf-8"))
    state["milestones"]["M0"]["status"] = "BLOCKED"
    history["events"].append(
        {
            "event_id": f"E{len(history['events']) + 1:06d}",
            "timestamp": utc_now(),
            "milestone_id": "M0",
            "action": "RECOVERY_FIXTURE",
            "detail": {},
        }
    )
    journal = {
        "schema_version": "1.0.0",
        "created_at": utc_now(),
        "state": state,
        "history": history,
    }
    journal_path = root / "runs" / ".governance-transaction.json"
    journal_path.write_text(json.dumps(journal, indent=2) + "\n", encoding="utf-8")
    recovered = MilestoneStore(root)
    assert recovered.state["milestones"]["M0"]["status"] == "BLOCKED"
    assert recovered.history["events"][-1]["action"] == "RECOVERY_FIXTURE"
    assert not journal_path.exists()
