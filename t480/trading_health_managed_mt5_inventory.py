"""Read-only managed-MT5 task-binding and inventory collector for M33.

It uses only fixed local Windows inspection.  It neither initializes MT5 nor
starts/stops a task or process.  The produced records are inputs to a later
separately authorised recovery executor, never authority by themselves.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
if HERE.parent.name in {"releases", "guardian-releases"}:
    loader = importlib.util.spec_from_file_location(
        "forex_m33_managed_mt5", HERE / "trading_health_managed_mt5_recovery.payload"
    )
    if loader is None or loader.loader is None:
        raise RuntimeError("M33 managed MT5 recovery payload is unavailable")
    module = importlib.util.module_from_spec(loader)
    sys.modules[loader.name] = module
    loader.loader.exec_module(module)
    classify_inventory, digest = module.classify_inventory, module.digest
else:
    if str(HERE) not in sys.path:
        sys.path.insert(0, str(HERE))
    from trading_health_managed_mt5_recovery import classify_inventory, digest  # noqa: E402

TASK_NAME = "CS AI Lab MT5 Start"


def _read(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _write(path: Path, value: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    temporary.replace(path)


def _sha(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def _candidate_binding(raw: dict[str, Any], terminal_path: str, terminal_config_sha256: str) -> dict[str, Any]:
    required = {"task_name", "task_xml", "task_action", "principal"}
    if (set(raw) != required or raw.get("task_name") != TASK_NAME
            or not all(isinstance(raw[name], str) and raw[name] for name in ("task_xml", "task_action", "principal"))):
        raise ValueError("TASK_BINDING_UNSAFE")
    if terminal_path.casefold() not in raw["task_action"].casefold():
        raise ValueError("TASK_ACTION_TERMINAL_PATH_MISMATCH")
    # The approved managed terminal is a non-interactive Session-0 S4U task;
    # never treat a copied/interactive task definition as its static binding.
    if "<LogonType>S4U</LogonType>" not in raw["task_xml"]:
        raise ValueError("TASK_PRINCIPAL_NOT_S4U")
    return {"schema_version": "forex.trading-health-mt5-expected-binding-candidate.v1", "task_name": raw["task_name"],
                         "task_xml_sha256": _sha(raw["task_xml"]), "task_action_sha256": _sha(raw["task_action"]),
                         "principal": raw["principal"], "terminal_path": terminal_path,
                         "terminal_config_sha256": terminal_config_sha256}


def _binding(raw: dict[str, Any], expected: dict[str, Any], terminal_path: str, terminal_config_sha256: str) -> dict[str, Any]:
    expected_required = {"schema_version", "task_name", "task_xml_sha256", "task_action_sha256", "principal", "terminal_path", "terminal_config_sha256", "session_id", "parent_path", "command_line_sha256"}
    candidate = _candidate_binding(raw, terminal_path, terminal_config_sha256)
    # Task XML has no observed execution session. Session 0 is therefore an
    # immutable expected constraint, while actual process SessionId is checked
    # independently in the inventory before any recovery action.
    observed_expected = {**candidate, "schema_version": "forex.trading-health-mt5-expected-binding.v1", "session_id": 0,
                         "parent_path": expected.get("parent_path"), "command_line_sha256": expected.get("command_line_sha256")}
    if set(expected) != expected_required or expected != observed_expected:
        raise ValueError("TASK_BINDING_DOES_NOT_MATCH_IMMUTABLE_EXPECTATION")
    value = {"schema_version": "forex.trading-health-mt5-task-binding.v1", "task_name": TASK_NAME,
             "task_xml_sha256": _sha(raw["task_xml"]), "task_action_sha256": _sha(raw["task_action"]),
             "principal": raw["principal"], "terminal_path": terminal_path,
             "terminal_config_sha256": terminal_config_sha256, "session_id": 0, "parent_path": expected["parent_path"], "command_line_sha256": expected["command_line_sha256"], "binding_sha256": None}
    value["binding_sha256"] = digest({key: item for key, item in value.items() if key != "binding_sha256"})
    return value


def _rows(raw: list[dict[str, Any]]) -> list[dict[str, Any]]:
    required = {"pid", "path", "session_id", "command_line", "parent_pid", "parent_path", "creation_id"}
    result = []
    for item in raw:
        if not isinstance(item, dict) or set(item) != required or not isinstance(item.get("command_line"), str):
            raise ValueError("PROCESS_INVENTORY_UNSAFE")
        value = dict(item); value["command_line_sha256"] = _sha(value.pop("command_line")); result.append(value)
    return result


def _observe_windows(terminal_path: str) -> dict[str, Any]:
    if os.name != "nt":
        raise RuntimeError("WINDOWS_FIXED_OBSERVATION_REQUIRED")
    literal = terminal_path.replace("'", "''")
    command = (
        "$ErrorActionPreference='Stop';$t=Get-ScheduledTask -TaskName 'CS AI Lab MT5 Start';"
        "$a=@($t.Actions);if($a.Count -ne 1){throw 'exactly one task action required'};"
        "$x=Export-ScheduledTask -TaskName 'CS AI Lab MT5 Start';"
        "$p=@(Get-CimInstance Win32_Process|Where-Object {$_.Name -in @('terminal.exe','terminal64.exe')}|ForEach-Object{$q=Get-CimInstance Win32_Process -Filter ('ProcessId='+[int]$_.ParentProcessId);[pscustomobject]@{pid=[int]$_.ProcessId;path=[string]$_.ExecutablePath;session_id=[int]$_.SessionId;command_line=[string]$_.CommandLine;parent_pid=[int]$_.ParentProcessId;parent_path=[string]$q.ExecutablePath;creation_id=$_.CreationDate.ToString()}});"
        "[pscustomobject]@{task_name=$t.TaskName;task_xml=$x;task_action=([string]$a[0].Execute+' '+[string]$a[0].Arguments);principal=[string]$t.Principal.UserId;processes=$p;configured_path='" + literal + "'}|ConvertTo-Json -Compress -Depth 8"
    )
    done = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command], capture_output=True,
                          text=True, timeout=15, check=False)
    if done.returncode != 0:
        raise RuntimeError("WINDOWS_FIXED_OBSERVATION_FAILED")
    value = json.loads(done.stdout)
    if not isinstance(value, dict) or value.get("configured_path") != terminal_path:
        raise ValueError("WINDOWS_FIXED_OBSERVATION_INVALID")
    return value


def collect_once(root: Path, observe=_observe_windows) -> dict[str, Any]:
    config = _read(root / "m20_demo_listener_service.local.json")
    terminal_path = config.get("terminal_path") if isinstance(config, dict) else None
    if not isinstance(terminal_path, str) or not terminal_path:
        raise ValueError("TERMINAL_CONFIGURATION_UNREADABLE")
    terminal_config_sha256 = _sha(json.dumps({"terminal_path": terminal_path}, sort_keys=True, separators=(",", ":")))
    expected = _read(root / "trading_health_mt5_expected_binding.local.json")
    if not isinstance(expected, dict):
        raise ValueError("TASK_BINDING_EXPECTATION_UNREADABLE")
    observed = observe(terminal_path)
    raw_binding = {key: observed.get(key) for key in ("task_name", "task_xml", "task_action", "principal")}
    binding = _binding(raw_binding, expected, terminal_path, terminal_config_sha256)
    raw_processes = observed.get("processes")
    inventory = classify_inventory(_rows(raw_processes if isinstance(raw_processes, list) else [raw_processes]), binding)
    _write(root / "trading_health_mt5_task_binding.local.json", binding)
    _write(root / "trading_health_mt5_inventory.local.json", inventory)
    return {"task_binding_sha256": binding["binding_sha256"], "inventory_sha256": inventory["inventory_sha256"],
            "broker_mutation": "NONE", "entry_eligible": False}


def capture_candidate_once(root: Path, observe=_observe_windows) -> dict[str, Any]:
    """Retain read-only candidate evidence; it never provisions authority."""
    config = _read(root / "m20_demo_listener_service.local.json")
    terminal_path = config.get("terminal_path") if isinstance(config, dict) else None
    if not isinstance(terminal_path, str) or not terminal_path:
        raise ValueError("TERMINAL_CONFIGURATION_UNREADABLE")
    terminal_config_sha256 = _sha(json.dumps({"terminal_path": terminal_path}, sort_keys=True, separators=(",", ":")))
    observed = observe(terminal_path)
    raw_binding = {key: observed.get(key) for key in ("task_name", "task_xml", "task_action", "principal")}
    candidate = _candidate_binding(raw_binding, terminal_path, terminal_config_sha256)
    rows = _rows(observed.get("processes") if isinstance(observed.get("processes"), list) else [observed.get("processes")])
    payload = {"schema_version": "forex.trading-health-mt5-binding-candidate-report.v1", "candidate": candidate, "processes": rows,
               "broker_mutation": "NONE", "entry_eligible": False}
    _write(root / "trading_health_mt5_binding_candidate.local.json", payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect fixed no-order M33 MT5 task and process evidence.")
    parser.add_argument("--state-root", type=Path, required=True)
    parser.add_argument("--capture-candidate", action="store_true")
    args = parser.parse_args(); print(json.dumps(capture_candidate_once(args.state_root) if args.capture_candidate else collect_once(args.state_root), separators=(",", ":"))); return 0


if __name__ == "__main__":
    raise SystemExit(main())
