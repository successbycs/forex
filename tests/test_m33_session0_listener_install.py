"""Safety envelope of the held Session 0 listener installer (M33.1)."""
import importlib.util
import re
from pathlib import Path

from scripts import t480_adapter as adapter
from t480_core import build_ssh_command

ROOT = Path(__file__).resolve().parents[1]
PAYLOAD = (ROOT / "t480" / "m33_listener_session0_install.ps1").read_text()
_spec = importlib.util.spec_from_file_location("apply_m33", ROOT / "scripts" / "apply_m33_session0_listener_install.py")
apply_m33 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(apply_m33)


def _operations():
    namespace = dict(vars(adapter))
    exec(compile(apply_m33.FUNCTION.rsplit("\n\nOPERATIONS.update", 1)[0], "<m33>", "exec"), namespace)
    return namespace[apply_m33.MARK]()


def test_every_guard_precedes_the_first_task_registration():
    register = PAYLOAD.index("Register-ScheduledTask")
    for guard in ("PREPARED_RELEASE_REQUIRED", "PAYLOAD_HASH_MISMATCH", "MAINTENANCE_HOLD_REQUIRED",
                  "LEGACY_WATCHDOG_MUST_BE_DISABLED", "LISTENER_MUST_NOT_BE_RUNNING",
                  "LISTENER_WORKERS_MUST_BE_ABSENT", "MT5_S4U_PRINCIPAL_REQUIRED",
                  "ONE_CONFIGURED_SESSION0_TERMINAL_REQUIRED"):
        assert PAYLOAD.index(guard) < register, guard


def test_installer_is_held_s4u_startup_with_verified_rollback():
    assert "-LogonType S4U" in PAYLOAD and "New-ScheduledTaskTrigger -AtStartup" in PAYLOAD
    assert "$principal = New-ScheduledTaskPrincipal -UserId $user" in PAYLOAD  # MT5 task principal, not a literal
    assert "-MultipleInstances IgnoreNew" in PAYLOAD and "-RestartCount 3" in PAYLOAD
    # the hold is re-read immediately around registration and start, and after the proof
    body = PAYLOAD[PAYLOAD.index("try {\n    Assert-Hold"):PAYLOAD.index("} catch {\n    $failure")]
    assert body.count("Assert-Hold") == 3
    assert body.index("Assert-Hold") < body.index("Register-ScheduledTask") < body.index("Assert-Hold", body.index("Register-ScheduledTask")) < body.index("Start-ScheduledTask")
    # success needs a new heartbeat after start, a running task and a live worker
    assert "$beat -gt $before" in body and "Get-Workers).Count -ge 1" in body and "-eq 'MAINTENANCE_HOLD'" in body
    restore = PAYLOAD[PAYLOAD.index("function Restore-Previous"):PAYLOAD.index("try {\n    Assert-Hold")]
    assert restore.index("Disable-ScheduledTask") < restore.index("Stop-Process") < restore.index("Register-ScheduledTask $task -Xml $previous")
    assert "RESTORE_NOT_CLEAN" in restore and "'Disabled'" in restore
    catch = PAYLOAD[PAYLOAD.index("} catch {\n    $failure"):]
    assert "Restore-Previous" in catch and "$failure" in catch and "RESTORE FAILED" in catch
    for forbidden in ("order_send", "Enable-ScheduledTask", "Remove-Item", "-Force | Out-Null\n    Remove"):
        assert forbidden not in PAYLOAD
    assert not re.search(r"Set-Content|Out-File|WriteAllText\(\$holdPath", PAYLOAD)
    assert "BLOCKED_BY_MAINTENANCE_HOLD" in PAYLOAD and "ACTIVE_UNDER_EXISTING_EXIT_POLICY" in PAYLOAD


def test_apply_script_is_independently_idempotent_for_adapter_and_catalog():
    text = (ROOT / "scripts" / "apply_m33_session0_listener_install.py").read_text()
    assert "adapter_done, catalog_done" in text and "if entry[\"id\"] not in present" in text


def test_operations_are_fixed_hash_bound_and_within_transport_limit():
    operations = _operations()
    assert list(operations) == apply_m33.NAMES
    for operation in operations.values():
        length = len(build_ssh_command("OEM@192.168.0.210", operation.powershell_command, adapter.TRANSPORT_SETTINGS)[-1])
        assert length < 7500
    run = operations["m33_listener_session0_install"].powershell_command
    assert "Get-FileHash" in run and "installer hash mismatch" in run
    assert run.index("Get-FileHash") < run.index("powershell.exe")
