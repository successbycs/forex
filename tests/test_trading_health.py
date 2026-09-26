from datetime import UTC, datetime, timedelta

import pytest

from forex import trading_health as th

NOW = datetime(2026, 9, 25, 1, 0, tzinfo=UTC)


def healthy(**kw):
    base = dict(
        boot_seconds=900, session_ok=True, managed_mt5_count=1, mt5_identity_ok=True,
        mt5_responding=True, permissions_ok=True, broker_connected=True, data_fresh=True,
        db_available=True, listener_present=True, listener_heartbeat_age_s=5,
        assessment_age_s=20, source_input_advancing=True, monitoring_fresh=True,
        exposure_flat=True, inflight_unresolved=False, risk_or_maintenance_hold=False,
        lease_valid=True, market_open=True,
    )
    base.update(kw)
    return th.Observation(**base)


def state(mode="RUN_DEMO", **kw):
    return th.classify(healthy(**kw), mode)


def test_healthy_ready_and_no_setup_is_not_a_failure():
    d = state()
    assert (d.state, d.entry_eligible, d.execution_capable) == (th.READY_FOR_ASSESSMENT, True, True)
    d = state(last_assessment_no_setup=True)
    assert d.state == th.HEALTHY_NO_SETUP and d.recommended_action == "NONE" and d.entry_eligible


@pytest.mark.parametrize("mode", [None, "", "run_demo", 1])
def test_missing_or_corrupt_intent_fences_entries(mode):
    d = th.classify(healthy(), mode)
    assert d.state == th.BLOCKED_POLICY and not d.entry_eligible


def test_operator_stop_and_monitor_only_survive_health():
    assert th.classify(healthy(listener_present=False), "STOPPED").state == th.STOPPED_BY_OPERATOR
    d = state("MONITOR_ONLY")
    assert d.state == th.MONITOR_ONLY and not d.entry_eligible


def test_observed_24_sept_outage_listener_absent_mt5_running():
    d = state(listener_present=False, listener_heartbeat_age_s=None)
    assert d.state == th.RECOVERING_LISTENER and d.recommended_action == "START_LISTENER"
    assert not d.entry_eligible


def test_startup_grace_then_recovery():
    assert state(boot_seconds=60, managed_mt5_count=0).state == th.STARTING
    d = state(boot_seconds=600, managed_mt5_count=0, exposure_flat=None)
    assert d.state == th.RECOVERING_MT5 and "EXPOSURE_UNKNOWN" in d.reasons
    assert d.recommended_action == "START_ONE_MT5"


def test_duplicate_recycle_only_when_flat_and_no_inflight():
    assert state(managed_mt5_count=3).recommended_action == "RECYCLE_MANAGED_SET_FLAT"
    for kw in ({"exposure_flat": False}, {"exposure_flat": None}, {"inflight_unresolved": None}):
        d = state(managed_mt5_count=2, **kw)
        assert d.state == th.EXPOSURE_RECOVERY_REQUIRED and d.recommended_action != "RECYCLE_MANAGED_SET_FLAT"


def test_unknown_process_is_ownership_incident_not_target():
    d = state(unattributable_mt5_count=1)
    assert d.state == th.BLOCKED_OWNERSHIP and d.recommended_action == "NONE"


def test_hung_worker_with_advancing_input_detected_but_stalled_input_is_not():
    assert state(assessment_age_s=300).state == th.RECOVERING_LISTENER
    assert state(assessment_age_s=300, source_input_advancing=False).state == th.READY_FOR_ASSESSMENT
    assert state(listener_heartbeat_age_s=45).reasons == ("LISTENER_HEARTBEAT_STALE",)


def test_dependencies_and_permissions_block_without_restart_storm():
    assert state(broker_connected=False).recommended_action == "BOUNDED_REPROBE"
    assert state(db_available=False).state == th.BLOCKED_DEPENDENCY
    assert state(permissions_ok=False).state == th.BLOCKED_POLICY
    assert state(mt5_identity_ok=None).state == th.BLOCKED_POLICY


def test_market_and_policy_holds():
    assert state(market_open=False).state == th.WAITING_MARKET
    assert state(market_open=None).state == th.BLOCKED_DEPENDENCY
    assert state(risk_or_maintenance_hold=True).state == th.BLOCKED_POLICY
    assert state(risk_or_maintenance_hold=None).state == th.BLOCKED_POLICY
    assert state(lease_valid=False).entry_eligible is False
    assert state(inflight_unresolved=True).state == th.RECOVERY_WAIT_INFLIGHT
    assert state(monitoring_fresh=False).state == th.RECONCILING


