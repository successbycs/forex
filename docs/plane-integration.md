# Plane delivery-board integration

Harness H5 connects the existing T480 Plane installation to a Forex-specific,
Symphony-style task controller. Plane is a visible delivery board only. It
cannot authorize a broker operation, accept a repository task, close M29, or
change trading authority. The repository task catalog, review evidence and
milestone contracts remain authoritative.

## Interactive MCP access

The Forex-owned launcher is `t480/plane-mcp.sh`. Copy
`t480/plane_mcp.local.example.env` to `~/.config/forex/plane-mcp.env`, reuse
the existing Planner token only as a temporary local value, and set mode `0600`.
It is deliberately independent of Product Planner's `.env`.

Install the `uv` Python tool runner on each client that runs this launcher.
The launcher looks for `uvx` on `PATH`, then `~/.local/bin/uvx`, because an
editor can start without the login shell's path. A Product Planner virtual
environment is not a Forex dependency. A missing runner produces an explicit
local dependency error before any MCP process starts.

Register it globally without embedding an API key in Codex configuration:

    codex mcp remove plane_forex
    codex mcp add plane_forex -- ~/projects/forex/t480/plane-mcp.sh

The wrapper is an interactive, workspace-scoped administration/discovery tool.
It uses `PLANE_BASE_URL=<Plane origin>/api`. It must never be used as evidence,
task acceptance, broker authority, or a generic task-execution channel.

## Access from the T16

The T16 is an interactive client; the H5 scheduling service runs on T480.
For browser access, use the Plane origin already configured in the protected
local settings and sign in with the existing Plane account. Do not paste an
API token into the browser URL. UI access and authenticated API access are
separate checks: a working login page does not verify the REST routes.

The shared infrastructure checkout publishes Plane on T480 loopback port
`8090` (`cs-ai-lab-infra/plane/compose.yaml`). Its existing T16 control path
uses **Windows OpenSSH**, the Windows SSH configuration and verified host
keys. If a direct Plane origin is unavailable, a local SSH forward can carry
Plane over that existing connection. In a T16 Windows PowerShell window,
use the existing `T480_SSH_TARGET` alias from the ignored infrastructure
configuration; set it locally first if it is not already in the environment:

    if (-not $env:T480_SSH_TARGET) { throw 'Set the existing T480 SSH alias locally first' }
    ssh.exe -N -T -o BatchMode=yes -o StrictHostKeyChecking=yes -o ExitOnForwardFailure=yes -o ConnectTimeout=10 -L 127.0.0.1:18090:127.0.0.1:8090 $env:T480_SSH_TARGET

Keep that window open, then open `http://127.0.0.1:18090` in the T16 Windows
browser. The forward binds only T16 loopback. It requires the existing SSH
server to permit forwarding and the Windows T480 host to reach its Plane
loopback port. A refused forward or unreachable destination is a concrete
transport issue; inspect the shared infrastructure configuration before any
firewall, port-proxy or SSH-server change. Close the window or press Ctrl+C
to remove the temporary forward. Plane itself is left running.

For Codex on T16 WSL, use the same Forex-owned launcher and a T16-local
`~/.config/forex/plane-mcp.env` with mode `0600`. The API origin must be
reachable **from that WSL environment**. A Windows loopback forward is not
automatically reachable through WSL loopback on every network mode; verify
it before configuring `PLANE_BASE_URL=http://127.0.0.1:18090/api`. If it is
unreachable, use an existing approved Plane origin reachable from WSL, or
run the same loopback forward within WSL only when that client already has
its own verified SSH alias and key. Do not widen the listener to `0.0.0.0`.
Browser login does not require copying any server `.env` or API token.

An authenticated `404` by itself does not identify a broken proxy: it may
also be an unsupported route or an inaccessible workspace. Diagnose the
documented projects collection `/api/v1/workspaces/forex/projects/` and
retain only status codes and redacted results. MCP uses the `/api` suffix;
the REST controller adds `/api/v1` to the origin itself. Task-worker Git
cleanliness requirements do not prevent browser access or read-only API
diagnostics.

## T480 setup

The T480-local runtime is `scripts/plane_symphony_t480.py`. It deliberately
offers only `preflight`, `install`, `start`, `stop`, `status`, `sync-once`, and
`run-once`. It is not an SSH shell, Docker wrapper, or general Plane client.
It queries only the fixed Plane v1 work-items collection endpoint:

    /api/v1/workspaces/<workspace>/projects/<project>/work-items/

Create `~/.config/forex/symphony-h5.env` from
`t480/symphony_h5.local.example.env`, replace the example values with the T480
Plane origin and least-privilege token, and run `chmod 600` on the file. The
file must be owned by the T480 user, have exact mode `0600`, and contain only
the four `FOREX_PLANE_*` settings plus the exact
`FOREX_SYMPHONY_BASELINE_REVISION`. The workspace value is its Plane slug and
the project value is the fixed `FXD` board identifier. On first installation,
the controller verifies workspace `forex`, reuses or creates only the marked
private `Forex Delivery` board, and saves its immutable UUID in the protected
local board-state file. H5 REST uses `FOREX_PLANE_URL=<Plane origin>` without
`/api`, because the controller adds `/api/v1` itself. Never put its token, MT5 data, raw evidence,
or OpenAI credentials into Git, Plane descriptions, or terminal transcripts.

On T480, the operator completes the interactive Codex login first. Then run:

    cd ~/projects/forex
    python3 scripts/plane_symphony_t480.py preflight
    python3 scripts/plane_symphony_t480.py install
    python3 scripts/plane_symphony_t480.py start
    python3 scripts/plane_symphony_t480.py status

Preflight requires the Plane collection to authenticate and return an expected
JSON list, `systemd --user`, Git, Python, Codex App Server, at least 4 GiB
available WSL memory, at least 15 GiB free on Windows C: mounted at `/mnt/c`,
and a clean recorded Git baseline. `install` has the same gate; it copies only
the fixed user unit and never starts it. `start` rechecks the gate. The user
unit permits two workers collectively capped at two CPUs, 3 GiB, and 256 PIDs;
each worker's controller policy is one CPU, 1.5 GiB, and 128 PIDs.

`sync-once` and `run-once` always re-run preflight before invoking the
repository controller. The service executes fixed `run-once --loop` every 30
seconds. It does not make a task eligible if the baseline is dirty, if Plane is
unavailable, or if repository review evidence is absent. To stop safely, run
`python3 scripts/plane_symphony_t480.py stop`; durable leases and worktrees are
retained for diagnosis and safe restart.

## First rollout

The controller synchronizes only `[FOREX:H5]` and `[FOREX:A1]`. H5 appears on
the `Forex Delivery` project before A1 is selectable. Plane `Done` is display
state only: it must be derived from accepted repository evidence. H5 is not
formal M29 proof, does not advance `project_state.json`, and does not permit
Demo or Live trading.
