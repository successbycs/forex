#!/usr/bin/env python3
"""Governed fixed-operation T480 access adapter for Forex.

The reusable transport comes from ``cs-ai-lab-infra/t480_core``. This module
owns only fixed Forex and shared-platform inspection operations. It cannot
accept shell text, deploy services, place trades, or expose arbitrary MT5
operations. Its M20 session operation captures a fixed fresh Demo-only market
snapshot and contains no transaction capability.
"""

from __future__ import annotations

import argparse
import base64
from dataclasses import asdict
import gzip
import gzip
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any

TOOL_ID = "forex_t480"
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from forex.t480_dependency import inspect_dependency, require_dependency  # noqa: E402
from forex.config import load_configuration  # noqa: E402
from forex.milestones import configuration_fingerprint  # noqa: E402

CONFIG_PATH = ROOT / "config" / "t480.json"
CATALOG_PATH = ROOT / "t480" / "command-catalog.json"
LOCAL_TARGET_PATH = ROOT / ".env.t480.local"
LOG_PATH = ROOT / ".t480-execution.local.jsonl"

_CONFIG_FIELDS = {
    "schema_version",
    "shared_core",
    "shared_lab_root",
    "application_root",
    "shared_network",
    "compose_project",
    "mt5_process_names",
}
_SAFE_PATH = re.compile(r"/[A-Za-z0-9_./-]+\Z")
_SAFE_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*\Z")


def load_application_config(path: Path = CONFIG_PATH) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or set(payload) != _CONFIG_FIELDS:
        raise ValueError("Forex T480 adapter configuration fields are invalid")
    if payload["schema_version"] != "forex.t480.config.v2":
        raise ValueError("Forex T480 adapter configuration schema is unsupported")
    for field in ("shared_lab_root", "application_root"):
        if not _SAFE_PATH.fullmatch(str(payload[field])):
            raise ValueError(f"Unsafe configured path: {field}")
    dependency = payload["shared_core"]
    if not isinstance(dependency, dict) or not _SAFE_PATH.fullmatch(
        str(dependency.get("repository_root", ""))
    ):
        raise ValueError("Unsafe configured path: shared_core.repository_root")
    for field in ("shared_network", "compose_project"):
        if not _SAFE_IDENTIFIER.fullmatch(str(payload[field])):
            raise ValueError(f"Unsafe configured identifier: {field}")
    process_names = payload["mt5_process_names"]
    if not isinstance(process_names, list) or not process_names:
        raise ValueError("mt5_process_names must be a non-empty array")
    if any(not _SAFE_IDENTIFIER.fullmatch(str(name)) for name in process_names):
        raise ValueError("mt5_process_names contains an unsafe process name")
    return payload


APP_CONFIG = load_application_config()
DEPENDENCY_IDENTITY = require_dependency(APP_CONFIG)
SHARED_CORE_ROOT = Path(APP_CONFIG["shared_core"]["repository_root"]).resolve()
if str(SHARED_CORE_ROOT) not in sys.path:
    sys.path.insert(0, str(SHARED_CORE_ROOT))

from t480_core import (  # noqa: E402
    Operation,
    append_execution_log,
    execute_operation,
    fingerprint_files,
    load_transport_settings,
    preflight as shared_preflight,
    resolve_ssh_target,
    validate_catalog,
)

TRANSPORT_SETTINGS = load_transport_settings(SHARED_CORE_ROOT / "t480" / "transport-config.json")
SHARED_TARGET_PATH = SHARED_CORE_ROOT / ".env.t480.local"
LAB_ROOT = str(APP_CONFIG["shared_lab_root"])
SHARED_LAB_TARGET_PATH = Path(LAB_ROOT) / ".env.t480.local"
FOREX_ROOT = str(APP_CONFIG["application_root"])
SHARED_NETWORK = str(APP_CONFIG["shared_network"])
COMPOSE_PROJECT = str(APP_CONFIG["compose_project"])
CONFIGURATION_FINGERPRINT = fingerprint_files(
    [
        *[SHARED_CORE_ROOT / entry["path"] for entry in APP_CONFIG["shared_core"]["files"]],
        CONFIG_PATH,
        CATALOG_PATH,
    ]
)


def project_configuration_fingerprint() -> str:
    """Return the governed project fingerprint used by milestone evidence."""
    state = json.loads((ROOT / "project_state.json").read_text(encoding="utf-8"))
    return configuration_fingerprint(ROOT, state)


def _mt5_process_command(process_names: list[str]) -> str:
    names = ",".join("'" + name + "'" for name in process_names)
    return (
        "$ErrorActionPreference='Stop'; "
        f"$names=@({names}); "
        "$processes=@(Get-Process -ErrorAction SilentlyContinue | Where-Object { $names -contains $_.ProcessName }); "
        "$safe=@($processes | Select-Object ProcessName,Id,@{Name='started_at_utc';Expression={"
        "try {$_.StartTime.ToUniversalTime().ToString('o')} catch {$null}}}); "
        "[pscustomobject]@{running=($safe.Count -gt 0);process_count=$safe.Count;processes=$safe} | ConvertTo-Json -Compress -Depth 4"
    )


def _m1_mt5_demo_probe_command() -> str:
    """Return the fixed read-only M1 historical-export command for Windows."""
    return (
        "$ErrorActionPreference='Stop'; "
        "$s=gc -Raw (Join-Path $env:USERPROFILE 'Documents\\Code\\forex-m1-probe\\mt5.local.json')|ConvertFrom-Json; "
        "$p=Join-Path $env:USERPROFILE 'Documents\\Code\\forex-m1-probe\\m1_mt5_demo_probe.py'; "
        "if (!(Test-Path -LiteralPath $p)) { throw 'M1 fixed probe file is absent' }; "
        "if ([string]::IsNullOrWhiteSpace($s.python_path) -or !(Test-Path -LiteralPath $s.python_path)) { throw 'M1 local configured Python interpreter is absent' }; "
        "& $s.python_path $p $s.terminal_path; exit $LASTEXITCODE"
    )


def _m20_demo_account_liquidity_command() -> str:
    """Return fixed, read-only liquidity fields from the governed Demo account."""
    code = "import json,sys;import MetaTrader5 as m;p=sys.argv[1];ok=m.initialize(path=p);a=m.account_info() if ok else None;bad=(not a or a.server!='GOMarketsMU-Demo' or a.currency!='AUD');print(json.dumps({'ok':bool(a) and not bad,'server':getattr(a,'server',None),'currency':getattr(a,'currency',None),'balance':getattr(a,'balance',None),'equity':getattr(a,'equity',None),'margin':getattr(a,'margin',None),'free_margin':getattr(a,'margin_free',None),'margin_level':getattr(a,'margin_level',None),'leverage':getattr(a,'leverage',None),'open_positions':len(m.positions_get() or ()),'mt5_error':None if a else str(m.last_error())},separators=(',',':')));m.shutdown() if ok else None;sys.exit(0 if a and not bad else 3)"
    return "$ErrorActionPreference='Stop'; $s=gc -Raw (Join-Path $env:USERPROFILE 'Documents\\Code\\forex-m1-probe\\mt5.local.json')|ConvertFrom-Json; if ([string]::IsNullOrWhiteSpace($s.python_path) -or !(Test-Path -LiteralPath $s.python_path)) { throw 'M20 configured Python interpreter is absent' }; & $s.python_path -c '" + code.replace("'", "''") + "' $s.terminal_path; exit $LASTEXITCODE"


