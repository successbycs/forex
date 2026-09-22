"""Bounded Windows feasibility probes must not contact the broker."""
import re
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import t480_adapter as adapter
from t480_core import build_ssh_command
from t480 import m30_single_client_probe as probe


def test_child_policy_probe_is_fixed_compiles_and_fits_transport():
    adapter.validate_contract()
    command = adapter.OPERATIONS['m30_child_process_policy_probe'].powershell_command
    code = re.search(r"-c '(.*)';exit", command, re.S).group(1).replace("''", "'")
    compile(code, '<probe>', 'exec')
    assert 'MetaTrader5' not in code
    assert 'initialize(' not in code
    assert 'SetProcessMitigationPolicy' in code and 'GetProcessMitigationPolicy' in code
    assert "r.value==1" in code
    assert "blocked=True if child_error==367 else None" in code
    assert len(build_ssh_command('OEM@192.168.0.210', command, adapter.TRANSPORT_SETTINGS)[-1]) < 7500


def test_interactive_probe_transport_and_catalog():
    adapter.validate_contract()
    for name, operation in adapter.OPERATIONS.items():
        if name.startswith(('m30_single_client_probe_', 'm30_single_client_post_isolation_')):
            assert len(build_ssh_command('OEM@192.168.0.210', operation.powershell_command, adapter.TRANSPORT_SETTINGS)[-1]) < 7500, name
    command = adapter.OPERATIONS['m30_single_client_probe_run'].powershell_command
    assert '-LogonType Interactive' in command
    assert 'GetOwnerSid' in command
    assert 'Stop-Process' not in command and 'Stop-ScheduledTask' not in command
    post_isolation = adapter.OPERATIONS['m30_single_client_post_isolation_probe_run'].powershell_command
    assert "former tasks must remain disabled" in post_isolation
    assert "--post-isolation" in post_isolation and "--post-isolation-observe" not in post_isolation
    assert 'worker absence unproven' in post_isolation
    assert 'sole visible terminal required' in post_isolation
    assert '$hold.enabled -ne $true' in post_isolation
    assert 'Start-ScheduledTask' in post_isolation
    observe = adapter.OPERATIONS['m30_single_client_post_isolation_observe_run'].powershell_command
    assert '--post-isolation-observe' in observe
    assert 'Forex-M30-Client-PostIsolation-Observe-' in observe
    assert 'sole visible terminal required' in observe
    race = adapter.OPERATIONS['m30_single_client_post_isolation_race_run'].powershell_command
    assert '--post-isolation-race' in race
    assert 'Forex-M30-Client-PostIsolation-Race-' in race
    assert 'sole visible terminal required' in race
    session0 = adapter.OPERATIONS['m30_session0_probe_run'].powershell_command
    assert '-LogonType S4U' in session0 and '--session0' in session0
    assert 'Stop-Process' not in session0 and 'Stop-ScheduledTask' not in session0


def fake_mt5():
    account = SimpleNamespace(server='GOMarketsMU-Demo', currency='AUD', login=1,
                              trade_allowed=True, trade_expert=True)
    terminal = SimpleNamespace(path=r'C:\MT5', data_path=r'C:\Profile', connected=True,
                               trade_allowed=True, tradeapi_disabled=False)
    calls = []
    api = SimpleNamespace(initialize=lambda **_: True, shutdown=lambda: calls.append('shutdown'),
                          account_info=lambda: account, terminal_info=lambda: terminal,
                          positions_get=lambda: (), orders_get=lambda: ())
    return api, account, terminal, calls


def test_probe_reports_permissions_and_exposure_without_order_api():
    api, _, _, calls = fake_mt5()
    scope = 'sha256:' + hashlib.sha256(b'GOMarketsMU-Demo:1').hexdigest()
    result = probe.observe(api, r'C:\MT5\terminal64.exe', scope)
    assert result['connection'] == 'OBSERVED'
    assert result['server'] == 'GOMarketsMU-Demo' and result['currency'] == 'AUD'
    assert result['positions_count'] == 0 and result['pending_orders_count'] == 0
    assert result['terminal_trade_allowed'] is True
    assert calls == ['shutdown']


