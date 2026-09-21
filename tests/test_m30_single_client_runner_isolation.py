from __future__ import annotations

import importlib.util
import io
import json
from pathlib import Path
from queue import Queue
import sys
import types

import pytest

from scripts import t480_adapter
from t480_core import build_ssh_command

ROOT = Path(__file__).resolve().parents[1]


def _runner(monkeypatch):
    monkeypatch.setitem(
        sys.modules, "MetaTrader5",
        types.SimpleNamespace(TIMEFRAME_M1=1, TIMEFRAME_M5=5, TIMEFRAME_H1=60),
    )
    spec = importlib.util.spec_from_file_location(
        "m30_single_client_runner", ROOT / "t480/m20_demo_trading_session.py",
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _bridge():
    spec = importlib.util.spec_from_file_location(
        "m30_single_client_bridge", ROOT / "t480/m20_postgres_audit_bridge.py",
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_serve_keeps_existing_actions_fixed_and_refuses_resume(monkeypatch):
    bridge = _bridge()
    stdin = io.StringIO(
        json.dumps({"command": "ready", "payload": {}}) + "\n"
        + json.dumps({"command": "resume-risk-policy", "payload": {}}) + "\n"
    )
    stdout = io.StringIO()
    monkeypatch.setattr(bridge.sys, "stdin", stdin)
    monkeypatch.setattr(bridge.sys, "stdout", stdout)
    monkeypatch.setattr(bridge, "ready", lambda payload: {"ok": True, "marker": "FOREX_M20_AUDIT_BRIDGE_READY"})
    bridge._serve({"ready": bridge.ready, "resume-risk-policy": lambda payload: {"ok": True}})
    rows = [json.loads(line) for line in stdout.getvalue().splitlines()]
    assert rows == [
        {"ok": True, "result": {"ok": True, "marker": "FOREX_M20_AUDIT_BRIDGE_READY"}},
        {"ok": False, "reason": "M20_AUDIT_BRIDGE_REQUEST_REFUSED"},
    ]


def test_runner_bridge_requires_prestarted_fixed_channel(monkeypatch):
    runner = _runner(monkeypatch)

    class Process:
        def __init__(self):
            self.stdin = io.StringIO()

        def poll(self):
            return None

    process = Process()
    responses = Queue()
    responses.put(json.dumps({"ok": True, "result": {"ok": True, "value": "ack"}}))
    monkeypatch.setattr(runner, "_BRIDGE_PROCESS", process)
    monkeypatch.setattr(runner, "_BRIDGE_RESPONSES", responses)
    assert runner._bridge({}, "load-open-positions") == {"ok": True, "value": "ack"}
    assert json.loads(process.stdin.getvalue()) == {"command": "load-open-positions", "payload": {}}
    with pytest.raises(SystemExit, match="not permitted"):
        runner._bridge({}, "resume-risk-policy")


def test_isolation_starts_bridge_before_the_irrevocable_policy_and_reaps_it(monkeypatch):
    runner = _runner(monkeypatch)
    calls = []
    monkeypatch.setattr(runner, "_start_bridge_before_mt5", lambda: calls.append("bridge"))
    monkeypatch.setattr(runner, "_enforce_no_child_launch", lambda: calls.append("restricted"))
    monkeypatch.setattr(runner, "_close_bridge", lambda: calls.append("closed"))
    assert runner._run_single_client(lambda: calls.append("mt5") or "ok", requires_bridge=True) == "ok"
    assert calls == ["bridge", "restricted", "mt5", "closed"]


def test_failed_bridge_start_prevents_policy_and_mt5(monkeypatch):
    runner = _runner(monkeypatch)
    calls = []
    monkeypatch.setattr(runner, "_start_bridge_before_mt5", lambda: (_ for _ in ()).throw(SystemExit("bridge failed")))
    monkeypatch.setattr(runner, "_enforce_no_child_launch", lambda: calls.append("restricted"))
    monkeypatch.setattr(runner, "_close_bridge", lambda: calls.append("closed"))
    with pytest.raises(SystemExit, match="bridge failed"):
        runner._run_single_client(lambda: calls.append("mt5"), requires_bridge=True)
    assert calls == []


def test_runner_source_applies_restriction_to_every_mt5_cli_path():
    source = (ROOT / "t480/m20_demo_trading_session.py").read_text(encoding="utf-8")
    assert "_start_bridge_before_mt5()" in source
    assert "_enforce_no_child_launch()" in source
    assert "_close_bridge()" in source
    for command in ("--quote-identity", "--terminal-runtime-binding", "--financing-preview",
                    "--monitor-once", "--recover-open-positions-once", "--execution-drill",
                    "--audit-isolation-spike", "--pre-isolation-readiness"):
        assert command in source


def test_audit_isolation_spike_uses_two_fixed_read_only_calls(monkeypatch):
    runner = _runner(monkeypatch)
    calls = []
    monkeypatch.setattr(
        runner, "_bridge",
        lambda payload, command: calls.append((payload, command)) or {"ok": True, "open_positions": []},
    )
    assert runner.audit_isolation_spike() == {
        "marker": "FOREX_M30_AUDIT_ISOLATION_SPIKE_OK",
        "child_policy_verified": True,
        "first_open_positions_count": 0,
        "second_open_positions_count": 0,
        "mt5_called": False,
        "broker_mutation": "NONE",
    }
    assert calls == [({}, "load-open-positions"), ({}, "load-open-positions")]


def test_pre_isolation_readiness_uses_one_fixed_durable_read(monkeypatch):
    runner = _runner(monkeypatch)
    assert "pre-isolation-readiness" in runner._RUNNER_BRIDGE_COMMANDS
    calls = []
    response = {
        "ok": True, "marker": "FOREX_M30_PRE_ISOLATION_READINESS",
        "captured_at_utc": "2026-09-20T00:00:00Z",
        "durable_open_positions_count": 0,
        "unresolved_execution_attempts_count": 0, "clear": True,
    }
    monkeypatch.setattr(runner, "_bridge", lambda payload, command: calls.append((payload, command)) or response)
    assert runner.pre_isolation_readiness() == {**response, "broker_mutation": "NONE"}
    assert calls == [({}, "pre-isolation-readiness")]


def test_isolation_launcher_retains_unique_results_and_never_contacts_mt5():
    source = (ROOT / "t480/m30_runner_isolation_spike_launcher.py").read_text(encoding="utf-8")
    compile(source, "launcher", "exec")
    assert "uuid4" in source and "output.open(\"x\"" in source
    assert "MetaTrader5" not in source and "order_send" not in source


def test_adapter_exposes_only_fixed_runner_isolation_spike_operations():
    from scripts import t480_adapter

    for operation in (
        "m30_runner_isolation_spike_stage_1",
        "m30_runner_isolation_spike_stage_2",
        "m30_runner_isolation_spike_verify",
        "m30_runner_isolation_spike_run",
        "m30_runner_isolation_spike_status",
        "m30_runner_mt5_probe_run",
        "m30_runner_mt5_probe_status",
        "m30_runner_binding_probe_run",
        "m30_runner_binding_probe_status",
        "m30_runner_binding_post_isolation_run",
        "m30_runner_binding_post_isolation_status",
        "m30_pre_isolation_readiness_run",
        "m30_pre_isolation_readiness_status",
        "m30_session0_probe_run",
        "m30_session0_probe_status",
    ):
        assert operation in t480_adapter.OPERATIONS
        catalogue = json.loads(t480_adapter.CATALOG_PATH.read_text(encoding="utf-8"))
        assert operation in {entry["id"] for entry in catalogue["operations"]}
        assert t480_adapter.OPERATIONS[operation].approval_required is False
        assert len(build_ssh_command(
            "OEM@192.168.0.210",
            t480_adapter.OPERATIONS[operation].powershell_command,
            t480_adapter.TRANSPORT_SETTINGS,
        )[-1]) < 7_500