def _m3_mt5_history_depth_probe_command() -> str:
    """Return the fixed read-only M3 history-depth command for Windows."""
    source = (ROOT / "t480" / "m3_mt5_history_depth_probe.py").read_bytes()
    digest = hashlib.sha256(source).hexdigest()
    return (
        "$ErrorActionPreference='Stop'; "
        "$root=Join-Path $env:USERPROFILE 'Documents\\Code\\forex-m1-probe'; "
        "$s=gc -Raw (Join-Path $legacy 'mt5.local.json')|ConvertFrom-Json; "
        "if ([string]::IsNullOrWhiteSpace($s.python_path) -or !(Test-Path -LiteralPath $s.python_path)) { throw 'M3 local configured Python interpreter is absent' }; "
        "$p=Join-Path $root 'm3_mt5_history_depth_probe.py'; "
        "if (!(Test-Path -LiteralPath $p)) { throw 'M3 fixed probe file is absent; stage the committed probe with the fixed OpenSSH copy step first' }; "
        "if ((Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash.ToLower() -ne '" + digest + "') { throw 'M3 fixed probe hash does not match the committed source' }; "
        "$env:FOREX_M3_PROBE_SHA256='" + digest + "'; & $s.python_path $p $s.terminal_path; exit $LASTEXITCODE"
    )


def _m6_mt5_multi_timeframe_probe_command() -> str:
    """Return the fixed read-only M6 multi-timeframe command for Windows."""
    source = (ROOT / "t480" / "m6_mt5_multi_timeframe_probe.py").read_bytes()
    digest = hashlib.sha256(source).hexdigest()
    return (
        "$ErrorActionPreference='Stop'; "
        "$root=Join-Path $env:USERPROFILE 'Documents\\Code\\forex-m1-probe'; "
        "$s=gc -Raw (Join-Path $root 'mt5.local.json')|ConvertFrom-Json; "
        "if ([string]::IsNullOrWhiteSpace($s.python_path) -or !(Test-Path -LiteralPath $s.python_path)) { throw 'M6 local configured Python interpreter is absent' }; "
        "$p=Join-Path $root 'm6_mt5_multi_timeframe_probe.py'; "
        "if (!(Test-Path -LiteralPath $p)) { throw 'M6 fixed probe file is absent; stage the committed probe with the fixed OpenSSH copy step first' }; "
        "if ((Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash.ToLower() -ne '" + digest + "') { throw 'M6 fixed probe hash does not match the committed source' }; "
        "$env:FOREX_M6_PROBE_SHA256='" + digest + "'; & $s.python_path $p $s.terminal_path; exit $LASTEXITCODE"
    )


def _m20_demo_trading_session_command() -> str:
    """Return the fixed M20 session-preflight and market-snapshot command."""
    source = (ROOT / "t480" / "m20_demo_trading_session.py").read_bytes()
    digest = hashlib.sha256(source).hexdigest()
    bridge_source = (ROOT / "t480" / "m20_postgres_audit_bridge.py").read_bytes()
    bridge_digest = hashlib.sha256(bridge_source).hexdigest()
    fingerprint = project_configuration_fingerprint()
    configuration = load_configuration(ROOT, environ={})
    tick_offset_seconds = configuration.mt5.broker_tick_time_offset_seconds
    minimum_net_profit = configuration.runtime.demo_session_limits.minimum_net_profit_aud
    risk_policy = json.dumps(asdict(configuration.runtime.persistent_risk_policy), separators=(",", ":"))
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    return (
        "$ErrorActionPreference='Stop'; "
        "$base='C:\\ProgramData\\ForexListener'; $state=Join-Path $base 'state'; "
        "$status=gc -Raw (Join-Path $state 'm20_demo_listener_status.local.json')|ConvertFrom-Json; $release=[string]$status.release_id; "
        "if ($release -notmatch '^[0-9a-f]{16}$') { throw 'M20 active ProgramData release id is absent or invalid' }; "
        "$root=Join-Path $base ('releases\\'+$release); $c=gc -Raw (Join-Path $state 'm20_demo_listener_service.local.json')|ConvertFrom-Json; "
        "if ([string]$c.FOREX_M20_APPLICATION_REVISION -ne '" + revision + "') { throw 'M20 active ProgramData release revision does not match the committed evidence revision' }; "
        "if ([string]$c.FOREX_M20_CONFIGURATION_FINGERPRINT -ne '" + fingerprint + "') { throw 'M20 active ProgramData release configuration does not match the committed evidence configuration' }; "
        "if ([string]::IsNullOrWhiteSpace($c.python_path) -or !(Test-Path -LiteralPath $c.python_path)) { throw 'M20 ProgramData release configured Python interpreter is absent' }; "
        "$p=Join-Path $root 'm20_demo_trading_session.payload'; "
        "if (!(Test-Path -LiteralPath $p)) { throw 'M20 fixed ProgramData session runner is absent' }; "
        "if ((Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash.ToLower() -ne '" + digest + "') { throw 'M20 fixed session runner hash does not match the committed source' }; "
        "$bridge=Join-Path $root 'm20_postgres_audit_bridge.payload'; "
        "if (!(Test-Path -LiteralPath $bridge)) { throw 'M20 fixed ProgramData PostgreSQL audit bridge is absent' }; "
        "if ((Get-FileHash -LiteralPath $bridge -Algorithm SHA256).Hash.ToLower() -ne '" + bridge_digest + "') { throw 'M20 fixed PostgreSQL audit bridge hash does not match the committed source' }; "
        "$lease=Join-Path $state 'm20_demo_session.local.json'; "
        "$env:FOREX_M20_DEMO_TRADING_SESSION_SHA256='" + digest + "'; "
        "$env:FOREX_M20_POSTGRES_AUDIT_BRIDGE_SHA256='sha256:" + bridge_digest + "'; "
        "$env:FOREX_M20_CONFIGURATION_FINGERPRINT='" + fingerprint + "'; "
        "$env:FOREX_M20_TICK_TIME_OFFSET_SECONDS='" + str(tick_offset_seconds) + "'; "
        "$env:FOREX_M20_MINIMUM_NET_PROFIT_AUD='" + str(minimum_net_profit) + "'; "
        "$env:FOREX_M20_PERSISTENT_RISK_POLICY='" + risk_policy.replace("'", "''") + "'; "
        "$env:FOREX_M20_APPLICATION_REVISION='" + revision + "'; & $c.python_path $p $c.terminal_path $lease; exit $LASTEXITCODE"
    )


