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
    code = "import json,sys;import MetaTrader5 as m;p=sys.argv[1];initialized=m.initialize(path=p);a=m.account_info() if initialized else None;bad=(not a or a.server!='GOMarketsMU-Demo' or a.currency!='AUD');positions=m.positions_get() if a and not bad else None;position_error=None if positions is not None else str(m.last_error());result={'ok':bool(a) and not bad and positions is not None,'server':getattr(a,'server',None),'currency':getattr(a,'currency',None),'balance':getattr(a,'balance',None),'equity':getattr(a,'equity',None),'margin':getattr(a,'margin',None),'free_margin':getattr(a,'margin_free',None),'margin_level':getattr(a,'margin_level',None),'leverage':getattr(a,'leverage',None),'position_observation':'AVAILABLE' if positions is not None else 'UNAVAILABLE','open_positions':len(positions) if positions is not None else None,'mt5_error':None if a and positions is not None else str(m.last_error()),'position_error':position_error};print(json.dumps(result,separators=(',',':')));m.shutdown() if initialized else None;sys.exit(0 if result['ok'] else 3)"
    return "$ErrorActionPreference='Stop'; $s=gc -Raw (Join-Path $env:USERPROFILE 'Documents\\Code\\forex-m1-probe\\mt5.local.json')|ConvertFrom-Json; if ([string]::IsNullOrWhiteSpace($s.python_path) -or !(Test-Path -LiteralPath $s.python_path)) { throw 'M20 configured Python interpreter is absent' }; & $s.python_path -c '" + code.replace("'", "''") + "' $s.terminal_path; exit $LASTEXITCODE"


def _m20_unresolved_history_probe_command() -> str:
    """Read a fixed narrow Demo EURUSD deal window for unresolved-attempt attribution."""
    code = (
        "import json,sys;from datetime import datetime,timezone;import MetaTrader5 as m;"
        "p=sys.argv[1];ok=m.initialize(path=p);a=m.account_info() if ok else None;"
        "bad=(not a or a.server!='GOMarketsMU-Demo' or a.currency!='AUD');"
        "d=m.history_deals_get(datetime(2026,9,3,12,tzinfo=timezone.utc),datetime(2026,9,3,15,30,tzinfo=timezone.utc)) if not bad else None;"
        "rows=[] if d is None else [{'ticket':int(x.ticket),'order':int(x.order),'position_identifier':int(x.position_id),'broker_time_utc':datetime.fromtimestamp(x.time,timezone.utc).isoformat().replace('+00:00','Z'),'time_utc':datetime.fromtimestamp(x.time-10800,timezone.utc).isoformat().replace('+00:00','Z'),'entry':int(x.entry),'type':int(x.type),'volume':float(x.volume),'price':float(x.price),'profit':float(x.profit),'commission':float(x.commission),'swap':float(x.swap),'fee':float(x.fee),'reason':int(x.reason)} for x in d if x.symbol=='EURUSD'];"
        "print(json.dumps({'ok':bool(a) and not bad and d is not None,'server':getattr(a,'server',None),'currency':getattr(a,'currency',None),'symbol':'EURUSD','broker_timestamp_offset_seconds':10800,'from_broker_time_utc':'2026-09-03T12:00:00Z','to_broker_time_utc':'2026-09-03T15:30:00Z','deals':rows,'mt5_error':None if d is not None else str(m.last_error())},separators=(',',':')));"
        "m.shutdown() if ok else None;sys.exit(0 if a and not bad and d is not None else 3)"
    )
    return "$ErrorActionPreference='Stop'; $s=gc -Raw (Join-Path $env:USERPROFILE 'Documents\\Code\\forex-m1-probe\\mt5.local.json')|ConvertFrom-Json; if ([string]::IsNullOrWhiteSpace($s.python_path) -or !(Test-Path -LiteralPath $s.python_path)) { throw 'M20 configured Python interpreter is absent' }; & $s.python_path -c '" + code.replace("'", "''") + "' $s.terminal_path; exit $LASTEXITCODE"


def _m20_swap_terms_command() -> str:
    code = """import json,sys,datetime
import MetaTrader5 as m
if not m.initialize(path=sys.argv[1]): raise SystemExit('Terminal unavailable')
try:
 a=m.account_info()
 if not a or a.server!='GOMarketsMU-Demo' or a.currency!='AUD': raise SystemExit('Demo AUD required')
 s=m.symbol_info('EURUSD'); q=m.symbol_info_tick('EURUSD'); c=m.symbol_info_tick('AUDUSD')
 fields=('name','currency_base','currency_profit','currency_margin','point','trade_tick_size','trade_tick_value_loss','trade_contract_size','volume_min','swap_mode','swap_long','swap_short','swap_rollover3days')
 print(json.dumps({'captured_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'server':a.server,'currency':a.currency,'symbol':{k:getattr(s,k,None) for k in fields},'quote':{k:getattr(q,k,None) for k in ('bid','ask','time')},'audusd':{k:getattr(c,k,None) for k in ('bid','ask','time')}}))
finally:m.shutdown()
"""
    return "$ErrorActionPreference='Stop';$s=gc -Raw (Join-Path $env:USERPROFILE 'Documents\\Code\\forex-m1-probe\\mt5.local.json')|ConvertFrom-Json;& $s.python_path -c '" + code.replace("'", "''") + "' $s.terminal_path;exit $LASTEXITCODE"


def _m20_wave1_candles_command() -> str:
    code = ("import json,sys;import MetaTrader5 as m;ok=m.initialize(path=sys.argv[1]);a=m.account_info() if ok else None;"
            "valid=bool(a) and a.server=='GOMarketsMU-Demo' and a.currency=='AUD';s=m.symbol_info('EURUSD') if valid else None;t=m.terminal_info() if valid else None;"
            "r=m.copy_rates_from_pos('EURUSD',m.TIMEFRAME_M1,1,72) if valid else None;e=m.last_error();r5=m.copy_rates_from_pos('EURUSD',m.TIMEFRAME_M5,1,5) if valid else None;e5=m.last_error();"
            "print(json.dumps({'ok':valid,'server':getattr(a,'server',None),'terminal_build':getattr(t,'build',None),'maxbars':getattr(t,'maxbars',None),'connected':getattr(t,'connected',None),'api_version':m.__version__,'symbol_visible':getattr(s,'visible',None),'symbol_selected':getattr(s,'select',None),'rates_count':len(r) if r is not None else None,'rates_error':e,'m5_count':len(r5) if r5 is not None else None,'m5_error':e5,'last_bar_time':int(r[-1]['time']) if r is not None and len(r) else None}));m.shutdown() if ok else None")
    return "$ErrorActionPreference='Stop';$s=gc -Raw (Join-Path $env:USERPROFILE 'Documents\\Code\\forex-m1-probe\\mt5.local.json')|ConvertFrom-Json;& $s.python_path -c '" + code.replace("'", "''") + "' $s.terminal_path;exit $LASTEXITCODE"


def _m20_terminal_history_diagnostics_command() -> str:
    code = r"""import json,sys,re,pathlib,datetime
import MetaTrader5 as m
ok=m.initialize(path=sys.argv[1]);a=m.account_info() if ok else None
if not a or a.server!='GOMarketsMU-Demo' or a.currency!='AUD': raise SystemExit('Demo account required')
t=m.terminal_info();root=pathlib.Path(t.data_path);files=[]
for p in sorted((root/'logs').glob('[0-9]'*8+'.log'))[-2:]:
 text=p.read_bytes()[-100000:].decode('utf-16-le',errors='replace')
 lines=[re.sub(r'\b\d{6,}\b','[number]',x) for x in text.splitlines() if any(k in x.lower() for k in ['history','error','failed','synchron','update','crash'])][-35:]
 files.append({'file':p.name,'lines':lines})
print(json.dumps({'logs':files,'positions_count':None if m.positions_get() is None else len(m.positions_get()),'orders_count':None if m.orders_get() is None else len(m.orders_get())}));m.shutdown()
"""
    return "$ErrorActionPreference='Stop';$s=gc -Raw (Join-Path $env:USERPROFILE 'Documents\\Code\\forex-m1-probe\\mt5.local.json')|ConvertFrom-Json;$ps=@(Get-CimInstance Win32_Process -Filter \"Name='terminal64.exe'\" | Select-Object ProcessId,SessionId,@{Name='matches_configured_path';Expression={$_.ExecutablePath -eq $s.terminal_path}});$ps|ConvertTo-Json -Compress;& $s.python_path -c '" + code.replace("'", "''") + "' $s.terminal_path;exit $LASTEXITCODE"


