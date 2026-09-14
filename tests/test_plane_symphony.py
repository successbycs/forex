from __future__ import annotations

import copy
from datetime import datetime, timezone
import json
from pathlib import Path

import pytest

from forex.plane_symphony import (
    Controller, ControllerConfig, PlaneSymphonyError, bind_fixed_operation, desired_plane_state,
    issue_payload, redact, transition_task_state, validate_task_catalog,
    validate_preflight_receipt, _canonical_digest, _test_catalog, load_canonical_task_catalog,
)


def policy(task_id: str, *, eligible: bool = True, ops: list[str] | None = None, preflights: list[str] | None = None) -> dict:
    defaults = {"H5": (["plane_board_bootstrap"], ["plane_symphony_preflight"]),
                "A1": (["a1_retention_deploy"], ["a1_retention_preflight"])}
    default_ops, default_preflights = defaults[task_id]
    return {"allowed_external_operations": ops or default_ops, "preflight_commands": preflights or default_preflights,
            "review_route": "TERRA_IMPLEMENTATION_ASTRA_REVIEW", "eligible": eligible}


def catalog(h5="READY", a1="READY") -> dict:
    return {"schema_version": "forex.active-delivery-tasks.v2", "purpose": "test", "active_sequence": ["H5", "A1"], "execution_authority": False, "tasks": [
        {"id": "H5", "title": "H5 board", "state": h5, "requires": [], "review_disposition": "NOT_STARTED", "acceptance_results": [], "symphony": policy("H5")},
        {"id": "A1", "title": "A1 data", "state": a1, "requires": ["H5"], "review_disposition": "NOT_STARTED", "acceptance_results": [], "symphony": policy("A1")},
    ]}


class FakePlane:
    def __init__(self): self.issues, self.calls = {}, []
    def find_issue(self, external_id, expected_name):
        issue = self.issues.get(external_id)
        if issue is not None and issue.get("name") != expected_name:
            raise RuntimeError("unexpected test task name")
        return issue
    def create_issue(self, payload):
        self.calls.append(("create", copy.deepcopy(payload))); issue = {**payload, "id": str(len(self.issues) + 1)}; self.issues[payload["external_id"]] = issue; return issue
    def update_issue(self, issue_id, payload):
        self.calls.append(("update", copy.deepcopy(payload))); issue = {**payload, "id": issue_id}; self.issues[payload["external_id"]] = issue; return issue


class FakeRunner:
    def __init__(self, *, preflight=None, fail_start=False, lifecycle="RUNNING", fail_inspect=False):
        self.calls, self.preflight_result, self.fail_start, self.lifecycle, self.inspect_calls, self.fail_inspect = [], preflight, fail_start, lifecycle, [], fail_inspect
    def preflight(self, *, task_id, commands, baseline_revision, configuration_fingerprint):
        if self.preflight_result is not None: return self.preflight_result
        receipt = {"task_id": task_id, "commands": list(commands), "baseline_revision": baseline_revision,
                   "configuration_fingerprint": configuration_fingerprint, "status": "PASS",
                   "observed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"), "content": {"capacity": "ok"}}
        return {**receipt, "receipt_sha256": _canonical_digest(receipt)}
    def start(self, **kwargs):
        if self.fail_start: raise RuntimeError("runner unavailable")
        self.calls.append(kwargs); return f"run-{len(self.calls)}"
    def inspect(self, *, task_id, idempotency_key, agent_run_id):
        if self.fail_inspect: raise RuntimeError("inspection unavailable")
        self.inspect_calls.append((task_id, idempotency_key, agent_run_id))
        return {"task_id": task_id, "idempotency_key": idempotency_key, "agent_run_id": agent_run_id, "status": self.lifecycle}


def controller(tmp_path: Path, tasks: dict | None = None, workers=2):
    config = ControllerConfig(tmp_path / "state", tmp_path / "worktrees", workers, 1, 1536, 128, False)
    plane, runner = FakePlane(), FakeRunner()
    return Controller(config, _test_catalog(tasks or catalog()), plane, runner), plane, runner


