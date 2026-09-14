from __future__ import annotations

import os
import stat
from uuid import uuid4

import pytest

from forex.execution_loop import ExecutionLoopError, LoopStore


def arguments(**overrides: str) -> dict[str, str]:
    values = {"task_id": "H5", "item_id": "durable-loop-state", "selector_sha256": "sha256:" + "a" * 64,
              "work_plan_sha256": "sha256:" + "b" * 64, "canonical_task_sha256": "sha256:" + "c" * 64,
              "baseline_revision": "d" * 40, "configuration_fingerprint": "sha256:" + "e" * 64,
              "lease_id": str(uuid4()), "worker_run_id": str(uuid4()), "receipt_code": "SELECTED"}
    values.update(overrides); return values


def expected(record):
    return {"expected_selector_sha256": record["selector_sha256"], "expected_work_plan_sha256": record["work_plan_sha256"], "expected_canonical_task_sha256": record["canonical_task_sha256"]}


def test_store_is_private_durable_single_lease_and_never_locally_completes_review(tmp_path):
    store = LoopStore(tmp_path / "state"); record = store.select(**arguments())
    assert record["state"] == "SELECTED" and stat.S_IMODE(store.path.stat().st_mode) == 0o600
    with pytest.raises(ExecutionLoopError, match="active loop lease"): store.select(**arguments(item_id="other"))
    assert store.transition("PREFLIGHT_PASSED", "PREFLIGHT_PASS", **expected(record))["state"] == "PREFLIGHT_PASSED"
    assert store.transition("RUNNING", "WORKER_STARTED", **expected(record))["state"] == "RUNNING"
    assert store.transition("IN_REVIEW", "RESULT_READY", **expected(record))["state"] == "IN_REVIEW"
    with pytest.raises(ExecutionLoopError, match="not permitted"):
        store.transition("COMPLETE_REVIEWED", "FORGED_ACCEPTANCE", **expected(record))


def test_store_refuses_stale_free_text_and_duplicate_state_fields(tmp_path):
    store = LoopStore(tmp_path / "state"); record = store.select(**arguments())
    with pytest.raises(ExecutionLoopError, match="stale"):
        store.transition("PREFLIGHT_PASSED", "PREFLIGHT_PASS", **{**expected(record), "expected_canonical_task_sha256": "sha256:" + "f" * 64})
    with pytest.raises(ExecutionLoopError): LoopStore(tmp_path / "other").select(**arguments(receipt_code="token=do-not-retain"))
    store.path.write_text('{"task_id":"H5","task_id":"A1"}', encoding="utf-8"); store.path.chmod(0o600)
    with pytest.raises(ExecutionLoopError, match="duplicate"): store.read()


def test_terminal_lease_refuses_all_unverified_retries_or_task_switches(tmp_path):
    store = LoopStore(tmp_path / "state"); first = store.select(**arguments())
    store.transition("BLOCKED", "PREFLIGHT_FAILED", **expected(first))
    with pytest.raises(ExecutionLoopError, match="active loop lease"):
        store.select(**arguments(canonical_task_sha256=first["canonical_task_sha256"]))
    with pytest.raises(ExecutionLoopError, match="active loop lease"):
        store.select(**arguments(task_id="A1", item_id="fixed-operation-binding", canonical_task_sha256="sha256:" + "f" * 64))


def test_restart_holds_capacity_on_unknown_and_blocks_failed_worker(tmp_path):
    store = LoopStore(tmp_path / "state"); record = store.select(**arguments())
    identity = {key: record[key] for key in ("task_id", "item_id", "baseline_revision", "configuration_fingerprint", "lease_id", "worker_run_id")}
    assert store.recover(**identity, worker_status="UNKNOWN") == {"outcome": "HOLD_CAPACITY", "state": "SELECTED"}
    assert store.recover(**identity, worker_status="FAILED") == {"outcome": "BLOCKED", "state": "BLOCKED"}
    with pytest.raises(ExecutionLoopError, match="does not match"):
        store.recover(**{**identity, "lease_id": str(uuid4())}, worker_status="RUNNING")
    store = LoopStore(tmp_path / "completed-before-running"); record = store.select(**arguments())
    identity = {key: record[key] for key in ("task_id", "item_id", "baseline_revision", "configuration_fingerprint", "lease_id", "worker_run_id")}
    assert store.recover(**identity, worker_status="COMPLETED") == {"outcome": "BLOCKED", "state": "BLOCKED"}


@pytest.mark.parametrize("field,value", [("task_id", "h5"), ("item_id", "Generic Shell"), ("selector_sha256", "sha256:bad"), ("baseline_revision", "bad"), ("lease_id", "not-a-uuid")])
def test_store_rejects_unsafe_identifiers(tmp_path, field, value):
    with pytest.raises(ExecutionLoopError): LoopStore(tmp_path / field).select(**arguments(**{field: value}))


def test_store_refuses_symlink_or_unsafe_directory_and_recovers_stale_temp(tmp_path):
    unsafe = tmp_path / "unsafe"; unsafe.mkdir(mode=0o755)
    with pytest.raises(ExecutionLoopError, match="owner-only"): LoopStore(unsafe).select(**arguments())
    target = tmp_path / "target"; target.mkdir(mode=0o700); linked = tmp_path / "linked"; linked.symlink_to(target, target_is_directory=True)
    with pytest.raises(ExecutionLoopError): LoopStore(linked).select(**arguments())
    store = LoopStore(tmp_path / "state"); store.select(**arguments())
    stale = store.state_dir / ".execution-loop-crash.tmp"; stale.write_text("partial", encoding="utf-8"); stale.chmod(0o600)
    assert store.read()["task_id"] == "H5" and stale.exists()
    dangling = tmp_path / "dangling"; dangling.mkdir(mode=0o700)
    (dangling / "execution-loop.json").symlink_to(dangling / "absent")
    with pytest.raises(ExecutionLoopError): LoopStore(dangling).select(**arguments())
