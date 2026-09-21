"""Bounded Windows feasibility probes must not contact the broker."""
import re
import hashlib
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
        if name.startswith('m30_single_client_probe_'):
            assert len(build_ssh_command('OEM@192.168.0.210', operation.powershell_command, adapter.TRANSPORT_SETTINGS)[-1]) < 7500, name
    command = adapter.OPERATIONS['m30_single_client_probe_run'].powershell_command
    assert '-LogonType Interactive' in command
    assert 'GetOwnerSid' in command
    assert 'Stop-Process' not in command and 'Stop-ScheduledTask' not in command
    post_isolation = adapter.OPERATIONS['m30_single_client_post_isolation_probe_run'].powershell_command
    assert "former tasks must remain disabled" in post_isolation
    assert "--post-isolation-observe" in post_isolation
    assert 'Start-ScheduledTask' in post_isolation
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
    api = SimpleNamespace(initialize=lambda **_: False)
    assert probe.observe(api, r'C:\MT5\terminal64.exe', 'scope')['reason'] == 'INITIALIZE_FAILED'


def test_exposure_unavailable_is_not_flat():
    api, _, _, _ = fake_mt5()
    api.positions_get = api.orders_get = lambda: None
    scope = 'sha256:' + hashlib.sha256(b'GOMarketsMU-Demo:1').hexdigest()
    result = probe.observe(api, r'C:\MT5\terminal64.exe', scope)
    assert result['positions_count'] is None and result['pending_orders_count'] is None
