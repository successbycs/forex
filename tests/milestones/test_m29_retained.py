"""Negative controls for the bounded historical M29 acceptance path."""

import copy
import json
from pathlib import Path
import shutil

import pytest

from forex.milestones import (
    GovernanceError, MilestoneStore, _gate_errors, configuration_fingerprint,
    sha256_file, validate_evidence_bundle, validate_registry,
)

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def retained(tmp_path):
    store = MilestoneStore(ROOT)
    milestone = copy.deepcopy(store.milestone("M29"))
    state = copy.deepcopy(store.state)
    policy = milestone["retained_evidence_policy"]
    for relative in state["governed_configuration_paths"]:
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, destination)
    shutil.copytree(ROOT / "config/schemas", tmp_path / "config/schemas")
    for name in policy["runtime_payload_sha256"]:
        relative = "t480/" + name.replace(".payload", ".py")
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, destination)
    bundle = tmp_path / Path(policy["manifest_path"]).parent
    bundle.mkdir(parents=True)
    fp = configuration_fingerprint(tmp_path, state)
    policy["configuration_fingerprint"] = fp
    account = {"server": "GOMarketsMU-Demo", "currency": "AUD", "position_observation": "AVAILABLE", "open_positions": 0}
    binding = {"application_revision": policy["drill_revision"], "configuration_fingerprint": fp, "payload_sha256": policy["runtime_payload_sha256"]}
    snapshot = {"valid": True, "account": account, "deployment": binding, "heartbeat": {"valid": True, "state": "MAINTENANCE_HOLD"}, "unresolved_execution": {"state": "CLEAR"}}
    observations = [
        ("m29-continuity.json", "m20_listener_continuity_status", {"observation": "AVAILABLE", "record": {"state": "PASS", "handoff": {"state": "RECOVERED"}, "baseline": snapshot, "postflight": snapshot, "release_id": "release"}}),
        ("postflight-listener.json", "m20_listener_status", {"running": True, "state": "MAINTENANCE_HOLD", "release_id": "release", "monitor": {"state": "IDLE"}, "protection_observation": "LAST_KNOWN_UNVERIFIED"}),
        ("postflight-account.json", "m20_demo_account_liquidity", account),
        ("postflight-diagnostics.json", "m20_listener_diagnostics", {"maintenance_hold_present": True, "logon_type": "S4U", "deployment_binding": {**binding, "observation": "VALID", "application_revision": policy["diagnostics_revision"]}}),
    ]
    for index, (name, operation, value) in enumerate(observations):
        envelope = {"operation": operation, "ok": True, "result": {"ok": True, "exit_code": 0, "finished_at": f"2020-01-01T00:00:0{index}Z", "stdout": json.dumps(value)}}
        (bundle / name).write_text(json.dumps(envelope))
    for name, value in {"tests.txt": "tests passed", "governance.txt": "valid", "revision.txt": policy["collector_revision"], "summary.txt": "FOREX_M29_PROOF_OK"}.items():
        (bundle / name).write_text(value)
    manifest = {"schema_version": "1.0.0", "milestone_id": "M29", "captured_at": "2020-01-01T00:00:04Z", "git_revision": policy["collector_revision"], "dirty_worktree": False, "configuration_fingerprint": fp, "surface": milestone["real_world_proof"]["surface"], "operation": "synthetic held recovery test", "expected_result": "recovery", "observed_result": "FOREX_M29_PROOF_OK", "exit_code": 0, "redactions": ["Synthetic fixture"], "summary": "FOREX_M29_PROOF_OK", "artifacts": [{"path": path.name, "sha256": sha256_file(path)} for path in sorted(bundle.iterdir())]}
    manifest_path = bundle / "manifest.json"
    manifest_path.write_text(json.dumps(manifest))
    policy["manifest_sha256"] = sha256_file(manifest_path)
    return tmp_path, state, milestone, manifest_path


