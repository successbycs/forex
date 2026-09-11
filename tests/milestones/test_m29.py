def test_m29_is_a_bounded_nontrading_recovery_drill():
    capture = open('scripts/capture_m29_evidence.sh').read()
    verifier = open('scripts/verify_m29_evidence.sh').read()
    proof = open('docs/milestones/M29-proof.md').read()
    assert 'timeout 0.001s' in capture
    assert capture.count('execute --operation m27_demo_tick') == 3
    assert 'INTERRUPTED_CLIENT_SIDE' in capture
    assert 'STRUCTURALLY_DISABLED' in capture
    assert 'm20_listener_recover' not in capture
    assert 'FOREX_M29_EVIDENCE_VERIFIED' in verifier
    assert 'GOMarketsMU-Demo' in verifier
    assert 'restart' in proof.lower()
