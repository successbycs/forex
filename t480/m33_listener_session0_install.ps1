$ErrorActionPreference = 'Stop'
# M33.1 interim boot-start: install the prepared M20 listener as an S4U start-up
# task in the principal of the existing MT5 boot task.  The maintenance hold must
# be active before, and remain active after, so the listener can monitor open
# positions under the existing exit policy but cannot assess or enter.  This
# installer calls no order API and never edits the hold or any risk setting.
function Fail([string]$reason) { throw ('M33_SESSION0_INSTALL_REFUSED:' + $reason) }

$base = 'C:\ProgramData\ForexListener'
$state = Join-Path $base 'state'
$holdPath = Join-Path $state 'm20_demo_maintenance_hold.local.json'
$statusPath = Join-Path $state 'm20_demo_listener_status.local.json'
$task = 'Forex-M20-Demo-Listener'
$workerPattern = 'm20_demo_(listener_service|trading_session)[.]payload'

function Get-Workers { @(Get-CimInstance Win32_Process | Where-Object { $_.Name -match '^python(w)?\.exe$' -and $_.CommandLine -match $workerPattern }) }
function Assert-Hold {
    $h = Get-Content -Raw -LiteralPath $holdPath | ConvertFrom-Json
    if ($h.enabled -ne $true -or $h.schema_version -ne 'forex.m20.maintenance-hold.v1') { Fail 'MAINTENANCE_HOLD_REQUIRED' }
}

$config = Get-Content -Raw -LiteralPath (Join-Path $state 'm20_demo_listener_service.local.json') | ConvertFrom-Json
$prepared = Get-Content -Raw -LiteralPath (Join-Path $state 'm20_demo_listener_prepared.local.json') | ConvertFrom-Json
$releaseId = [string]$prepared.release_id
if ($releaseId -notmatch '^[0-9a-f]{16}$') { Fail 'PREPARED_RELEASE_REQUIRED' }
$payload = Join-Path $base ('releases\' + $releaseId + '\m20_demo_listener_service.payload')
if (!(Test-Path -LiteralPath $payload)) { Fail 'RELEASE_PAYLOAD_ABSENT' }
if (('sha256:' + (Get-FileHash -LiteralPath $payload -Algorithm SHA256).Hash.ToLower()) -ne [string]$prepared.service_sha256) { Fail 'PAYLOAD_HASH_MISMATCH' }

Assert-Hold
$watchdog = Get-ScheduledTask 'Forex-M20-Listener-Watchdog' -ErrorAction SilentlyContinue
if ($watchdog -and $watchdog.State.ToString() -ne 'Disabled') { Fail 'LEGACY_WATCHDOG_MUST_BE_DISABLED' }
$existing = Get-ScheduledTask $task
if ($existing.State.ToString() -eq 'Running') { Fail 'LISTENER_MUST_NOT_BE_RUNNING' }
if ((Get-Workers).Count -ne 0) { Fail 'LISTENER_WORKERS_MUST_BE_ABSENT' }
$probes = @(Get-ScheduledTask -ErrorAction SilentlyContinue | Where-Object { $_.TaskName -like 'Forex-M33-Unattended-Probe-*' -and $_.State.ToString() -in @('Running', 'Queued') })
if ($probes.Count -ne 0) { Fail 'PROBE_TASK_ACTIVE' }

$mt5 = Get-ScheduledTask 'CS AI Lab MT5 Start'
if ($mt5.Principal.LogonType.ToString() -ne 'S4U') { Fail 'MT5_S4U_PRINCIPAL_REQUIRED' }
$user = [string]$mt5.Principal.UserId
if ([string]::IsNullOrWhiteSpace($user) -or $user -match '^(SYSTEM|NT AUTHORITY\\.*|LOCAL SERVICE|NETWORK SERVICE)$') { Fail 'MT5_USER_PRINCIPAL_REQUIRED' }
$terminals = @(Get-CimInstance Win32_Process | Where-Object { $_.Name -in @('terminal.exe', 'terminal64.exe') })
if ($terminals.Count -ne 1 -or $terminals[0].SessionId -ne 0 -or $terminals[0].ExecutablePath -ne $config.terminal_path) { Fail 'ONE_CONFIGURED_SESSION0_TERMINAL_REQUIRED' }

$previous = Export-ScheduledTask $task
[IO.File]::WriteAllText((Join-Path $state 'previous-task.xml'), $previous, (New-Object Text.UTF8Encoding($false)))
$before = try { ([datetime]::Parse((Get-Content -Raw -LiteralPath $statusPath | ConvertFrom-Json).heartbeat_at_utc)).ToUniversalTime() } catch { [datetime]::MinValue }
$action = New-ScheduledTaskAction -Execute $config.python_path -Argument ('"' + $payload + '"')
$trigger = New-ScheduledTaskTrigger -AtStartup
$trigger.Delay = 'PT1M'
$principal = New-ScheduledTaskPrincipal -UserId $user -LogonType S4U -RunLevel Highest
$settings = New-ScheduledTaskSettingsSet -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

function Restore-Previous {
    Stop-ScheduledTask $task -ErrorAction SilentlyContinue
    Disable-ScheduledTask $task -ErrorAction SilentlyContinue | Out-Null
    foreach ($worker in (Get-Workers)) { Stop-Process -Id $worker.ProcessId -Force -ErrorAction SilentlyContinue }
    Start-Sleep 2
    Register-ScheduledTask $task -Xml $previous -Force | Out-Null
    Disable-ScheduledTask $task | Out-Null
    if ((Get-ScheduledTask $task).State.ToString() -ne 'Disabled' -or (Get-Workers).Count -ne 0) { throw 'RESTORE_NOT_CLEAN' }
}

try {
    Assert-Hold
    Register-ScheduledTask $task -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null
    Assert-Hold
    Start-ScheduledTask $task
    $deadline = (Get-Date).AddSeconds(60)
    $ok = $false
    while ((Get-Date) -lt $deadline -and -not $ok) {
        Start-Sleep 3
        $status = try { Get-Content -Raw -LiteralPath $statusPath | ConvertFrom-Json } catch { $null }
        if ($status -and (Get-ScheduledTask $task).State.ToString() -eq 'Running' -and (Get-Workers).Count -ge 1) {
            $beat = ([datetime]::Parse($status.heartbeat_at_utc)).ToUniversalTime()
            $age = ((Get-Date).ToUniversalTime() - $beat).TotalSeconds
            $ok = [string]$status.release_id -eq $releaseId -and $beat -gt $before -and $age -ge 0 -and $age -lt 30 -and $status.state -eq 'MAINTENANCE_HOLD'
        }
    }
    if (-not $ok) { Fail 'HELD_HEARTBEAT_NOT_FRESH_AFTER_START' }
    Assert-Hold
} catch {
    $failure = $_.Exception.Message
    try { Restore-Previous; $restored = 'previous task restored Disabled' } catch { $restored = 'RESTORE FAILED: ' + $_.Exception.Message }
    throw ('Session0 listener install held; ' + $restored + '; cause: ' + $failure)
}
$installed = Get-ScheduledTask $task
[pscustomobject]@{
    installed = $true
    release_id = $releaseId
    logon_type = $installed.Principal.LogonType.ToString()
    user = $user
    trigger = $installed.Triggers[0].CimClass.CimClassName
    state = $installed.State.ToString()
    heartbeat_state = $status.state
    entry_assessment = 'BLOCKED_BY_MAINTENANCE_HOLD'
    open_position_monitoring = 'ACTIVE_UNDER_EXISTING_EXIT_POLICY'
} | ConvertTo-Json -Compress
