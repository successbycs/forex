from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest

from forex.h_slow_readiness import HSlowReadinessError, evaluate_h_slow_readiness
from tests.test_h_slow_lifecycle import observation, registry
from tests.test_h_slow_order_preparation import market, limits, prepared_plan, primary_context
from tests.test_h_slow_decision import DECISION
from forex.h_slow_initial_trial import load_initial_trial


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "h_slow_readiness.py"


def payload(**changes):
    _, eligibility, decision = prepared_plan()
    value = {
        "schema_version": "forex.h-slow.readiness-input.v1",
        "research_decision": decision,
        "envelope": {"schema_version": "forex.h-slow.timed-observation.v1", "observed_at_utc": DECISION,
                     "received_at_utc": DECISION, "observation": observation()},
        "stream_registry": registry(), "evaluated_at_utc": DECISION,
        "maximum_observation_age_seconds": 30, "market_inputs": market(), "limits": limits(),
        "event_eligibility": eligibility, "primary_context": primary_context(),
        "initial_trial": load_initial_trial(ROOT / "config" / "h_slow_initial_trial.json"),
    }
    value.update(changes)
    return value


def test_local_readiness_connects_runtime_isolation_event_and_sizing_without_authority():
    first = evaluate_h_slow_readiness(payload())
    second = evaluate_h_slow_readiness(payload())
    assert first == second
    assert first["runtime"]["plan"]["stream_id"] == "H_SLOW"
    assert first["preparation"]["outcome"] == "PREPARED_DISABLED"
    assert first["readiness_state"] == "PREPARED_DISABLED_NO_ROUTING"
    assert first["execution_authority"] is False
    assert first["submission_status"] == "DISABLED_NOT_ROUTED"


def test_current_unavailable_primary_context_is_a_local_no_new_entry_outcome():
    from forex.primary_event_context import load_contract, qualify_context
    current = qualify_context(contract=load_contract(ROOT / "config" / "primary_event_context.json"), observations=[])
    result = evaluate_h_slow_readiness(payload(primary_context=current))
    assert result["readiness_state"] == "NO_NEW_ENTRY"
    assert result["preparation"] == {
        "schema_version": "forex.h-slow.order-preparation.v1", "outcome": "REFUSED",
        "reason": "EVENT_CONTEXT_UNAVAILABLE", "plan_sha256": result["preparation"]["plan_sha256"],
        "market_inputs_sha256": result["preparation"]["market_inputs_sha256"],
        "limits_sha256": result["preparation"]["limits_sha256"],
        "preparation_input_sha256": result["preparation"]["preparation_input_sha256"],
        "edge_sizing_result_sha256": None, "edge_policy_sha256": None, "edge_evidence_sha256": None,
        "initial_trial_sha256": result["preparation"]["initial_trial_sha256"],
        "execution_authority": False, "submission_status": "DISABLED_NOT_ROUTED",
    }


@pytest.mark.parametrize("change", [
    {"schema_version": "bad"},
    {"market_inputs": {"bad": True}},
])
def test_readiness_rejects_malformed_or_unknown_contract_inputs(change):
    with pytest.raises((HSlowReadinessError, ValueError)):
        evaluate_h_slow_readiness(payload(**change))


def test_readiness_turns_a_malformed_primary_context_into_no_new_entry():
    result = evaluate_h_slow_readiness(payload(primary_context={"bad": True}))
    assert result["readiness_state"] == "NO_NEW_ENTRY"
    assert result["preparation"]["reason"] == "EVENT_CONTEXT_INVALID"


def test_cli_preserves_local_input_and_rejects_duplicate_json_fields(tmp_path):
    input_path = tmp_path / "readiness.json"
    raw = json.dumps(payload()).encode()
    input_path.write_bytes(raw)
    result = subprocess.run([sys.executable, str(SCRIPT), str(input_path)], cwd=tmp_path, text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["readiness_state"] == "PREPARED_DISABLED_NO_ROUTING"
    assert input_path.read_bytes() == raw
    duplicate = tmp_path / "duplicate.json"
    duplicate.write_text('{"schema_version":"forex.h-slow.readiness-input.v1","schema_version":"bad"}')
    result = subprocess.run([sys.executable, str(SCRIPT), str(duplicate)], cwd=tmp_path, text=True, capture_output=True)
    assert result.returncode == 2
    assert not result.stdout


def test_readiness_surface_cannot_import_or_invoke_workers_broker_or_network_layers():
    source = (ROOT / "src" / "forex" / "h_slow_readiness.py").read_text()
    script = SCRIPT.read_text()
    forbidden = ("h_slow_worker", "h_slow_persistence", "psycopg", "mt5", "requests", "urllib", "subprocess", "socket")
    assert not any(term in source for term in forbidden)
    assert not any(term in script for term in ("h_slow_worker", "psycopg", "mt5", "requests", "urllib", "subprocess", "socket"))