def _m20_close_duplicate_terminal_command() -> str:
    # Narrow recovery: only duplicate interactive instances of the configured
    # terminal; the Session 0 terminal and listener state are preserved.
    code = "import MetaTrader5 as m,sys;ok=m.initialize(path=sys.argv[1]);a=m.account_info() if ok else None;p=m.positions_get() if a else None;o=m.orders_get() if a else None;valid=bool(a) and a.server=='GOMarketsMU-Demo' and a.currency=='AUD' and p is not None and len(p)==0 and o is not None and len(o)==0;m.shutdown() if ok else None;sys.exit(0 if valid else 3)"
    return (
        "$ErrorActionPreference='Stop';$state='C:\\ProgramData\\ForexListener\\state';"
        "if(!(Test-Path (Join-Path $state 'm20_demo_maintenance_hold.local.json'))){throw 'Recovery requires maintenance hold'};"
        "if((Get-ScheduledTask -TaskName 'Forex-M20-Demo-Listener').State -eq 'Running'){throw 'Stop listener before terminal recovery'};"
        "$s=gc -Raw (Join-Path $env:USERPROFILE 'Documents\\Code\\forex-m1-probe\\mt5.local.json')|ConvertFrom-Json;"
        "& $s.python_path -c '" + code.replace("'", "''") + "' $s.terminal_path;if($LASTEXITCODE -ne 0){throw 'Fresh Demo flatness not established'};"
        "$ps=@(Get-CimInstance Win32_Process -Filter \"Name='terminal64.exe'\" | Where-Object {$_.ExecutablePath -eq $s.terminal_path});"
        "if(@($ps|Where-Object {$_.SessionId -eq 0}).Count -ne 1){throw 'Expected one service-session terminal'};"
        "$closed=@();foreach($p in @($ps|Where-Object {$_.SessionId -ne 0})){Stop-Process -Id $p.ProcessId -Force -ErrorAction Stop;$closed+=$p.ProcessId};"
        "[pscustomobject]@{closed_duplicate_process_ids=$closed;service_terminal_preserved=$true;maintenance_hold=$true}|ConvertTo-Json -Compress"
    )


def _m20_wave1_history_command() -> str:
    """Fixed read-only account history covering the current reconciliation gap."""
    code = (
        "import json,sys;from datetime import datetime,timezone;import MetaTrader5 as m;"
        "ok=m.initialize(path=sys.argv[1]);a=m.account_info() if ok else None;"
        "valid=bool(a) and a.server=='GOMarketsMU-Demo' and a.currency=='AUD';"
        "start=datetime(2026,9,7,tzinfo=timezone.utc);end=datetime(2026,9,11,tzinfo=timezone.utc);"
        "d=m.history_deals_get(start,end) if valid else None;o=m.history_orders_get(start,end) if valid else None;"
        "bounded=d is not None and o is not None and len(d)<=200 and len(o)<=200;"
        "dk='ticket order time time_msc type entry magic position_id reason volume price commission swap profit fee symbol comment'.split();"
        "okeys='ticket time_setup time_setup_msc time_done time_done_msc type state magic position_id reason volume_initial volume_current price_open sl tp symbol comment'.split();"
        "rows=lambda values,keys:[{k:getattr(x,k,None) for k in keys} for x in values];"
        "print(json.dumps({'ok':valid and bounded,'captured_at_utc':datetime.now(timezone.utc).isoformat(),'server':getattr(a,'server',None),'currency':getattr(a,'currency',None),'broker_timestamp_offset_seconds':10800,'deals':rows(d,dk) if bounded else None,'orders':rows(o,okeys) if bounded else None,'error':None if bounded else 'History unavailable or exceeds fixed 200-row bound'}));"
        "m.shutdown() if ok else None;sys.exit(0 if valid and bounded else 3)"
    )
    return "$ErrorActionPreference='Stop'; $s=gc -Raw (Join-Path $env:USERPROFILE 'Documents\\Code\\forex-m1-probe\\mt5.local.json')|ConvertFrom-Json; & $s.python_path -c '" + code.replace("'", "''") + "' $s.terminal_path; exit $LASTEXITCODE"


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
    financing = json.dumps(configuration.runtime.financing_policy, separators=(",", ":"))
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
        "foreach($k in @('FOREX_M20_DEMO_TRADING_SESSION_SHA256','FOREX_M20_POSTGRES_AUDIT_BRIDGE_SHA256','FOREX_M20_CONFIGURATION_FINGERPRINT','FOREX_M20_TICK_TIME_OFFSET_SECONDS','FOREX_M20_MINIMUM_NET_PROFIT_AUD','FOREX_M20_FINANCING_POLICY','FOREX_M20_PERSISTENT_RISK_POLICY','FOREX_M20_APPLICATION_REVISION')){[Environment]::SetEnvironmentVariable($k,[string]$c.$k,'Process')}; "
        "& $c.python_path $p $c.terminal_path $lease; exit $LASTEXITCODE"
    )



def _m20_reconcile_retained_history_command() -> str:
    """Run only the fixed append-only reconciliation of four retained Demo positions."""
    runner_digest = hashlib.sha256((ROOT / "t480" / "m20_demo_trading_session.py").read_bytes()).hexdigest()
    bridge_digest = hashlib.sha256((ROOT / "t480" / "m20_postgres_audit_bridge.py").read_bytes()).hexdigest()
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    fingerprint = project_configuration_fingerprint()
    return (
        "$ErrorActionPreference='Stop'; $b='C:\\ProgramData\\ForexListener';$s=Join-Path $b state;$h=gc -Raw (Join-Path $s 'm20_demo_listener_status.local.json')|ConvertFrom-Json;$r=[string]$h.release_id;"
        "if($r -notmatch '^[0-9a-f]{16}$'){throw 'M20 active release id is absent or invalid'};$root=Join-Path $b ('releases\\'+$r);$c=gc -Raw (Join-Path $s 'm20_demo_listener_service.local.json')|ConvertFrom-Json;"
        "if($c.FOREX_M20_APPLICATION_REVISION -ne '" + revision + "' -or $c.FOREX_M20_CONFIGURATION_FINGERPRINT -ne '" + fingerprint + "'){throw 'M20 active release binding differs from the fixed reconciliation'};"
        "$p=Join-Path $root 'm20_demo_trading_session.payload';$q=Join-Path $root 'm20_postgres_audit_bridge.payload';if(!(Test-Path -LiteralPath $p)-or !(Test-Path -LiteralPath $q)){throw 'M20 release payload is absent'};"
        "if((Get-FileHash $p -Algorithm SHA256).Hash.ToLower() -ne '" + runner_digest + "' -or (Get-FileHash $q -Algorithm SHA256).Hash.ToLower() -ne '" + bridge_digest + "'){throw 'M20 fixed reconciliation payload hash differs'};"
        "$env:FOREX_M20_DEMO_TRADING_SESSION_SHA256='" + runner_digest + "';$env:FOREX_M20_POSTGRES_AUDIT_BRIDGE_SHA256='sha256:" + bridge_digest + "';$env:FOREX_M20_CONFIGURATION_FINGERPRINT=$c.FOREX_M20_CONFIGURATION_FINGERPRINT;$env:FOREX_M20_APPLICATION_REVISION=$c.FOREX_M20_APPLICATION_REVISION;$env:FOREX_M20_TICK_TIME_OFFSET_SECONDS=$c.FOREX_M20_TICK_TIME_OFFSET_SECONDS;& $c.python_path $p $c.terminal_path _ --reconcile-retained-history;exit $LASTEXITCODE"
    )

