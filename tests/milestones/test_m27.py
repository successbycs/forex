def test_m27_uses_only_the_fixed_read_only_demo_listener_status_surface():
    source=open('scripts/t480_adapter.py').read()
    assert 'm20_listener_status' in source and 'GOMarketsMU-Live' in source
    capture=open('scripts/capture_m27_evidence.sh').read()
    assert 'm20_listener_status' in capture
    assert 'position-protection identifiers and prices' in capture