def test_sync_is_idempotent_and_never_uploads_evidence_or_authority(tmp_path: Path):
    service, plane, _ = controller(tmp_path)
    assert [row["action"] for row in service.sync_once()] == ["created", "created"]
    assert [row["action"] for row in service.sync_once()] == ["unchanged", "unchanged"]
    assert len(plane.calls) == 2
    assert all("repository evidence" in row[1]["description"] for row in plane.calls)
    assert all("symphony" not in row[1] for row in plane.calls)


def test_title_with_secret_shaped_content_is_refused_before_plane_payload():
    raw = catalog()
    raw["tasks"][0]["title"] = "token replacement"
    with pytest.raises(PlaneSymphonyError, match="identity"):
        validate_task_catalog(raw)


def test_only_h5_is_eligible_until_its_repository_state_is_complete(tmp_path: Path):
    service, _, _ = controller(tmp_path)
    assert service.eligible({"H5": "Ready", "A1": "Ready"}, clean_baseline=True) == ["H5"]
    raw = catalog(h5="COMPLETE_REVIEWED")
    raw["tasks"][0]["review_disposition"] = "ACCEPTED_INDEPENDENT_REVIEW"
    raw["tasks"][0]["acceptance_results"] = ["independent evidence"]
    service, _, _ = controller(tmp_path, raw)
    assert service.eligible({"H5": "Done", "A1": "Ready"}, clean_baseline=True) == ["A1"]


def test_full_catalog_dependency_and_rollout_h5_acceptance_are_both_required(tmp_path: Path):
    raw = catalog(h5="COMPLETE_REVIEWED")
    raw["tasks"][0]["review_disposition"] = "ACCEPTED_INDEPENDENT_REVIEW"
    raw["tasks"][0]["acceptance_results"] = ["H5 review evidence"]
    raw["tasks"][1]["requires"] = ["H3"]
    raw["tasks"].append({"id": "H3", "title": "prior harness", "state": "COMPLETE_REVIEWED",
                         "review_disposition": "ACCEPTED_INDEPENDENT_REVIEW", "acceptance_results": ["H3 evidence"]})
    service, _, _ = controller(tmp_path, raw)
    assert service.eligible({"H5": "Done", "A1": "Ready"}, clean_baseline=True) == ["A1"]
    raw["tasks"][0]["acceptance_results"] = []
    service, _, _ = controller(tmp_path / "forged", raw)
    assert service.eligible({"H5": "Done", "A1": "Ready"}, clean_baseline=True) == []


def test_duplicate_leases_and_dirty_write_baseline_are_refused(tmp_path: Path):
    service, _, runner = controller(tmp_path)
    assert service.run_once({"H5": "Ready", "A1": "Ready"}, baseline_revision="abc1234", clean_baseline=True)
    assert service.run_once({"H5": "Ready", "A1": "Ready"}, baseline_revision="abc1234", clean_baseline=True) == []
    assert len(runner.calls) == 1
    other, _, other_runner = controller(tmp_path / "dirty")
    assert other.run_once({"H5": "Ready"}, baseline_revision="abc1234", clean_baseline=False) == []
    assert other_runner.calls == []


def test_repository_policy_can_withhold_an_otherwise_ready_task(tmp_path: Path):
    raw = catalog()
    raw["tasks"][0]["symphony"]["eligible"] = False
    service, _, _ = controller(tmp_path, raw)
    assert service.eligible({"H5": "Ready", "A1": "Ready"}, clean_baseline=True) == []


@pytest.mark.parametrize("field,value", [
    ("allowed_external_operations", ["generic-shell"]), ("allowed_external_operations", ["broker-call"]),
    ("allowed_external_operations", ["mt5_read"]), ("allowed_external_operations", ["harmless_unknown"]),
    ("preflight_commands", ["live_preflight"]), ("preflight_commands", ["harmless_preflight"]),
])
def test_unsafe_policy_is_rejected(field, value):
    raw = catalog(); raw["tasks"][0]["symphony"][field] = value
    with pytest.raises(PlaneSymphonyError, match="prohibited|fixed allowlist"):
        validate_task_catalog(raw)