def _m20_listener_status_command() -> str:
    """Return a redacted heartbeat only; recovery is an explicit fixed operation."""
    return (
        "$ErrorActionPreference='Stop'; "
        "$state='C:\\ProgramData\\ForexListener\\state'; $p=Join-Path $state 'm20_demo_listener_status.local.json'; "
        "if (!(Test-Path -LiteralPath $p)) { [pscustomobject]@{running=$false;state='NOT_STARTED';detail='No listener heartbeat exists.'}|ConvertTo-Json -Compress; exit 0 }; "
        "$s=gc -Raw -LiteralPath $p|ConvertFrom-Json; $notifications=$false; $config=Join-Path $state 'm20_demo_listener_service.local.json'; if(Test-Path -LiteralPath $config){try{$c=gc -Raw -LiteralPath $config|ConvertFrom-Json;$notifications=(([string]$c.FOREX_M20_DISCORD_NOTIFICATIONS_ENABLED).ToLower() -eq 'true' -and -not [string]::IsNullOrWhiteSpace([string]$c.FOREX_M20_DISCORD_WEBHOOK_URL))}catch{}}; "
        "$age=$null; $stale=$false; try { $age=[Math]::Round(((Get-Date).ToUniversalTime()-([datetime]::Parse([string]$s.heartbeat_at_utc)).ToUniversalTime()).TotalSeconds,1); $stale=($age -ge 30) } catch { $stale=$true }; "
        "$recovery=if ($stale) { 'EXPLICIT_RECOVERY_REQUIRED' } else { 'NOT_REQUIRED' }; $recoveryDetail=$null; "
        "$protection=$null;$protectionObservation='NO_DURABLE_PROTECTION_RECORD';$job=Join-Path $state 'm20_demo_monitor_job.local.json';if(Test-Path -LiteralPath $job){try{$j=gc -Raw -LiteralPath $job|ConvertFrom-Json;$protection=[ordered]@{ticket=$j.position.ticket;action=$j.proposal.action;entry_price=$j.position.price_open;stop_loss=$j.position.sl;take_profit=$j.position.tp;submitted_at_utc=$j.submitted_at_utc};$protectionObservation=if($s.monitor.state -eq 'RUNNING'){'OBSERVED_ACTIVE'}else{'LAST_KNOWN_UNVERIFIED'}}catch{$protectionObservation='DURABLE_PROTECTION_STATE_UNREADABLE'}};$drill=if($null -eq $s.protected_restart_drill){[ordered]@{observation='NOT_REPORTED';state=$null}}else{$s.protected_restart_drill};$state=if ($stale) { 'STALE' } else { $s.state }; $supervisorAlive=(!$stale -and ($s.state -notin @('STOPPED','STARTUP_FAILED'))); [pscustomobject]@{running=$supervisorAlive;state=$state;release_id=$s.release_id;heartbeat_at_utc=$s.heartbeat_at_utc;heartbeat_at_nzst=$s.heartbeat_at_nzst;heartbeat_age_seconds=$age;iteration=$s.process_iteration;assessment_total=$s.assessment_total;assessment_started_at_utc=$s.assessment_started_at_utc;assessment_completed_at_utc=$s.assessment_completed_at_utc;assessment_duration_ms=$s.assessment_duration_ms;next_assessment_at_utc=$s.next_assessment_at_utc;next_assessment_at_nzst=$s.next_assessment_at_nzst;detail=$s.detail;monitor=$s.monitor;quote=$s.quote;discord_open_alert_configured=$notifications;open_position_protection=$protection;protection_observation=$protectionObservation;protected_restart_drill=$drill;last_result=$s.last_result;recovery_action=$recovery;recovery_detail=$recoveryDetail}|ConvertTo-Json -Compress -Depth 8"
    )


def _m20_listener_diagnostics_command() -> str:
    """Inspect the fixed task and its process identities without recovery."""
    return (
        "$ErrorActionPreference='Stop'; $task=Get-ScheduledTask -TaskName 'Forex-M20-Demo-Listener'; "
        "$info=Get-ScheduledTaskInfo -TaskName $task.TaskName; "
        "$settings=$task.Settings|Select-Object DisallowStartIfOnBatteries,StopIfGoingOnBatteries,ExecutionTimeLimit,RestartCount,RestartInterval; "
        "$events=@(Get-WinEvent -FilterHashtable @{LogName='Application';StartTime=$info.LastRunTime;Id=1000,1001} -MaxEvents 10 -ErrorAction SilentlyContinue|Where-Object {$_.Message -match 'python'}|Select-Object TimeCreated,Id,ProviderName,Message); "
        "$processes=@(Get-CimInstance Win32_Process | Where-Object { $_.Name -match '^python(w)?\\.exe$' -and $_.CommandLine -like '*ForexListener*' } | Select-Object ProcessId,ParentProcessId,SessionId,CreationDate); "
        "$hold=Test-Path -LiteralPath 'C:\\ProgramData\\ForexListener\\state\\m20_demo_maintenance_hold.local.json'; $binding=[ordered]@{observation='UNAVAILABLE'};try{$state='C:\\ProgramData\\ForexListener\\state';$h=gc -Raw (Join-Path $state 'm20_demo_listener_status.local.json')|ConvertFrom-Json;$r=[string]$h.release_id;if($r -notmatch '^[0-9a-f]{16}$'){throw 'bad release'};$c=gc -Raw (Join-Path $state 'm20_demo_listener_service.local.json')|ConvertFrom-Json;$l=gc -Raw (Join-Path $state 'm20_demo_session.local.json')|ConvertFrom-Json;$root='C:\\ProgramData\\ForexListener\\releases\\'+$r;$hash=[ordered]@{};foreach($x in @('m20_demo_listener_service.payload','m20_demo_trading_session.payload','m20_postgres_audit_bridge.payload','m20_discord_trade_notification.payload')){$hash[$x]='sha256:'+(Get-FileHash (Join-Path $root $x) -Algorithm SHA256).Hash.ToLower()};$binding=[ordered]@{observation='VALID';application_revision=$c.FOREX_M20_APPLICATION_REVISION;configuration_fingerprint=$c.FOREX_M20_CONFIGURATION_FINGERPRINT;payload_sha256=$hash;lease=[ordered]@{session_id=$l.session_id;server=$l.server;symbol=$l.symbol;expires_at_utc=$l.expires_at_utc;maximum_trades=$l.maximum_trades;maximum_duration_minutes=$l.maximum_duration_minutes;maximum_open_positions=$l.maximum_open_positions;maximum_notional_per_trade_usd=$l.maximum_notional_per_trade_usd;maximum_cumulative_notional_usd=$l.maximum_cumulative_notional_usd;maximum_loss_per_trade_aud=$l.maximum_loss_per_trade_aud};persistent_risk_policy=$c.FOREX_M20_PERSISTENT_RISK_POLICY;financing_policy=$c.FOREX_M20_FINANCING_POLICY}}catch{}; "
        "$failure=$null;$f='C:\\ProgramData\\ForexListener\\state\\m20_demo_listener_failures.local.jsonl';if(Test-Path -LiteralPath $f){$failure=Get-Content -LiteralPath $f -Tail 1|ConvertFrom-Json}; "
        "[pscustomobject]@{captured_at_utc=(Get-Date).ToUniversalTime().ToString('o');task_state=$task.State.ToString();last_result=$info.LastTaskResult;last_run_utc=$info.LastRunTime.ToUniversalTime().ToString('o');logon_type=$task.Principal.LogonType.ToString();maintenance_hold_present=$hold;deployment_binding=$binding;processes=$processes;settings=$settings;python_events=$events;last_failure=$failure}|ConvertTo-Json -Depth 6 -Compress"
    )


def _m20_listener_continuity_status_command() -> str:
    """Read retained continuity evidence and its fixed task identity only."""
    return (
        "$ErrorActionPreference='Stop';$s='C:\\ProgramData\\ForexListener\\state';$p=Join-Path $s 'm20_demo_continuity_protocol.local.json';"
        "$l=Join-Path $s 'm20_demo_continuity_protocol.local.jsonl';$t=Get-ScheduledTask -TaskName 'Forex-M20-Continuity-Protocol' -ErrorAction SilentlyContinue;$i=if($t){Get-ScheduledTaskInfo -TaskName $t.TaskName}else{$null};"
        "$r=$null;$o='ABSENT';if(Test-Path -LiteralPath $p){try{$r=gc -Raw $p|ConvertFrom-Json;$o='AVAILABLE'}catch{$o='UNREADABLE'}};"
        "[pscustomobject]@{captured_at_utc=(Get-Date).ToUniversalTime().ToString('o');observation=$o;record=$r;event_log_sha256=if(Test-Path -LiteralPath $l){'sha256:'+(Get-FileHash -LiteralPath $l -Algorithm SHA256).Hash.ToLower()}else{$null};task_state=if($t){$t.State.ToString()}else{'ABSENT'};logon_type=if($t){$t.Principal.LogonType.ToString()}else{$null};last_result=if($i){$i.LastTaskResult}else{$null};last_run_utc=if($i){$i.LastRunTime.ToUniversalTime().ToString('o')}else{$null}}|ConvertTo-Json -Compress -Depth 10"
    )


