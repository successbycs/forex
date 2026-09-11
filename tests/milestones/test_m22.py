from pathlib import Path

from forex.simulated_risk import drill, evaluate, load_policy


ROOT = Path(__file__).resolve().parents[2]


def test_m22_offline_risk_drill_enforces_every_declared_limit():
    result = drill(ROOT)
    outcomes = {item["intent_id"]: item for item in result["results"]}
    assert outcomes["allowed"]["outcome"] == "APPROVE_SIMULATION"
    assert outcomes["allowed"]["order_submission"] == "STRUCTURALLY_DISABLED"
    assert outcomes["position"]["reasons"] == ["ONE_POSITION_LIMIT"]
    assert outcomes["loss"]["reasons"] == ["LOSS_LIMIT"]
    assert outcomes["spread"]["reasons"] == ["SPREAD_LIMIT"]
    assert outcomes["cutoff"]["reasons"] == ["MANDATORY_FLAT_BY_CUTOFF"]
    assert outcomes["event"]["reasons"] == ["SCHEDULED_EVENT_BLACKOUT"]


def test_m22_rejects_event_context_unavailable_at_decision_time():
    policy, digest = load_policy(ROOT)
    result = evaluate({"intent_id": "future-event", "instrument": "EUR/USD", "decision_at_utc": "2026-09-11T12:00:00Z", "planned_exit_at_utc": "2026-09-11T12:05:00Z", "open_positions": 0, "planned_loss_aud": 1.0, "spread_points": 1.0, "qualified_events": [{"scheduled_at_utc": "2026-09-11T13:00:00Z", "available_at_utc": "2026-09-11T12:01:00Z"}]}, policy=policy, policy_sha256=digest)
    assert result["outcome"] == "REFUSE"
    assert result["reasons"] == ["UNQUALIFIED_EVENT_CONTEXT"]
