from __future__ import annotations

import copy

import pytest

from forex.stream_isolation import (
    DEMO_SERVER,
    StreamIsolationError,
    assert_registry_fingerprint,
    validate_stream_registry,
)


def valid_registry() -> dict:
    def record(stream_id: str, suffix: str, deployment_state: str) -> dict:
        return {
            "stream_id": stream_id,
            "server": DEMO_SERVER,
            "account_scope": f"demo_scope_{suffix}",
            "terminal_instance": f"terminal_instance_{suffix}",
            "namespaces": {
                "state_namespace": f"state_{suffix}",
                "monitor_namespace": f"monitor_{suffix}",
                "lease_namespace": f"lease_{suffix}",
                "reservation_namespace": f"reservation_{suffix}",
                "outcome_namespace": f"outcome_{suffix}",
            },
            "deployment_state": deployment_state,
            "account_selection": "NOT_SELECTED",
            "execution_capability": "NOT_EXPOSED",
        }

    return {
        "schema_version": "forex.stream-isolation.v1",
        "streams": [
            record("M1", "m1", "RETAINED_EXISTING_OPERATION"),
            record("H_SLOW", "hslow", "NOT_DEPLOYED"),
        ],
    }


def test_valid_plan_is_deterministic_isolated_and_exposes_no_execution_capability():
    registry = valid_registry()
    first = validate_stream_registry(registry)
    second = validate_stream_registry(copy.deepcopy(registry))

    assert first.status == "ISOLATED_DISABLED_PLAN"
    assert first.registry_fingerprint == second.registry_fingerprint
    assert first.as_dict()["streams"] == [
        {
            "stream_id": "M1",
            "isolation_status": "EXISTING_OWNER_UNCHANGED",
            "deployment_state": "RETAINED_EXISTING_OPERATION",
            "execution_capability": "NOT_EXPOSED",
        },
        {
            "stream_id": "H_SLOW",
            "isolation_status": "ISOLATED_DISABLED",
            "deployment_state": "NOT_DEPLOYED",
            "execution_capability": "NOT_EXPOSED",
        },
    ]


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("account_scope", "demo_scope_m1", "duplicate account_scope"),
        ("terminal_instance", "terminal_instance_m1", "duplicate terminal_instance"),
    ],
)
def test_rejects_duplicate_account_or_terminal_targets(field: str, value: str, message: str):
    registry = valid_registry()
    registry["streams"][1][field] = value
    with pytest.raises(StreamIsolationError, match=message):
        validate_stream_registry(registry)


def test_rejects_duplicate_namespace_target():
    registry = valid_registry()
    registry["streams"][1]["namespaces"]["lease_namespace"] = "lease_m1"
    with pytest.raises(StreamIsolationError, match="duplicate namespace"):
        validate_stream_registry(registry)


def test_rejects_namespace_collision_within_one_stream():
    registry = valid_registry()
    registry["streams"][1]["namespaces"]["monitor_namespace"] = "state_hslow"
    with pytest.raises(StreamIsolationError, match="duplicate namespace within H_SLOW"):
        validate_stream_registry(registry)


def test_rejects_live_or_non_demo_server():
    registry = valid_registry()
    registry["streams"][1]["server"] = "GOMarketsMU-Live"
    with pytest.raises(StreamIsolationError, match="Live is forbidden"):
        validate_stream_registry(registry)
    registry["streams"][1]["server"] = "some-other-demo"
    with pytest.raises(StreamIsolationError, match="GOMarketsMU-Demo"):
        validate_stream_registry(registry)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("deployment_state", "ACTIVE", "H_SLOW must remain"),
        ("execution_capability", "ORDER_SUBMISSION", "cannot expose execution"),
        ("account_selection", "SELECT_SAVED_LOGIN", "cannot select an account"),
    ],
)
def test_rejects_hslow_activation_or_implied_authority(field: str, value: str, message: str):
    registry = valid_registry()
    registry["streams"][1][field] = value
    with pytest.raises(StreamIsolationError, match=message):
        validate_stream_registry(registry)


def test_rejects_unknown_stream_and_authority_bearing_extra_fields():
    registry = valid_registry()
    registry["streams"][1]["stream_id"] = "H_FAST"
    with pytest.raises(StreamIsolationError, match="unsupported stream ID"):
        validate_stream_registry(registry)
    registry = valid_registry()
    registry["streams"][1]["mt5_login"] = "not-permitted"
    with pytest.raises(StreamIsolationError, match="unsupported mt5_login"):
        validate_stream_registry(registry)


def test_fingerprint_detects_mutated_declaration_and_plan_is_a_snapshot():
    registry = valid_registry()
    plan = validate_stream_registry(registry)
    registry["streams"][1]["namespaces"]["outcome_namespace"] = "outcome_changed"

    assert plan.as_dict()["registry_fingerprint"] != validate_stream_registry(registry).registry_fingerprint
    with pytest.raises(StreamIsolationError, match="fingerprint mismatch"):
        assert_registry_fingerprint(registry, plan.registry_fingerprint)
