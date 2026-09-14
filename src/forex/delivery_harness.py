"""Read-only status diagnostics for the active Harness/A/B/C task plan.

This is deliberately a reporting boundary.  It consumes repository task
metadata and governance state, but cannot select an account, call a broker,
modify a queue, or change a milestone.  In particular, package delivery is
reported separately from formal milestone proof.
"""
from __future__ import annotations

from typing import Any

from forex.active_delivery_tasks import ActiveDeliveryTaskError, select_active_task, validate_task_plan
from forex.milestones import GovernanceError, validate_registry, validate_run_history, validate_state


SCHEMA = "forex.delivery-harness-status.v1"


class DeliveryHarnessError(ValueError):
    """Repository task metadata or governance state is not safe to report."""


def _contracts(registry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    try:
        validate_registry(registry)
    except GovernanceError as exc:
        raise DeliveryHarnessError("milestone registry is invalid") from exc
    return {row["milestone_id"]: row for row in registry["milestones"]}


def _governance_issues(state: dict[str, Any], registry: dict[str, Any], history: dict[str, Any]) -> list[str]:
    """Use existing read-only governance validators; never repair their input."""
    issues: list[str] = []
    try:
        validate_state(state, registry)
        validate_run_history(history)
    except GovernanceError as exc:
        issues.append(f"GOVERNANCE_STATE_INVALID:{exc}")
    return issues


def _completion_claim_issues(state: dict[str, Any]) -> list[str]:
    """Identify claims that lack the formal proof timestamp required by state."""
    issues: list[str] = []
    milestones = state.get("milestones")
    if not isinstance(milestones, dict):
        return ["MILESTONE_STATE_UNAVAILABLE"]
    for milestone_id, item in sorted(milestones.items()):
        if not isinstance(item, dict):
            issues.append(f"MILESTONE_STATE_INVALID:{milestone_id}")
            continue
        status, proven_at = item.get("status"), item.get("proven_at")
        if status == "PROVEN" and not proven_at:
            issues.append(f"UNSUPPORTED_COMPLETION_CLAIM:{milestone_id}:PROVEN_WITHOUT_PROVEN_AT")
        elif status not in {"PROVEN", "NEEDS_REVALIDATION"} and proven_at:
            issues.append(f"UNSUPPORTED_COMPLETION_CLAIM:{milestone_id}:PROVEN_AT_WITH_NONPROVEN_STATE")
    return issues


def harness_status(*, task_plan: dict[str, Any], state: dict[str, Any], registry: dict[str, Any],
                   history: dict[str, Any]) -> dict[str, Any]:
    """Return a fail-closed, read-only operational handover status.

    The active Harness/A/B/C plan is the repository's task metadata.  The registry/state/history
    remain the authoritative plan and formal-status sources.  Invalid inputs
    are represented as consistency issues, never repaired or interpreted as
    evidence of completion.
    """
    contracts = _contracts(registry)
    try:
        tasks = validate_task_plan(task_plan)
        active_task_metadata, blocked_tasks = select_active_task(task_plan)
    except ActiveDeliveryTaskError as exc:
        raise DeliveryHarnessError(f"active delivery task plan is invalid: {exc}") from exc

    active = state.get("current_milestone")
    milestones = state.get("milestones")
    if not isinstance(active, str) or active not in contracts or not isinstance(milestones, dict):
        raise DeliveryHarnessError("active formal milestone is unavailable")
    formal_state = milestones.get(active)
    if not isinstance(formal_state, dict):
        raise DeliveryHarnessError("active formal milestone state is unavailable")

    issues = _governance_issues(state, registry, history) + _completion_claim_issues(state)
    for task in tasks:
        milestone_id = task["formal_milestone"]
        if milestone_id not in contracts:
            issues.append(f"TASK_PLAN_MISMATCH:{task['id']}:UNKNOWN_FORMAL_MILESTONE")
        elif milestone_id not in milestones:
            issues.append(f"TASK_PLAN_MISMATCH:{task['id']}:MISSING_FORMAL_STATE")
        elif any(item not in {criterion["id"] for criterion in contracts[milestone_id]["acceptance_criteria"]}
                 for item in task["acceptance"]):
            issues.append(f"TASK_PLAN_MISMATCH:{task['id']}:UNKNOWN_ACCEPTANCE")
    if active_task_metadata is not None and active_task_metadata["formal_milestone"] != active:
        issues.append("TASK_PLAN_MISMATCH:ACTIVE_TASK_DOES_NOT_MATCH_ACTIVE_MILESTONE")

    if active_task_metadata is None:
        active_task = {
            "task_id": active,
            "task_kind": "FORMAL_MILESTONE",
            "title": contracts[active]["title"],
            "formal_milestone": active,
            "task_state": formal_state["status"],
        }
        next_action = {
            "state": "NO_ACTIVE_DELIVERY_TASK",
            "action": "Resolve one declared active-plan blocker or record a separately authorised task.",
        }
    else:
        active_task = {
            "task_id": active_task_metadata["id"],
            "task_kind": "ACTIVE_DELIVERY_TASK",
            "title": active_task_metadata["title"],
            "stage": active_task_metadata["stage"],
            "formal_milestone": active_task_metadata["formal_milestone"],
            "task_state": active_task_metadata["state"],
            "acceptance": active_task_metadata["acceptance"],
            "owned_paths": active_task_metadata["owned_paths"],
            "acceptance_commands": active_task_metadata["acceptance_commands"],
            "acceptance_results": active_task_metadata["acceptance_results"],
            "review_disposition": active_task_metadata["review_disposition"],
            "evidence_class": active_task_metadata["evidence_class"],
        }
        next_action = {
            "state": "ACTIVE_TASK",
            "action": f"Complete or review {active_task_metadata['id']} within its declared acceptance.",
        }

    blockers = list(formal_state.get("blockers", []))
    blockers.extend({"task_id": item["id"], "state": item["state"], "requires": item["requires"]}
                    for item in blocked_tasks)
    return {
        "schema_version": SCHEMA,
        "execution_authority": False,
        "read_only": True,
        "active_task": active_task,
        "demonstrated_result": {
            "formal_milestone_status": formal_state["status"],
            "formal_proven_at": formal_state.get("proven_at"),
            "recorded_evidence_count": len(formal_state.get("evidence", [])),
            "verification_result": formal_state.get("verification"),
            "formal_proof_required": contracts[active]["real_world_proof"]["real_world_execution"],
        },
        "blockers": blockers,
        "next_action": next_action,
        "task_plan_consistency": {
            "ok": not issues,
            "issues": issues,
            "active_formal_milestone": active,
            "active_task_plan": "docs/milestones/active-delivery-tasks.json",
        },
        "unsupported_completion_claims": [item for item in issues if item.startswith("UNSUPPORTED_COMPLETION_CLAIM:")],
    }
