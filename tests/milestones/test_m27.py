def test_m27_uses_only_the_fixed_read_only_demo_listener_status_surface():
    source=open('scripts/t480_adapter.py').read()
    assert 'm20_listener_status' in source and 'GOMarketsMU-Live' in source
    capture=open('scripts/capture_m27_evidence.sh').read()
    assert 'm20_listener_status' in capture
    assert 'position-protection identifiers and prices' in capture


def test_m27_verifier_binds_tick_proof_to_raw_read_only_listener_response():
    verifier=open('scripts/verify_m27_evidence.sh').read()
    for requirement in (
        "outer['operation']=='m20_listener_status'",
        "outer['approval_required'] is False",
        "result['execution']['status']=='NOT_SUBMITTED'",
        "t['assessment_captured_at_utc']==result['captured_at_utc']",
        "t['quote_server']==quote['server']",
    ):
        assert requirement in verifier
