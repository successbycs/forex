import hashlib
import json
from pathlib import Path
import subprocess

import pytest

from forex.t480_dependency import inspect_dependency
from scripts import t480_adapter


def test_catalog_and_adapter_operations_match():
    t480_adapter.validate_contract()
    catalog = json.loads(t480_adapter.CATALOG_PATH.read_text(encoding="utf-8"))
    assert {entry["id"] for entry in catalog["operations"]} == set(t480_adapter.OPERATIONS)


def test_adapter_emits_the_governed_project_fingerprint_for_evidence_binding():
    fingerprint = t480_adapter.project_configuration_fingerprint()
    assert fingerprint.startswith("sha256:")
    assert len(fingerprint) == 71


def test_adapter_is_read_only_and_has_no_arbitrary_command_surface():
    assert all(not operation.approval_required for operation in t480_adapter.OPERATIONS.values())
    help_text = t480_adapter.parser().format_help()
    assert "--command" not in help_text
    assert "--script" not in help_text
    assert "--approve" not in help_text


def test_configuration_rejects_unknown_fields(tmp_path):
    payload = dict(t480_adapter.APP_CONFIG)
    payload["unexpected"] = "value"
    path = tmp_path / "config.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError):
        t480_adapter.load_application_config(path)


def test_configuration_rejects_unsafe_paths(tmp_path):
    payload = dict(t480_adapter.APP_CONFIG)
    payload["application_root"] = "/safe/path; touch /tmp/not-allowed"
    path = tmp_path / "config.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError):
        t480_adapter.load_application_config(path)


def test_mt5_status_is_process_only():
    operation = t480_adapter.OPERATIONS["mt5_process_status"]
    command = operation.powershell_command or ""
    assert "Get-Process" in command
    assert "MetaTrader5" not in command
    assert "account_info" not in command
    assert "symbol_info_tick" not in command
    assert "order_send" not in command


def test_m1_mt5_probe_is_fixed_and_read_only():
    command = t480_adapter.OPERATIONS["m1_mt5_demo_probe"].powershell_command or ""
    probe = (t480_adapter.ROOT / "t480" / "m1_mt5_demo_probe.py").read_text(encoding="utf-8")
    assert "copy_rates_from_pos" in probe
    assert "TIMEFRAME_H1" in probe
    assert "BAR_COUNT = 720" in probe
    assert "bars_encoding" in probe
    assert "gzip+base64-json" in probe
    assert "symbol_info_tick" not in probe
    assert "order_send" not in probe
    assert "OEM" not in command
    assert "mt5.local.json" in command
    assert "m1_mt5_demo_probe.py" in command
    assert "terminal_path" in command
    assert "python_path" in command
    assert "--command" not in t480_adapter.parser().format_help()
    assert t480_adapter.OPERATIONS["m1_mt5_demo_probe"].approval_required is False

def test_m1_probe_checks_demo_server_before_any_market_data_call():
    probe = (t480_adapter.ROOT / "t480" / "m1_mt5_demo_probe.py").read_text(encoding="utf-8")
    assert probe.index('account.server != "GOMarketsMU-Demo"') < probe.index("symbol_info")
    assert probe.index('account.server != "GOMarketsMU-Demo"') < probe.index("copy_rates_from_pos")

def test_m1_verification_marker_is_reserved_for_a_successful_fixed_probe(monkeypatch):
    monkeypatch.setattr(t480_adapter, "require_dependency", lambda _: None)
    monkeypatch.setattr(t480_adapter, "append_execution_log", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        t480_adapter,
        "execute",
        lambda operation_id: {"operation": operation_id, "ok": True, "result": {}},
    )
    assert t480_adapter.main(["verify", "--operation", "m1_mt5_demo_probe"]) == 0


def test_requirements_prohibit_trading_and_arbitrary_market_data_access():
    prohibited = " ".join(t480_adapter.requirements()["prohibited"])
    assert "generic MetaTrader API" in prohibited
    assert "arbitrary" in prohibited
    assert "order" in prohibited


def test_shared_core_root_cannot_be_redirected_by_environment(monkeypatch):
    monkeypatch.setenv("CS_AI_LAB_INFRA_ROOT", "/tmp/untrusted-core")
    assert t480_adapter.SHARED_CORE_ROOT == Path(
        t480_adapter.APP_CONFIG["shared_core"]["repository_root"]
    )


def test_shared_dependency_allows_unrelated_owner_changes_but_rejects_locked_file_drift(tmp_path):
    repository = tmp_path / "shared-core"
    repository.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repository, check=True)
    paths = ["t480_core/__init__.py", "t480_core/core.py", "t480/transport-config.json"]
    for index, relative in enumerate(paths):
        path = repository / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"locked-content-{index}\n", encoding="utf-8")
    subprocess.run(["git", "add", "--", *paths], cwd=repository, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Forex Test",
            "-c",
            "user.email=forex-test@example.invalid",
            "commit",
            "-qm",
            "fixture",
        ],
        cwd=repository,
        check=True,
    )
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repository, text=True, capture_output=True, check=True
    ).stdout.strip()
    config = {
        "shared_core": {
            "repository": "fixture/shared-core",
            "repository_root": str(repository),
            "expected_git_revision": revision,
            "require_clean_worktree": False,
            "require_tracked_files": True,
            "files": [
                {
                    "path": relative,
                    "sha256": hashlib.sha256((repository / relative).read_bytes()).hexdigest(),
                }
                for relative in paths
            ],
        }
    }
    assert inspect_dependency(config)["ok"] is True
    (repository / paths[1]).write_text("drifted\n", encoding="utf-8")
    drifted = inspect_dependency(config)
    assert drifted["ok"] is False
    assert f"locked dependency hash mismatch: {paths[1]}" in drifted["errors"]
