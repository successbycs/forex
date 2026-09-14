from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / "scripts/codex_stop_hook.py"


def _module():
    spec = importlib.util.spec_from_file_location("forex_codex_stop_hook", HOOK)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _event(**extra):
    return {"hook_event_name": "Stop", "permission_mode": "default", "cwd": str(ROOT), "stop_hook_active": False, **extra}


def test_blocked_active_h5_plan_does_not_invent_actionable_work():
    assert _module().response(_event()) == {}


def test_blocked_active_h5_plan_does_not_reblock_second_stop():
    assert _module().response(_event(stop_hook_active=True)) == {}


def test_non_stop_plan_mode_and_external_directory_do_not_interfere():
    hook = _module()
    assert hook.response(_event(hook_event_name="SessionEnd")) == {}
    assert hook.response(_event(permission_mode="plan")) == {}
    assert hook.response(_event(cwd="/tmp")) == {}


def test_subagent_stop_for_blocked_plan_does_not_interfere():
    hook = _module()
    assert hook.response({"hook_event_name": "SubagentStop", "stop_hook_active": False}) == {}


def test_invalid_stop_input_is_a_visible_warning_not_a_continuation(monkeypatch, capsys):
    hook = _module()
    monkeypatch.setattr(hook, "response", lambda _event: (_ for _ in ()).throw(ValueError("bad")))
    monkeypatch.setattr(hook.sys, "stdin", type("Input", (), {"buffer": type("Buffer", (), {"read": lambda _self, _n: b"{}"})()})())
    assert hook.main() == 0
    assert json.loads(capsys.readouterr().out)["decision"] == "block"