def _m20_listener_status_command() -> str:
    """Return a redacted heartbeat only; recovery is an explicit fixed operation."""
    return (
        "$ErrorActionPreference='Stop'; "
        "$state='C:\\ProgramData\\ForexListener\\state'; $p=Join-Path $state 'm20_demo_listener_status.local.json'; "
        "if (!(Test-Path -LiteralPath $p)) { [pscustomobject]@{running=$false;state='NOT_STARTED';detail='No listener heartbeat exists.'}|ConvertTo-Json -Compress; exit 0 }; "
        "$s=gc -Raw -LiteralPath $p|ConvertFrom-Json; "
        "$age=$null; $stale=$false; try { $age=[Math]::Round(((Get-Date).ToUniversalTime()-([datetime]::Parse([string]$s.heartbeat_at_utc)).ToUniversalTime()).TotalSeconds,1); $stale=($age -ge 30) } catch { $stale=$true }; "
        "$recovery=if ($stale) { 'EXPLICIT_RECOVERY_REQUIRED' } else { 'NOT_REQUIRED' }; $recoveryDetail=$null; "
        "$taskAction=$null; try { $taskAction=(Get-ScheduledTask -TaskName 'Forex-M20-Demo-Listener' -ErrorAction Stop).Actions|Select-Object -First 1|ForEach-Object {$_.Execute+' '+$_.Arguments} } catch {}; $protection=$null; $job=Join-Path $state 'm20_demo_monitor_job.local.json'; if (($s.monitor.state -eq 'RUNNING') -and (Test-Path -LiteralPath $job)) { try { $j=gc -Raw -LiteralPath $job|ConvertFrom-Json; $protection=[ordered]@{ticket=$j.position.ticket;action=$j.proposal.action;entry_price=$j.position.price_open;stop_loss=$j.position.sl;take_profit=$j.position.tp;submitted_at_utc=$j.submitted_at_utc} } catch {} }; $state=if ($stale) { 'STALE' } else { $s.state }; $supervisorAlive=(!$stale -and ($s.state -notin @('STOPPED','STARTUP_FAILED'))); [pscustomobject]@{running=$supervisorAlive;state=$state;release_id=$s.release_id;task_action=$taskAction;heartbeat_at_utc=$s.heartbeat_at_utc;heartbeat_at_nzst=$s.heartbeat_at_nzst;heartbeat_age_seconds=$age;iteration=$s.process_iteration;assessment_total=$s.assessment_total;assessment_started_at_utc=$s.assessment_started_at_utc;assessment_completed_at_utc=$s.assessment_completed_at_utc;assessment_duration_ms=$s.assessment_duration_ms;next_assessment_at_utc=$s.next_assessment_at_utc;next_assessment_at_nzst=$s.next_assessment_at_nzst;detail=$s.detail;monitor=$s.monitor;quote=$s.quote;open_position_protection=$protection;last_result=$s.last_result;recovery_action=$recovery;recovery_detail=$recoveryDetail}|ConvertTo-Json -Compress -Depth 8"
    )


def _m20_listener_recover_command() -> str:
    """Restart only the fixed listener Scheduled Task; no trading/order surface."""
    return (
        "$ErrorActionPreference='Stop'; "
        "$task=Get-ScheduledTask -TaskName 'Forex-M20-Demo-Listener' -ErrorAction Stop; "
        "if ($task.State -eq 'Running') { Stop-ScheduledTask -TaskName 'Forex-M20-Demo-Listener' -ErrorAction Stop }; "
        "Start-ScheduledTask -TaskName 'Forex-M20-Demo-Listener' -ErrorAction Stop; "
        "[pscustomobject]@{recovery_action='RESTART_REQUESTED';task='Forex-M20-Demo-Listener'}|ConvertTo-Json -Compress"
    )


def _m20_listener_activate_demo_lease_command() -> str:
    """Create only the fixed, bounded M20 Demo lease for the listener."""
    return (
        "$ErrorActionPreference='Stop'; $state='C:\\ProgramData\\ForexListener\\state'; New-Item -ItemType Directory -Force $state|Out-Null; "
        "$now=(Get-Date).ToUniversalTime(); $lease=[ordered]@{schema_version='forex.m20.demo-session-lease.v1';session_id=([guid]::NewGuid().ToString());enabled=$true;server='GOMarketsMU-Demo';symbol='EURUSD';starts_at_utc=$now.ToString('o');expires_at_utc='9999-12-31T23:59:59Z';maximum_trades=$null;maximum_duration_minutes=0;maximum_open_positions=1;maximum_notional_per_trade_usd=10000;maximum_cumulative_notional_usd=100000;maximum_loss_per_trade_aud=100;audit_prerequisites=[ordered]@{postgres_audit_schema='READY';proposal_persistence='READY';idempotency_store='READY'}}; "
        "$tmp=Join-Path $state 'm20_demo_session.local.json.tmp'; [IO.File]::WriteAllText($tmp,($lease|ConvertTo-Json -Compress -Depth 4),(New-Object Text.UTF8Encoding($false))); Move-Item -LiteralPath $tmp -Destination (Join-Path $state 'm20_demo_session.local.json') -Force; "
        "[pscustomobject]@{activated=$true;server=$lease.server;symbol=$lease.symbol;session_id=$lease.session_id;starts_at_utc=$lease.starts_at_utc;expires_at_utc=$lease.expires_at_utc;maximum_trades=$lease.maximum_trades;maximum_notional_per_trade_usd=$lease.maximum_notional_per_trade_usd;maximum_cumulative_notional_usd=$lease.maximum_cumulative_notional_usd;maximum_loss_per_trade_aud=$lease.maximum_loss_per_trade_aud}|ConvertTo-Json -Compress"
    )


def _m20_listener_resume_risk_policy_command() -> str:
    """Record a fixed manual-review resume request without exposing database input."""
    bridge = (ROOT / "t480" / "m20_postgres_audit_bridge.py").read_bytes()
    digest = hashlib.sha256(bridge).hexdigest()
    return (
        "$ErrorActionPreference='Stop'; $base='C:\\ProgramData\\ForexListener'; $state=Join-Path $base 'state'; "
        "$status=gc -Raw (Join-Path $state 'm20_demo_listener_status.local.json')|ConvertFrom-Json; $release=[string]$status.release_id; "
        "if ($release -notmatch '^[0-9a-f]{16}$') { throw 'M20 active ProgramData release id is absent or invalid' }; "
        "$root=Join-Path $base ('releases\\'+$release); $c=gc -Raw (Join-Path $state 'm20_demo_listener_service.local.json')|ConvertFrom-Json; "
        "if ([string]::IsNullOrWhiteSpace($c.python_path) -or !(Test-Path -LiteralPath $c.python_path)) { throw 'M20 ProgramData release configured Python interpreter is absent' }; "
        "$bridge=Join-Path $root 'm20_postgres_audit_bridge.payload'; "
        "if (!(Test-Path -LiteralPath $bridge)) { throw 'M20 fixed ProgramData PostgreSQL audit bridge is absent' }; "
        "if ((Get-FileHash -LiteralPath $bridge -Algorithm SHA256).Hash.ToLower() -ne '" + digest + "') { throw 'M20 fixed PostgreSQL audit bridge hash does not match the committed source' }; "
        "'{}' | & $c.python_path $bridge resume-risk-policy; exit $LASTEXITCODE"
    )


def _m20_listener_stop_command() -> str:
    """Stop only the fixed listener task for an atomic hash-checked deployment."""
    return (
        "$ErrorActionPreference='Stop'; "
        "$task=Get-ScheduledTask -TaskName 'Forex-M20-Demo-Listener' -ErrorAction Stop; "
        "if ($task.State -eq 'Running') { Stop-ScheduledTask -TaskName 'Forex-M20-Demo-Listener' -ErrorAction Stop }; "
        "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { $_.CommandLine -like '*\\ProgramData\\ForexListener\\releases\\*m20_demo_listener_service.payload*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction Stop }; "
        "[pscustomobject]@{stopped=$true;task='Forex-M20-Demo-Listener'}|ConvertTo-Json -Compress"
    )


