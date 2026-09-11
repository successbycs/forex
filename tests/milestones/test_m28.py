import yaml


def test_m28_uses_fixed_read_only_tick_and_configured_spread_limit():
    capture = open('scripts/capture_m28_evidence.sh').read()
    verifier = open('scripts/verify_m28_evidence.sh').read()
    assert 'm27_demo_tick' in capture
    assert 'maximum_spread_points' in capture
    assert 'SPREAD_LIMIT' in capture
    assert 'GOMarketsMU-Demo' in verifier and 'FOREX_M28_EVIDENCE_VERIFIED' in verifier
    assert yaml.safe_load(open('config/risk.yaml'))['maximum_spread_points'] > 0
