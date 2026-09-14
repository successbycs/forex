"""Fail-closed selection of independent Demo-delivery work packages.

This module is deliberately separate from milestone transitions.  It cannot
write project state, invoke a broker, select an account, or grant execution
authority.  It makes a formal evidence block visible while selecting a
separately-authorised, market-independent package when one is ready.
"""
from __future__ import annotations

from typing import Any

QUEUE_SCHEMA_VERSION = "forex.autonomous-delivery-queue.v1"
_PACKAGE_FIELDS = {"id", "wave", "title", "state", "formal_milestone", "requires", "execution_authority"}
_COMPLETED_STATES = frozenset({
    "COMPLETE",
    # A bounded non-trading component may be deployed and observed while its
    # external source result remains explicitly unknown. It satisfies only
    # its own delivery dependency; downstream context qualification still
    # enforces separate coverage requirements.
    "DEPLOYED_OBSERVED_CONTEXT_UNKNOWN",
    "COMPLETE_REVIEWED_SUBMISSION_DISABLED",
    "COMPLETE_REVIEWED_DISABLED",
    "COMPLETE_REVIEWED_NOT_DEPLOYED",
})
_PARKED_STATES = frozenset({
    "PARKED_EXTERNAL_PROOF",
    "PARKED_EXTERNAL_OBSERVATION",
    "PARKED_EXTERNAL_COVERAGE",
    "PARKED_HUMAN_MANDATE",
    "PARKED_HUMAN_POLICY_APPROVAL",
    "PARKED_EXECUTION_INTEGRATION",
})
_DEFERRED_STATES = frozenset({"DEFERRED_POST_INITIAL_DEMO_LOOP"})
_STATES = frozenset({"READY"}) | _COMPLETED_STATES | _PARKED_STATES | _DEFERRED_STATES


class DeliveryQueueError(ValueError):
    """The autonomous delivery queue cannot safely be interpreted."""


def validate_queue(queue: dict[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(queue, dict) or set(queue) != {"schema_version", "purpose", "packages"}:
        raise DeliveryQueueError("queue schema is invalid")
    if queue["schema_version"] != QUEUE_SCHEMA_VERSION or not isinstance(queue["purpose"], str):
        raise DeliveryQueueError("queue identity is invalid")
    packages = queue["packages"]
    if not isinstance(packages, list) or not packages:
        raise DeliveryQueueError("queue packages are invalid")
    seen: set[str] = set()
    for package in packages:
        if not isinstance(package, dict) or set(package) != _PACKAGE_FIELDS:
            raise DeliveryQueueError("package schema is invalid")
        package_id = package["id"]
        if not isinstance(package_id, str) or not package_id or package_id in seen:
            raise DeliveryQueueError("package IDs must be unique non-empty strings")
        seen.add(package_id)
        if package["wave"] not in {"W1", "W2", "W3"} or package["state"] not in _STATES:
            raise DeliveryQueueError("package wave or state is invalid")
        if not isinstance(package["title"], str) or not package["title"]:
            raise DeliveryQueueError("package title is invalid")
        if not isinstance(package["formal_milestone"], str) or not package["formal_milestone"]:
            raise DeliveryQueueError("package formal milestone is invalid")
        if not isinstance(package["requires"], list) or not all(isinstance(item, str) and item for item in package["requires"]):
            raise DeliveryQueueError("package requirements are invalid")
        if package["execution_authority"] is not False:
            raise DeliveryQueueError("delivery packages cannot grant execution authority")
    return packages


def select_next(queue: dict[str, Any], project_state: dict[str, Any]) -> dict[str, Any]:
    """Return the first ready non-executing package and all parked reasons."""
    packages = validate_queue(queue)
    milestones = project_state.get("milestones")
    if not isinstance(milestones, dict):
        raise DeliveryQueueError("project milestone state is invalid")
    # A reviewed-complete disabled package can meet a delivery dependency, but
    # it is never selected: selection admits only explicit READY packages.
    completed = {item["id"] for item in packages if item["state"] in _COMPLETED_STATES}
    ready = [item for item in packages if item["state"] == "READY" and all(
        requirement in completed or not requirement.startswith(("W1-", "W2-", "W3-"))
        for requirement in item["requires"]
    )]
    parked = [{"id": item["id"], "state": item["state"], "requires": item["requires"]}
              for item in packages if item["state"].startswith("PARKED_")]
    active = project_state.get("current_milestone")
    active_state = milestones.get(active, {}).get("status") if isinstance(active, str) else None
    return {
        "schema_version": QUEUE_SCHEMA_VERSION,
        "formal_milestone": active,
        "formal_milestone_status": active_state,
        "next_package": ready[0] if ready else None,
        "parked_packages": parked,
        "execution_authority": False,
    }
