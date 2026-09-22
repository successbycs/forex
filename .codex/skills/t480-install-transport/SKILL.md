---
name: t480-install-transport
description: Build or repair fixed Forex T480 install/update operations that must stay below the encoded SSH command limit. Use for Scheduled Task install, rollback, release binding, or T480 transport-length failures; not for generic remote access.
---

# T480 Install Transport

Use this skill when changing a fixed T480 adapter operation that installs or
updates a Forex listener and its fully encoded SSH command may approach the
hard 7,500-character envelope.

This is a transport and fail-closed construction skill. It does not authorize
deployment, Scheduled Task mutation, Demo entry enablement, generic shells, or
file copying. Use the existing fixed adapter and release procedure only.

## Non-negotiable boundary

`t480_core.build_ssh_command()` measures the actual encoded command sent to
T480. Raw PowerShell length is not evidence of transport safety. Each
non-fragment operation used by the candidate deployment must measure strictly
below 7,500 characters. Treat `>= 7500` as `NO-GO`; do not retry it remotely.

The normal locations are:

- `scripts/t480_adapter.py` for fixed operation construction;
- `tests/test_t480_adapter.py` for an encoded-length regression assertion;
- `docs/t480-deployment.md` for the transport rule;
- `t480/command-catalog.json` if operation identities or purposes change.

## Build or repair an install operation

1. Read `AGENTS.md`, `docs/t480-deployment.md`, the active ExecPlan, and the
   existing install/prepare/stage operations before editing. Preserve the
   fixed-adapter boundary: no arbitrary command parameter, remote shell, or
   unbound copy mechanism.
2. Keep the install operation small. Put large immutable source into numbered
   Base64 fragments, then assemble and SHA-256 verify it on T480 before
   installation. Prefer a pre-existing hash-bound payload for a small launcher.
3. Preserve source binding: installer checks the prepared release ID and
   payload hash; configuration binds the intended Git revision and governed
   fingerprint. A transport fix must not weaken those checks merely to shorten
   a command.
4. Make failure fail closed. Stop and disable any partially installed task.
   If prior task XML is retained for rollback, restore it Disabled; never
   automatically start an old S4U/Session-0 task. Preconditions that prevent
   an unsafe legacy watchdog or topology must be enforced in the install
   operation, not solely written in deployment instructions.
5. Move independent safety work into a separately catalogued fixed operation
   when that keeps installation under the limit (for example, retiring a
   legacy watchdog before install). The install operation must then fail
   before mutation unless that prerequisite is already safe.

## Measure the encoded operation

Run from the repository root after every edit. Replace operation names with
the exact candidate deployment operations.

```bash
python3 - <<'PY'
from scripts import t480_adapter
from t480_core import build_ssh_command

for name in (
    "m20_listener_install",
    "m20_listener_status",
    "m20_listener_prepare",
    "m20_listener_copy_unchanged_payloads",
):
    operation = t480_adapter.OPERATIONS[name]
    encoded = build_ssh_command(
        "OEM@192.168.0.210",
        operation.powershell_command,
        t480_adapter.TRANSPORT_SETTINGS,
    )[-1]
    assert len(encoded) < 7_500, (name, len(encoded))
    print(name, len(encoded))
PY
```

Add or retain a focused test using the same measurement for every changed
non-fragment operation. Do not substitute `len(powershell_command)` for this
test.

## Verification and handoff

Run the changed adapter tests, relevant listener/probe tests, catalog and
milestone validation, plus `git diff --check`. Refresh the governed
configuration fingerprint after catalog changes. Before actual deployment,
use `release-readiness`: inspect current fixed read-only T480 preflight output,
verify committed source binding, retain raw evidence separately, and leave any
maintenance hold in place until the active plan explicitly authorizes release.

Report the measured encoded lengths, the exact failure/rollback behaviour, and
any operation intentionally excluded because it is not part of the candidate
deployment. A green local length check is not deployment approval.
