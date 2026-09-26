#!/usr/bin/env python3
"""Add the fixed M33.1 Session 0 listener install operations (operator applies).

    python3 scripts/apply_m33_session0_listener_install.py --check   # read-only
    python3 scripts/apply_m33_session0_listener_install.py --apply   # edits adapter + catalog

All guards live in the hash-bound payload ``t480/m33_listener_session0_install.ps1``;
the adapter only stages it in eight numbered fragments, verifies its SHA-256 and runs
it, following ``docs/t480-deployment.md``.  Adding the operations registers nothing.
Running ``m33_listener_session0_install`` installs the prepared listener release as an
S4U start-up task in the principal of the ``CS AI Lab MT5 Start`` task, refuses unless
the hold, one Session 0 terminal and a stopped listener are verified, and on failure
restores the previous task Disabled.  Undo the edit with ``git checkout`` of the
adapter and catalog.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADAPTER = ROOT / "scripts" / "t480_adapter.py"
CATALOG = ROOT / "t480" / "command-catalog.json"
ANCHOR = "OPERATIONS.update(_m33_unattended_probe_operations())\n"
MARK = "_m33_listener_session0_install_operations"
NAMES = [f"m33_listener_session0_install_stage_{i}" for i in range(1, 9)] + [
    "m33_listener_session0_install_verify", "m33_listener_session0_install"]

FUNCTION = r'''

def _m33_listener_session0_install_operations() -> dict[str, Operation]:
    """Stage one reviewed installer payload; every guard is inside the hashed payload."""
    source = (ROOT / 't480/m33_listener_session0_install.ps1').read_bytes()
    digest = hashlib.sha256(source).hexdigest()
    encoded = base64.b64encode(source).decode('ascii')
    parts = 8
    width = ((len(encoded) + (parts * 4) - 1) // (parts * 4)) * 4
    root = 'C:\\ProgramData\\ForexListener\\diagnostics\\session0-listener-install-' + digest[:16]
    script = root + '\\install.ps1'
    result: dict[str, Operation] = {}
    for index in range(parts):
        name = 'm33_listener_session0_install_stage_' + str(index + 1)
        result[name] = Operation(name, 'Stage fixed Session0 listener installer payload fragment ' + str(index + 1) + '.',
            powershell_command=("$ErrorActionPreference='Stop';$d='" + root + "';New-Item -ItemType Directory -Force $d|Out-Null;[IO.File]::WriteAllText((Join-Path $d 'part" + str(index) + "'),'" + encoded[index * width:(index + 1) * width] + "');[pscustomobject]@{staged=$true}|ConvertTo-Json -Compress"))
    result['m33_listener_session0_install_verify'] = Operation(
        'm33_listener_session0_install_verify', 'Assemble, hash-verify and parse the fixed Session0 listener installer payload without running it.',
        powershell_command=("$ErrorActionPreference='Stop';$d='" + root + "';$e=((0..7|ForEach-Object{[IO.File]::ReadAllText((Join-Path $d ('part'+$_)))}) -join '');$b=[Convert]::FromBase64String($e);$h=([BitConverter]::ToString([Security.Cryptography.SHA256]::Create().ComputeHash($b))).Replace('-','').ToLower();if($h -ne '" + digest + "'){throw 'installer hash mismatch'};[IO.File]::WriteAllBytes('" + script + "',$b);$t=$null;$x=$null;[System.Management.Automation.Language.Parser]::ParseFile('" + script + "',[ref]$t,[ref]$x)|Out-Null;if($x.Count -ne 0){throw 'installer parse failed'};[pscustomobject]@{verified=$true;source_sha256=$h}|ConvertTo-Json -Compress"))
    result['m33_listener_session0_install'] = Operation(
        'm33_listener_session0_install', 'Install the prepared listener as an S4U start-up task under the MT5 boot-task principal, only with the maintenance hold, one Session0 terminal and a stopped listener verified; restores the prior disabled task on failure.',
        powershell_command=("$ErrorActionPreference='Stop';$p='" + script + "';if((Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash.ToLower() -ne '" + digest + "'){throw 'installer hash mismatch'};$o=& powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File $p 2>&1;if($LASTEXITCODE -ne 0){throw ('installer refused: '+($o -join ' '))};$o"), timeout_seconds=120)
    return result


OPERATIONS.update(_m33_listener_session0_install_operations())
'''


def catalog_entries() -> list[dict]:
    purposes = {"m33_listener_session0_install_verify": "Assemble, hash-verify and parse the fixed Session0 listener installer payload without running it.",
                "m33_listener_session0_install": "Install the prepared listener as an S4U start-up task under the MT5 boot-task principal, only with maintenance hold, one Session0 terminal and a stopped listener; restores the prior disabled task on failure."}
    return [{"id": n, "purpose": purposes.get(n, "Stage fixed Session0 listener installer payload fragment " + n.rsplit("_", 1)[1] + "."),
             "approval_required": False} for n in NAMES]


def check() -> int:
    sys.path.insert(0, str(ROOT))
    from scripts import t480_adapter as adapter
    from t480_core import build_ssh_command

    namespace = dict(vars(adapter))
    exec(compile(FUNCTION.rsplit("\n\nOPERATIONS.update", 1)[0], "<m33-session0-install>", "exec"), namespace)
    operations = namespace[MARK]()
    worst = 0
    for name, operation in operations.items():
        worst = max(worst, len(build_ssh_command("OEM@192.168.0.210", operation.powershell_command, adapter.TRANSPORT_SETTINGS)[-1]))
    print(f"{len(operations)} operations, maximum encoded length {worst} (limit 7500)")
    payload = (ROOT / "t480" / "m33_listener_session0_install.ps1").read_text()
    register = payload.index("Register-ScheduledTask")
    for guard in ("MAINTENANCE_HOLD_REQUIRED", "LISTENER_MUST_NOT_BE_RUNNING", "LISTENER_WORKERS_MUST_BE_ABSENT",
                  "ONE_CONFIGURED_SESSION0_TERMINAL_REQUIRED", "LEGACY_WATCHDOG_MUST_BE_DISABLED",
                  "PAYLOAD_HASH_MISMATCH", "MT5_S4U_PRINCIPAL_REQUIRED"):
        assert payload.index(guard) < register, guard
    assert "order_send" not in payload and "Enable-ScheduledTask" not in payload
    return 0 if worst < 7500 else 1


def apply() -> int:
    source = ADAPTER.read_text()
    catalog = json.loads(CATALOG.read_text())
    present = {entry["id"] for entry in catalog["operations"]}
    adapter_done, catalog_done = MARK in source, set(NAMES) <= present
    if adapter_done and catalog_done:
        print("already applied")
        return 0
    if not adapter_done and source.count(ANCHOR) != 1:
        print("anchor not found; adapter changed", file=sys.stderr)
        return 1
    if not adapter_done:
        ADAPTER.write_text(source.replace(ANCHOR, ANCHOR + FUNCTION, 1))
    catalog["operations"].extend(entry for entry in catalog_entries() if entry["id"] not in present)
    CATALOG.write_text(json.dumps(catalog, indent=2) + "\n")
    print("applied; refresh the project_state configuration fingerprint and run the tests")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true")
    group.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    raise SystemExit(check() if args.check else apply())