def test_fixed_operation_binding_uses_only_canonical_allowlisted_operations():
    tasks = _test_catalog(catalog())
    bound = bind_fixed_operation(tasks, task_id="H5", operation="plane_board_bootstrap")
    assert bound["task_id"] == "H5"
    assert bound["preflight_commands"] == ("plane_symphony_preflight",)
    assert bound["canonical_task_sha256"].startswith("sha256:")
    for operation in ("generic-shell", "broker-call", "a1_retention_deploy"):
        with pytest.raises(PlaneSymphonyError):
            bind_fixed_operation(tasks, task_id="H5", operation=operation)
    raw = catalog(); raw["tasks"][0]["symphony"]["eligible"] = False
    with pytest.raises(PlaneSymphonyError, match="not eligible"):
        bind_fixed_operation(_test_catalog(raw), task_id="H5", operation="plane_board_bootstrap")


def test_controller_uses_fixed_operation_binding_before_runner_preflight(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    service, _, runner = controller(tmp_path)
    monkeypatch.setattr("forex.plane_symphony.bind_fixed_operation", lambda *_args, **_kwargs: (_ for _ in ()).throw(PlaneSymphonyError("binding refused")))
    with pytest.raises(PlaneSymphonyError, match="binding refused"):
        service.run_once({"H5": "Ready"}, baseline_revision="abcdef1", clean_baseline=True)
    assert runner.calls == []


def test_production_catalog_loader_is_fixed_source_and_controller_rejects_raw_dict(tmp_path: Path):
    root = Path(__file__).resolve().parents[1]
    catalog_object = load_canonical_task_catalog(root)
    assert set(catalog_object.snapshot()) >= {"H5", "A1"}
    config = ControllerConfig(tmp_path / "state", tmp_path / "worktrees", 2, 1, 1536, 128, False)
    with pytest.raises(PlaneSymphonyError, match="canonical task catalog"):
        Controller(config, catalog_object.snapshot(), FakePlane(), FakeRunner())  # type: ignore[arg-type]


def test_catalog_snapshot_mutation_cannot_change_binding_or_lease_digest(tmp_path: Path):
    original = _test_catalog(catalog())
    altered = original.snapshot(); altered["H5"]["symphony"]["allowed_external_operations"] = ["symphony_service_install"]
    assert bind_fixed_operation(original, task_id="H5", operation="plane_board_bootstrap")["operation"] == "plane_board_bootstrap"
    with pytest.raises(PlaneSymphonyError):
        bind_fixed_operation(original, task_id="H5", operation="symphony_service_install")
    service, _, _ = controller(tmp_path)
    service.run_once({"H5": "Ready"}, baseline_revision="abcdef1", clean_baseline=True)
    lease = service.leases.read()["H5"]
    assert lease["catalog_source_sha256"] == service.catalog.source_sha256
    assert lease["task_policy_sha256"] == "sha256:" + lease["configuration_fingerprint"]


def test_done_display_requires_repository_acceptance_evidence():
    task = catalog(h5="COMPLETE_REVIEWED")["tasks"][0]
    assert desired_plane_state(task) == "Review"
    task["review_disposition"] = "ACCEPTED_INDEPENDENT_REVIEW"
    task["acceptance_results"] = ["independent evidence"]
    assert issue_payload(task)["state"] == "Done"


def test_repository_transition_sequence_rejects_plane_style_shortcuts():
    blocked = catalog(h5="BLOCKED_EXTERNAL_PLANE")["tasks"][0]
    ready = transition_task_state(blocked, "READY")
    in_review = transition_task_state(ready, "IN_REVIEW")
    accepted = transition_task_state(
        in_review, "COMPLETE_REVIEWED",
        review_disposition="ACCEPTED_INDEPENDENT_REVIEW",
        acceptance_results=["repository review record"],
    )
    assert accepted["state"] == "COMPLETE_REVIEWED"
    with pytest.raises(PlaneSymphonyError, match="not permitted"):
        transition_task_state(ready, "COMPLETE_REVIEWED")
    with pytest.raises(PlaneSymphonyError, match="accepted repository review"):
        transition_task_state(in_review, "COMPLETE_REVIEWED", review_disposition="NOT_STARTED", acceptance_results=["x"])
    with pytest.raises(PlaneSymphonyError, match="accepted repository review"):
        transition_task_state(in_review, "COMPLETE_REVIEWED", review_disposition="ACCEPTED_BY_PLANE", acceptance_results=["x"])


def test_manual_plane_done_never_advances_repository_state(tmp_path: Path):
    service, _, _ = controller(tmp_path)
    assert service.eligible({"H5": "Done", "A1": "Ready"}, clean_baseline=True) == []
    assert service.tasks["H5"]["state"] == "READY"


def test_redaction_removes_nested_credentials_and_restart_reads_lease(tmp_path: Path):
    assert redact({"api_token": "secret", "nested": {"password": "value"}}) == {"api_token": "[REDACTED]", "nested": {"password": "[REDACTED]"}}
    service, _, _ = controller(tmp_path)
    service.run_once({"H5": "Ready"}, baseline_revision="abcdef1", clean_baseline=True)
    restarted, _, _ = controller(tmp_path)
    assert restarted.eligible({"H5": "Ready"}, clean_baseline=True) == []
    assert restarted.recover_leases(baseline_revision="abcdef1") == [{"task_id": "H5", "status": "RESUMABLE"}]
    assert restarted.recover_leases(baseline_revision="abcdef2") == [{"task_id": "H5", "status": "BLOCKED_CONFIGURATION_DRIFT"}]


def test_retained_preflight_content_is_hash_bound_fresh_and_not_redacted(tmp_path: Path):
    service, _, runner = controller(tmp_path)
    assert service.run_once({"H5": "Ready"}, baseline_revision="abcdef1", clean_baseline=True)
    receipt = service.leases.read()["H5"]["preflight_receipt"]
    assert receipt["content"] == {"capacity": "ok"}
    receipt["content"] = {"capacity": "changed"}
    with pytest.raises(PlaneSymphonyError, match="valid PASS"):
        validate_preflight_receipt("H5", ("plane_symphony_preflight",), "abcdef1",
                                   service.leases.read()["H5"]["configuration_fingerprint"], receipt)
    stale = copy.deepcopy(service.leases.read()["H5"]["preflight_receipt"])
    stale["observed_at"] = "2000-01-01T00:00:00Z"
    stale["receipt_sha256"] = _canonical_digest({key: value for key, value in stale.items() if key != "receipt_sha256"})
    with pytest.raises(PlaneSymphonyError, match="valid PASS"):
        validate_preflight_receipt("H5", ("plane_symphony_preflight",), "abcdef1",
                                   service.leases.read()["H5"]["configuration_fingerprint"], stale)
    assert runner.calls[0]["idempotency_key"] == service.leases.read()["H5"]["idempotency_key"]


def test_sync_preserves_runtime_state_and_completion_requires_lifecycle_inspection(tmp_path: Path):
    service, plane, runner = controller(tmp_path)
    service.run_once({"H5": "Ready"}, baseline_revision="abcdef1", clean_baseline=True)
    assert plane.issues["FOREX:H5"]["state"] == "In progress"
    runner.lifecycle = "COMPLETED"
    service.run_once({"H5": "Ready"}, baseline_revision="abcdef1", clean_baseline=True)
    assert runner.inspect_calls
    assert service.leases.read()["H5"]["status"] == "COMPLETED"
    assert service.tasks["H5"]["state"] == "IN_REVIEW"
    assert plane.issues["FOREX:H5"]["state"] == "Review"


def test_failed_or_unavailable_lifecycle_never_silently_releases_capacity(tmp_path: Path):
    service, plane, runner = controller(tmp_path)
    service.run_once({"H5": "Ready"}, baseline_revision="abcdef1", clean_baseline=True)
    runner.lifecycle = "FAILED"
    service.run_once({"H5": "Ready"}, baseline_revision="abcdef1", clean_baseline=True)
    assert service.leases.read()["H5"]["status"] == "BLOCKED_RUNNER_FAILURE"
    assert plane.issues["FOREX:H5"]["state"] == "Blocked"
    unavailable, unavailable_plane, unavailable_runner = controller(tmp_path / "unavailable")
    unavailable.run_once({"H5": "Ready"}, baseline_revision="abcdef1", clean_baseline=True)
    unavailable_runner.fail_inspect = True
    unavailable.run_once({"H5": "Ready"}, baseline_revision="abcdef1", clean_baseline=True)
    assert unavailable.leases.read()["H5"]["status"] == "IN_PROGRESS"
    assert unavailable_plane.issues["FOREX:H5"]["state"] == "In progress"


def test_two_worker_limit_never_creates_more_than_two_leases(tmp_path: Path):
    raw = catalog(h5="COMPLETE_REVIEWED")
    raw["tasks"][0]["review_disposition"] = "ACCEPTED_INDEPENDENT_REVIEW"
    raw["tasks"][0]["acceptance_results"] = ["independent evidence"]
    service, _, runner = controller(tmp_path, raw, workers=2)
    assert service.run_once({"H5": "Done", "A1": "Ready"}, baseline_revision="1234567", clean_baseline=True)
    assert len(runner.calls) == 1


def test_locked_reservation_prevents_competing_controllers_from_starting_twice(tmp_path: Path):
    first, _, first_runner = controller(tmp_path)
    second, _, second_runner = controller(tmp_path)
    assert first.run_once({"H5": "Ready"}, baseline_revision="abcdef1", clean_baseline=True)
    assert second.run_once({"H5": "Ready"}, baseline_revision="abcdef1", clean_baseline=True) == []
    assert len(first_runner.calls) + len(second_runner.calls) == 1


def test_existing_active_lease_consumes_the_only_worker_slot(tmp_path: Path):
    raw = catalog(h5="COMPLETE_REVIEWED")
    raw["tasks"][0]["review_disposition"] = "ACCEPTED_INDEPENDENT_REVIEW"
    raw["tasks"][0]["acceptance_results"] = ["accepted"]
    service, _, _ = controller(tmp_path, raw, workers=1)
    service.leases.reserve({"task_id": "OTHER", "status": "IN_PROGRESS"}, max_workers=1)
    assert service.eligible({"H5": "Done", "A1": "Ready"}, clean_baseline=True) == []


def test_wrong_or_missing_preflight_blocks_before_agent_start(tmp_path: Path):
    service, _, runner = controller(tmp_path)
    runner.preflight_result = {"task_id": "H5", "commands": ["wrong"], "status": "PASS", "receipt_sha256": "a" * 64}
    assert service.run_once({"H5": "Ready"}, baseline_revision="abcdef1", clean_baseline=True) == [{"task_id": "H5", "status": "BLOCKED_PREFLIGHT"}]
    assert runner.calls == []
    leases = service.leases.read()
    assert leases["H5"]["status"] == "BLOCKED_PREFLIGHT"
    missing, _, missing_runner = controller(tmp_path / "missing")
    missing_runner.preflight_result = {"task_id": "H5", "commands": ["plane_symphony_preflight"], "status": "PASS"}
    assert missing.run_once({"H5": "Ready"}, baseline_revision="abcdef1", clean_baseline=True) == [{"task_id": "H5", "status": "BLOCKED_PREFLIGHT"}]
    assert missing_runner.calls == []


def test_runner_failure_is_retained_as_blocked_reservation(tmp_path: Path):
    service, plane, runner = controller(tmp_path)
    runner.fail_start = True
    assert service.run_once({"H5": "Ready"}, baseline_revision="abcdef1", clean_baseline=True) == [{"task_id": "H5", "status": "RUNNER_START_UNKNOWN"}]
    assert service.leases.read()["H5"]["status"] == "RUNNER_START_UNKNOWN"
    assert plane.issues["FOREX:H5"]["state"] == "Blocked"


def test_uninspected_runner_start_uncertainty_still_consumes_capacity(tmp_path: Path):
    raw = catalog(h5="COMPLETE_REVIEWED")
    raw["tasks"][0]["review_disposition"] = "ACCEPTED_INDEPENDENT_REVIEW"
    raw["tasks"][0]["acceptance_results"] = ["accepted"]
    service, _, _ = controller(tmp_path, raw, workers=1)
    service.leases.reserve({"task_id": "OTHER", "status": "RUNNER_START_UNKNOWN"}, max_workers=1)
    assert service.eligible({"H5": "Done", "A1": "Ready"}, clean_baseline=True) == []