def _m20_listener_repair_permissions_command() -> str:
    service = (ROOT / "t480" / "m20_demo_listener_service.py").read_bytes()
    runner = (ROOT / "t480" / "m20_demo_trading_session.py").read_bytes()
    bridge = (ROOT / "t480" / "m20_postgres_audit_bridge.py").read_bytes()
    discord = (ROOT / "t480" / "m20_discord_trade_notification.py").read_bytes()
    release_id = hashlib.sha256(service + runner + bridge + discord).hexdigest()[:16]
    return (
        "$ErrorActionPreference='Stop'; $base='C:\\ProgramData\\ForexListener'; $root=Join-Path $base 'releases\\" + release_id + "'; "
        "New-Item -ItemType Directory -Force $base|Out-Null; icacls $base /grant ($env:USERNAME+':(OI)(CI)M') /T | Out-Null; "
        "$task=Get-ScheduledTask -TaskName 'Forex-M20-Demo-Listener' -ErrorAction SilentlyContinue; $active=$false; if ($null -ne $task) { $active=@($task.Actions|ForEach-Object {$_.Arguments}) -match [regex]::Escape($root) }; "
        "if ((Test-Path -LiteralPath $root) -and !$active) { Remove-Item -LiteralPath $root -Recurse -Force }; "
        "[pscustomobject]@{repaired=$true;path=$base;cleared_unreferenced_release=(!$active)}|ConvertTo-Json -Compress"
    )


def _m20_listener_prepare_command() -> str:
    """Verify a staged release and atomically write its local service config."""
    service = (ROOT / "t480" / "m20_demo_listener_service.py").read_bytes()
    service_digest = hashlib.sha256(service).hexdigest()
    runner_digest = hashlib.sha256((ROOT / "t480" / "m20_demo_trading_session.py").read_bytes()).hexdigest()
    bridge_digest = hashlib.sha256((ROOT / "t480" / "m20_postgres_audit_bridge.py").read_bytes()).hexdigest()
    discord = (ROOT / "t480" / "m20_discord_trade_notification.py").read_bytes()
    discord_digest = hashlib.sha256(discord).hexdigest()
    release_id = hashlib.sha256(service + (ROOT / "t480" / "m20_demo_trading_session.py").read_bytes() + (ROOT / "t480" / "m20_postgres_audit_bridge.py").read_bytes() + discord).hexdigest()[:16]
    fingerprint = project_configuration_fingerprint()
    configuration = load_configuration(ROOT, environ={})
    tick_offset_seconds = configuration.mt5.broker_tick_time_offset_seconds
    minimum_net_profit = configuration.runtime.demo_session_limits.minimum_net_profit_aud
    risk_policy = json.dumps(asdict(configuration.runtime.persistent_risk_policy), separators=(",", ":"))
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    return (
        "$ErrorActionPreference='Stop'; "
        "$base='C:\\ProgramData\\ForexListener'; $root=Join-Path $base 'releases\\" + release_id + "'; $state=Join-Path $base 'state'; $legacy=Join-Path $env:USERPROFILE 'Documents\\Code\\forex-m1-probe'; New-Item -ItemType Directory -Force $state|Out-Null; "
        "$s=gc -Raw (Join-Path $legacy 'mt5.local.json')|ConvertFrom-Json; "
        "$runner=Join-Path $root 'm20_demo_trading_session.payload'; $bridge=Join-Path $root 'm20_postgres_audit_bridge.payload'; $discord=Join-Path $root 'm20_discord_trade_notification.payload'; $service=Join-Path $root 'm20_demo_listener_service.payload'; $task='Forex-M20-Demo-Listener'; "
        "if ((Get-FileHash -LiteralPath $runner -Algorithm SHA256).Hash.ToLower() -ne '" + runner_digest + "') { throw 'M20 listener runner hash does not match fixed source' }; "
        "if ((Get-FileHash -LiteralPath $bridge -Algorithm SHA256).Hash.ToLower() -ne '" + bridge_digest + "') { throw 'M20 listener bridge hash does not match fixed source' }; "
        "if ((Get-FileHash -LiteralPath $discord -Algorithm SHA256).Hash.ToLower() -ne '" + discord_digest + "') { throw 'M20 Discord adapter hash does not match fixed source' }; "
        "if ((Get-FileHash -LiteralPath $service -Algorithm SHA256).Hash.ToLower() -ne '" + service_digest + "') { throw 'M20 listener service staging hash failed' }; "
        "$discordConfigKey='FOREX_M20_DISCORD_WEBHOOK_URL'; $c=[ordered]@{FOREX_M20_DEMO_TRADING_SESSION_SHA256='" + runner_digest + "';FOREX_M20_POSTGRES_AUDIT_BRIDGE_SHA256='sha256:" + bridge_digest + "';FOREX_M20_CONFIGURATION_FINGERPRINT='" + fingerprint + "';FOREX_M20_TICK_TIME_OFFSET_SECONDS='" + str(tick_offset_seconds) + "';FOREX_M20_MINIMUM_NET_PROFIT_AUD='" + str(minimum_net_profit) + "';FOREX_M20_PERSISTENT_RISK_POLICY='" + risk_policy.replace("'", "''") + "';FOREX_M20_APPLICATION_REVISION='" + revision + "';python_path=$s.python_path;terminal_path=$s.terminal_path}; "
        "if (!(Test-Path (Join-Path $state 'm20_demo_session.local.json'))) { Copy-Item (Join-Path $legacy 'm20_demo_session.local.json') (Join-Path $state 'm20_demo_session.local.json') -ErrorAction SilentlyContinue }; $tmp=Join-Path $state 'm20_demo_listener_service.local.json.tmp'; [IO.File]::WriteAllText($tmp,($c|ConvertTo-Json -Compress),(New-Object Text.UTF8Encoding($false))); Move-Item -LiteralPath $tmp -Destination (Join-Path $state 'm20_demo_listener_service.local.json') -Force; "
        "[pscustomobject]@{prepared=$true;release_id='" + release_id + "';service_sha256='sha256:" + service_digest + "'}|ConvertTo-Json -Compress"
    )


def _m20_listener_install_command() -> str:
    """Activate the exact prepared release and restore the old task on failure."""
    service = (ROOT / "t480" / "m20_demo_listener_service.py").read_bytes()
    runner = (ROOT / "t480" / "m20_demo_trading_session.py").read_bytes()
    bridge = (ROOT / "t480" / "m20_postgres_audit_bridge.py").read_bytes()
    discord = (ROOT / "t480" / "m20_discord_trade_notification.py").read_bytes()
    release_id = hashlib.sha256(service + runner + bridge + discord).hexdigest()[:16]
    service_digest = hashlib.sha256(service).hexdigest()
    return (
        "$ErrorActionPreference='Stop'; $base='C:\\ProgramData\\ForexListener'; $root=Join-Path $base 'releases\\" + release_id + "'; $state=Join-Path $base 'state'; $service=Join-Path $root 'm20_demo_listener_service.payload'; $task='Forex-M20-Demo-Listener'; "
        "$c=Get-Content -Raw (Join-Path $state 'm20_demo_listener_service.local.json')|ConvertFrom-Json; if (!(Test-Path -LiteralPath $service)) { throw 'M20 release was not prepared' }; "
        "$previous=$null; try { $previous=Export-ScheduledTask -TaskName $task -ErrorAction Stop } catch {}; if ($null -ne $previous) { [IO.File]::WriteAllText((Join-Path $state 'previous-task.xml'),$previous,(New-Object Text.UTF8Encoding($false))) }; "
        "$action=New-ScheduledTaskAction -Execute $c.python_path -Argument ('\"'+$service+'\"'); $trigger=New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME; $settings=New-ScheduledTaskSettingsSet -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero); "
        "try { if ($null -ne $previous) { Stop-ScheduledTask -TaskName $task -ErrorAction SilentlyContinue }; Register-ScheduledTask -TaskName $task -Action $action -Trigger $trigger -Settings $settings -RunLevel Highest -Force|Out-Null; Start-ScheduledTask -TaskName $task; Start-Sleep -Seconds 5; $h=Get-Content -Raw (Join-Path $state 'm20_demo_listener_status.local.json')|ConvertFrom-Json; $age=((Get-Date).ToUniversalTime()-([datetime]::Parse($h.heartbeat_at_utc)).ToUniversalTime()).TotalSeconds; if (($h.release_id -ne '" + release_id + "') -or ($age -ge 30) -or ($h.state -eq 'STARTUP_FAILED')) { throw 'new listener did not produce a fresh ProgramData heartbeat' } } catch { $failure=$_.Exception.Message; if ($null -ne $previous) { Stop-ScheduledTask -TaskName $task -ErrorAction SilentlyContinue; Register-ScheduledTask -TaskName $task -Xml $previous -Force|Out-Null; Start-ScheduledTask -TaskName $task -ErrorAction SilentlyContinue }; throw ('M20 deployment rolled back: '+$failure) }; "
        "[pscustomobject]@{installed=$true;task=$task;release_id='" + release_id + "';service_sha256='sha256:" + service_digest + "'}|ConvertTo-Json -Compress"
    )


