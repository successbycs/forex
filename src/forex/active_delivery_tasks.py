"""Validation and read-only selection for the active Harness/A/B/C plan."""
from __future__ import annotations

from typing import Any


SCHEMA = "forex.active-delivery-tasks.v2"
_TOP = {"schema_version", "purpose", "active_sequence", "execution_authority", "tasks"}
_TASK = {"id", "stage", "title", "state", "formal_milestone", "acceptance", "requires", "owned_paths", "acceptance_commands", "acceptance_results", "review_disposition", "evidence_class", "execution_authority"}
_TASK_OPTIONAL = {"symphony"}
_STATES = {"PENDING", "READY", "IN_PROGRESS", "IN_REVIEW", "COMPLETE_REVIEWED", "BLOCKED_EXTERNAL_PLANE", "BLOCKED_EXTERNAL_OBSERVATION", "BLOCKED_HUMAN_MIGRATION"}
_STAGES = {"HARNESS", "A", "B", "C"}
_ACTIVE = {"READY", "IN_PROGRESS", "IN_REVIEW"}


class ActiveDeliveryTaskError(ValueError):
    """The active delivery task metadata cannot safely be interpreted."""


def validate_task_plan(plan: dict[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(plan, dict) or set(plan) != _TOP or plan.get("schema_version") != SCHEMA:
        raise ActiveDeliveryTaskError("task plan schema is invalid")
    if not isinstance(plan["purpose"], str) or not plan["purpose"] or plan["execution_authority"] is not False:
        raise ActiveDeliveryTaskError("task plan authority or purpose is invalid")
    sequence, tasks = plan["active_sequence"], plan["tasks"]
    if not isinstance(sequence, list) or not isinstance(tasks, list) or len(sequence) != len(tasks):
        raise ActiveDeliveryTaskError("task plan sequence is invalid")
    by_id: dict[str, dict[str, Any]] = {}
    for task in tasks:
        if not isinstance(task, dict) or not _TASK <= set(task) or not set(task) <= (_TASK | _TASK_OPTIONAL):
            raise ActiveDeliveryTaskError("task schema is invalid")
        task_id = task["id"]
        if not isinstance(task_id, str) or not task_id or task_id in by_id:
            raise ActiveDeliveryTaskError("task IDs must be unique")
        if task["stage"] not in _STAGES or task["state"] not in _STATES or task["execution_authority"] is not False:
            raise ActiveDeliveryTaskError("task state, stage or authority is invalid")
        if not isinstance(task["title"], str) or not task["title"] or not isinstance(task["formal_milestone"], str):
            raise ActiveDeliveryTaskError("task identity is invalid")
        if (not isinstance(task["acceptance"], list) or not task["acceptance"]
                or not all(isinstance(item, str) and item for item in task["acceptance"])
                or not isinstance(task["requires"], list) or not all(isinstance(item, str) and item for item in task["requires"])):
            raise ActiveDeliveryTaskError("task acceptance or requirements are invalid")
        if (not isinstance(task["owned_paths"], list) or not all(isinstance(item, str) and item for item in task["owned_paths"])
                or not isinstance(task["acceptance_commands"], list) or not all(isinstance(item, str) and item for item in task["acceptance_commands"])
                or not isinstance(task["acceptance_results"], list) or not all(isinstance(item, str) and item for item in task["acceptance_results"])
                or not isinstance(task["review_disposition"], str) or not task["review_disposition"]
                or not isinstance(task["evidence_class"], str) or not task["evidence_class"]):
            raise ActiveDeliveryTaskError("task evidence metadata is invalid")
        if "symphony" in task:
            policy = task["symphony"]
            expected = {"eligible", "allowed_external_operations", "preflight_commands", "review_route"}
            if task_id not in {"H5", "A1"} or not isinstance(policy, dict) or set(policy) != expected:
                raise ActiveDeliveryTaskError("task Symphony policy is invalid")
            if policy["eligible"] is not True or not isinstance(policy["review_route"], str) or not policy["review_route"]:
                raise ActiveDeliveryTaskError("task Symphony eligibility is invalid")
            operations, commands = policy["allowed_external_operations"], policy["preflight_commands"]
            forbidden = ("broker", "mt5", "live", "shell", "bash", "powershell", "curl", "http://", "https://")
            if (not isinstance(operations, list) or not operations or not all(isinstance(item, str) and item for item in operations)
                    or not isinstance(commands, list) or not commands or not all(isinstance(item, str) and item for item in commands)
                    or any(any(token in item.lower() for token in forbidden) for item in [*operations, *commands])):
                raise ActiveDeliveryTaskError("task Symphony operation policy is unsafe")
        by_id[task_id] = task
    if sequence != list(by_id):
        raise ActiveDeliveryTaskError("task sequence must exactly match task order")
    for task in tasks:
        if any(item not in by_id or item == task["id"] for item in task["requires"]):
            raise ActiveDeliveryTaskError("task requirement is unknown or self-referential")
    return tasks


def select_active_task(plan: dict[str, Any]) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    """Return the first active task and explicit blocked tasks; never mutate plan."""
    tasks = validate_task_plan(plan)
    by_id = {task["id"]: task for task in tasks}
    active = [task for task in tasks if task["state"] in _ACTIVE]
    if len(active) > 1:
        raise ActiveDeliveryTaskError("more than one active task is declared")
    if active and any(by_id[item]["state"] != "COMPLETE_REVIEWED" for item in active[0]["requires"]):
        raise ActiveDeliveryTaskError("active task has unmet prerequisite")
    blocked = [task for task in tasks if task["state"].startswith("BLOCKED_")]
    return (active[0] if active else None), blocked
