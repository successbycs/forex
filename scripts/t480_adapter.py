#!/usr/bin/env python3
"""Governed read-only T480 access adapter for Forex.

The reusable transport comes from ``cs-ai-lab-infra/t480_core``. This module
owns only fixed Forex and shared-platform inspection operations. It cannot
accept shell text, connect through the MetaTrader Python API, retrieve account
or market data, deploy services, or place trades.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys
from typing import Any

TOOL_ID = "forex_t480"
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from forex.t480_dependency import inspect_dependency, require_dependency  # noqa: E402

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
DEPENDENCY_IDENTITY = inspect_dependency(APP_CONFIG)
unsafe_identity_errors = [
    error
    for error in DEPENDENCY_IDENTITY["errors"]
    if error != "owner repository worktree is not clean"
    and not error.startswith("locked dependency file is not tracked:")
]
if unsafe_identity_errors:
    raise ValueError("Unsafe T480 shared-core import: " + "; ".join(unsafe_identity_errors))
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
}


def validate_contract() -> None:
    validate_catalog(CATALOG_PATH, OPERATIONS)
    if any(operation.approval_required for operation in OPERATIONS.values()):
        raise ValueError("The initial Forex T480 adapter must remain read-only")


def target() -> str:
    return resolve_ssh_target(TRANSPORT_SETTINGS, [LOCAL_TARGET_PATH, SHARED_TARGET_PATH])


def requirements() -> dict[str, Any]:
    return {
        "tool_id": TOOL_ID,
        "shared_core_root": str(SHARED_CORE_ROOT),
        "shared_core_identity": DEPENDENCY_IDENTITY,
        "description": "Run fixed read-only Forex and shared-platform T480 inspections.",
        "configuration_fingerprint": CONFIGURATION_FINGERPRINT,
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
            "MetaTrader API access",
            "account or market-data access",
            "order operations",
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
            config_paths=[LOCAL_TARGET_PATH, SHARED_TARGET_PATH],
        )
    else:
        require_dependency(APP_CONFIG)
        if not args.operation:
            raise SystemExit("--operation is required for execute and verify")
        payload = execute(args.operation)
        if args.command == "verify":
            payload["verified_operation"] = args.operation
    if args.command != "dependency-status":
        payload["configuration_fingerprint"] = CONFIGURATION_FINGERPRINT
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
