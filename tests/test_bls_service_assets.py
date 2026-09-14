"""Static guards for the prepared, non-installed BLS systemd assets."""
from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "deploy" / "bls"


def _unit(path: Path) -> dict[str, dict[str, str]]:
    sections: dict[str, dict[str, str]] = {}
    section = None
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
            sections[section] = {}
            continue
        assert section is not None, f"unsectioned unit directive: {line}"
        key, value = line.split("=", 1)
        sections[section][key] = value
    return sections


def test_service_template_is_one_shot_bounded_no_shell_or_retry():
    service = _unit(ASSETS / "forex-bls-schedule.service")
    assert service["Service"]["Type"] == "oneshot"
    assert service["Service"]["Restart"] == "no"
    assert service["Service"]["TimeoutStartSec"] == "210s"
    assert service["Service"]["UMask"] == "0077"
    assert service["Service"]["NoNewPrivileges"] == "true"
    command = service["Service"]["ExecStart"]
    assert command == ("{{PYTHON_EXECUTABLE_ABSOLUTE_PATH}} "
                       "{{FOREX_REPOSITORY_ABSOLUTE_PATH}}/scripts/bls_schedule.py "
                       "--store {{BLS_RETAINED_STORE_ABSOLUTE_PATH}}")
    assert all(token not in command for token in ("/bin/sh", "bash", "sh -c", ";", "&&", "|"))
    assert "MemoryMax" not in service["Service"]
    assert "CPUQuota" not in service["Service"]


def test_timer_is_hourly_and_never_catches_up_missed_requests():
    timer = _unit(ASSETS / "forex-bls-schedule.timer")
    assert timer["Timer"] == {"OnCalendar": "hourly", "Persistent": "false",
                               "Unit": "forex-bls-schedule.service"}
    assert timer["Install"]["WantedBy"] == "timers.target"


def test_documentation_carries_capacity_hold_and_t480_boundary():
    text = (ASSETS / "README.md").read_text(encoding="utf-8")
    for phrase in ("Do not install", "capacity", "T480 native", "Persistent=false",
                   "no retry", "no broker, order", "{{BLS_RETAINED_STORE_ABSOLUTE_PATH}}"):
        assert phrase in text


def test_schedule_cli_is_a_fixed_argument_vector_with_two_collector_budget():
    source = (ROOT / "scripts" / "bls_schedule.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    runs = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute) and node.func.attr == "run"]
    assert len(runs) == 1
    call = runs[0]
    assert isinstance(call.args[0], ast.Name) and call.args[0].id == "command"
    keywords = {item.arg: item.value for item in call.keywords}
    assert isinstance(keywords["timeout"], ast.Constant) and keywords["timeout"].value == 90
    assert isinstance(keywords["check"], ast.Constant) and keywords["check"].value is False
    assert "shell" not in keywords
    assert "for " not in source[source.index("def collect_once"):source.index("def main")]
