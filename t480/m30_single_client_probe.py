"""One-shot interactive MT5 observation; no order or runtime repair interface.

Feasibility probe only. Restricts this process before importing MT5 and retains
hashes rather than paths/account numbers. It does not assert native PID binding.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes as w
from datetime import datetime, timezone
import hashlib
import json
import ntpath
import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

CONFIG = Path(r'C:\ProgramData\ForexListener\state\m20_demo_listener_service.local.json')
REFUSALS = {
    'SESSION_UNAVAILABLE', 'PROCESS_INVENTORY_UNAVAILABLE',
    'TERMINAL_CREATION_TIME_UNAVAILABLE', 'CHILD_POLICY_UNAVAILABLE',
    'CHILD_POLICY_NOT_ENFORCED', 'CHILD_POLICY_CANARY_FAILED',
    'LOCAL_PROFILE_INVALID', 'INTERACTIVE_SESSION_REQUIRED',
    'SINGLE_VISIBLE_CANDIDATE_REQUIRED',
    'TERMINAL_INVENTORY_CHANGED',
    'MAINTENANCE_HOLD_REQUIRED',
    'ISOLATED_STATE_REQUIRED',
}


def digest(value):
    return 'sha256:' + hashlib.sha256(ntpath.normcase(ntpath.normpath(value)).encode()).hexdigest()


def kernel():
    k = ctypes.WinDLL('kernel32', use_last_error=True)
    signatures = {
        'GetCurrentProcess': (w.HANDLE, []),
        'OpenProcess': (w.HANDLE, [w.DWORD, w.BOOL, w.DWORD]),
        'CloseHandle': (w.BOOL, [w.HANDLE]),
        'ProcessIdToSessionId': (w.BOOL, [w.DWORD, ctypes.POINTER(w.DWORD)]),
        'QueryFullProcessImageNameW': (w.BOOL, [w.HANDLE, w.DWORD, w.LPWSTR, ctypes.POINTER(w.DWORD)]),
        'GetProcessTimes': (w.BOOL, [w.HANDLE] + [ctypes.POINTER(w.FILETIME)] * 4),
        'SetProcessMitigationPolicy': (w.BOOL, [ctypes.c_int, ctypes.c_void_p, ctypes.c_size_t]),
        'GetProcessMitigationPolicy': (w.BOOL, [w.HANDLE, ctypes.c_int, ctypes.c_void_p, ctypes.c_size_t]),
        'K32EnumProcesses': (w.BOOL, [ctypes.POINTER(w.DWORD), w.DWORD, ctypes.POINTER(w.DWORD)]),
    }
    for name, (result, arguments) in signatures.items():
        getattr(k, name).restype = result
        getattr(k, name).argtypes = arguments
    return k


def session(k, pid):
    value = w.DWORD()
    if not k.ProcessIdToSessionId(pid, ctypes.byref(value)):
        raise RuntimeError('SESSION_UNAVAILABLE')
    return value.value


def inventory(k):
    pids = (w.DWORD * 8192)()
    size = w.DWORD()
    if not k.K32EnumProcesses(pids, ctypes.sizeof(pids), ctypes.byref(size)) or size.value >= ctypes.sizeof(pids):
        raise RuntimeError('PROCESS_INVENTORY_UNAVAILABLE')
    rows = []
    for pid in pids[:size.value // ctypes.sizeof(w.DWORD)]:
        handle = k.OpenProcess(0x1000, False, pid)
        if not handle:
            continue
        try:
            name = ctypes.create_unicode_buffer(32768)
            length = w.DWORD(len(name))
            if not k.QueryFullProcessImageNameW(handle, 0, name, ctypes.byref(length)):
                continue
            if ntpath.basename(name.value).lower() not in {'terminal.exe', 'terminal64.exe'}:
                continue
            times = [w.FILETIME() for _ in range(4)]
            if not k.GetProcessTimes(handle, *(ctypes.byref(t) for t in times)):
                raise RuntimeError('TERMINAL_CREATION_TIME_UNAVAILABLE')
            rows.append({'pid': pid, 'session_id': session(k, pid),
                         'created_filetime': (times[0].dwHighDateTime << 32) | times[0].dwLowDateTime,
                         'installation_exe_sha256': digest(name.value)})
        finally:
            k.CloseHandle(handle)
    return sorted(rows, key=lambda row: row['pid'])


def restrict_children(k):
    flags, observed = w.DWORD(1), w.DWORD()
    if not k.SetProcessMitigationPolicy(13, ctypes.byref(flags), ctypes.sizeof(flags)):
        raise RuntimeError('CHILD_POLICY_UNAVAILABLE')
    if not k.GetProcessMitigationPolicy(k.GetCurrentProcess(), 13, ctypes.byref(observed), ctypes.sizeof(observed)) or observed.value != 1:
        raise RuntimeError('CHILD_POLICY_NOT_ENFORCED')
    try:
        subprocess.run([sys.executable, '-c', 'pass'], check=True, capture_output=True, timeout=5)
    except OSError as error:
        if error.winerror == 367:
            return
    raise RuntimeError('CHILD_POLICY_CANARY_FAILED')


def observe(mt5, terminal_path, expected_scope):
    if not mt5.initialize(path=terminal_path, timeout=5000):
        return {'connection': 'UNAVAILABLE', 'reason': 'INITIALIZE_FAILED'}
    try:
        a, t = mt5.account_info(), mt5.terminal_info()
        if not a or not t or a.server != 'GOMarketsMU-Demo' or a.currency != 'AUD':
            return {'connection': 'UNAVAILABLE', 'reason': 'DEMO_ACCOUNT_REQUIRED'}
        scope = 'sha256:' + hashlib.sha256((a.server + ':' + str(a.login)).encode()).hexdigest()
        if scope != expected_scope:
            return {'connection': 'UNAVAILABLE', 'reason': 'ACCOUNT_PROFILE_MISMATCH'}
        if not getattr(t, 'data_path', None) or not getattr(t, 'path', None):
            return {'connection': 'UNAVAILABLE', 'reason': 'TERMINAL_IDENTITY_UNAVAILABLE'}
        if digest(ntpath.join(t.path, ntpath.basename(terminal_path))) != digest(terminal_path):
            return {'connection': 'UNAVAILABLE', 'reason': 'INSTALLATION_MISMATCH'}
        positions, orders = mt5.positions_get(), mt5.orders_get()
        return {'connection': 'OBSERVED', 'server': a.server, 'currency': a.currency,
                'account_scope_sha256': scope,
                'data_path_sha256': digest(t.data_path), 'terminal_connected': t.connected,
                'terminal_trade_allowed': t.trade_allowed, 'terminal_tradeapi_disabled': t.tradeapi_disabled,
                'account_trade_allowed': a.trade_allowed, 'account_trade_expert': a.trade_expert,
                'positions_count': len(positions) if positions is not None else None,
                'pending_orders_count': len(orders) if orders is not None else None}
    finally:
        mt5.shutdown()


def run(expected_session_id=None, require_isolated=False, restrict_child_creation=True):
    result = {'schema_version': 'forex.m30.single-client-probe.v1', 'probe_pid': os.getpid(),
              'captured_at_utc': datetime.now(timezone.utc).isoformat(), 'broker_mutation': 'NONE',
              'attribution': 'UNVERIFIED', 'child_policy_verified': False}
    result['inventory_scope'] = 'ACCESSIBLE_PROCESS_IMAGES_ONLY'
    try:
        config_bytes = CONFIG.read_bytes()
        config = json.loads(config_bytes.decode('utf-8-sig'))
        result['configuration_sha256'] = 'sha256:' + hashlib.sha256(config_bytes).hexdigest()
        status = json.loads((CONFIG.parent / 'm20_demo_listener_status.local.json').read_text(encoding='utf-8-sig'))
        if not isinstance(status.get('release_id'), str) or len(status['release_id']) != 16:
            raise RuntimeError('LOCAL_PROFILE_INVALID')
        result['listener_release_id'] = status['release_id']
        hold = json.loads((CONFIG.parent / 'm20_demo_maintenance_hold.local.json').read_text(encoding='utf-8-sig'))
        if hold.get('enabled') is not True or hold.get('schema_version') != 'forex.m20.maintenance-hold.v1':
            raise RuntimeError('MAINTENANCE_HOLD_REQUIRED')
        profile = json.loads(config['FOREX_M20_ACCOUNT_EXECUTION_PROFILE'])
        if profile.get('profile_id') != 'M1_EURUSD_DEMO' or profile.get('server') != 'GOMarketsMU-Demo' or profile.get('currency') != 'AUD' or profile.get('symbol') != 'EURUSD':
            raise RuntimeError('LOCAL_PROFILE_INVALID')
        k = kernel()
        result['session_id'] = session(k, os.getpid())
        if expected_session_id is None:
            if result['session_id'] == 0:
                raise RuntimeError('INTERACTIVE_SESSION_REQUIRED')
            expected_session_id = result['session_id']
        if (not isinstance(expected_session_id, int) or expected_session_id < 0
                or result['session_id'] != expected_session_id):
            raise RuntimeError('SESSION_UNAVAILABLE')
        result['expected_session_id'] = expected_session_id
        if restrict_child_creation:
            restrict_children(k)
            result['child_policy_verified'] = True
        else:
            result['child_policy_verified'] = False
            result['attachment_guard'] = 'PRE_POST_TERMINAL_INVENTORY_ONLY'
        result['before'] = inventory(k)
        if require_isolated:
            rows = list(CONFIG.parent.glob('m30-session0-isolation-*.json'))
            if not rows:
                raise RuntimeError('ISOLATED_STATE_REQUIRED')
            isolation = json.loads(max(rows, key=lambda path: path.stat().st_mtime).read_text(encoding='utf-8-sig'))
            completed = datetime.fromisoformat(isolation['completed_at_utc'].replace('Z', '+00:00'))
            if (isolation.get('state') != 'ISOLATED' or isolation.get('broker_mutation') != 'NONE'
                    or not 0 <= (datetime.now(timezone.utc) - completed).total_seconds() < 900
                    or any(row['session_id'] == 0 and row['installation_exe_sha256'] == digest(config['terminal_path']) for row in result['before'])):
                raise RuntimeError('ISOLATED_STATE_REQUIRED')
        candidates = [p for p in result['before'] if p['session_id'] == expected_session_id
                      and p['installation_exe_sha256'] == digest(config['terminal_path'])]
        if len(candidates) != 1:
            raise RuntimeError('SINGLE_VISIBLE_CANDIDATE_REQUIRED')
        import MetaTrader5 as mt5
        result['observation'] = observe(mt5, config['terminal_path'], profile['account_scope_sha256'])
        result['after'] = inventory(k)
        result['inventory_unchanged'] = result['before'] == result['after']
        result['state'] = 'OBSERVATION_COMPLETE' if result['inventory_unchanged'] else 'REFUSED'
        if not result['inventory_unchanged']:
            result['reason'] = 'TERMINAL_INVENTORY_CHANGED'
        # The MT5 API provides no PID attach contract.  Do not overstate this
        # bounded observation as native process ownership.
        result['attribution'] = 'SESSION_SCOPED_NOT_PID_BOUND'
    except Exception as error:
        # No raw exception text: Windows/API errors may contain paths or secrets.
        result['state'] = 'REFUSED'
        result['exception_type'] = type(error).__name__
        result['reason'] = str(error) if isinstance(error, RuntimeError) and str(error) in REFUSALS else 'PROBE_ERROR'
    prefix = 'observation-session0-' if expected_session_id == 0 else 'observation-'
    output = Path(__file__).resolve().parent / (prefix + uuid4().hex + '.json')
    with output.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, sort_keys=True)
    return result


if __name__ == '__main__':
    if len(sys.argv) == 1:
        run()
    elif len(sys.argv) == 2 and sys.argv[1] == '--session0':
        run(0)
    elif len(sys.argv) == 2 and sys.argv[1] == '--post-isolation':
        run(require_isolated=True)
    elif len(sys.argv) == 2 and sys.argv[1] == '--post-isolation-observe':
        run(require_isolated=True, restrict_child_creation=False)
    else:
        raise SystemExit('expected no arguments, fixed --session0, fixed --post-isolation, or fixed --post-isolation-observe')
