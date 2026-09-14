import json
from pathlib import Path
import subprocess
import sys

import pytest

from tests.test_h_slow_order_preparation import edge_sizing_result, limits, market, prepared_plan, primary_context
from tests.test_h_slow_decision import monthly_snapshot


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/h_slow_prepare.py"


def invoke(path):
    return subprocess.run([sys.executable, str(SCRIPT), str(path)],
                          capture_output=True, text=True, cwd=path.parent)


def test_preparation_cli_preserves_inputs_and_never_routes(tmp_path):
    path = tmp_path / "preparation.json"
    lifecycle_plan, event_eligibility, research_decision = prepared_plan()
    raw = json.dumps({"lifecycle_plan": lifecycle_plan, "market_inputs": market(), "limits": limits(),
                      "event_eligibility": event_eligibility, "research_decision": research_decision,
                      "primary_context": primary_context(), "edge_sizing_result": edge_sizing_result(
                          decision_at_utc=research_decision["decision_at_utc"],
                          research_decision_sha256=lifecycle_plan["decision_sha256"],
                          strategy_policy_version=research_decision["policy_version"])}).encode()
    path.write_bytes(raw)
    result = invoke(path)
    assert result.returncode == 0, result.stderr
    output = json.loads(result.stdout)
    assert output["outcome"] == "PREPARED_DISABLED"
    assert output["planned_total_loss_aud"] == 2.25
    assert output["execution_authority"] is False
    assert output["submission_status"] == "DISABLED_NOT_ROUTED"
    assert path.read_bytes() == raw


@pytest.mark.parametrize("raw", ['{}', '{"limits":{},"limits":{}}', '{"limits":NaN}'])
def test_bad_cli_inputs_have_no_success_output(tmp_path, raw):
    path = tmp_path / "bad.json"
    path.write_text(raw)
    result = invoke(path)
    assert result.returncode == 2
    assert not result.stdout
    assert "Traceback" not in result.stderr


def derived_payload():
    quote = market()
    del quote["technical_stop_price"]
    lifecycle_plan, event_eligibility, research_decision = prepared_plan()
    return {"lifecycle_plan": lifecycle_plan, "market_inputs": quote, "limits": limits(),
            "protection_snapshot": monthly_snapshot(), "event_eligibility": event_eligibility,
            "research_decision": research_decision, "primary_context": primary_context(),
            "edge_sizing_result": edge_sizing_result(
                decision_at_utc=research_decision["decision_at_utc"],
                research_decision_sha256=lifecycle_plan["decision_sha256"],
                strategy_policy_version=research_decision["policy_version"])}


def test_snapshot_protection_connects_to_disabled_sizing(tmp_path):
    path = tmp_path / "derived.json"
    path.write_text(json.dumps(derived_payload()))
    result = invoke(path)
    assert result.returncode == 0, result.stderr
    output = json.loads(result.stdout)
    assert output["outcome"] == "PREPARED_DISABLED"
    assert output["execution_authority"] is False
    assert output["derived_protection"]["execution_authority"] is False
    assert output["derived_protection"]["rule"]["rule_id"] == "hslow-atr20x3-v1"
    assert output["derived_protection"]["snapshot_artifact_sha256"] == monthly_snapshot()["artifact_sha256"]


@pytest.mark.parametrize("case", ["stop_override", "wrong_decision", "direction", "future_decision", "expired"])
def test_derived_protection_refuses_inconsistent_inputs(tmp_path, case):
    payload = derived_payload()
    if case == "stop_override":
        payload["market_inputs"]["technical_stop_price"] = "1.0"
    elif case == "wrong_decision":
        payload["lifecycle_plan"]["decision_sha256"] = "sha256:" + "0" * 64
    elif case == "direction":
        payload["lifecycle_plan"]["intent"]["direction"] = "SELL"
    elif case == "future_decision":
        payload["market_inputs"]["observed_at_utc"] = "2026-08-31T12:00:00Z"
    else:
        payload["market_inputs"]["evaluated_at_utc"] = "2026-10-01T12:00:00Z"
    path = tmp_path / "derived.json"
    path.write_text(json.dumps(payload))
    result = invoke(path)
    assert result.returncode == 2
    assert not result.stdout
    assert "Traceback" not in result.stderr


def test_derived_protection_accepts_verified_optional_event_annotation(tmp_path):
    from forex.h_slow_decision import attach_event_context, evaluate_h_slow_snapshot
    from forex.h_slow_lifecycle import plan_h_slow_lifecycle
    from forex.event_annotations import event_annotation
    from forex.event_quality import qualify_events
    from tests.test_h_slow_lifecycle import registry, observation
    from tests.test_h_slow_decision import DECISION
    payload = derived_payload()
    decision = evaluate_h_slow_snapshot(payload["protection_snapshot"], decision_at_utc=DECISION)
    annotation = event_annotation(qualify_events([], DECISION), decision_at_utc=DECISION,
        window_start_utc=DECISION, window_end_utc="2026-09-02T12:00:00Z")
    decision = attach_event_context(decision, annotation)
    from forex.h_slow_event_eligibility import build_h_slow_event_eligibility
    payload["research_decision"] = decision
    payload["event_eligibility"] = build_h_slow_event_eligibility(
        decision, primary_context=primary_context(), entry_status="ALLOW",
        policy_version="forex.event-risk.disabled.v1",
    )
    payload["lifecycle_plan"] = plan_h_slow_lifecycle(research_decision=decision,
        reconciliation_observation=observation(), stream_registry=registry())
    payload["edge_sizing_result"] = edge_sizing_result(
        decision_at_utc=decision["decision_at_utc"],
        research_decision_sha256=payload["lifecycle_plan"]["decision_sha256"],
        strategy_policy_version=decision["policy_version"],
    )
    path = tmp_path / "annotated.json"
    path.write_text(json.dumps(payload))
    result = invoke(path)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["outcome"] == "PREPARED_DISABLED"
    payload["research_decision"]["event_annotation"]["coverage"] = "CLEAR"
    path.write_text(json.dumps(payload))
    result = invoke(path)
    assert result.returncode == 2
    assert not result.stdout