def test_session_and_clock_fail_closed():
    assert state(session_ok=None).state == th.BLOCKED_SESSION
    assert state(clock_trusted=False).state == th.BLOCKED_DEPENDENCY


def test_entry_eligible_only_in_two_states():
    d = th.HealthDecision(th.BLOCKED_POLICY, (), True, True)
    assert th._d(th.BLOCKED_POLICY, eligible=True).entry_eligible is False and d


def test_budget_three_per_window_spacing_and_no_reboot_reset():
    t = lambda s: NOW - timedelta(seconds=s)
    assert th.recovery_budget([], NOW, True) == (False, 0.0)
    assert th.recovery_budget([t(30)], NOW, True) == (False, 30.0)
    assert th.recovery_budget([t(400), t(150)], NOW, True) == (False, 0.0)
    assert th.recovery_budget([t(800), t(400), t(150)], NOW, True)[0] is True
    assert th.recovery_budget([t(1000), t(400), t(150)], NOW, True)[0] is False
    assert th.recovery_budget([], NOW, False)[0] is True
    assert th.recovery_budget([NOW + timedelta(seconds=5)], NOW, True)[0] is True
    assert th.classify(healthy(), "RUN_DEMO", budget_open=True).state == th.CIRCUIT_OPEN


def permit(**kw):
    p = {"boot_id": "b1", "generation": 7,
         "issued_at_utc": (NOW - timedelta(seconds=10)).isoformat(),
         "expires_at_utc": (NOW + timedelta(seconds=100)).isoformat()}
    p.update(kw)
    return p


def check(p, mode="RUN_DEMO", boot="b1", gen=7, now=NOW):
    return th.validate_entry_permit(p, boot, gen, mode, now)


def test_permit_valid_only_when_current_and_matching():
    assert check(permit()) == th.PermitDecision(True, "PERMIT_CURRENT")
    assert check(None).reason == "PERMIT_MISSING"
    assert check(permit(), mode="MONITOR_ONLY").reason == "INTENT_NOT_RUN_DEMO"
    assert check(permit(), boot="b2").reason == "PERMIT_WRONG_BOOT"
    assert check(permit(), gen=8).reason == "PERMIT_GENERATION_MISMATCH"
    assert check(permit(), now=NOW + timedelta(seconds=100)).reason == "PERMIT_EXPIRED"
    assert check(permit(), now=NOW - timedelta(seconds=60)).reason == "PERMIT_FROM_FUTURE"
    assert check(permit(expires_at_utc=(NOW + timedelta(seconds=500)).isoformat())).reason == "PERMIT_LIFETIME_INVALID"


@pytest.mark.parametrize("bad", [{"generation": True}, {"generation": "7"}, {"issued_at_utc": "x"},
                                 {"issued_at_utc": "2026-09-25T00:59:50"}, {"boot_id": None}])
def test_corrupt_permit_refused(bad):
    assert not check(permit(**bad)).valid


def test_schemas_validate_and_refuse_extra_authority_fields():
    import json
    from pathlib import Path
    from jsonschema import Draft202012Validator

    load = lambda n: json.loads(Path(f"config/schemas/trading-health-{n}.schema.json").read_text())
    for n in ("intent", "permit", "status"):
        Draft202012Validator.check_schema(load(n))
    permit_schema = Draft202012Validator(load("permit"))
    good = dict(schema_version="forex.trading-health-permit.v1", boot_id="b", generation=1,
                issued_at_utc="2026-09-25T01:00:00Z", expires_at_utc="2026-09-25T01:02:00Z", guardian_id="g")
    assert not list(permit_schema.iter_errors(good))
    assert list(permit_schema.iter_errors({**good, "order_authority": True}))
    intent = Draft202012Validator(load("intent"))
    assert list(intent.iter_errors({"schema_version": "forex.trading-health-intent.v1", "mode": "LIVE"}))
    status_states = set(load("status")["properties"]["state"]["enum"])
    assert status_states == {v for k, v in vars(th).items() if k.isupper() and isinstance(v, str) and k == v}
