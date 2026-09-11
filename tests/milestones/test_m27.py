def test_m27_uses_only_the_fixed_read_only_demo_tick_surface():
    source=open('scripts/t480_adapter.py').read()
    assert 'm20_listener_status' in source and 'GOMarketsMU-Live' in source
    capture=open('scripts/capture_m27_evidence.sh').read()
    assert 'm27_demo_tick' in capture
    assert 'EURUSD bid/ask' in capture


def test_m27_verifier_binds_tick_proof_to_raw_read_only_listener_response():
    verifier=open('scripts/verify_m27_evidence.sh').read()
    assert 'assert ' not in verifier
    for requirement in (
        "outer['operation']=='m27_demo_tick'",
        "outer['approval_required'] is False",
        "tick['bid']>0 and tick['ask']>=tick['bid']",
        "tick['broker_timestamp_offset_seconds']==10800",
        "0<=manifest_age<24*3600",
        "t['tick_time_msc']==tick['tick_time_msc']",
        "(bundle_capture-tick_at).total_seconds()<=15",
    ):
        assert requirement in verifier
