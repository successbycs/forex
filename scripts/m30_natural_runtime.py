"""Read-only binding of natural evidence to the approved Interactive runtime."""
from datetime import timedelta
import hashlib
import re
import subprocess

from m30_natural_sources import require, read_output, strict_json
import m20_demo_evidence_contract as m20


def validate_runtime(bundle, joined, *, root, fingerprint, captured, approval):
    require(approval.get('task_id') == 'M30-DEMO-MVP-UNBLOCKING', 'wrong topology authority record')
    items = [item for item in approval.get('items', []) if item.get('id') == 'm29-applicability']
    require(len(items) == 1 and items[0].get('state') == 'DONE'
            and 'Chris explicitly approved' in '\n'.join(items[0].get('evidence', []))
            and 'Interactive' in approval.get('authorization', '')
            and 'disabled-watchdog' in approval.get('authorization', ''), 'missing retained Interactive exception')
    observations = {}
    for name, operation in [('listener-diagnostics.json', 'm20_listener_diagnostics'),
                             ('listener-status.json', 'm20_listener_status'),
                             ('terminal-identity.json', 'm20_listener_terminal_identity'),
                             ('watchdog-status.json', 'm20_listener_watchdog_status')]:
        raw = (bundle / name).read_bytes()
        wrapper = strict_json(raw)
        require(wrapper.get('configuration_fingerprint') == fingerprint, 'runtime observation configuration mismatch')
        result = wrapper.get('result', {})
        started = m20.utc(result.get('started_at'), 'operation started')
        finished = m20.utc(result.get('finished_at'), 'operation finished')
        require(captured - timedelta(seconds=120) <= started <= finished <= captured,
                'runtime wrapper observation stale or future-dated')
        m20.ensure_no_live_reference(wrapper)
        observations[name] = read_output(raw, operation, tool_id='forex_t480')
    diagnostics, status = observations['listener-diagnostics.json'], observations['listener-status.json']
    identity, watchdog = observations['terminal-identity.json'], observations['watchdog-status.json']
    require(diagnostics.get('task_state') == 'Running' and diagnostics.get('logon_type') == 'Interactive'
            and diagnostics.get('maintenance_hold_present') is False, 'approved Interactive runtime not running unheld')
    require(status.get('running') is True and status.get('state') in {'RUNNING', 'WAITING_FOR_FRESH_MT5_QUOTE'}
            and status.get('monitor', {}).get('state') in {'IDLE', 'RUNNING'}, 'listener or monitor unhealthy')
    require(status.get('release_id') == identity.get('listener_release_id') == joined['listener_release_id'],
            'capture spans different listener releases')
    for value, age in [(status.get('heartbeat_at_utc'), 30), (diagnostics.get('captured_at_utc'), 60)]:
        require(timedelta(0) <= captured - m20.utc(value, 'runtime timestamp') <= timedelta(seconds=age),
                'runtime observation stale or future-dated')
    binding = diagnostics.get('deployment_binding', {})
    revision = joined['receipt']['application_revision']
    require(isinstance(revision, str) and re.fullmatch('[0-9a-f]{40}', revision), 'runtime revision malformed')
    require(binding.get('observation') == 'VALID' and binding.get('application_revision') == revision
            and binding.get('configuration_fingerprint') == fingerprint
            == joined['source']['assessment']['configuration_fingerprint'], 'deployed identity mismatch')
    hashes = binding.get('payload_sha256', {})
    runtime_sources = {}
    for name in ('m20_demo_listener_service', 'm20_demo_trading_session',
                 'm20_postgres_audit_bridge', 'm20_discord_trade_notification'):
        relative = f't480/{name}.py'
        committed = subprocess.check_output(['git', 'show', f'{revision}:{relative}'], cwd=root)
        digest = 'sha256:' + hashlib.sha256(committed).hexdigest()
        require((root / relative).read_bytes() == committed, 'runtime source differs from deployed revision')
        require(hashes.get(f'{name}.payload') == digest, 'deployed payload digest mismatch')
        runtime_sources[relative] = digest
    lease = binding.get('lease', {})
    for key, value in [('maximum_duration_minutes', 0), ('maximum_trades', None),
                       ('maximum_open_positions', 1), ('maximum_notional_per_trade_usd', 10000),
                       ('maximum_cumulative_notional_usd', 100000), ('maximum_loss_per_trade_aud', 100)]:
        require(key in lease and lease[key] == value, f'deployed lease control mismatch: {key}')
    financing = strict_json(binding.get('financing_policy'))
    require(financing.get('qualification_basis') == 'DEFERRED_FOR_DEMO'
            and financing.get('exit_mode') == 'EXISTING_OWNER_EXITS', 'Demo financing scope mismatch')
    require(identity.get('observation') == 'MAPPED' and identity.get('heartbeat_fresh') is True
            and identity.get('runtime_binding_fresh') is True and identity.get('task_state') == 'Running'
            and identity.get('broker_mutation') == 'NONE', 'terminal identity not mapped')
    terminal_binding = identity.get('runtime_binding', {})
    require(timedelta(0) <= captured - m20.utc(terminal_binding.get('captured_at_utc'), 'terminal binding time')
            <= timedelta(seconds=60), 'terminal runtime binding stale or future-dated')
    require(terminal_binding.get('server') == 'GOMarketsMU-Demo' and terminal_binding.get('currency') == 'AUD'
            and terminal_binding.get('state') == 'MAPPED', 'terminal account surface mismatch')
    for field in ('account_trade_allowed', 'account_trade_expert', 'submission_permitted',
                  'terminal_connected', 'terminal_trade_allowed'):
        require(terminal_binding.get(field) is True, f'terminal permission missing: {field}')
    require(terminal_binding.get('terminal_tradeapi_disabled') is False, 'terminal API disabled')
    terminals = identity.get('terminal_processes')
    require(isinstance(terminals, list) and len(terminals) == 1, 'terminal process not unique')
    terminal = terminals[0]
    require(terminal.get('matches_configured_terminal_path') is True
            and terminal.get('matches_connected_terminal_path') is True, 'terminal path mapping mismatch')
    path_hash = m20.sha256(terminal_binding.get('configured_terminal_path_sha256'), 'terminal path hash')
    require(path_hash == terminal_binding.get('connected_terminal_path_sha256')
            == terminal.get('executable_path_sha256'), 'terminal process path digest mismatch')
    processes = identity.get('listener_processes', [])
    listeners = [p for p in processes if p.get('process_id') == terminal_binding.get('listener_process_id')]
    require(len(listeners) == 1 and type(terminal.get('session_id')) is int and terminal['session_id'] > 0
            and listeners[0].get('session_id') == terminal['session_id'], 'listener/client desktop session mismatch')
    require(watchdog.get('installed') is True and watchdog.get('task') == 'Forex-M20-Listener-Watchdog'
            and watchdog.get('state') == 'Disabled' and watchdog.get('retired') is True,
            'legacy watchdog not disabled and retired')
    return {'lease': lease, 'runtime_revision': revision, 'runtime_sources': runtime_sources,
            'topology': 'Interactive; operator-managed single terminal; legacy watchdog retired'}
