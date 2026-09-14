"""Offline validation for the future Plane work-item integration.

This module deliberately makes no HTTP request.  Plane is a visibility surface;
repository acceptance and milestone proof retain their existing authorities.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from forex.active_delivery_tasks import ActiveDeliveryTaskError, validate_task_plan

SCHEMA = "forex.plane-sync.v2"
_FIELDS = {
    "schema_version", "enabled", "external_state", "task_source",
    "workflow_state_authority", "plane_base_url_env", "plane_api_key_env",
    "plane_workspace_env", "plane_project_env", "execution_authority",
}
_ENV_FIELDS = {
    "plane_base_url_env", "plane_api_key_env", "plane_workspace_env",
    "plane_project_env",
}


class PlaneSyncError(ValueError):
    """The offline Plane contract or task source is unsafe to use."""


def _pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in items:
        if key in result:
            raise PlaneSyncError("duplicate JSON field")
        result[key] = value
    return result


def _load_json(path: Path) -> dict[str, Any]:
    if not isinstance(path, Path) or path.is_symlink() or not path.is_file():
        raise PlaneSyncError("source must be a regular file")
    try:
        value = json.loads(
            path.read_bytes(), object_pairs_hook=_pairs,
            parse_constant=lambda _: (_ for _ in ()).throw(PlaneSyncError("nonfinite JSON")),
        )
    except (OSError, json.JSONDecodeError) as exc:
        raise PlaneSyncError("source is not valid JSON") from exc
    if not isinstance(value, dict):
        raise PlaneSyncError("source must be a JSON object")
    return value


def load_contract(path: Path) -> dict[str, Any]:
    value = _load_json(path)
    if set(value) != _FIELDS or value.get("schema_version") != SCHEMA:
        raise PlaneSyncError("Plane contract schema is invalid")
    if value["enabled"] is not True or value["execution_authority"] is not False:
        raise PlaneSyncError("Plane contract authority is invalid")
    if value["external_state"] != "H5_CONFIGURATION_REQUIRED":
        raise PlaneSyncError("Plane external state is invalid")
    if value["workflow_state_authority"] != "PLANE_VISIBLE_REPO_ACCEPTANCE":
        raise PlaneSyncError("Plane authority boundary is invalid")
    if not isinstance(value["task_source"], str) or value["task_source"] != "docs/milestones/active-delivery-tasks.json":
        raise PlaneSyncError("Plane task source is invalid")
    if not all(isinstance(value[key], str) and value[key].startswith("FOREX_PLANE_") for key in _ENV_FIELDS):
        raise PlaneSyncError("Plane environment names are invalid")
    return value


def load_task_ids(path: Path) -> list[str]:
    plan = _load_json(path)
    try:
        return [item["id"] for item in validate_task_plan(plan)]
    except ActiveDeliveryTaskError as exc:
        raise PlaneSyncError("active task source is invalid") from exc


def offline_report(contract: dict[str, Any], task_ids: list[str]) -> dict[str, Any]:
    if contract != load_contract_from_value(contract):
        raise PlaneSyncError("Plane contract is invalid")
    if not task_ids or not all(isinstance(task_id, str) and task_id for task_id in task_ids):
        raise PlaneSyncError("task IDs are invalid")
    return {
        "schema_version": SCHEMA,
        "external_state": contract["external_state"],
        "synchronization": "NOT_ATTEMPTED_OFFLINE_PREPARATION",
        "task_count": len(task_ids),
        "task_ids": task_ids,
        "plane_authority": "VISIBLE_STATUS_ONLY",
        "repository_authority": "TASK_ACCEPTANCE_AND_MILESTONE_PROOF",
        "execution_authority": False,
    }


def load_contract_from_value(value: dict[str, Any]) -> dict[str, Any]:
    """Validate an already loaded contract without making a filesystem call."""
    if not isinstance(value, dict) or set(value) != _FIELDS or value.get("schema_version") != SCHEMA:
        raise PlaneSyncError("Plane contract schema is invalid")
    if value.get("enabled") is not True or value.get("execution_authority") is not False:
        raise PlaneSyncError("Plane contract authority is invalid")
    if value.get("external_state") != "H5_CONFIGURATION_REQUIRED" or value.get("workflow_state_authority") != "PLANE_VISIBLE_REPO_ACCEPTANCE":
        raise PlaneSyncError("Plane authority boundary is invalid")
    if value.get("task_source") != "docs/milestones/active-delivery-tasks.json":
        raise PlaneSyncError("Plane task source is invalid")
    if not all(isinstance(value.get(key), str) and value[key].startswith("FOREX_PLANE_") for key in _ENV_FIELDS):
        raise PlaneSyncError("Plane environment names are invalid")
    return value
