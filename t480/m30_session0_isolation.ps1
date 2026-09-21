# Fixed, held-only Session 0 isolation experiment.  This is deliberately not a
# recovery launcher: on any failure it leaves the maintenance hold intact and
# never recreates either S4U task or terminal.
$ErrorActionPreference = 'Stop'

$state = 'C:\ProgramData\ForexListener\state'
$diagnostics = 'C:\ProgramData\ForexListener\diagnostics'
$run = [guid]::NewGuid().ToString('N')
$recordPath = Join-Path $state ('m30-session0-isolation-' + $run + '.json')
$record = [ordered]@{schema_version='forex.m30.session0-isolation.v1';run_id=$run;started_at_utc=(Get-Date).ToUniversalTime().ToString('o');broker_mutation='NONE';actions=@();state='STARTED'}

function Fail([string]$reason) { throw ('M30_ISOLATION_REFUSED:' + $reason) }
function Hash([string]$path) { 'sha256:' + (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLower() }
function Creation([object]$process) { ([datetime]$process.CreationDate).ToUniversalTime().ToFileTimeUtc() }
function Save([string]$outcome, [string]$reason = '') {
    $record.state = $outcome; $record.completed_at_utc = (Get-Date).ToUniversalTime().ToString('o')
    if ($reason) { $record.reason = $reason }
    $tmp = $recordPath + '.tmp'
    [IO.File]::WriteAllText($tmp, ($record | ConvertTo-Json -Compress -Depth 12), (New-Object Text.UTF8Encoding($false)))
    Move-Item -LiteralPath $tmp -Destination $recordPath -Force
}
function FreshJson([string]$directoryPattern, [string]$filePattern, [string]$namePattern) {
    $row = @(Get-ChildItem -LiteralPath $diagnostics -Directory -Filter $directoryPattern -ErrorAction Stop |
        ForEach-Object { Get-ChildItem -LiteralPath $_.FullName -File -Filter $filePattern -ErrorAction SilentlyContinue } |
        Where-Object { $_.Name -match $namePattern } | Sort-Object LastWriteTimeUtc -Descending | Select-Object -First 1)
    if ($row.Count -ne 1 -or $row[0].Length -le 0 -or $row[0].Length -gt 65536) { Fail 'FRESH_OBSERVATION_REQUIRED' }
    $age = ((Get-Date).ToUniversalTime() - $row[0].LastWriteTimeUtc.ToUniversalTime()).TotalSeconds
    if ($age -lt 0 -or $age -gt 120) { Fail 'FRESH_OBSERVATION_REQUIRED' }
    try { $value = Get-Content -Raw -LiteralPath $row[0].FullName | ConvertFrom-Json } catch { Fail 'FRESH_OBSERVATION_INVALID' }
    [pscustomobject]@{value=$value;sha256=(Hash $row[0].FullName);age_seconds=[math]::Round($age,3);file=$row[0].Name}
}
function SameTerminal([object]$current, [object]$observed) {
    return $null -ne $current -and [int]$current.ProcessId -eq [int]$observed.pid -and
        [int]$current.SessionId -eq [int]$observed.session_id -and
        [int64]((Creation $current) / 10000) -eq [int64]([int64]$observed.created_filetime / 10000)
}
function WaitNotRunning([string]$name) {
    for ($i=0; $i -lt 15; $i++) {
        if ((Get-ScheduledTask -TaskName $name -ErrorAction Stop).State.ToString() -ne 'Running') { return }
        Start-Sleep -Seconds 1
    }
    Fail 'TASK_DID_NOT_STOP'
}

try {
    $configPath = Join-Path $state 'm20_demo_listener_service.local.json'
    $statusPath = Join-Path $state 'm20_demo_listener_status.local.json'
    $holdPath = Join-Path $state 'm20_demo_maintenance_hold.local.json'
    if (!(Test-Path -LiteralPath $configPath) -or !(Test-Path -LiteralPath $statusPath) -or !(Test-Path -LiteralPath $holdPath)) { Fail 'LOCAL_STATE_REQUIRED' }
    $configHash = Hash $configPath; $config = Get-Content -Raw -LiteralPath $configPath | ConvertFrom-Json
    $status = Get-Content -Raw -LiteralPath $statusPath | ConvertFrom-Json
    $hold = Get-Content -Raw -LiteralPath $holdPath | ConvertFrom-Json
    $age = ((Get-Date).ToUniversalTime() - ([datetime]::Parse([string]$status.heartbeat_at_utc)).ToUniversalTime()).TotalSeconds
    if ($hold.enabled -ne $true -or $hold.schema_version -ne 'forex.m20.maintenance-hold.v1' -or $status.state -ne 'MAINTENANCE_HOLD' -or $age -lt 0 -or $age -ge 30) { Fail 'FRESH_HELD_IDLE_LISTENER_REQUIRED' }
    if ($null -ne $status.assessment_started_at_utc -or $status.monitor.state -ne 'IDLE' -or @($status.monitor.result.recovered).Count -ne 0) { Fail 'IN_FLIGHT_OR_UNRESOLVED_MONITOR_REQUIRED' }
    if ([string]$status.release_id -notmatch '^[0-9a-f]{16}$') { Fail 'CURRENT_RELEASE_REQUIRED' }
    $profile = [string]$config.FOREX_M20_ACCOUNT_EXECUTION_PROFILE | ConvertFrom-Json
    if ($profile.server -ne 'GOMarketsMU-Demo' -or $profile.currency -ne 'AUD' -or [string]::IsNullOrWhiteSpace($profile.account_scope_sha256)) { Fail 'APPROVED_PROFILE_REQUIRED' }

    $s0 = FreshJson 'single-client-*' 'observation-session0-*.json' '^observation-session0-[0-9a-f]{32}\.json$'
    $ui = FreshJson 'single-client-*' 'observation-*.json' '^observation-[0-9a-f]{32}\.json$'
    $ready = FreshJson 'single-client-runner-*' 'pre-isolation-*.json' '^pre-isolation-[0-9a-f]{32}\.json$'
    foreach ($sample in @($s0.value, $ui.value)) {
        if ($sample.state -ne 'OBSERVATION_COMPLETE' -or $sample.child_policy_verified -ne $true -or $sample.inventory_unchanged -ne $true -or $sample.configuration_sha256 -ne $configHash -or $sample.listener_release_id -ne $status.release_id) { Fail 'CURRENT_EPOCH_OBSERVATION_REQUIRED' }
        $o=$sample.observation
        if ($o.connection -ne 'OBSERVED' -or $o.server -ne 'GOMarketsMU-Demo' -or $o.currency -ne 'AUD' -or $o.account_scope_sha256 -ne $profile.account_scope_sha256 -or $o.terminal_connected -ne $true -or $o.positions_count -ne 0 -or $o.pending_orders_count -ne 0) { Fail 'FLAT_APPROVED_ACCOUNT_REQUIRED' }
    }
    if ($s0.value.session_id -ne 0 -or $s0.value.expected_session_id -ne 0 -or $ui.value.session_id -le 0 -or $ui.value.session_id -ne $ui.value.expected_session_id) { Fail 'SESSION_OBSERVATION_REQUIRED' }
    $r=$ready.value
    if ($r.marker -ne 'FOREX_M30_PRE_ISOLATION_READINESS' -or $r.clear -ne $true -or $r.durable_open_positions_count -ne 0 -or $r.unresolved_execution_attempts_count -ne 0 -or $r.broker_mutation -ne 'NONE') { Fail 'DURABLE_CLEAR_REQUIRED' }

    $record.evidence=[ordered]@{session0_observation_sha256=$s0.sha256;interactive_observation_sha256=$ui.sha256;durable_readiness_sha256=$ready.sha256;durable_readiness_provenance='FRESH_DATABASE_READ_NOT_CONFIG_BOUND'}
    $listener = Get-ScheduledTask -TaskName 'Forex-M20-Demo-Listener' -ErrorAction Stop
    $watchdog = Get-ScheduledTask -TaskName 'Forex-M20-Listener-Watchdog' -ErrorAction Stop
    $listenerAction = @($listener.Actions); $watchdogAction = @($watchdog.Actions)
    $listenerSid=(New-Object Security.Principal.NTAccount($listener.Principal.UserId)).Translate([Security.Principal.SecurityIdentifier]).Value
    $watchdogSid=(New-Object Security.Principal.NTAccount($watchdog.Principal.UserId)).Translate([Security.Principal.SecurityIdentifier]).Value
    $listenerPayload=Join-Path ('C:\ProgramData\ForexListener\releases\'+$status.release_id) 'm20_demo_listener_service.payload'
    $expectedListenerArgument='"'+$listenerPayload+'"'
    if ($listener.Principal.LogonType.ToString() -ne 'S4U' -or $watchdog.Principal.LogonType.ToString() -ne 'S4U' -or $listenerSid -ne $watchdogSid -or $listenerAction.Count -ne 1 -or $watchdogAction.Count -ne 1 -or $listenerAction[0].Execute -ne $config.python_path -or $listenerAction[0].Arguments -ne $expectedListenerArgument -or [IO.Path]::GetFileName([string]$watchdogAction[0].Execute).ToLowerInvariant() -ne 'schtasks.exe' -or $watchdogAction[0].Arguments -ne '/run /tn "Forex-M20-Demo-Listener"') { Fail 'TASK_IDENTITY_REQUIRED' }
    $listenerXml = Export-ScheduledTask -TaskName $listener.TaskName
    $watchdogXml = Export-ScheduledTask -TaskName $watchdog.TaskName
    $snapshotRoot = Join-Path $state ('m30-session0-isolation-' + $run)
    New-Item -ItemType Directory -Path $snapshotRoot -ErrorAction Stop | Out-Null
    $lp=Join-Path $snapshotRoot 'listener.xml';$wp=Join-Path $snapshotRoot 'watchdog.xml'
    [IO.File]::WriteAllText($lp,$listenerXml,(New-Object Text.UTF8Encoding($false)));[IO.File]::WriteAllText($wp,$watchdogXml,(New-Object Text.UTF8Encoding($false)))
    $record.snapshot=[ordered]@{listener_xml_sha256=(Hash $lp);watchdog_xml_sha256=(Hash $wp);listener_enabled=($listener.State.ToString() -ne 'Disabled');watchdog_enabled=($watchdog.State.ToString() -ne 'Disabled')};$record.actions += 'TASK_DEFINITIONS_SNAPSHOTTED'

    $terminals=@(Get-CimInstance Win32_Process | Where-Object { $_.Name -in @('terminal.exe','terminal64.exe') -and $_.ExecutablePath -eq $config.terminal_path })
    $zero=@($terminals|Where-Object {$_.SessionId -eq 0});$visible=@($terminals|Where-Object {$_.SessionId -gt 0})
    if($zero.Count -ne 1 -or $visible.Count -ne 1 -or !(SameTerminal $zero[0] (@($s0.value.before|Where-Object {$_.session_id -eq 0})[0])) -or !(SameTerminal $visible[0] (@($ui.value.before|Where-Object {$_.session_id -eq $ui.value.session_id})[0]))) { Fail 'TERMINAL_IDENTITY_CHANGED' }
    $record.terminals_before=@($terminals|ForEach-Object {[ordered]@{pid=[int]$_.ProcessId;session_id=[int]$_.SessionId;created_filetime=(Creation $_)}})

    Disable-ScheduledTask -TaskName $watchdog.TaskName -ErrorAction Stop | Out-Null; $record.actions += 'WATCHDOG_DISABLED'
    Disable-ScheduledTask -TaskName $listener.TaskName -ErrorAction Stop | Out-Null; $record.actions += 'LISTENER_DISABLED'
    if ($watchdog.State.ToString() -eq 'Running') { Stop-ScheduledTask -TaskName $watchdog.TaskName -ErrorAction Stop }
    if ($listener.State.ToString() -eq 'Running') { Stop-ScheduledTask -TaskName $listener.TaskName -ErrorAction Stop }
    WaitNotRunning $watchdog.TaskName; WaitNotRunning $listener.TaskName; $record.actions += 'TASKS_STOPPED'
    $servicePattern='*\ProgramData\ForexListener\releases\'+$status.release_id+'\m20_demo_listener_service.payload*'
    $runnerPattern='*\ProgramData\ForexListener\releases\'+$status.release_id+'\m20_demo_trading_session.payload*'
    $workers=@(Get-CimInstance Win32_Process|Where-Object {$_.Name -match '^python(w)?\.exe$' -and ($_.CommandLine -like $servicePattern -or $_.CommandLine -like $runnerPattern)})
    foreach($worker in $workers){if($worker.SessionId -ne 0){Fail 'UNEXPECTED_LISTENER_WORKER_SESSION'};$workerPid=[int]$worker.ProcessId;$created=Creation $worker;$check=Get-CimInstance Win32_Process -Filter ('ProcessId='+$workerPid) -ErrorAction SilentlyContinue;if($null -ne $check -and (Creation $check) -eq $created){Stop-Process -Id $workerPid -Force -ErrorAction Stop;$record.actions += ('LISTENER_WORKER_STOPPED:'+ $workerPid)}}
    Start-Sleep -Seconds 2
    if(@(Get-CimInstance Win32_Process|Where-Object {$_.Name -match '^python(w)?\.exe$' -and ($_.CommandLine -like $servicePattern -or $_.CommandLine -like $runnerPattern)}).Count -ne 0){Fail 'LISTENER_WORKER_REMAINS'}
    $terminals=@(Get-CimInstance Win32_Process | Where-Object { $_.Name -in @('terminal.exe','terminal64.exe') -and $_.ExecutablePath -eq $config.terminal_path });$zero=@($terminals|Where-Object {$_.SessionId -eq 0});$visible=@($terminals|Where-Object {$_.SessionId -gt 0})
    if($zero.Count -ne 1 -or $visible.Count -ne 1 -or !(SameTerminal $zero[0] (@($s0.value.before|Where-Object {$_.session_id -eq 0})[0])) -or !(SameTerminal $visible[0] (@($ui.value.before|Where-Object {$_.session_id -eq $ui.value.session_id})[0]))) { Fail 'TERMINAL_IDENTITY_CHANGED_BEFORE_STOP' }
    if((Hash $configPath) -ne $configHash){Fail 'CONFIGURATION_CHANGED_BEFORE_STOP'};$latestHold=Get-Content -Raw -LiteralPath $holdPath|ConvertFrom-Json;if($latestHold.enabled -ne $true -or $latestHold.schema_version -ne 'forex.m20.maintenance-hold.v1'){Fail 'HOLD_CHANGED_BEFORE_STOP'}
    Stop-Process -Id $zero[0].ProcessId -Force -ErrorAction Stop;$record.actions += ('SESSION0_TERMINAL_STOPPED:'+ $zero[0].ProcessId)
    Start-Sleep -Seconds 2
    $post=@(Get-CimInstance Win32_Process | Where-Object { $_.Name -in @('terminal.exe','terminal64.exe') -and $_.ExecutablePath -eq $config.terminal_path });$postZero=@($post|Where-Object {$_.SessionId -eq 0});$postVisible=@($post|Where-Object {$_.SessionId -gt 0})
    if($postZero.Count -ne 0 -or $postVisible.Count -ne 1 -or !(SameTerminal $postVisible[0] (@($ui.value.before|Where-Object {$_.session_id -eq $ui.value.session_id})[0])) -or (Get-ScheduledTask -TaskName $listener.TaskName).State.ToString() -ne 'Disabled' -or (Get-ScheduledTask -TaskName $watchdog.TaskName).State.ToString() -ne 'Disabled' -or !(Test-Path -LiteralPath $holdPath)){Fail 'POSTFLIGHT_FAILED'}
    $record.terminals_after=@($post|ForEach-Object {[ordered]@{pid=[int]$_.ProcessId;session_id=[int]$_.SessionId;created_filetime=(Creation $_)}});Save 'ISOLATED';$record | ConvertTo-Json -Compress -Depth 12
} catch {
    $message=[string]$_.Exception.Message
    $reason=if($message -like 'M30_ISOLATION_REFUSED:*'){$message}elseif($message -match 'FRESH_OBSERVATION_REQUIRED'){'M30_ISOLATION_REFUSED:FRESH_OBSERVATION_REQUIRED'}else{'M30_ISOLATION_FAILED'}
    $record.failure_reason_sha256='sha256:'+(-join ([Security.Cryptography.SHA256]::Create().ComputeHash([Text.Encoding]::UTF8.GetBytes($message))|ForEach-Object {$_.ToString('x2')}))
    $record.failure_category=[string]$_.CategoryInfo.Category
    $record.failure_id=[string]$_.FullyQualifiedErrorId
    try{Save 'FAILED' $reason}catch{};throw $reason
}
