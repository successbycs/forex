"""Safety envelope of the fixed, observation-only feasibility task."""
from scripts import t480_adapter as adapter
from t480_core import build_ssh_command


def test_probe_is_bounded_and_preserves_production_tasks():
    adapter.validate_contract()
    operation = adapter.OPERATIONS['m33_unattended_probe_run']
    command = operation.powershell_command
    # Refuse before registering the disposable probe if runtime ownership or
    # maintenance prerequisites cannot be established.
    register = command.index('Register-ScheduledTask')
    for refusal in ('probe hash mismatch', 'maintenance hold required',
                    'disabled listener required', 'listener workers must be absent', 'existing MT5 S4U principal required',
                    'principal mismatch', 'one configured Session0 terminal required',
                    'terminal owner mismatch', 'probe already running'):
        assert command.index(refusal) < register
    for forbidden in ('Stop-Process', 'Stop-ScheduledTask', 'Enable-ScheduledTask',
                      'Disable-ScheduledTask', 'order_send', '--post-isolation-observe'):
        assert forbidden not in command
    assert "--session0" in command
    assert "-Minutes 1" in command
    assert "-MultipleInstances IgnoreNew" in command
    assert "$n='Forex-M33-Unattended-Probe-" in command
    assert 'Register-ScheduledTask -TaskName $n' in command


def test_probe_transport_and_read_only_receipt_surface():
    for name in ('m33_unattended_probe_run', 'm33_unattended_probe_status'):
        command = adapter.OPERATIONS[name].powershell_command
        assert len(build_ssh_command('OEM@192.168.0.210', command, adapter.TRANSPORT_SETTINGS)[-1]) < 7500
    status = adapter.OPERATIONS['m33_unattended_probe_status'].powershell_command
    assert 'observation-session0-*.json' in status
    assert 'Get-FileHash' in status
    assert 'Register-ScheduledTask' not in status
    assert 'Start-ScheduledTask' not in status
