from __future__ import annotations

import copy
import json
from pathlib import Path
import subprocess
import sys

import pytest

from forex.plane_sync import PlaneSyncError, load_contract, load_task_ids, offline_report

ROOT = Path(__file__).resolve().parents[1]


def test_offline_contract_maps_existing_task_ids_without_connecting_to_plane():
    contract = load_contract(ROOT / "config/plane_sync.json")
    task_ids = load_task_ids(ROOT / contract["task_source"])
    report = offline_report(contract, task_ids)
    assert report["synchronization"] == "NOT_ATTEMPTED_OFFLINE_PREPARATION"
    assert report["plane_authority"] == "VISIBLE_STATUS_ONLY"
    assert report["execution_authority"] is False
    result = subprocess.run([sys.executable, "scripts/plane_sync.py"], cwd=ROOT, text=True, capture_output=True)
    assert result.returncode == 0
    assert json.loads(result.stdout)["task_ids"] == task_ids


def test_contract_refuses_connection_or_execution_authority(tmp_path: Path):
    source = json.loads((ROOT / "config/plane_sync.json").read_text())
    source["enabled"] = True
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(source))
    with pytest.raises(PlaneSyncError, match="authority"):
        load_contract(path)
    source = json.loads((ROOT / "config/plane_sync.json").read_text())
    source["execution_authority"] = True
    path.write_text(json.dumps(source))
    with pytest.raises(PlaneSyncError, match="authority"):
        load_contract(path)


def test_task_mapping_refuses_duplicate_or_missing_active_task_ids(tmp_path: Path):
    plan = json.loads((ROOT / "docs/milestones/active-delivery-tasks.json").read_text())
    plan["tasks"].append(copy.deepcopy(plan["tasks"][0]))
    path = tmp_path / "tasks.json"
    path.write_text(json.dumps(plan))
    with pytest.raises(PlaneSyncError, match="active task source"):
        load_task_ids(path)


def test_cli_refuses_an_arbitrary_queue_override():
    result = subprocess.run(
        [sys.executable, "scripts/plane_sync.py", "--queue", "/tmp/not-contract-pinned.json"],
        cwd=ROOT, text=True, capture_output=True,
    )
    assert result.returncode != 0