def test_pinned_historical_bundle_passes_without_running_later_verifier(retained):
    root, state, milestone, manifest = retained
    milestone["real_world_proof"]["verifier_command"] = ["must-not-be-executed"]
    assert validate_evidence_bundle(root, state, milestone, manifest)["observed_result"] == "FOREX_M29_PROOF_OK"


@pytest.mark.parametrize("change, message", [
    ("artifact", "hash mismatch"), ("manifest", "manifest hash"),
    ("payload", "current runtime payload changed"), ("configuration", "configuration fingerprint"),
    ("path", "manifest path"), ("policy_payload", "runtime payload hashes"),
    ("policy_config", "configuration mismatch"), ("collector", "collector revision"),
    ("drill", "runtime revision"), ("diagnostics", "runtime revision"),
    ("extra_field", "invalid M29 retained evidence policy"),
])
def test_retained_policy_fails_closed(retained, change, message):
    root, state, milestone, manifest = retained
    policy = milestone["retained_evidence_policy"]
    if change == "artifact":
        (manifest.parent / "summary.txt").write_text("tampered")
    elif change == "manifest":
        manifest.write_text(manifest.read_text() + "\n")
    elif change == "payload":
        (root / "t480/m20_demo_listener_service.py").write_text("changed")
    elif change == "configuration":
        with (root / state["governed_configuration_paths"][0]).open("a") as handle:
            handle.write("\n# changed\n")
    elif change == "path":
        other = manifest.parent.parent / "other"
        shutil.copytree(manifest.parent, other)
        manifest = other / "manifest.json"
    elif change == "policy_payload":
        policy["runtime_payload_sha256"]["m20_demo_listener_service.payload"] = "sha256:" + "0" * 64
    elif change == "policy_config":
        policy["configuration_fingerprint"] = "sha256:" + "0" * 64
    elif change in {"collector", "drill", "diagnostics"}:
        policy[change + "_revision"] = "0" * 40
    else:
        policy["skip_checks"] = True
    with pytest.raises(GovernanceError, match=message):
        validate_evidence_bundle(root, state, milestone, manifest)


def test_policy_is_rejected_for_m30(retained):
    _, _, milestone, _ = retained
    registry = copy.deepcopy(MilestoneStore(ROOT).registry)
    registry["milestones"][30]["retained_evidence_policy"] = milestone["retained_evidence_policy"]
    with pytest.raises(GovernanceError, match="only for M29"):
        validate_registry(registry)


def test_unpinned_m29_still_requires_fresh_evidence(retained):
    root, state, milestone, manifest = retained
    del milestone["retained_evidence_policy"]
    with pytest.raises(GovernanceError, match="freshness window"):
        validate_evidence_bundle(root, state, milestone, manifest)


def test_retained_approval_survives_local_verification_but_requires_exact_bundle(retained, monkeypatch):
    root, state, milestone, manifest = retained
    store = MilestoneStore(ROOT)
    store.root = root
    store.state = state
    store.registry = copy.deepcopy(store.registry)
    store.registry["milestones"][29] = milestone
    item = state["milestones"]["M29"]
    item["evidence"][-1]["manifest_sha256"] = sha256_file(manifest)
    item["human_signoff"]["evidence_manifest_sha256"] = sha256_file(manifest)
    item["verification"].update(passed=True, git_revision="new-local-revision", recorded_at="2026-09-16T05:00:00Z")
    monkeypatch.setattr("forex.milestones.git_revision", lambda _: "new-local-revision")
    monkeypatch.setattr("forex.milestones.material_worktree_changes", lambda _: [])
    errors = _gate_errors(store, "M29")
    assert not any("human sign-off" in error for error in errors)
    item["human_signoff"]["evidence_manifest_sha256"] = "0" * 64
    assert "human sign-off is not tied to the current evidence bundle" in _gate_errors(store, "M29")
    item["verification"]["passed"] = False
    assert "milestone verification has not passed" in _gate_errors(store, "M29")
