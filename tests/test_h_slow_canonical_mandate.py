from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from forex.h_slow_initial_trial import load_initial_trial
from forex.h_slow_trial_mandate import HSlowMandateError, validate_h_slow_trial_mandate
from forex.stream_isolation import StreamIsolationError, validate_stream_registry


ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "config" / "h_slow_stream_registry.json"
MANDATE_PATH = ROOT / "config" / "h_slow_trial_mandate.json"
INITIAL_TRIAL_PATH = ROOT / "config" / "h_slow_initial_trial.json"


def _load(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _initial_trial_limits() -> dict:
    trial = load_initial_trial(INITIAL_TRIAL_PATH)
    return {
        field: trial[field]
        for field in (
            "max_open_positions",
            "max_loss_aud",
            "max_notional_usd",
            "lease_budget_usd",
        )
    }


def _require_approved_limits(mandate: dict) -> None:
    """Guard this canonical declaration against its fixed human-approved caps."""
    if mandate.get("limits") != _initial_trial_limits():
        raise ValueError("canonical H_SLOW mandate limits drift from approved fixed trial caps")


def test_canonical_disabled_registry_and_pre_activation_mandate_validate():
    registry = _load(REGISTRY_PATH)
    mandate = _load(MANDATE_PATH)

    plan = validate_stream_registry(registry)
    result = validate_h_slow_trial_mandate(mandate, stream_registry=registry)

    assert plan.status == "ISOLATED_DISABLED_PLAN"
    assert plan.as_dict()["streams"] == [
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
    assert result["preflight_status"] == "PRE_ACTIVATION_MANDATE_VALIDATED"
    assert result["execution_authority"] is False
    _require_approved_limits(mandate)


@pytest.mark.parametrize(
    ("limit", "value"),
    [
        ("max_open_positions", 2),
        ("max_loss_aud", 1000.01),
        ("max_notional_usd", 10000.01),
        ("lease_budget_usd", 100000.01),
    ],
)
def test_canonical_mandate_cap_drift_is_detected(limit: str, value: float):
    registry = _load(REGISTRY_PATH)
    mandate = _load(MANDATE_PATH)
    mandate["limits"][limit] = value

    # The generic mandate validator permits human-owned positive caps.  This
    # canonical file is intentionally stricter: it declares only the fixed
    # initial trial approved by the operator.
    with pytest.raises(ValueError, match="approved fixed trial caps"):
        _require_approved_limits(mandate)
    if limit == "max_open_positions":
        with pytest.raises(HSlowMandateError, match="one position"):
            validate_h_slow_trial_mandate(mandate, stream_registry=registry)


def test_scope_drift_refuses_mandate_and_registry_collision_refuses():
    registry = _load(REGISTRY_PATH)
    mandate = _load(MANDATE_PATH)
    drifted_mandate = copy.deepcopy(mandate)
    drifted_mandate["account_scope"] = "other_demo_scope"
    with pytest.raises(HSlowMandateError, match="does not match"):
        validate_h_slow_trial_mandate(drifted_mandate, stream_registry=registry)

    drifted_registry = copy.deepcopy(registry)
    drifted_registry["streams"][1]["account_scope"] = "m1_demo_scope"
    with pytest.raises(StreamIsolationError, match="duplicate account_scope"):
        validate_stream_registry(drifted_registry)
