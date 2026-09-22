from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from scripts.m30_natural_lifecycle import validate_trade  # establishes script imports
from m30_natural_sources import SourceError
from scripts.m30_natural_runtime import validate_runtime


@pytest.fixture
def runtime(tmp_path):
    revision, fingerprint, release = 'a' * 40, 'sha256:' + 'b' * 64, '0123456789abcdef'
    now = datetime.now(timezone.utc)
    sha = 'sha256:' + hashlib.sha256(b'synthetic runtime').hexdigest()
    names = ['m20_demo_listener_service', 'm20_demo_trading_session',
             'm20_postgres_audit_bridge', 'm20_discord_trade_notification']
    (tmp_path / 't480').mkdir()
    for name in names:
        (tmp_path / 't480' / f'{name}.py').write_bytes(b'synthetic runtime')
    lease = dict(maximum_duration_minutes=0, maximum_trades=None, maximum_open_positions=1,
                 maximum_notional_per_trade_usd=10000, maximum_cumulative_notional_usd=100000,
                 maximum_loss_per_trade_aud=100)
    diagnostics = dict(task_state='Running', logon_type='Interactive', maintenance_hold_present=False,
        captured_at_utc=now.isoformat(), deployment_binding=dict(observation='VALID', application_revision=revision,
        configuration_fingerprint=fingerprint, payload_sha256={f'{n}.payload': sha for n in names}, lease=lease,
        financing_policy=json.dumps(dict(qualification_basis='DEFERRED_FOR_DEMO', exit_mode='EXISTING_OWNER_EXITS'))))
    status = dict(running=True, state='RUNNING', monitor={'state': 'IDLE'},
                  protection_observation='NO_ACTIVE_PROTECTION_REQUIRED',
                  open_position_protection=None, release_id=release, heartbeat_at_utc=now.isoformat())
    identity = dict(observation='MAPPED', heartbeat_fresh=True, runtime_binding_fresh=True, task_state='Running',
        broker_mutation='NONE', listener_release_id=release,
        runtime_binding=dict(server='GOMarketsMU-Demo', currency='AUD', state='MAPPED',
            captured_at_utc=now.isoformat(),
            account_trade_allowed=True, account_trade_expert=True, submission_permitted=True,
            terminal_connected=True, terminal_trade_allowed=True, terminal_tradeapi_disabled=False,
            configured_terminal_path_sha256=sha, connected_terminal_path_sha256=sha, listener_process_id=1),
        terminal_processes=[dict(process_id=2, session_id=2, executable_path_sha256=sha,
            matches_configured_terminal_path=True, matches_connected_terminal_path=True)],
        listener_processes=[dict(process_id=1, session_id=2)])
    watchdog = dict(installed=True, task='Forex-M20-Listener-Watchdog', state='Disabled', retired=True)
    observations = {'listener-diagnostics.json': ('m20_listener_diagnostics', diagnostics),
                    'listener-status.json': ('m20_listener_status', status),
                    'terminal-identity.json': ('m20_listener_terminal_identity', identity),
                    'watchdog-status.json': ('m20_listener_watchdog_status', watchdog)}
    joined = dict(listener_release_id=release, receipt={'application_revision': revision},
                  source={'assessment': {'configuration_fingerprint': fingerprint}})
    arguments = dict(root=tmp_path, fingerprint=fingerprint, captured=now,
                     approval=dict(task_id='M30-DEMO-MVP-UNBLOCKING', authorization='Interactive disabled-watchdog',
                                   items=[dict(id='m29-applicability', state='DONE', evidence=['Chris explicitly approved'])]))

    def run():
        for name, (operation, value) in observations.items():
            (tmp_path / name).write_text(json.dumps(dict(tool_id='forex_t480', operation=operation, ok=True,
                configuration_fingerprint=fingerprint, result=dict(ok=True, exit_code=0, stdout=json.dumps(value),
                    started_at=now.isoformat(), finished_at=now.isoformat()))))
        with patch('scripts.m30_natural_runtime.subprocess.check_output', return_value=b'synthetic runtime'):
            return validate_runtime(tmp_path, joined, **arguments)
    return observations, arguments, run


def test_approved_interactive_binding(runtime):
    _, _, run = runtime
    result = run()
    assert result['runtime_revision'] == 'a' * 40
    assert result['continuous_session_controls']['mode'] == 'CONTINUOUS_CAP_CONSTRAINED_DEMO'


@pytest.mark.parametrize('name,change', [
    ('listener-diagnostics.json', lambda x: x.update(logon_type='S4U')),
    ('listener-diagnostics.json', lambda x: x['deployment_binding'].update(application_revision='c' * 40)),
    ('listener-status.json', lambda x: x.update(release_id='other')),
    ('listener-status.json', lambda x: x.update(heartbeat_at_utc='2020-01-01T00:00:00Z')),
    ('listener-status.json', lambda x: x.update(protection_observation='LAST_KNOWN_UNVERIFIED')),
    ('listener-status.json', lambda x: x.update(open_position_protection={'ticket': 1})),
    ('terminal-identity.json', lambda x: x['runtime_binding'].update(server='OTHER')),
    ('terminal-identity.json', lambda x: x['terminal_processes'].append(x['terminal_processes'][0])),
    ('terminal-identity.json', lambda x: x['terminal_processes'][0].update(session_id=0)),
    ('terminal-identity.json', lambda x: x['runtime_binding'].update(terminal_trade_allowed=False)),
    ('terminal-identity.json', lambda x: x['runtime_binding'].update(captured_at_utc='2020-01-01T00:00:00Z')),
    ('watchdog-status.json', lambda x: x.update(state='Ready')),
])
def test_runtime_bindings_fail_closed(runtime, name, change):
    observations, _, run = runtime
    change(observations[name][1])
    with pytest.raises(SourceError):
        run()


def test_missing_exception_refused(runtime):
    _, arguments, run = runtime
    arguments['approval']['items'] = []
    with pytest.raises(SourceError):
        run()


def test_active_monitor_requires_complete_observed_protection(runtime):
    observations, _, run = runtime
    status = observations['listener-status.json'][1]
    status.update(monitor={'state': 'RUNNING'}, protection_observation='OBSERVED_ACTIVE',
                  open_position_protection=dict(ticket=42, action='SELL', entry_price=1.1,
                                                stop_loss=1.2, take_profit=1.0))
    assert run()['runtime_revision'] == 'a' * 40
