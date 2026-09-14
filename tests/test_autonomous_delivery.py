from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from forex.autonomous_delivery import DeliveryQueueError, select_next, validate_queue

ROOT = Path(__file__).resolve().parents[1]


def queue() -> dict:
    return json.loads((ROOT / "docs/milestones/autonomous-delivery-queue.json").read_text(encoding="utf-8"))


def state() -> dict:
    return json.loads((ROOT / "project_state.json").read_text(encoding="utf-8"))


def test_critical_strategy_queue_truthfully_reports_only_governed_or_external_packages_after_local_delivery():
    assert validate_queue(queue())
    selection = select_next(queue(), state())
    assert selection["formal_milestone"] == "M29"
    assert selection["formal_milestone_status"] == "BLOCKED"
    assert selection["next_package"] is None
    assert {item["id"] for item in selection["parked_packages"]} == {
        "W1-M29-EXTERNAL-PROOF", "W1-M1-RELIABILITY-TRIAGE", "W3-HSLOW-DEMO-ACTIVATION",
        "W2-PRIMARY-EVENT-STRATEGY-CONTEXT",
    }
    assert selection["execution_authority"] is False


def test_unknown_or_execution_enabling_queue_fields_are_refused():
    invalid = copy.deepcopy(queue())
    invalid["packages"][0]["execution_authority"] = True
    with pytest.raises(DeliveryQueueError, match="execution authority"):
        validate_queue(invalid)
    invalid = copy.deepcopy(queue())
    invalid["packages"][0]["unexpected"] = True
    with pytest.raises(DeliveryQueueError, match="schema"):
        validate_queue(invalid)


def test_package_dependency_prevents_later_work_until_completed():
    queued = copy.deepcopy(queue())
    queued["packages"][1]["state"] = "READY"
    queued["packages"][0]["state"] = "COMPLETE"
    selection = select_next(queued, state())
    assert selection["next_package"]["id"] == "W1-M29-EXTERNAL-PROOF"


def test_reviewed_complete_disabled_package_satisfies_dependency_without_becoming_ready():
    queued = copy.deepcopy(queue())
    reviewed = next(item for item in queued["packages"] if item["id"] == "W3-HSLOW-CANONICAL-DISABLED-MANDATE")
    assert reviewed["state"] == "COMPLETE_REVIEWED_DISABLED"
    dependent = copy.deepcopy(reviewed)
    dependent.update({
        "id": "W3-HSLOW-LOCAL-DEPENDENT-CHECK",
        "title": "Dependent local disabled check",
        "state": "READY",
        "requires": [reviewed["id"]],
    })
    queued["packages"].append(dependent)
    selection = select_next(queued, state())
    assert selection["next_package"]["id"] == dependent["id"]
    assert all(item["state"] != "READY" for item in queued["packages"] if item["id"] == reviewed["id"])
    assert selection["execution_authority"] is False


def test_deployed_unknown_context_satisfies_only_a_non_execution_delivery_dependency():
    queued = copy.deepcopy(queue())
    observed = next(item for item in queued["packages"] if item["id"] == "W2-FIXED-POLICY-CALENDAR-COLLECTOR")
    assert observed["state"] == "DEPLOYED_OBSERVED_CONTEXT_UNKNOWN"
    dependent = copy.deepcopy(observed)
    dependent.update({
        "id": "W2-LOCAL-OBSERVATION-DEPENDENT-CHECK",
        "title": "Dependent non-trading observation check",
        "state": "READY",
        "requires": [observed["id"]],
    })
    queued["packages"].append(dependent)
    selection = select_next(queued, state())
    assert selection["next_package"]["id"] == dependent["id"]
    assert selection["execution_authority"] is False
