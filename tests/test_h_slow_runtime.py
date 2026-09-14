import pytest

from forex.h_slow_lifecycle import HSlowLifecycleError
from forex.h_slow_runtime import evaluate_runtime_observation
from tests.test_h_slow_lifecycle import decision, observation, registry
from tests.test_h_slow_decision import DECISION


def envelope():
    return {"schema_version": "forex.h-slow.timed-observation.v1",
            "observed_at_utc": DECISION, "received_at_utc": DECISION,
            "observation": observation()}


def evaluate(value=None, **kwargs):
    return evaluate_runtime_observation(research_decision=decision(), envelope=value or envelope(),
        stream_registry=registry(), evaluated_at_utc=kwargs.get("now", DECISION),
        maximum_observation_age_seconds=kwargs.get("age", 30))


def test_current_observation_binds_plan_without_submission_authority():
    result = evaluate()
    assert result["plan"]["next_action"] == "OPEN"
    assert result["observation_age_seconds"] == 0
    assert result["execution_authority"] is False
    assert result == evaluate()


def test_unknown_reconciliation_stays_wait_even_when_clock_is_fresh():
    value = envelope()
    value["observation"]["reconciliation_status"] = "UNKNOWN"
    assert evaluate(value)["plan"]["next_action"] == "WAIT"


@pytest.mark.parametrize("age", [True, 0, -1, float("nan"), float("inf")])
def test_invalid_age_policy_rejected(age):
    with pytest.raises(HSlowLifecycleError, match="age"):
        evaluate(age=age)


def test_stale_observation_cannot_supply_flat_state():
    from datetime import datetime, timedelta
    later = (datetime.fromisoformat(DECISION.replace("Z", "+00:00")) + timedelta(seconds=31)).isoformat()
    with pytest.raises(HSlowLifecycleError, match="stale"):
        evaluate(now=later)


def test_age_limit_is_inclusive():
    from datetime import datetime, timedelta
    later = (datetime.fromisoformat(DECISION.replace("Z", "+00:00")) + timedelta(seconds=30)).isoformat()
    assert evaluate(now=later)["observation_age_seconds"] == 30


def test_expired_target_is_refused_even_with_fresh_observation():
    from datetime import datetime, timedelta
    next_month = (datetime.fromisoformat(DECISION.replace("Z", "+00:00")) + timedelta(days=32)).isoformat()
    value = envelope()
    value["observed_at_utc"] = value["received_at_utc"] = next_month
    with pytest.raises(HSlowLifecycleError, match="expired"):
        evaluate(value, now=next_month)


def test_reversed_receipt_clock_is_rejected():
    value = envelope()
    value["received_at_utc"] = "2000-01-01T00:00:00Z"
    with pytest.raises(HSlowLifecycleError, match="clocks"):
        evaluate(value)


def test_cli_uses_retained_inputs_without_mutation(tmp_path):
    import json
    from pathlib import Path
    import subprocess
    import sys
    path = tmp_path / "evaluation.json"
    raw = json.dumps({"research_decision": decision(), "envelope": envelope(),
        "stream_registry": registry(), "evaluated_at_utc": DECISION,
        "maximum_observation_age_seconds": 30})
    path.write_text(raw)
    command = Path(__file__).resolve().parents[1] / "scripts/h_slow_runtime.py"
    result = subprocess.run([sys.executable, str(command), str(path)], cwd=tmp_path,
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["plan"]["next_action"] == "OPEN"
    assert path.read_text() == raw