def _m20_listener_cancel_continuity_protocol_command() -> str:
    """Stop only the non-trading continuity task and retain its cancellation."""
    return (
        "$ErrorActionPreference='Stop';$s='C:\\ProgramData\\ForexListener\\state';$h=Join-Path $s 'm20_demo_maintenance_hold.local.json';"
        "if(!(Test-Path -LiteralPath $h)){throw 'Continuity cancellation requires maintenance hold'};$n='Forex-M20-Continuity-Protocol';$t=Get-ScheduledTask -TaskName $n -ErrorAction Stop;"
        "if($t.State -eq 'Running'){Stop-ScheduledTask -TaskName $n -ErrorAction Stop};$p=Join-Path $s 'm20_demo_continuity_protocol.local.json';"
        "if(Test-Path -LiteralPath $p){$r=gc -Raw $p|ConvertFrom-Json;if($r.state -eq 'ARMED'){$r|Add-Member -NotePropertyName state -NotePropertyValue 'INCONCLUSIVE' -Force;$r|Add-Member -NotePropertyName completed_at_utc -NotePropertyValue ((Get-Date).ToUniversalTime().ToString('o')) -Force;$r|Add-Member -NotePropertyName failure_reason -NotePropertyValue 'OPERATOR_CANCELLED_BEFORE_INTERVAL' -Force;$r|Add-Member -NotePropertyName recovery_delivery -NotePropertyValue ([ordered]@{state='NOT_ATTEMPTED'}) -Force;$tmp=$p+'.tmp';[IO.File]::WriteAllText($tmp,($r|ConvertTo-Json -Compress -Depth 12),(New-Object Text.UTF8Encoding($false)));Move-Item -LiteralPath $tmp -Destination $p -Force}};"
        "[pscustomobject]@{cancelled=$true;task=$n;maintenance_hold=$true;broker_mutation='NONE'}|ConvertTo-Json -Compress"
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


def _m20_listener_install_watchdog_command() -> str:
    """Install a fixed Session-0 task that asks Task Scheduler to run the listener."""
    return (
        "$ErrorActionPreference='Stop';$listener='Forex-M20-Demo-Listener';$watch='Forex-M20-Listener-Watchdog';"
        "if($null -eq (Get-ScheduledTask -TaskName $listener -ErrorAction SilentlyContinue)){throw 'Listener task is absent'};"
        "$principal=New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType S4U -RunLevel Highest;"
        "$action=New-ScheduledTaskAction -Execute 'schtasks.exe' -Argument '/run /tn \"Forex-M20-Demo-Listener\"';"
        "$boot=New-ScheduledTaskTrigger -AtStartup;$repeat=New-ScheduledTaskTrigger -Once -At ((Get-Date).AddMinutes(1)) -RepetitionInterval (New-TimeSpan -Minutes 2) -RepetitionDuration (New-TimeSpan -Days 3650);"
        "$settings=New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 1) -MultipleInstances IgnoreNew;"
        "Register-ScheduledTask -TaskName $watch -Action $action -Trigger @($boot,$repeat) -Principal $principal -Settings $settings -Force|Out-Null;Start-ScheduledTask -TaskName $watch -ErrorAction SilentlyContinue;"
        "[pscustomobject]@{installed=$true;task=$watch;listener=$listener;interval_minutes=2;broker_mutation='NONE'}|ConvertTo-Json -Compress"
    )


def _m20_listener_watchdog_status_command() -> str:
    """Read the fixed watchdog identity and schedule without starting either task."""
    return (
        "$ErrorActionPreference='Stop';$t=Get-ScheduledTask -TaskName 'Forex-M20-Listener-Watchdog' -ErrorAction SilentlyContinue;"
        "if($null -eq $t){[pscustomobject]@{installed=$false;task='Forex-M20-Listener-Watchdog'}|ConvertTo-Json -Compress;exit 0};"
        "$i=Get-ScheduledTaskInfo -TaskName $t.TaskName;$a=$t.Actions|Select-Object -First 1;"
        "[pscustomobject]@{installed=$true;task=$t.TaskName;state=$t.State.ToString();logon_type=$t.Principal.LogonType.ToString();execute=$a.Execute;arguments=$a.Arguments;last_result=$i.LastTaskResult;last_run_utc=$i.LastRunTime.ToUniversalTime().ToString('o')}|ConvertTo-Json -Compress"
    )


def _m20_listener_run_reboot_recovery_protocol_command() -> str:
    """Arm the fixed held-only post-boot verifier, then request a T480 reboot."""
    return (
        "$ErrorActionPreference='Stop';$s='C:\\ProgramData\\ForexListener\\state';if(!(Test-Path (Join-Path $s 'm20_demo_maintenance_hold.local.json'))){throw 'hold required'};$l=Get-ScheduledTask 'Forex-M20-Demo-Listener';$w=Get-ScheduledTask 'Forex-M20-Listener-Watchdog';if($l.Principal.LogonType -ne 'S4U'-or $w.Principal.LogonType -ne 'S4U'){throw 'S4U required'};$h=gc -Raw (Join-Path $s 'm20_demo_listener_status.local.json')|ConvertFrom-Json;if($h.state -ne 'MAINTENANCE_HOLD'-or $h.monitor.state -ne 'IDLE'-or @($h.monitor.result.recovered).Count -ne 0){throw 'held idle monitor required'};if(((Get-Date).ToUniversalTime()-([datetime]::Parse($h.heartbeat_at_utc)).ToUniversalTime()).TotalSeconds -ge 30){throw 'heartbeat stale'};$c=gc -Raw (Join-Path $env:USERPROFILE 'Documents\\Code\\forex-m1-probe\\mt5.local.json')|ConvertFrom-Json;& $c.python_path -c \"import sys;import MetaTrader5 as m;m.initialize(path=sys.argv[1]);a=m.account_info();p=m.positions_get();m.shutdown();raise SystemExit(0 if a and a.server=='GOMarketsMU-Demo' and a.currency=='AUD' and p is not None and len(p)==0 else 3)\" $c.terminal_path;if($LASTEXITCODE){throw 'flat available Demo account required'};"
        r'''$p=Join-Path $s 'm20_demo_reboot_recovery.local.json';$o=[ordered]@{run_id=([guid]::NewGuid().ToString('N'));state='ARMED';listener_release_id=$h.release_id;broker_mutation='NONE'};[IO.File]::WriteAllText($p,($o|ConvertTo-Json -Compress),(New-Object Text.UTF8Encoding($false)));$f=Join-Path $s 'm20_demo_reboot_recovery_postboot.ps1';$x="Start-Sleep 75;`$s='C:\ProgramData\ForexListener\state';`$p=Join-Path `$s 'm20_demo_reboot_recovery.local.json';`$r=gc -Raw `$p|ConvertFrom-Json;`$l=Get-ScheduledTask 'Forex-M20-Demo-Listener';`$w=Get-ScheduledTask 'Forex-M20-Listener-Watchdog';`$h=gc -Raw (Join-Path `$s 'm20_demo_listener_status.local.json')|ConvertFrom-Json;`$r|Add-Member postboot_release_id `$h.release_id -Force;`$r|Add-Member listener_task_state `$l.State.ToString() -Force;`$r|Add-Member watchdog_task_state `$w.State.ToString() -Force;`$r|Add-Member postboot_heartbeat_at_utc `$h.heartbeat_at_utc -Force;`$r.state='POSTBOOT_CAPTURED';[IO.File]::WriteAllText(`$p,(`$r|ConvertTo-Json -Compress),(New-Object Text.UTF8Encoding(`$false)))";[IO.File]::WriteAllText($f,$x,(New-Object Text.UTF8Encoding($false)));'''
        '''$t='Forex-M20-Reboot-Recovery-Verifier';$a=New-ScheduledTaskAction powershell.exe ('-NoProfile -NonInteractive -File '+$f);$g=New-ScheduledTaskTrigger -AtStartup;$q=New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType S4U -RunLevel Highest;Register-ScheduledTask $t -Action $a -Trigger $g -Principal $q -Force|Out-Null;$z='Forex-M20-Reboot-Request';$ra=New-ScheduledTaskAction shutdown.exe '/r /f /t 5';Register-ScheduledTask $z -Action $ra -Principal $q -Force|Out-Null;Start-ScheduledTask $z;[pscustomobject]@{armed=$true;run_id=$o.run_id;broker_mutation='NONE'}|ConvertTo-Json -Compress'''



    )


def _m20_listener_reboot_recovery_status_command() -> str:
    """Read only the retained reboot protocol record after T480 returns."""
    return (
        "$ErrorActionPreference='Stop';$p='C:\\ProgramData\\ForexListener\\state\\m20_demo_reboot_recovery.local.json';"
        "if(!(Test-Path -LiteralPath $p)){[pscustomobject]@{observation='ABSENT'}|ConvertTo-Json -Compress;exit 0};$r=gc -Raw $p|ConvertFrom-Json;"
        "[pscustomobject]@{observation='AVAILABLE';record=$r;sha256=('sha256:'+(Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash.ToLower())}|ConvertTo-Json -Compress -Depth 8"
    )


def _m20_listener_activate_demo_lease_command() -> str:
    """Create only the fixed, bounded M20 Demo lease for the listener."""
    return (
        "$ErrorActionPreference='Stop'; $state='C:\\ProgramData\\ForexListener\\state'; New-Item -ItemType Directory -Force $state|Out-Null; "
        "$now=(Get-Date).ToUniversalTime(); $lease=[ordered]@{schema_version='forex.m20.demo-session-lease.v1';session_id=([guid]::NewGuid().ToString());enabled=$true;server='GOMarketsMU-Demo';symbol='EURUSD';starts_at_utc=$now.ToString('o');expires_at_utc='9999-12-31T23:59:59Z';maximum_trades=$null;maximum_duration_minutes=0;maximum_open_positions=1;maximum_notional_per_trade_usd=10000;maximum_cumulative_notional_usd=100000;maximum_loss_per_trade_aud=100;audit_prerequisites=[ordered]@{postgres_audit_schema='READY';proposal_persistence='READY';idempotency_store='READY'}}; "
        "$tmp=Join-Path $state 'm20_demo_session.local.json.tmp'; [IO.File]::WriteAllText($tmp,($lease|ConvertTo-Json -Compress -Depth 4),(New-Object Text.UTF8Encoding($false))); Move-Item -LiteralPath $tmp -Destination (Join-Path $state 'm20_demo_session.local.json') -Force; "
        "[pscustomobject]@{activated=$true;server=$lease.server;symbol=$lease.symbol;session_id=$lease.session_id;starts_at_utc=$lease.starts_at_utc;expires_at_utc=$lease.expires_at_utc;maximum_trades=$lease.maximum_trades;maximum_notional_per_trade_usd=$lease.maximum_notional_per_trade_usd;maximum_cumulative_notional_usd=$lease.maximum_cumulative_notional_usd;maximum_loss_per_trade_aud=$lease.maximum_loss_per_trade_aud}|ConvertTo-Json -Compress"
    )


def _m20_listener_activate_refusal_drill_lease_command() -> str:
    """Reduce only planned loss on the existing lease; preserve cumulative caps."""
    return (
        "$ErrorActionPreference='Stop';$s='C:\\ProgramData\\ForexListener\\state';"
        "if(!(Test-Path (Join-Path $s 'm20_demo_maintenance_hold.local.json'))){throw 'Refusal setup requires maintenance hold'};"
        "$p=Join-Path $s 'm20_demo_session.local.json';$b=Join-Path $s 'm20_demo_refusal_original_lease.local.json';"
        "if(Test-Path $b){throw 'An unfinished refusal drill already exists'};$l=gc -Raw $p|ConvertFrom-Json;"
        "if($l.server -ne 'GOMarketsMU-Demo'-or $l.symbol -ne 'EURUSD'-or $l.maximum_loss_per_trade_aud -ne 100){throw 'Expected approved Demo lease'};"
        "Copy-Item -LiteralPath $p -Destination $b;$l.maximum_loss_per_trade_aud=0.01;$t=$p+'.tmp';"
        "[IO.File]::WriteAllText($t,($l|ConvertTo-Json -Compress -Depth 5),(New-Object Text.UTF8Encoding($false)));Move-Item $t $p -Force;"
        "[pscustomobject]@{activated=$true;session_id=$l.session_id;maximum_loss_per_trade_aud=$l.maximum_loss_per_trade_aud;original_lease_preserved=$true}|ConvertTo-Json -Compress"
    )


def _m20_listener_restore_refusal_lease_command() -> str:
    return (
        "$ErrorActionPreference='Stop';$s='C:\\ProgramData\\ForexListener\\state';"
        "if(!(Test-Path (Join-Path $s 'm20_demo_maintenance_hold.local.json'))){throw 'Refusal restoration requires maintenance hold'};"
        "$p=Join-Path $s 'm20_demo_session.local.json';$b=Join-Path $s 'm20_demo_refusal_original_lease.local.json';"
        "$l=gc -Raw $p|ConvertFrom-Json;$o=gc -Raw $b|ConvertFrom-Json;"
        "if($o.maximum_loss_per_trade_aud -ne 100-or $l.maximum_loss_per_trade_aud -ne 0.01){throw 'Unexpected refusal limits'};"
        "$l.maximum_loss_per_trade_aud=100;"
        "if(($l|ConvertTo-Json -Compress -Depth 5) -ne ($o|ConvertTo-Json -Compress -Depth 5)){throw 'Lease changed during refusal drill'};"
        "Move-Item -LiteralPath $b -Destination $p -Force;[pscustomobject]@{restored=$true;session_id=$o.session_id;maximum_loss_per_trade_aud=100}|ConvertTo-Json -Compress"
    )


def _m20_listener_refusal_drill_command() -> str:
    """Run only the exact hash-bound calculation-only AUD 0.01 refusal drill."""
    runner = (ROOT / "t480" / "m20_demo_trading_session.py").read_bytes()
    runner_digest = hashlib.sha256(runner).hexdigest()
    fingerprint = project_configuration_fingerprint()
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    return (
        "$ErrorActionPreference='Stop'; $base='C:\\ProgramData\\ForexListener'; $state=Join-Path $base 'state'; "
        "$status=gc -Raw (Join-Path $state 'm20_demo_listener_status.local.json')|ConvertFrom-Json; $release=[string]$status.release_id; "
        "if ($release -notmatch '^[0-9a-f]{16}$') { throw 'M20 active ProgramData release id is absent or invalid' }; "
        "$root=Join-Path $base ('releases\\'+$release); $c=gc -Raw (Join-Path $state 'm20_demo_listener_service.local.json')|ConvertFrom-Json; "
        "if ($c.FOREX_M20_APPLICATION_REVISION -ne '" + revision + "' -or $c.FOREX_M20_CONFIGURATION_FINGERPRINT -ne '" + fingerprint + "') { throw 'M20 active release binding differs from the fixed refusal drill' }; "
        "if ([string]::IsNullOrWhiteSpace($c.python_path) -or !(Test-Path -LiteralPath $c.python_path)) { throw 'M20 ProgramData release configured Python interpreter is absent' }; "
        "$runner=Join-Path $root 'm20_demo_trading_session.payload'; if (!(Test-Path -LiteralPath $runner)) { throw 'M20 fixed ProgramData trading runner is absent' }; "
        "if ((Get-FileHash -LiteralPath $runner -Algorithm SHA256).Hash.ToLower() -ne '" + runner_digest + "') { throw 'M20 fixed trading runner hash does not match the committed source' }; "
        "$env:FOREX_M20_TICK_TIME_OFFSET_SECONDS=$c.FOREX_M20_TICK_TIME_OFFSET_SECONDS;& $c.python_path $runner $c.terminal_path (Join-Path $state 'm20_demo_session.local.json') --risk-refusal-drill; exit $LASTEXITCODE"
    )


def _m20_listener_resume_risk_policy_command() -> str:
    """Resume through the same T480 WSL database path as the trading runner."""
    bridge = (ROOT / "t480" / "m20_postgres_audit_bridge.py").read_bytes()
    digest = hashlib.sha256(bridge).hexdigest()
    return (
        "$ErrorActionPreference='Stop'; $base='C:\\ProgramData\\ForexListener'; $state=Join-Path $base 'state'; "
        "$status=gc -Raw (Join-Path $state 'm20_demo_listener_status.local.json')|ConvertFrom-Json; $release=[string]$status.release_id; "
        "if ($release -notmatch '^[0-9a-f]{16}$') { throw 'M20 active ProgramData release id is absent or invalid' }; "
        "$root=Join-Path $base ('releases\\'+$release); "
        "$bridge=Join-Path $root 'm20_postgres_audit_bridge.payload'; "
        "if (!(Test-Path -LiteralPath $bridge)) { throw 'M20 fixed ProgramData PostgreSQL audit bridge is absent' }; "
        "if ((Get-FileHash -LiteralPath $bridge -Algorithm SHA256).Hash.ToLower() -ne '" + digest + "') { throw 'M20 fixed PostgreSQL audit bridge hash does not match the committed source' }; "
        # PostgreSQL is loopback-bound inside Ubuntu, not Windows. Forward the
        # existing machine-local DSN by environment name, never in command text
        # or stdout, and invoke only the verified ProgramData bridge payload.
        "if ([string]::IsNullOrWhiteSpace($env:FOREX_M20_POSTGRES_DSN)) { throw 'M20 PostgreSQL bridge WSL prerequisites are absent' }; "
        "$wslBridge='/mnt/c/ProgramData/ForexListener/releases/'+$release+'/m20_postgres_audit_bridge.payload'; "
        "$previousWslEnv=$env:WSLENV; try { "
        "$env:WSLENV=(@($previousWslEnv -split ':' | Where-Object { $_ -and $_ -notmatch '^FOREX_M20_POSTGRES_DSN(/.*)?$' }) + 'FOREX_M20_POSTGRES_DSN') -join ':'; "
        "'{}' | & wsl.exe -d Ubuntu -- python3 $wslBridge resume-risk-policy; $bridgeExit=$LASTEXITCODE "
        "} finally { $env:WSLENV=$previousWslEnv }; exit $bridgeExit"
    )


def _m20_listener_stop_command() -> str:
    """Stop only the fixed listener task for an atomic hash-checked deployment."""
    return (
        "$ErrorActionPreference='Stop'; "
        "$task=Get-ScheduledTask -TaskName 'Forex-M20-Demo-Listener' -ErrorAction Stop; "
        "if ($task.State -eq 'Running') { Stop-ScheduledTask -TaskName 'Forex-M20-Demo-Listener' -ErrorAction Stop }; "
        "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { $_.CommandLine -like '*\\ProgramData\\ForexListener\\releases\\*m20_demo_listener_service.payload*' } | ForEach-Object { try { Stop-Process -Id $_.ProcessId -Force -ErrorAction Stop } catch { if ($_.FullyQualifiedErrorId -notlike 'NoProcessFoundForGivenId,*') { throw } } }; "
        "[pscustomobject]@{stopped=$true;task='Forex-M20-Demo-Listener'}|ConvertTo-Json -Compress"
    )


def _m20_listener_enable_maintenance_hold_command() -> str:
    """Write the sole fixed maintenance hold used for coordinated recovery."""
    return (
        "$ErrorActionPreference='Stop'; $state='C:\\ProgramData\\ForexListener\\state'; New-Item -ItemType Directory -Force $state|Out-Null; "
        "$hold=[ordered]@{schema_version='forex.m20.maintenance-hold.v1';enabled=$true;reason='W1R_COORDINATED_MAINTENANCE';created_at_utc=(Get-Date).ToUniversalTime().ToString('o')}; "
        "$tmp=Join-Path $state 'm20_demo_maintenance_hold.local.json.tmp'; [IO.File]::WriteAllText($tmp,($hold|ConvertTo-Json -Compress),(New-Object Text.UTF8Encoding($false))); Move-Item -LiteralPath $tmp -Destination (Join-Path $state 'm20_demo_maintenance_hold.local.json') -Force; "
        "[pscustomobject]@{maintenance_hold=$true;reason=$hold.reason}|ConvertTo-Json -Compress"
    )


def _m20_listener_disable_maintenance_hold_command() -> str:
    """Remove only the fixed maintenance hold after an independently verified release."""
    return (
        "$ErrorActionPreference='Stop'; $p='C:\\ProgramData\\ForexListener\\state\\m20_demo_maintenance_hold.local.json'; "
        "Remove-Item -LiteralPath $p -Force -ErrorAction SilentlyContinue; "
        "[pscustomobject]@{maintenance_hold=$false;reason='NONE'}|ConvertTo-Json -Compress"
    )


def _m20_listener_retire_legacy_restart_drill_command() -> str:
    """Archive only the known failed pre-repair drill marker under a hold."""
    return (
        "$ErrorActionPreference='Stop';$s='C:\\ProgramData\\ForexListener\\state';"
        "if(!(Test-Path (Join-Path $s 'm20_demo_maintenance_hold.local.json'))){throw 'Legacy drill retirement requires maintenance hold'};"
        "$p=Join-Path $s 'm20_demo_protected_restart_drill.local.json';$a=Join-Path $s 'm20_demo_protected_restart_drill.legacy-42235606.json';"
        "if(Test-Path $a){throw 'Legacy drill archive already exists'};if(!(Test-Path $p)){throw 'Legacy drill marker is absent'};"
        "$d=gc -Raw $p|ConvertFrom-Json;if($d.schema_version -ne 'forex.m20.protected-restart-drill.v1'-or $d.state -ne 'RESTART_REQUESTED'-or $d.attempt_id -ne '47433bf8-565d-5f24-9550-ddeea4124cd3'-or $d.position_ticket -ne 42235606){throw 'Marker is not the exact failed pre-repair drill'};"
        "Move-Item -LiteralPath $p -Destination $a -ErrorAction Stop;"
        "[pscustomobject]@{retired=$true;archive='m20_demo_protected_restart_drill.legacy-42235606.json';attempt_id=$d.attempt_id;position_ticket=$d.position_ticket;original_marker_preserved=$true}|ConvertTo-Json -Compress"
    )


def _m20_listener_run_continuity_protocol_command() -> str:
    """Arm the fixed held-only autonomous T480 continuity protocol."""
    service = (ROOT / "t480" / "m20_demo_listener_service.py").read_bytes()
    runner = (ROOT / "t480" / "m20_demo_trading_session.py").read_bytes()
    bridge = (ROOT / "t480" / "m20_postgres_audit_bridge.py").read_bytes()
    discord = (ROOT / "t480" / "m20_discord_trade_notification.py").read_bytes()
    release_id = hashlib.sha256(service + runner + bridge + discord).hexdigest()[:16]
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    fingerprint = project_configuration_fingerprint()
    return (
        "$ErrorActionPreference='Stop';$b='C:\\ProgramData\\ForexListener';$s=Join-Path $b state;$h=gc -Raw (Join-Path $s 'm20_demo_listener_status.local.json')|ConvertFrom-Json;$c=gc -Raw (Join-Path $s 'm20_demo_listener_service.local.json')|ConvertFrom-Json;"
        "if($h.release_id -ne '" + release_id + "' -or $c.FOREX_M20_APPLICATION_REVISION -ne '" + revision + "' -or $c.FOREX_M20_CONFIGURATION_FINGERPRINT -ne '" + fingerprint + "'){throw 'Continuity protocol release binding differs'};"
        "$p=Join-Path $b ('releases\\'+$h.release_id+'\\m20_demo_listener_service.payload');& $c.python_path $p --arm-continuity-protocol;exit $LASTEXITCODE"
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
    """Verify every staged payload and atomically record its release binding."""
    service = (ROOT / "t480" / "m20_demo_listener_service.py").read_bytes()
    service_digest = hashlib.sha256(service).hexdigest()
    runner_digest = hashlib.sha256((ROOT / "t480" / "m20_demo_trading_session.py").read_bytes()).hexdigest()
    bridge_digest = hashlib.sha256((ROOT / "t480" / "m20_postgres_audit_bridge.py").read_bytes()).hexdigest()
    discord = (ROOT / "t480" / "m20_discord_trade_notification.py").read_bytes()
    discord_digest = hashlib.sha256(discord).hexdigest()
    release_id = hashlib.sha256(service + (ROOT / "t480" / "m20_demo_trading_session.py").read_bytes() + (ROOT / "t480" / "m20_postgres_audit_bridge.py").read_bytes() + discord).hexdigest()[:16]
    fingerprint = project_configuration_fingerprint()
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    return (
        "$ErrorActionPreference='Stop'; "
        "$b='C:\\ProgramData\\ForexListener';$r=Join-Path $b 'releases\\" + release_id + "';$s=Join-Path $b state;ni -it d -fo $s|out-null;"
        "$e=@{'m20_demo_listener_service.payload'='" + service_digest + "';'m20_demo_trading_session.payload'='" + runner_digest + "';'m20_postgres_audit_bridge.payload'='" + bridge_digest + "';'m20_discord_trade_notification.payload'='" + discord_digest + "'};"
        "$e.GetEnumerator()|%{$p=Join-Path $r $_.Key;if(!(Test-Path -LiteralPath $p)-or (Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash.ToLower() -ne $_.Value){throw ('M20 staged payload hash failed: '+$_.Key)}};"
        "$m=[ordered]@{release_id='" + release_id + "';service_sha256='sha256:" + service_digest + "';configuration_fingerprint='" + fingerprint + "';application_revision='" + revision + "'};$t=Join-Path $s 'm20_demo_listener_prepared.local.json.tmp';[IO.File]::WriteAllText($t,($m|ConvertTo-Json -Compress),(New-Object Text.UTF8Encoding($false)));Move-Item $t (Join-Path $s 'm20_demo_listener_prepared.local.json') -Force;"
        "[pscustomobject]@{prepared=$true;release_id=$m.release_id;service_sha256=$m.service_sha256}|ConvertTo-Json -Compress"
    )


def _m20_listener_enable_discord_from_existing_secret_command() -> str:
    """Enable the alert only from an approved T480-local secret source."""
    return (
        "$ErrorActionPreference='Stop';$state='C:\\ProgramData\\ForexListener\\state';$active=Join-Path $state 'm20_demo_listener_service.local.json';if(!(Test-Path -LiteralPath $active)){throw 'M20 listener configuration is absent'};$c=gc -Raw -LiteralPath $active|ConvertFrom-Json;$candidate=[string]$c.FOREX_M20_DISCORD_WEBHOOK_URL;if([string]::IsNullOrWhiteSpace($candidate)){$candidate=[Environment]::GetEnvironmentVariable('FOREX_M20_DISCORD_WEBHOOK_URL','User')};if([string]::IsNullOrWhiteSpace($candidate)){$candidate=[Environment]::GetEnvironmentVariable('FOREX_M20_DISCORD_WEBHOOK_URL','Machine')};if([string]::IsNullOrWhiteSpace($candidate)){$mt5=Join-Path $env:USERPROFILE 'Documents\\Code\\forex-m1-probe\\mt5.local.json';if(Test-Path -LiteralPath $mt5){try{$candidate=[string]((gc -Raw -LiteralPath $mt5|ConvertFrom-Json).FOREX_M20_DISCORD_WEBHOOK_URL)}catch{}}};if($candidate -notmatch '^https://(discord\\.com|discordapp\\.com)/api/webhooks/'){[pscustomobject]@{configured=$false;detail='No approved T480-local Discord webhook is configured.'}|ConvertTo-Json -Compress;exit 0};$c|Add-Member -NotePropertyName FOREX_M20_DISCORD_NOTIFICATIONS_ENABLED -NotePropertyValue 'true' -Force;$c|Add-Member -NotePropertyName FOREX_M20_DISCORD_WEBHOOK_URL -NotePropertyValue $candidate -Force;$tmp=$active+'.tmp';[IO.File]::WriteAllText($tmp,($c|ConvertTo-Json -Compress),(New-Object Text.UTF8Encoding($false)));Move-Item $tmp $active -Force;[pscustomobject]@{configured=$true;detail='Discord open alerts enabled from an approved T480-local secret source.'}|ConvertTo-Json -Compress"
    )


def _m20_listener_configure_command() -> str:
    """Write only the governed non-secret configuration after payload verification."""
    service = (ROOT / "t480" / "m20_demo_listener_service.py").read_bytes()
    runner_digest = hashlib.sha256((ROOT / "t480" / "m20_demo_trading_session.py").read_bytes()).hexdigest()
    bridge_digest = hashlib.sha256((ROOT / "t480" / "m20_postgres_audit_bridge.py").read_bytes()).hexdigest()
    discord = (ROOT / "t480" / "m20_discord_trade_notification.py").read_bytes()
    release_id = hashlib.sha256(service + (ROOT / "t480" / "m20_demo_trading_session.py").read_bytes() + (ROOT / "t480" / "m20_postgres_audit_bridge.py").read_bytes() + discord).hexdigest()[:16]
    fingerprint = project_configuration_fingerprint()
    configuration = load_configuration(ROOT, environ={})
    risk_policy = json.dumps(asdict(configuration.runtime.persistent_risk_policy), separators=(",", ":"))
    financing = json.dumps(configuration.runtime.financing_policy, separators=(",", ":"))
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    return (
        "$ErrorActionPreference='Stop';$b='C:\\ProgramData\\ForexListener';$s=Join-Path $b state;$l=Join-Path $env:USERPROFILE 'Documents\\Code\\forex-m1-probe';"
        "$m=gc -Raw (Join-Path $s 'm20_demo_listener_prepared.local.json')|ConvertFrom-Json;if($m.release_id -ne '" + release_id + "'-or $m.configuration_fingerprint -ne '" + fingerprint + "'-or $m.application_revision -ne '" + revision + "'){throw 'M20 verified release binding is absent or stale'};"
        "$x=gc -Raw (Join-Path $l 'mt5.local.json')|ConvertFrom-Json;$active=Join-Path $s 'm20_demo_listener_service.local.json';$previous=$null;if(Test-Path $active){try{$previous=gc -Raw $active|ConvertFrom-Json}catch{}};$c=[ordered]@{FOREX_M20_DEMO_TRADING_SESSION_SHA256='" + runner_digest + "';FOREX_M20_POSTGRES_AUDIT_BRIDGE_SHA256='sha256:" + bridge_digest + "';FOREX_M20_CONFIGURATION_FINGERPRINT='" + fingerprint + "';FOREX_M20_TICK_TIME_OFFSET_SECONDS='" + str(configuration.mt5.broker_tick_time_offset_seconds) + "';FOREX_M20_MINIMUM_NET_PROFIT_AUD='" + str(configuration.runtime.demo_session_limits.minimum_net_profit_aud) + "';FOREX_M20_FINANCING_POLICY='" + financing.replace("'", "''") + "';FOREX_M20_PERSISTENT_RISK_POLICY='" + risk_policy.replace("'", "''") + "';FOREX_M20_APPLICATION_REVISION='" + revision + "';python_path=$x.python_path;terminal_path=$x.terminal_path};if($null -ne $previous){foreach($key in @('FOREX_M20_DISCORD_NOTIFICATIONS_ENABLED','FOREX_M20_DISCORD_WEBHOOK_URL')){if($previous.PSObject.Properties.Name -contains $key){$c[$key]=[string]$previous.$key}}};"
        "if(!(Test-Path (Join-Path $s 'm20_demo_session.local.json'))){Copy-Item (Join-Path $l 'm20_demo_session.local.json') (Join-Path $s 'm20_demo_session.local.json') -ea SilentlyContinue};$t=Join-Path $s 'm20_demo_listener_service.local.json.tmp';[IO.File]::WriteAllText($t,($c|ConvertTo-Json -Compress),(New-Object Text.UTF8Encoding($false)));Move-Item $t $active -Force;[pscustomobject]@{configured=$true;release_id=$m.release_id}|ConvertTo-Json -Compress"
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
        "$c=Get-Content -Raw (Join-Path $state 'm20_demo_listener_service.local.json')|ConvertFrom-Json; $prepared=Get-Content -Raw (Join-Path $state 'm20_demo_listener_prepared.local.json')|ConvertFrom-Json; if (!(Test-Path -LiteralPath $service) -or $prepared.release_id -ne '" + release_id + "' -or $prepared.service_sha256 -ne 'sha256:" + service_digest + "') { throw 'M20 release was not prepared and hash-bound' }; "
        "$previous=$null; try { $previous=Export-ScheduledTask -TaskName $task -ErrorAction Stop } catch {}; if ($null -ne $previous) { [IO.File]::WriteAllText((Join-Path $state 'previous-task.xml'),$previous,(New-Object Text.UTF8Encoding($false))) }; "
        "$action=New-ScheduledTaskAction -Execute $c.python_path -Argument ('\"'+$service+'\"'); $trigger=New-ScheduledTaskTrigger -AtStartup; $principal=New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType S4U -RunLevel Highest; $settings=New-ScheduledTaskSettingsSet -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero);$watch='Forex-M20-Listener-Watchdog';$watchAction=New-ScheduledTaskAction -Execute 'schtasks.exe' -Argument '/run /tn \"Forex-M20-Demo-Listener\"';$watchStartup=New-ScheduledTaskTrigger -AtStartup;$watchRepeat=New-ScheduledTaskTrigger -Once -At ((Get-Date).AddMinutes(1)) -RepetitionInterval (New-TimeSpan -Minutes 2) -RepetitionDuration (New-TimeSpan -Days 3650);$watchSettings=New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 1) -MultipleInstances IgnoreNew; "
        "try { if ($null -ne $previous) { Stop-ScheduledTask -TaskName $task -ErrorAction SilentlyContinue }; Get-CimInstance Win32_Process | Where-Object { $_.Name -match '^python(w)?\\.exe$' -and $_.CommandLine -like '*\\ProgramData\\ForexListener\\releases\\*m20_demo_listener_service.payload*' } | ForEach-Object { try { Stop-Process -Id $_.ProcessId -Force -ErrorAction Stop } catch { if ($_.FullyQualifiedErrorId -notlike 'NoProcessFoundForGivenId,*') { throw } } }; Register-ScheduledTask -TaskName $task -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force|Out-Null;Register-ScheduledTask -TaskName $watch -Action $watchAction -Trigger @($watchStartup,$watchRepeat) -Principal $principal -Settings $watchSettings -Force|Out-Null;Start-ScheduledTask -TaskName $task;Start-ScheduledTask -TaskName $watch -ErrorAction SilentlyContinue; Start-Sleep -Seconds 5; $h=Get-Content -Raw (Join-Path $state 'm20_demo_listener_status.local.json')|ConvertFrom-Json; $age=((Get-Date).ToUniversalTime()-([datetime]::Parse($h.heartbeat_at_utc)).ToUniversalTime()).TotalSeconds; if (($h.release_id -ne '" + release_id + "') -or ($age -ge 30) -or ($h.state -eq 'STARTUP_FAILED')) { throw 'new listener did not produce a fresh ProgramData heartbeat' } } catch { $failure=$_.Exception.Message; if ($null -ne $previous) { Stop-ScheduledTask -TaskName $task -ErrorAction SilentlyContinue; Register-ScheduledTask -TaskName $task -Xml $previous -Force|Out-Null; Start-ScheduledTask -TaskName $task -ErrorAction SilentlyContinue }; throw ('M20 deployment rolled back: '+$failure) }; "
        "[pscustomobject]@{installed=$true;task=$task;release_id='" + release_id + "';service_sha256='sha256:" + service_digest + "'}|ConvertTo-Json -Compress"
    )


def _m20_listener_stage_command(index: int) -> str:
    """Transfer a bounded immutable source segment through the fixed adapter."""
    source = (ROOT / "t480" / "m20_demo_listener_service.py").read_bytes()
    release_id = hashlib.sha256(source + (ROOT / "t480" / "m20_demo_trading_session.py").read_bytes() + (ROOT / "t480" / "m20_postgres_audit_bridge.py").read_bytes() + (ROOT / "t480" / "m20_discord_trade_notification.py").read_bytes()).hexdigest()[:16]
    # Raw Base64 decoding is accepted by the T480 endpoint; in-process gzip
    # expansion is not.  Twenty-two bounded fixed fragments stay below its command
    # cap and match the catalogued release protocol.
    encoded = base64.b64encode(source).decode("ascii")
    chunk_size = ((len(encoded) + (22 * 4) - 1) // (22 * 4)) * 4
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
    "m20_terminal_history_diagnostics": Operation("m20_terminal_history_diagnostics", "Inspect bounded terminal history error lines and Demo exposure without trading.", powershell_command=_m20_terminal_history_diagnostics_command(), timeout_seconds=60),
    "m20_close_duplicate_terminal": Operation("m20_close_duplicate_terminal", "Close duplicate interactive configured MT5 instances only while Demo is flat and the listener is held and stopped.", powershell_command=_m20_close_duplicate_terminal_command(), timeout_seconds=60),
    "m20_financing_preview": Operation("m20_financing_preview", "Run the hash-bound deployed Demo financing calculator without placing orders.", powershell_command=_m20_demo_trading_session_command().replace("$c.terminal_path $lease;", "$c.terminal_path $lease --financing-preview;"), timeout_seconds=60),
    "m20_swap_terms": Operation("m20_swap_terms", "Read fixed Demo EURUSD financing terms and AUDUSD conversion quotes without trading.", powershell_command=_m20_swap_terms_command(), timeout_seconds=60),
    "m20_wave1_candles": Operation("m20_wave1_candles", "Inspect fixed Demo M1 candle availability and the terminal error without trading.", powershell_command=_m20_wave1_candles_command(), timeout_seconds=60),
    "m20_wave1_history": Operation("m20_wave1_history", "Read the fixed September 2026 Wave 1 Demo account deal/order reconciliation window.", powershell_command=_m20_wave1_history_command(), timeout_seconds=60),
    "m20_unresolved_history_probe": Operation(
        "m20_unresolved_history_probe",
        "Read only the fixed GOMarketsMU-Demo EURUSD broker-deal window for unresolved M20 attempts.",
        powershell_command=_m20_unresolved_history_probe_command(),
        timeout_seconds=60,
    ),
    "m20_reconcile_retained_history": Operation(
        "m20_reconcile_retained_history",
        "Append only the four fixed, broker-verified historical GOMarketsMU-Demo EURUSD lifecycle reconciliations.",
        powershell_command=_m20_reconcile_retained_history_command(),
        timeout_seconds=90,
    ),
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
    "m20_listener_diagnostics": Operation(
        "m20_listener_diagnostics",
        "Read the fixed Forex listener task and process identities without restart or broker access.",
        powershell_command=_m20_listener_diagnostics_command(),
    ),
    "m20_listener_continuity_status": Operation(
        "m20_listener_continuity_status",
        "Read retained T480-local continuity protocol state and task identity without recovery or broker access.",
        powershell_command=_m20_listener_continuity_status_command(),
    ),
    "m20_listener_cancel_continuity_protocol": Operation(
        "m20_listener_cancel_continuity_protocol",
        "Stop only the active held-only continuity task and retain an inconclusive cancellation result.",
        powershell_command=_m20_listener_cancel_continuity_protocol_command(),
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
    "m20_listener_install_watchdog": Operation(
        "m20_listener_install_watchdog",
        "Install the fixed Session-0 watchdog that asks Windows Task Scheduler to run the existing Demo listener at boot and every two minutes.",
        powershell_command=_m20_listener_install_watchdog_command(),
    ),
    "m20_listener_watchdog_status": Operation(
        "m20_listener_watchdog_status",
        "Read the fixed Session-0 listener watchdog task and schedule without starting either task.",
        powershell_command=_m20_listener_watchdog_status_command(),
    ),
    "m20_listener_run_reboot_recovery_protocol": Operation(
        "m20_listener_run_reboot_recovery_protocol",
        "Arm the fixed held-only T480 post-boot verifier and request one controlled reboot; it cannot submit an order.",
        powershell_command=_m20_listener_run_reboot_recovery_protocol_command(),
    ),
    "m20_listener_reboot_recovery_status": Operation(
        "m20_listener_reboot_recovery_status",
        "Read the retained fixed T480 reboot-recovery protocol record without starting or restarting a task.",
        powershell_command=_m20_listener_reboot_recovery_status_command(),
    ),
    "m20_listener_activate_demo_lease": Operation(
        "m20_listener_activate_demo_lease",
        "Create a new continuous GOMarketsMU-Demo EURUSD M1 lease with the governed M20 caps.",
        powershell_command=_m20_listener_activate_demo_lease_command(),
    ),
    "m20_listener_activate_refusal_drill_lease": Operation(
        "m20_listener_activate_refusal_drill_lease",
        "Create only the fixed five-minute AUD 0.01 W1.4 Demo refusal-drill lease.",
        powershell_command=_m20_listener_activate_refusal_drill_lease_command(),
    ),
    "m20_listener_restore_refusal_lease": Operation("m20_listener_restore_refusal_lease", "Restore the exact original Demo lease after the fixed refusal drill.", powershell_command=_m20_listener_restore_refusal_lease_command()),
    "m20_listener_refusal_drill": Operation(
        "m20_listener_refusal_drill",
        "Run only the hash-bound calculation-only EURUSD minimum-increment refusal drill on GOMarketsMU-Demo.",
        powershell_command=_m20_listener_refusal_drill_command(),
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
    "m20_listener_enable_maintenance_hold": Operation(
        "m20_listener_enable_maintenance_hold",
        "Enable the fixed W1.R maintenance hold: monitor positions but block all assessments and Demo entries.",
        powershell_command=_m20_listener_enable_maintenance_hold_command(),
    ),
    "m20_listener_disable_maintenance_hold": Operation(
        "m20_listener_disable_maintenance_hold",
        "Remove only the fixed W1.R maintenance hold after verified maintenance.",
        powershell_command=_m20_listener_disable_maintenance_hold_command(),
    ),
    "m20_listener_retire_legacy_restart_drill": Operation(
        "m20_listener_retire_legacy_restart_drill",
        "Archive only the exact failed pre-repair protected-restart marker while the listener is held.",
        powershell_command=_m20_listener_retire_legacy_restart_drill_command(),
    ),
    "m20_listener_run_continuity_protocol": Operation(
        "m20_listener_run_continuity_protocol",
        "Arm the fixed held-only T480-local continuity and alert protocol; it cannot submit an order.",
        powershell_command=_m20_listener_run_continuity_protocol_command(),
    ),
    "m20_listener_repair_permissions": Operation("m20_listener_repair_permissions", "Repair current-user Modify access only for the fixed Forex listener deployment directory.", powershell_command=_m20_listener_repair_permissions_command()),
    "m20_listener_prepare": Operation(
        "m20_listener_prepare",
        "Verify every fixed staged M20 release payload and atomically record its binding.",
        powershell_command=_m20_listener_prepare_command(),
        timeout_seconds=60,
    ),
    "m20_listener_enable_discord_from_existing_secret": Operation(
        "m20_listener_enable_discord_from_existing_secret",
        "Enable M20 Discord open alerts from an approved existing T480-local secret without returning it.",
        powershell_command=_m20_listener_enable_discord_from_existing_secret_command(),
    ),
    "m20_listener_configure": Operation(
        "m20_listener_configure",
        "Write the governed non-secret M20 listener configuration after release verification.",
        powershell_command=_m20_listener_configure_command(),
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

for _index in range(6, 23):
    OPERATIONS[f"m20_listener_stage_{_index}"] = Operation(
        f"m20_listener_stage_{_index}",
        ("Stage and verify" if _index == 22 else "Stage") + f" fixed M20 listener payload part {_index}.",
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
    parts = 64
    chunk_size = ((len(encoded) + (parts * 4) - 1) // (parts * 4)) * 4
    chunks = tuple(encoded[offset:offset + chunk_size] for offset in range(0, len(encoded), chunk_size))
    prefix = "$ErrorActionPreference='Stop'; $base='C:\\ProgramData\\ForexListener'; $root=Join-Path $base 'releases\\" + release_id + "'; New-Item -ItemType Directory -Force $root|Out-Null; $payload=Join-Path $root 'm20_demo_trading_session.payload'; "
    if index <= parts:
        return prefix + "[IO.File]::WriteAllText((Join-Path $root 'm20_demo_trading_session.part" + f"{index:02d}" + "'),'" + chunks[index - 1] + "',(New-Object Text.UTF8Encoding($false))); [pscustomobject]@{stage=" + str(index) + ";ok=$true}|ConvertTo-Json -Compress"
    raise ValueError("M20 listener runner stage index is invalid")


for _index in range(1, 65):
    _final = _index == 64
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
        "if ($fragments.Count -ne 64) { throw ('M20 listener runner fragments are incomplete: '+$fragments.Count) }; "
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
    parts = 32
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
        "if ($fragments.Count -ne 32) { throw ('M20 listener bridge fragments are incomplete: '+$fragments.Count) }; "
        "$encoded=(($fragments|ForEach-Object {[IO.File]::ReadAllText($_)}) -join ''); [IO.File]::WriteAllBytes($file,[Convert]::FromBase64String($encoded)); "
        "if ((Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash.ToLower() -ne '" + _bridge_source_digest + "') { throw 'M20 listener bridge staged source hash failed' }; "
        "$fragments|ForEach-Object { Remove-Item -LiteralPath $_ -Force }; [pscustomobject]@{verified=$true}|ConvertTo-Json -Compress"
    ),
)
for _index in range(1, 33):
    _final = _index == 32
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
    parts = 6
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


for _index in range(1, 7):
    _final = _index == 6
    OPERATIONS[f"m20_listener_discord_stage_{_index}"] = Operation(
        f"m20_listener_discord_stage_{_index}",
        ("Stage and verify" if _final else "Stage") + f" fixed M20 Discord lifecycle-notification adapter part {_index}.",
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
