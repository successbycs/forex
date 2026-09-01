from forex.regime import classify_context, classify_regime, event_window, session_contract


CONFIG={"intraday_session":{"contract_version":"eurusd-intraday-session.v1","decision_time_utc":"08:00","flat_by_time_utc":"20:00","daylight_saving_policy":"UTC_FIXED","scheduled_event_blackout_minutes":60}}


def test_m14_regimes_and_event_blackout_are_deterministic():
    bars=[{"close":1.10,"high":1.101,"low":1.099},{"close":1.104,"high":1.105,"low":1.103}]
    assert classify_regime(bars)=="TRENDING"
    assert event_window("2026-08-28T08:00:00Z", [{"scheduled_at_utc":"2026-08-28T08:30:00Z"}], 60)=="EVENT_BLACKOUT"
    assert classify_context(bars,"2026-08-28T08:00:00Z",[],CONFIG)["event_window"]=="NO_SCHEDULED_EVENT_BLACKOUT"
    assert session_contract(CONFIG)["daylight_saving_policy"]=="UTC_FIXED"
