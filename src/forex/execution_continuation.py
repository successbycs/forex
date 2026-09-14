"""Read-only, fail-closed selection of the next execution-work item."""
from __future__ import annotations

from typing import Any


SCHEMA_VERSION = "forex.execution-work.v1"
_TOP_FIELDS = {"schema_version", "task_id", "authorization", "markdown_plan", "items"}
_ITEM_FIELDS = {"id", "title", "state", "requires", "evidence", "blocker"}
_STATES = {"PENDING", "IN_PROGRESS", "IN_REVIEW", "DONE", "BLOCKED"}
_ACTIVE_UNFINISHED = {"PENDING", "IN_PROGRESS", "IN_REVIEW"}
_BLOCKER_FIELDS = {"source", "reason", "unblock_action"}


class ExecutionWorkError(ValueError):
    """The execution-work document cannot safely be used for continuation."""


def _nonempty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def validate_work_plan(plan: object) -> list[dict[str, Any]]:
    """Validate a v1 work plan and return its ordered items without changing it."""
    if not isinstance(plan, dict) or set(plan) != _TOP_FIELDS:
        raise ExecutionWorkError("work plan schema is invalid")
    if plan.get("schema_version") != SCHEMA_VERSION:
        raise ExecutionWorkError("work plan schema version is invalid")
    if (not _nonempty_string(plan.get("task_id")) or not _nonempty_string(plan.get("authorization"))
            or not _nonempty_string(plan.get("markdown_plan"))):
        raise ExecutionWorkError("work plan identity or authorization is invalid")
    items = plan.get("items")
    if not isinstance(items, list) or not items:
        raise ExecutionWorkError("work plan items must be a nonempty list")

    seen: set[str] = set()
    by_id: dict[str, dict[str, Any]] = {}
    for item in items:
        if not isinstance(item, dict) or set(item) != _ITEM_FIELDS:
            raise ExecutionWorkError("work item schema is invalid")
        item_id = item.get("id")
        if not _nonempty_string(item_id) or item_id in seen:
            raise ExecutionWorkError("work item IDs must be nonempty and unique")
        if not _nonempty_string(item.get("title")) or item.get("state") not in _STATES:
            raise ExecutionWorkError("work item identity or state is invalid")
        requires, evidence = item.get("requires"), item.get("evidence")
        if (not isinstance(requires, list) or not all(_nonempty_string(requirement) for requirement in requires)
                or len(set(requires)) != len(requires)):
            raise ExecutionWorkError("work item requirements are invalid")
        if not isinstance(evidence, list) or not all(_nonempty_string(entry) for entry in evidence):
            raise ExecutionWorkError("work item evidence is invalid")
        if item["state"] == "DONE":
            if not evidence or item["blocker"] is not None:
                raise ExecutionWorkError("done work item needs evidence and no blocker")
        elif item["state"] == "BLOCKED":
            blocker = item["blocker"]
            if (not isinstance(blocker, dict) or set(blocker) != _BLOCKER_FIELDS
                    or not all(_nonempty_string(blocker.get(field)) for field in _BLOCKER_FIELDS)):
                raise ExecutionWorkError("blocked work item needs a complete blocker")
        elif item["blocker"] is not None:
            raise ExecutionWorkError("nonblocked work item must not have a blocker")
        seen.add(item_id)
        by_id[item_id] = item

    prior: set[str] = set()
    for item in items:
        for requirement in item["requires"]:
            if requirement not in prior:
                raise ExecutionWorkError("work item requirement must name an earlier item")
        prior.add(item["id"])
    for item in items:
        if item["state"] in {"IN_PROGRESS", "IN_REVIEW"} and any(
            by_id[requirement]["state"] != "DONE" for requirement in item["requires"]
        ):
            raise ExecutionWorkError("active work item has an unmet prerequisite")
    return items


def evaluate_work_plan(plan: object, *, work_plan_sha256: str) -> dict[str, Any]:
    """Return advisory continuation state; this function never executes work."""
    if not _nonempty_string(work_plan_sha256):
        raise ExecutionWorkError("work plan digest is invalid")
    items = validate_work_plan(plan)
    by_id = {item["id"]: item for item in items}
    actionable = [
        item for item in items
        if item["state"] in _ACTIVE_UNFINISHED
        and all(by_id[requirement]["state"] == "DONE" for requirement in item["requires"])
    ]
    blockers = _terminal_blockers(items, by_id)
    report: dict[str, Any] = {
        "enforcement": "ADVISORY_REQUIRES_CALLER",
        "execution_authority": False,
        "work_plan_sha256": work_plan_sha256,
        "terminal_blockers": blockers,
    }
    if actionable:
        item = actionable[0]
        return {**report, "outcome": "CONTINUE", "next_item": {"id": item["id"], "title": item["title"]}, "stop_allowed": False}
    if all(item["state"] == "DONE" for item in items):
        return {**report, "outcome": "COMPLETE", "next_item": None, "stop_allowed": True}
    if blockers:
        return {**report, "outcome": "BLOCKED", "next_item": None, "stop_allowed": True}
    raise ExecutionWorkError("unfinished work has no safe continuation or terminal blocker")


def _terminal_blockers(items: list[dict[str, Any]], by_id: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """Return unique blocked prerequisites of unfinished work, in plan order."""
    blocked_ids: set[str] = set()

    def visit(item_id: str) -> None:
        item = by_id[item_id]
        if item["state"] == "BLOCKED":
            blocked_ids.add(item_id)
            return
        for requirement in item["requires"]:
            visit(requirement)

    for item in items:
        if item["state"] != "DONE":
            visit(item["id"])
    return [
        {"id": item["id"], "title": item["title"], "blocker": item["blocker"]}
        for item in items if item["id"] in blocked_ids
    ]