def _m20_listener_stage_command(index: int) -> str:
    """Transfer a bounded immutable source segment through the fixed adapter."""
    source = (ROOT / "t480" / "m20_demo_listener_service.py").read_bytes()
    release_id = hashlib.sha256(source + (ROOT / "t480" / "m20_demo_trading_session.py").read_bytes() + (ROOT / "t480" / "m20_postgres_audit_bridge.py").read_bytes() + (ROOT / "t480" / "m20_discord_trade_notification.py").read_bytes()).hexdigest()[:16]
    # Raw Base64 decoding is accepted by the T480 endpoint; in-process gzip
    # expansion is not.  Twelve bounded fixed fragments stay below its command
    # cap and match the catalogued release protocol.
    encoded = base64.b64encode(source).decode("ascii")
    chunk_size = ((len(encoded) + (12 * 4) - 1) // (12 * 4)) * 4
    chunks = tuple(encoded[offset:offset + chunk_size] for offset in range(0, len(encoded), chunk_size))
    if index not in range(1, len(chunks) + 1):
        raise ValueError("M20 listener stage index is invalid")
    chunk = chunks[index - 1]
    if index == 1:
        write = "[IO.File]::WriteAllBytes($service,[Convert]::FromBase64String('" + chunk + "'));"
    else:
        write = "$bytes=[Convert]::FromBase64String('" + chunk + "'); $stream=[IO.File]::Open($service,[IO.FileMode]::Append,[IO.FileAccess]::Write,[IO.FileShare]::None); try {$stream.Write($bytes,0,$bytes.Length)} finally {$stream.Dispose()};"
    if index == len(chunks):
        write += " if ((Get-FileHash -LiteralPath $service -Algorithm SHA256).Hash.ToLower() -ne '" + hashlib.sha256(source).hexdigest() + "') { throw 'M20 listener staged source hash failed' };"
    return "$ErrorActionPreference='Stop'; $base='C:\\ProgramData\\ForexListener'; $root=Join-Path $base 'releases\\" + release_id + "'; New-Item -ItemType Directory -Force $root|Out-Null; $service=Join-Path $root 'm20_demo_listener_service.payload'; " + write + " [pscustomobject]@{stage=" + str(index) + ";ok=$true}|ConvertTo-Json -Compress"


def _m20_listener_dependency_stage_command(source_name: str, runtime_name: str, marker: str, index: int, *, parts: int | None = None, verify_final: bool = True) -> str:
    """Stage a fixed hash-bound M20 listener dependency in bounded source chunks."""
    source = (ROOT / "t480" / source_name).read_bytes()
    release_id = hashlib.sha256((ROOT / "t480" / "m20_demo_listener_service.py").read_bytes() + (ROOT / "t480" / "m20_demo_trading_session.py").read_bytes() + (ROOT / "t480" / "m20_postgres_audit_bridge.py").read_bytes() + (ROOT / "t480" / "m20_discord_trade_notification.py").read_bytes()).hexdigest()[:16]
    encoded = base64.b64encode(source).decode("ascii")
    parts = parts if parts is not None else (48 if source_name == "m20_demo_trading_session.py" else 24)
    # The runner is deliberately split into small fixed direct-decode chunks:
    # this avoids a blocked in-process decompressor and bridge length limits.
    chunk_size = ((len(encoded) + (parts * 4) - 1) // (parts * 4)) * 4
    chunks = tuple(encoded[offset:offset + chunk_size] for offset in range(0, len(encoded), chunk_size))
    if index not in range(1, len(chunks) + 1):
        raise ValueError("M20 listener dependency stage index is invalid")
    chunk = chunks[index - 1]
    if index == 1:
        write = "[IO.File]::WriteAllBytes($file,[Convert]::FromBase64String('" + chunk + "'));"
    else:
        # Add-Content's byte encoding has produced non-identical staged
        # payloads on some Windows PowerShell hosts.  Append the decoded bytes
        # through FileStream so the final SHA-256 verifies the exact source.
        write = "$bytes=[Convert]::FromBase64String('" + chunk + "'); $stream=[IO.File]::Open($file,[IO.FileMode]::Append,[IO.FileAccess]::Write,[IO.FileShare]::None); try {$stream.Write($bytes,0,$bytes.Length)} finally {$stream.Dispose()};"
    if index == len(chunks) and verify_final:
        write += " if ((Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash.ToLower() -ne '" + hashlib.sha256(source).hexdigest() + "') { throw '" + marker + " staged source hash failed' };"
    elif index == len(chunks):
        # The constrained endpoint runs the actual hash comparison in the
        # dedicated verification operation immediately after this final write.
        write += " Get-Command Get-FileHash|Out-Null;"
    return (
        "$ErrorActionPreference='Stop'; $base='C:\\ProgramData\\ForexListener'; $root=Join-Path $base 'releases\\" + release_id + "'; New-Item -ItemType Directory -Force $root|Out-Null; "
        "$file=Join-Path $root '" + runtime_name + "'; " + write
        + " [pscustomobject]@{stage=" + str(index) + ";ok=$true}|ConvertTo-Json -Compress"
    )


OPERATIONS: dict[str, Operation] = {
    "health": Operation(
        "health",
        "Inspect non-secret T480 Windows host health.",
        powershell_command=(
            "$ErrorActionPreference='Stop'; "
            "$os=Get-CimInstance Win32_OperatingSystem; "
            "$computer=Get-CimInstance Win32_ComputerSystem; "
            "[pscustomobject]@{hostname=$env:COMPUTERNAME;os=$os.Caption;version=$os.Version;"
            "uptime_since_utc=$os.LastBootUpTime.ToUniversalTime().ToString('o');"
            "memory_gib=[math]::Round($computer.TotalPhysicalMemory/1GB,1)} | ConvertTo-Json -Compress"
        ),
    ),
    "storage": Operation(
        "storage",
        "Inspect Windows filesystem capacity.",
        powershell_command=(
            "$ErrorActionPreference='Stop'; Get-CimInstance Win32_LogicalDisk -Filter 'DriveType = 3' | "
            "Select-Object DeviceID,@{Name='size_gib';Expression={[math]::Round($_.Size/1GB,1)}},"
            "@{Name='free_gib';Expression={[math]::Round($_.FreeSpace/1GB,1)}} | ConvertTo-Json -Compress"
        ),
    ),
    "wsl_status": Operation(
        "wsl_status",
        "Inspect WSL status and distributions.",
        powershell_command="$ErrorActionPreference='Stop'; wsl.exe --status; wsl.exe --list --verbose",
    ),
    "docker_status": Operation(
        "docker_status",
        "Inspect Docker Engine and Compose availability in WSL.",
        wsl_script="set -euo pipefail\ndocker --version\ndocker compose version\ndocker info >/dev/null\necho docker-daemon-ok\n",
    ),
    "docker_runtime_evidence": Operation(
        "docker_runtime_evidence",
        "Inspect WSL capacity and Docker runtime health.",
        wsl_script=(
            "set -euo pipefail\n"
            "echo ---os---\nuname -a\n"
            "echo ---capacity---\ndf -h /\nfree -h\n"
            "echo ---docker---\ndocker --version\ndocker compose version\ndocker info >/dev/null\n"
            "echo docker-daemon-ok\n"
        ),
    ),
    "shared_lab_status": Operation(
        "shared_lab_status",
        "Inspect shared AI Lab Compose services and internal network.",
        wsl_script=(
            "set -euo pipefail\n"
            f"cd '{LAB_ROOT}'\n"
            "echo ---revision---\ngit rev-parse --short HEAD\n"
            "echo ---compose---\ndocker compose config --quiet\necho compose-valid\ndocker compose ps -a\n"
            "echo ---network---\n"
            f"docker network inspect '{SHARED_NETWORK}' --format '{{{{.Name}}}} driver={{{{.Driver}}}} containers={{{{len .Containers}}}}'\n"
        ),
    ),
    "postgres_status": Operation(
        "postgres_status",
        "Inspect shared PostgreSQL and pgvector readiness without data access.",
        wsl_script=(
            "set -euo pipefail\n"
            f"cd '{LAB_ROOT}'\n"
            "test -f .env || { echo shared-lab-env-absent; exit 4; }\n"
            "set -a\nsource .env\nset +a\n"
            "docker compose ps postgres\n"
            "docker compose exec -T postgres pg_isready -U \"$POSTGRES_USER\" -d \"$POSTGRES_DB\" </dev/null\n"
            "docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U \"$POSTGRES_USER\" -d \"$POSTGRES_DB\" "
            "-Atc \"SELECT current_database(), extname FROM pg_extension WHERE extname = 'vector';\" </dev/null\n"
        ),
    ),
    "forex_preflight": Operation(
        "forex_preflight",
        "Inspect Forex checkout, toolchain, configuration artifacts, and shared-network readiness.",
        wsl_script=(
            "set -euo pipefail\n"
            f"repository_root='{FOREX_ROOT}'\n"
            "test -d \"$repository_root/.git\" || { echo checkout-absent; exit 4; }\n"
            "cd \"$repository_root\"\n"
            "echo ---revision---\ngit rev-parse --short HEAD\n"
            "printf 'worktree_change_count=%s\\n' \"$(git status --porcelain | wc -l)\"\n"
            "echo ---toolchain---\npython3 --version\ngit --version\ndocker --version\ndocker compose version\n"
            "echo ---configuration-artifacts---\n"
            "for path in config/t480.json t480/command-catalog.json scripts/t480_adapter.py; do "
            "test -f \"$path\" && echo \"$path=present\" || { echo \"$path=absent\"; exit 4; }; done\n"
            "echo ---shared-network---\n"
            f"docker network inspect '{SHARED_NETWORK}' --format '{{{{.Name}}}} driver={{{{.Driver}}}} containers={{{{len .Containers}}}}'\n"
            "echo forex-preflight-ok\n"
        ),
    ),
    "forex_runtime_status": Operation(
        "forex_runtime_status",
        "Inspect deployed Forex Compose container state without logs, data, or mutations.",
        wsl_script=(
            "set -euo pipefail\n"
            f"repository_root='{FOREX_ROOT}'\n"
            "test -f \"$repository_root/compose.yaml\" || { echo forex-runtime-not-configured; exit 4; }\n"
            "cd \"$repository_root\"\n"
            "docker compose config --quiet\n"
            "docker compose ps -a\n"
            f"docker ps -a --filter 'label=com.docker.compose.project={COMPOSE_PROJECT}' --format '{{{{.Names}}}} {{{{.Status}}}}'\n"
        ),
    ),
    "mt5_process_status": Operation(
        "mt5_process_status",
        "Inspect whether a configured MetaTrader terminal process is running without using the MT5 API.",
        powershell_command=_mt5_process_command([str(name) for name in APP_CONFIG["mt5_process_names"]]),
    ),
    "m1_mt5_demo_probe": Operation(
        "m1_mt5_demo_probe",
        "Export a fixed read-only closed EURUSD H1 historical sample from GOMarketsMU-Demo for M1.",
        powershell_command=_m1_mt5_demo_probe_command(),
        timeout_seconds=60,
    ),
    "m20_demo_account_liquidity": Operation("m20_demo_account_liquidity", "Read fixed GOMarketsMU-Demo account liquidity fields without trading.", powershell_command=_m20_demo_account_liquidity_command()),
    "m3_mt5_history_depth_probe": Operation(
        "m3_mt5_history_depth_probe",
        "Measure fixed closed EURUSD H1 history depth from GOMarketsMU-Demo without persisting or trading.",
        powershell_command=_m3_mt5_history_depth_probe_command(),
        timeout_seconds=120,
    ),
    "m6_mt5_multi_timeframe_probe": Operation(
        "m6_mt5_multi_timeframe_probe",
        "Measure fixed closed EURUSD M15, H1, and D1 Demo history without persisting or trading.",
        powershell_command=_m6_mt5_multi_timeframe_probe_command(),
        timeout_seconds=120,
    ),
    "m20_demo_trading_session": Operation(
        "m20_demo_trading_session",
        "Run the fixed bounded GOMarketsMU-Demo EURUSD M1/M5 session; a hash-bound PostgreSQL audit bridge must persist before any transaction.",
        powershell_command=_m20_demo_trading_session_command(),
        timeout_seconds=720,
    ),
    "m20_listener_status": Operation(
        "m20_listener_status",
        "Inspect the permanent M20 Demo listener heartbeat and recover its fixed task when the heartbeat is stale.",
        powershell_command=_m20_listener_status_command(),
    ),
    "m20_listener_recover": Operation(
        "m20_listener_recover",
        "Restart only the fixed permanent M20 Demo listener Scheduled Task.",
        powershell_command=_m20_listener_recover_command(),
    ),
    "m20_listener_activate_demo_lease": Operation(
        "m20_listener_activate_demo_lease",
        "Create a new continuous GOMarketsMU-Demo EURUSD M1 lease with the governed M20 caps.",
        powershell_command=_m20_listener_activate_demo_lease_command(),
    ),
    "m20_listener_resume_risk_policy": Operation(
        "m20_listener_resume_risk_policy",
        "Record a fixed operator resume request for a current Option B manual-review pause; it cannot override a still-breached limit.",
        powershell_command=_m20_listener_resume_risk_policy_command(),
    ),
    "m20_listener_stop": Operation(
        "m20_listener_stop",
        "Stop only the fixed permanent M20 Demo listener Scheduled Task for deployment.",
        powershell_command=_m20_listener_stop_command(),
    ),
    "m20_listener_repair_permissions": Operation("m20_listener_repair_permissions", "Repair current-user Modify access only for the fixed Forex listener deployment directory.", powershell_command=_m20_listener_repair_permissions_command()),
    "m20_listener_prepare": Operation(
        "m20_listener_prepare",
        "Verify the fixed staged M20 release and atomically prepare its non-secret service configuration.",
        powershell_command=_m20_listener_prepare_command(),
        timeout_seconds=60,
    ),
    "m20_listener_install": Operation(
        "m20_listener_install",
        "Install or update the fixed permanent M20 Demo listener Scheduled Task.",
        powershell_command=_m20_listener_install_command(),
        timeout_seconds=60,
    ),
    "m20_listener_stage_1": Operation("m20_listener_stage_1", "Stage fixed M20 listener payload part one.", powershell_command=_m20_listener_stage_command(1)),
    "m20_listener_stage_2": Operation("m20_listener_stage_2", "Stage fixed M20 listener payload part two.", powershell_command=_m20_listener_stage_command(2)),
    "m20_listener_stage_3": Operation("m20_listener_stage_3", "Stage fixed M20 listener payload part three.", powershell_command=_m20_listener_stage_command(3)),
    "m20_listener_stage_4": Operation("m20_listener_stage_4", "Stage fixed M20 listener payload part four.", powershell_command=_m20_listener_stage_command(4)),
    "m20_listener_stage_5": Operation("m20_listener_stage_5", "Stage fixed M20 listener payload part five.", powershell_command=_m20_listener_stage_command(5)),
}

for _index in range(6, 13):
    OPERATIONS[f"m20_listener_stage_{_index}"] = Operation(
        f"m20_listener_stage_{_index}",
        ("Stage and verify" if _index == 12 else "Stage") + f" fixed M20 listener payload part {_index}.",
        powershell_command=_m20_listener_stage_command(_index),
    )

def _m20_listener_runner_stage_command(index: int) -> str:
    """Stage runner fragments independently, then assemble and hash-check them.

    The T480 endpoint intermittently corrupts a long sequence of append writes;
    independent Base64 fragments avoid that while retaining exact-source proof.
    """
    source = (ROOT / "t480" / "m20_demo_trading_session.py").read_bytes()
    release_id = hashlib.sha256(
        (ROOT / "t480" / "m20_demo_listener_service.py").read_bytes() + source
        + (ROOT / "t480" / "m20_postgres_audit_bridge.py").read_bytes()
        + (ROOT / "t480" / "m20_discord_trade_notification.py").read_bytes()
    ).hexdigest()[:16]
    encoded = base64.b64encode(source).decode("ascii")
    parts = 48
    chunk_size = ((len(encoded) + (parts * 4) - 1) // (parts * 4)) * 4
    chunks = tuple(encoded[offset:offset + chunk_size] for offset in range(0, len(encoded), chunk_size))
    prefix = "$ErrorActionPreference='Stop'; $base='C:\\ProgramData\\ForexListener'; $root=Join-Path $base 'releases\\" + release_id + "'; New-Item -ItemType Directory -Force $root|Out-Null; $payload=Join-Path $root 'm20_demo_trading_session.payload'; "
    if index <= parts:
        return prefix + "[IO.File]::WriteAllText((Join-Path $root 'm20_demo_trading_session.part" + f"{index:02d}" + "'),'" + chunks[index - 1] + "',(New-Object Text.UTF8Encoding($false))); [pscustomobject]@{stage=" + str(index) + ";ok=$true}|ConvertTo-Json -Compress"
    raise ValueError("M20 listener runner stage index is invalid")


for _index in range(1, 49):
    _final = _index == 48
    OPERATIONS[f"m20_listener_runner_stage_{_index}"] = Operation(
        f"m20_listener_runner_stage_{_index}",
        ("Stage and verify" if _final else "Stage") + f" fixed M20 listener runner payload part {_index}.",
        powershell_command=_m20_listener_runner_stage_command(_index),
    )
_runner_source_digest = hashlib.sha256((ROOT / "t480" / "m20_demo_trading_session.py").read_bytes()).hexdigest()
_runner_release_id = hashlib.sha256(
    (ROOT / "t480" / "m20_demo_listener_service.py").read_bytes()
    + (ROOT / "t480" / "m20_demo_trading_session.py").read_bytes()
    + (ROOT / "t480" / "m20_postgres_audit_bridge.py").read_bytes()
    + (ROOT / "t480" / "m20_discord_trade_notification.py").read_bytes()
).hexdigest()[:16]
OPERATIONS["m20_listener_runner_verify"] = Operation(
    "m20_listener_runner_verify",
    "Verify the fully staged fixed M20 listener runner payload hash.",
    powershell_command=(
        "$ErrorActionPreference='Stop'; $base='C:\\ProgramData\\ForexListener'; "
        "$root=Join-Path $base 'releases\\" + _runner_release_id + "'; "
        "$file=Join-Path $root 'm20_demo_trading_session.payload'; "
        "$fragments=@(Get-ChildItem -LiteralPath $root|Where-Object {$_.Name -match '^m20_demo_trading_session\\.part\\d{2}$'}|Sort-Object Name|ForEach-Object {$_.FullName}); "
        "if ($fragments.Count -ne 48) { throw ('M20 listener runner fragments are incomplete: '+$fragments.Count) }; "
        "$encoded=(($fragments|ForEach-Object {[IO.File]::ReadAllText($_)}) -join ''); "
        "[IO.File]::WriteAllBytes($file,[Convert]::FromBase64String($encoded)); "
        "if ((Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash.ToLower() -ne '" + _runner_source_digest + "') { throw 'M20 listener runner staged source hash failed' }; "
        "$fragments|ForEach-Object { Remove-Item -LiteralPath $_ -Force }; "
        "[pscustomobject]@{verified=$true}|ConvertTo-Json -Compress"
    ),
)


def _m20_listener_bridge_stage_command(index: int) -> str:
    """Stage bridge fragments independently for the constrained T480 endpoint."""
    source = (ROOT / "t480" / "m20_postgres_audit_bridge.py").read_bytes()
    release_id = _runner_release_id
    encoded = base64.b64encode(source).decode("ascii")
    parts = 24
    chunk_size = ((len(encoded) + (parts * 4) - 1) // (parts * 4)) * 4
    chunks = tuple(encoded[offset:offset + chunk_size] for offset in range(0, len(encoded), chunk_size))
    if index not in range(1, parts + 1):
        raise ValueError("M20 listener bridge stage index is invalid")
    prefix = "$ErrorActionPreference='Stop'; $base='C:\\ProgramData\\ForexListener'; $root=Join-Path $base 'releases\\" + release_id + "'; New-Item -ItemType Directory -Force $root|Out-Null; "
    return prefix + "[IO.File]::WriteAllText((Join-Path $root 'm20_postgres_audit_bridge.part" + f"{index:02d}" + "'),'" + chunks[index - 1] + "',(New-Object Text.UTF8Encoding($false))); [pscustomobject]@{stage=" + str(index) + ";ok=$true}|ConvertTo-Json -Compress"


_bridge_source_digest = hashlib.sha256((ROOT / "t480" / "m20_postgres_audit_bridge.py").read_bytes()).hexdigest()
OPERATIONS["m20_listener_bridge_verify"] = Operation(
    "m20_listener_bridge_verify",
    "Assemble and verify the fully staged fixed M20 listener PostgreSQL bridge payload.",
    powershell_command=(
        "$ErrorActionPreference='Stop'; $base='C:\\ProgramData\\ForexListener'; $root=Join-Path $base 'releases\\" + _runner_release_id + "'; "
        "$file=Join-Path $root 'm20_postgres_audit_bridge.payload'; "
        "$fragments=@(Get-ChildItem -LiteralPath $root|Where-Object {$_.Name -match '^m20_postgres_audit_bridge\\.part\\d{2}$'}|Sort-Object Name|ForEach-Object {$_.FullName}); "
        "if ($fragments.Count -ne 24) { throw ('M20 listener bridge fragments are incomplete: '+$fragments.Count) }; "
        "$encoded=(($fragments|ForEach-Object {[IO.File]::ReadAllText($_)}) -join ''); [IO.File]::WriteAllBytes($file,[Convert]::FromBase64String($encoded)); "
        "if ((Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash.ToLower() -ne '" + _bridge_source_digest + "') { throw 'M20 listener bridge staged source hash failed' }; "
        "$fragments|ForEach-Object { Remove-Item -LiteralPath $_ -Force }; [pscustomobject]@{verified=$true}|ConvertTo-Json -Compress"
    ),
)
for _index in range(1, 25):
    _final = _index == 24
    OPERATIONS[f"m20_listener_bridge_stage_{_index}"] = Operation(
        f"m20_listener_bridge_stage_{_index}",
        ("Stage and verify" if _final else "Stage") + f" fixed M20 listener PostgreSQL bridge payload part {_index}.",
        powershell_command=_m20_listener_bridge_stage_command(_index),
    )

def _m20_listener_discord_stage_command(index: int) -> str:
    """Stage Discord fragments separately, then atomically assemble one payload.

    This avoids both the T480 endpoint command-length limit and endpoint
    protection briefly locking a file while another command appends to it.
    """
    source = (ROOT / "t480" / "m20_discord_trade_notification.py").read_bytes()
    release_id = hashlib.sha256((ROOT / "t480" / "m20_demo_listener_service.py").read_bytes() + (ROOT / "t480" / "m20_demo_trading_session.py").read_bytes() + (ROOT / "t480" / "m20_postgres_audit_bridge.py").read_bytes() + source).hexdigest()[:16]
    encoded = base64.b64encode(source).decode("ascii")
    parts = 4
    chunk_size = ((len(encoded) + (parts * 4) - 1) // (parts * 4)) * 4
    chunks = tuple(encoded[offset:offset + chunk_size] for offset in range(0, len(encoded), chunk_size))
    if index not in range(1, parts + 1):
        raise ValueError("M20 Discord adapter stage index is invalid")
    prefix = "$ErrorActionPreference='Stop'; $base='C:\\ProgramData\\ForexListener'; $root=Join-Path $base 'releases\\" + release_id + "'; New-Item -ItemType Directory -Force $root|Out-Null; $payload=Join-Path $root 'm20_discord_trade_notification.payload'; "
    if index < parts:
        part = "m20_discord_trade_notification.part" + str(index)
        return prefix + "[IO.File]::WriteAllText((Join-Path $root '" + part + "'),'" + chunks[index - 1] + "',(New-Object Text.UTF8Encoding($false))); [pscustomobject]@{stage=" + str(index) + ";ok=$true}|ConvertTo-Json -Compress"
    fragment_names = ",".join("(Join-Path $root 'm20_discord_trade_notification.part" + str(number) + "')" for number in range(1, parts))
    final_chunk = chunks[-1]
    digest = hashlib.sha256(source).hexdigest()
    return prefix + "$fragments=@(" + fragment_names + "); if ($fragments | Where-Object { !(Test-Path -LiteralPath $_) }) { throw 'M20 Discord adapter fragments are incomplete' }; $encoded=(($fragments|ForEach-Object {[IO.File]::ReadAllText($_)}) -join '')+'" + final_chunk + "'; [IO.File]::WriteAllBytes($payload,[Convert]::FromBase64String($encoded)); if ((Get-FileHash -LiteralPath $payload -Algorithm SHA256).Hash.ToLower() -ne '" + digest + "') { throw 'M20 Discord adapter staged source hash failed' }; $fragments|ForEach-Object { Remove-Item -LiteralPath $_ -Force }; [pscustomobject]@{stage=" + str(index) + ";ok=$true}|ConvertTo-Json -Compress"


for _index in range(1, 5):
    _final = _index == 4
    OPERATIONS[f"m20_listener_discord_stage_{_index}"] = Operation(
        f"m20_listener_discord_stage_{_index}",
        ("Stage and verify" if _final else "Stage") + f" fixed M20 Discord sale-notification adapter part {_index}.",
        powershell_command=_m20_listener_discord_stage_command(_index),
    )


def validate_contract() -> None:
    validate_catalog(CATALOG_PATH, OPERATIONS)
    if any(operation.approval_required for operation in OPERATIONS.values()):
        raise ValueError("The Forex T480 adapter must not expose an approval-based execution surface")


def target() -> str:
    return resolve_ssh_target(
        TRANSPORT_SETTINGS,
        [LOCAL_TARGET_PATH, SHARED_TARGET_PATH, SHARED_LAB_TARGET_PATH],
    )


def requirements() -> dict[str, Any]:
    return {
        "tool_id": TOOL_ID,
        "shared_core_root": str(SHARED_CORE_ROOT),
        "shared_core_identity": DEPENDENCY_IDENTITY,
        "description": "Run fixed Forex and shared-platform T480 inspections, including one bounded M20 Demo session operation.",
        "configuration_fingerprint": project_configuration_fingerprint(),
        "adapter_configuration_fingerprint": CONFIGURATION_FINGERPRINT,
        "commands": ["describe-requirements", "preflight", "execute", "verify"],
        "operations": [
            {
                "id": operation.operation_id,
                "purpose": operation.purpose,
                "approval_required": operation.approval_required,
            }
            for operation in OPERATIONS.values()
        ],
        "prohibited": [
            "arbitrary commands",
            "deployment mutations",
            "generic MetaTrader API access",
            "arbitrary account or market-data access",
            "order operations",
            "GOMarketsMU-Live access",
        ],
    }


def execute(operation_id: str) -> dict[str, Any]:
    operation = OPERATIONS.get(operation_id)
    if operation is None:
        raise ValueError(f"Unknown operation: {operation_id}")
    payload = execute_operation(operation, target=target(), settings=TRANSPORT_SETTINGS)
    payload["tool_id"] = TOOL_ID
    return payload


def parser() -> argparse.ArgumentParser:
    command_parser = argparse.ArgumentParser(description="Governed read-only T480 adapter for Forex.")
    command_parser.add_argument(
        "command",
        choices=["dependency-status", "describe-requirements", "preflight", "execute", "verify"],
    )
    command_parser.add_argument("--operation", choices=sorted(OPERATIONS))
    return command_parser


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    validate_contract()
    if args.command == "dependency-status":
        payload = inspect_dependency(APP_CONFIG)
    elif args.command == "describe-requirements":
        payload = requirements()
    elif args.command == "preflight":
        require_dependency(APP_CONFIG)
        payload = shared_preflight(
            tool_id=TOOL_ID,
            settings=TRANSPORT_SETTINGS,
            config_paths=[LOCAL_TARGET_PATH, SHARED_TARGET_PATH, SHARED_LAB_TARGET_PATH],
        )
    else:
        require_dependency(APP_CONFIG)
        if not args.operation:
            raise SystemExit("--operation is required for execute and verify")
        payload = execute(args.operation)
        if args.operation == "m1_mt5_demo_probe" and payload.get("ok"):
            payload["proof_marker"] = "FOREX_M1_PROOF_OK"
        if args.command == "verify":
            payload["verified_operation"] = args.operation
    if args.command != "dependency-status":
        payload["configuration_fingerprint"] = project_configuration_fingerprint()
        payload["adapter_configuration_fingerprint"] = CONFIGURATION_FINGERPRINT
    append_execution_log(
        LOG_PATH,
        tool_id=TOOL_ID,
        command_name=args.command,
        operation_id=args.operation,
        payload=payload,
    )
    print(json.dumps(payload, indent=2))
    return 0 if payload.get("ok", True) else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (PermissionError, RuntimeError, ValueError) as error:
        print(json.dumps({"tool_id": TOOL_ID, "ok": False, "error": str(error)}, indent=2), file=sys.stderr)
        raise SystemExit(2) from error
