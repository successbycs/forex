from scripts.listener_workflow_report import build_report, render_workflow


def fixture(action='NO_TRADE', assessment_id='new'):
    return {name: {'data': data, 'fetched_at_utc': '2026-09-22T06:00:00Z'} for name, data in {
        'status': {'state': 'RUNNING', 'last_result': {'proposal': {'proposal_id': 'new', 'action': action},
                   'execution': {'status': 'ACCEPTED' if action == 'BUY' else 'NOT_SUBMITTED'}},
                   'protection_observation': 'LAST_KNOWN_UNVERIFIED', 'open_position_protection': {'ticket': 12}},
        'assessment': {'observation': 'AVAILABLE', 'assessment': {'proposal': {'proposal_id': assessment_id}, 'risk_policy': {'entry_allowed': True}}},
        'account': {'error': 'offline'},
        'ledger': [{'attempt_id': 'older', 'lifecycle': 'OPEN_MONITORING', 'action': 'SELL'},
                   {'attempt_id': 'closed', 'lifecycle': 'CLOSED_MATCHED', 'realized_pnl_account': 0.55, 'account_currency': 'AUD'},
                   {'attempt_id': 'bad', 'lifecycle': 'CLOSED_MATCHED', 'reconciliation_status': 'RECONCILIATION_ERROR', 'realized_pnl_account': 99, 'account_currency': 'AUD'}],
    }.items()}


def test_no_trade_does_not_hide_older_open_trade_or_invent_exposure():
    report = build_report(fixture())
    text = render_workflow(report, 60)
    assert 'older' in text and 'MONITORING' in text and 'NO_TRADE' in text
    assert 'Broker positions observed: UNKNOWN' in text
    assert '+0.55 AUD' in text and '+99.00' not in text
    assert 'LAST_KNOWN_UNVERIFIED' in text
    assert all(len(line) <= 60 for line in text.splitlines())


def test_mismatched_assessment_cannot_supply_permission():
    report = build_report(fixture(assessment_id='other'))
    assert report['risk'] is None
    assert 'Risk entry permission: UNKNOWN' in render_workflow(report)


def test_accepted_execution_does_not_verify_retained_protection():
    text = render_workflow(build_report(fixture(action='BUY')))
    assert 'ACCEPTED' in text
    assert 'not a fresh broker protection check' in text


def test_missing_sources_and_rejection_render():
    assert 'UNKNOWN' in render_workflow(build_report({}))
    sources = fixture()
    sources['ledger']['data'] = [{'lifecycle': 'TERMINAL_REJECTED', 'attempt_id': 'rejected'}]
    text = render_workflow(build_report(sources))
    assert 'REJECTED' in text and 'N/A' in text


def test_stale_heartbeat_and_failed_ledger_are_prominent():
    sources = fixture()
    sources['status']['data']['heartbeat_at_utc'] = '2020-01-01T00:00:00Z'
    sources['ledger']['data'] = [{'error': 'database unavailable'}]
    text = render_workflow(build_report(sources))
    assert 'STALE listener heartbeat' in text
    assert text.index('ledger: UNAVAILABLE') < text.index('1. PRICE')


def test_unverified_open_row_cannot_display_numeric_profit():
    sources = fixture()
    sources['ledger']['data'] = [{'lifecycle': 'OPEN_MONITORING', 'realized_pnl_account': 88, 'account_currency': 'AUD'}]
    report = build_report(sources)
    assert report['trades'][0]['display_pnl'] == 'Pending'


def test_reconciliation_error_reason_survives_normal_close_reason():
    sources = fixture()
    sources['ledger']['data'] = [{'lifecycle': 'CLOSED_RECONCILIATION_ERROR',
                                 'close_reason': 'TAKE_PROFIT',
                                 'reconciliation_reason': 'unmatched broker deal'}]
    assert 'Reconciliation detail: unmatched broker deal' in render_workflow(build_report(sources))