def test_probe_source_binds_observation_to_current_config_and_listener_epoch():
    source = (Path(__file__).resolve().parents[1] / 't480/m30_single_client_probe.py').read_text(encoding='utf-8')
    assert "configuration_sha256" in source
    assert "listener_release_id" in source
    assert "--post-isolation-observe" in source and "ISOLATED_STATE_REQUIRED" in source


@pytest.mark.parametrize('field,value', [('server', 'GOMarketsMU-Live'), ('currency', 'USD'), ('login', 2)])
def test_wrong_account_refuses_before_exposure_query(field, value):
    api, account, _, calls = fake_mt5()
    setattr(account, field, value)
    def forbidden():
        pytest.fail('wrong-account exposure query')
    api.positions_get = api.orders_get = forbidden
    scope = 'sha256:' + hashlib.sha256(b'GOMarketsMU-Demo:1').hexdigest()
    assert probe.observe(api, r'C:\MT5\terminal64.exe', scope)['connection'] == 'UNAVAILABLE'
    assert calls == ['shutdown']


def test_unavailable_mt5_stops_without_querying_account():
    api = SimpleNamespace(initialize=lambda **_: False,
                          last_error=lambda: (-10005, 'private diagnostic text'))
    result = probe.observe(api, r'C:\MT5\terminal64.exe', 'scope')
    assert result['reason'] == 'INITIALIZE_FAILED'
    assert result['mt5_error_code'] == -10005
    assert 'private' not in str(result)


def test_exposure_unavailable_is_not_flat():
    api, _, _, _ = fake_mt5()
    api.positions_get = api.orders_get = lambda: None
    scope = 'sha256:' + hashlib.sha256(b'GOMarketsMU-Demo:1').hexdigest()
    result = probe.observe(api, r'C:\MT5\terminal64.exe', scope)
    assert result['positions_count'] is None and result['pending_orders_count'] is None


@pytest.mark.parametrize('change', ['none', 'future', 'malformed', 'naive', 'failed', 'mutation',
                                    'unrestricted', 'missing', 'duplicate', 'session0', 'wrong_path'])
def test_historical_isolation_requires_safe_current_observation(change):
    isolation = {'completed_at_utc': '2026-09-20T11:30:00Z', 'state': 'ISOLATED', 'broker_mutation': 'NONE'}
    path = r'C:\MT5\terminal64.exe'
    before = [{'session_id': 2, 'installation_exe_sha256': probe.digest(path)}]
    if change in {'future', 'malformed', 'naive'}:
        isolation['completed_at_utc'] = {'future': '2027-01-01T00:00:00Z', 'malformed': 'bad',
                                        'naive': '2026-09-20T11:30:00'}[change]
    if change == 'failed': isolation['state'] = 'FAILED'
    if change == 'mutation': isolation['broker_mutation'] = 'UNKNOWN'
    if change == 'missing': before = []
    if change == 'duplicate': before *= 2
    if change == 'session0': before[0]['session_id'] = 0
    if change == 'wrong_path': before[0]['installation_exe_sha256'] = 'wrong'
    assert probe.isolated_observation_allowed(isolation, before, path, 2,
        change != 'missing', datetime(2026, 9, 21, tzinfo=timezone.utc)) is (change in {'none', 'unrestricted'})


def test_race_mode_is_fixed_to_a_bounded_child_restricted_delay():
    source = (Path(__file__).resolve().parents[1] / 't480/m30_single_client_probe.py').read_text(encoding='utf-8')
    assert "--post-isolation-race" in source
    assert 'race_delay_seconds=30' in source
    assert 'restrict_child_creation=True, race_delay_seconds=0' in source
