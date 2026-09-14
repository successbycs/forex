# Harness H5 — production-safe Plane and Codex orchestration

This ExecPlan is a living document. Maintain it under `PLANS.md`; `AGENTS.md`,
`project_state.json`, `milestone_registry.json`, and
`docs/evidence_and_milestones.md` take precedence. Its step record is
`docs/plans/harness-h5-production-orchestration-work.json`.

## Purpose / Big Picture

H5 already has a live Plane board, five workflow states, and display-only H5
and A1 work items. This plan turns that prototype into a safe, repeatable way
to manage Forex repository delivery. Plane will show work and blockers; a
T480 Codex App Server worker may perform only a repository-approved task in an
isolated worktree. The repository remains the sole authority for acceptance,
evidence, review, commits, broker safety, and formal milestone closeout.

After this plan, an operator can see the current H5/A1 work in Plane, start a
bounded worker only after its fixed checks pass, see a timeout or failure as a
redacted `Blocked` status, and retry only after repository review changes the
canonical task record. No Plane action can create broker, MT5, Live-trading,
commit, push, or closeout authority.

## Current Facts

The T480-hosted Plane board `Forex Delivery` (`FXD`) is live in the `forex`
workspace. Its approved visibility is Public. It contains exactly one
`[FOREX:H5]` and one `[FOREX:A1]` work item and the fixed states `Ready`, `In
progress`, `Review`, `Blocked`, and `Done`. Plane payloads must contain only
redacted delivery metadata.

T16 reaches Plane only through an authenticated SSH local forward to a T480
loopback bridge. Do not add LAN bindings, firewall rules, router forwarding,
or public control ports.

The complete H5 package is in locally committed, human-authorised revision
`39e7f89be2b2c0eed59705241ed791309a529568`. T480 still has its older dirty
checkout, so that revision must be published/deployed and recorded in the
protected T480 H5 environment before any write-capable worker is selected.
T480 has user-local Node.js, npm, Codex CLI, and an operator-completed Codex
login; no credential was read or copied.

## Non-negotiable boundaries

- Plane is display and scheduling metadata only. It is never acceptance or
  proof authority.
- The worker never receives the Plane token, broker credentials, MT5 files,
  raw evidence, or a generic external-command capability.
- `GOMarketsMU-Live` remains prohibited. This plan adds no trading authority;
  Demo operations still require their separately declared task and preflight.
- The service never creates commits, pushes, branches, pull requests, or
  formal milestone completion records.
- A clean Git baseline and exact task fingerprint are required before a
  write-capable worker begins. A dirty checkout must fail closed.

## Progress

<!-- forex-work-projection:start task=H5 schema=forex.execution-work-projection.v1 -->
<!-- forex-work-item id=baseline-provenance state=DONE -->
- [x] baseline-provenance — Require H5 package presence in the approved clean baseline (DONE)
<!-- forex-work-item id=identity-hardening state=DONE -->
- [x] identity-hardening — Pin and revalidate exact Plane board, state, and work-item identities (DONE)
<!-- forex-work-item id=state-machine state=DONE -->
- [x] state-machine — Implement repository-only task transitions and fresh selection readback (DONE)
<!-- forex-work-item id=host-tool-egress-confinement state=DONE -->
- [x] host-tool-egress-confinement — Confine Codex host tool egress while retaining App Server transport (DONE)
<!-- forex-work-item id=per-run-ipc-state-isolation state=DONE -->
- [x] per-run-ipc-state-isolation — Expose only per-run IPC state to host and worker (DONE)
<!-- forex-work-item id=ipc-readiness-and-lifecycle state=DONE -->
- [x] ipc-readiness-and-lifecycle — Verify socket readiness and clean up failed IPC host units (DONE)
<!-- forex-work-item id=ipc-integration-review state=DONE -->
- [x] ipc-integration-review — Prove the fixed IPC path and obtain Astra review (DONE)
<!-- forex-work-item id=lifecycle-retry state=DONE -->
- [x] lifecycle-retry — Implement timeouts, health receipts, and review-gated retry (DONE)
<!-- forex-work-item id=t480-codex-setup state=DONE -->
- [x] t480-codex-setup — Install and interactively authenticate T480 Codex CLI (DONE)
<!-- forex-work-item id=clean-baseline state=BLOCKED -->
- [ ] clean-baseline — Record a human-authorized clean baseline containing H5 (BLOCKED)
<!-- forex-work-item id=live-h5-review state=PENDING -->
- [ ] live-h5-review — Run bounded H5 self-test to Review and repository-gated Done (PENDING)
<!-- forex-work-projection:end -->

- [x] (2026-09-14) Live board, state set, T16 private transport, and H5/A1
  display reconciliation were observed and retained in the prior H5 record.
- [x] (2026-09-14) Astra independently reviewed the prototype and identified
  baseline provenance, board/task identity, worker isolation, lifecycle,
  retry, state-machine, and documentation gaps.
- [x] (2026-09-14) Chris authorised and Codex created clean local revision
  `39e7f89be2b2c0eed59705241ed791309a529568` containing the H5 package.
- [x] (2026-09-15) Completed and independently reviewed the MVP controller,
  worker boundary, state transitions, lifecycle receipts, and strict
  no-automatic-retry behavior.
- [x] (2026-09-14) Install the user-local Codex CLI on T480 and complete
  Chris's interactive login; controlled readback confirmed App Server access.
- [x] Replace the fail-closed worker's total network denial with a
  controller-owned fixed Codex egress/IPC path, without exposing Plane, broker,
  MT5, LAN, arbitrary Internet, or inherited secrets to the worker. The
  isolated App Server host retains the transport connectivity Codex needs; its
  workspace-write tool sandbox is explicitly started with
  `sandbox_workspace_write.network_access=false`. This is a Codex tool policy,
  not an OS-level destination allowlist for the host process.
- [x] Complete the linked durable-loop sub-ExecPlan,
  `harness-h5-execution-loop-orchestration.md`: it governs implementation
  continuation separately from the controller's canonical H5/A1 runtime
  scheduling and must not turn ExecPlan items into runtime operations.
- [ ] Run the live H5 self-test through `Review`, obtain repository review,
  then display `Done` and release A1 eligibility.

## Work plan

### 1. Make the deployable revision explicit

Extend `scripts/plane_symphony_t480.py` preflight so it checks that every H5
runtime path exists in `FOREX_SYMPHONY_BASELINE_REVISION`: the controller,
runtime adapter, agent, service unit, configuration, canonical task catalog,
and this ExecPlan. Use `git cat-file` or `git ls-tree` against that revision;
do not inspect the dirty working tree as a substitute. Emit the redacted error
`DEPLOYABLE_REVISION_REQUIRED` when any path is absent.

Add focused tests for a clean revision that contains all paths and one that
does not. The installer and `run-once` must refuse the latter. Once tests pass,
Chris must explicitly authorize a clean baseline commit or another immutable
revision. The controller must not make that commit.

### 2. Verify the live board and work-item identities every cycle

Replace prefix matching in `PlaneWorkItemsV1.find_issue()` with a protected
mapping from canonical task ID to the Plane work-item UUID. On first safe
creation, save the UUID beside the existing board UUID in the owner-only
T480 state record. On every `sync-once`, `run-once`, service start, and loop
iteration, verify all of the following before a worker can be selected:

- one board has the exact `Forex Delivery`/`FXD` identity, approved network,
  source, and external ID;
- every required state exists exactly once with the required group;
- the mapped work item exists, has the exact expected `[FOREX:<id>]` name,
  and belongs to the retained board;
- zero, duplicate, renamed, or manually substituted items are a conflict.

Record only redacted IDs, state names, and error codes. Add fake Plane tests
for duplicate names, a prefix lookalike, deleted/recreated board, wrong state,
and a second reconciliation that produces no create or update request when
the returned representation is semantically unchanged.

### 3. Separate display synchronization from worker execution

Keep `sync-once` display-only: it may bootstrap the exact board and reconcile
H5/A1, but it may not require Codex login, worker capacity, a clean baseline,
or start a lease. `run-once` must perform the full worker preflight, then
perform a fresh board/task verification immediately before selection and read
the Plane display state again after reconciliation.

Implement a repository-owned state transition function in
`src/forex/plane_symphony.py`. The only permitted H5 sequence is:

    BLOCKED or READY -> READY -> IN_REVIEW -> COMPLETE_REVIEWED

Plane changes can be displayed but cannot move the canonical record. A task is
selectable only when the canonical record says `READY`, dependencies are
complete in the same catalog, its review route permits execution, and the
verified Plane display is `Ready`. Add tests for stale Plane state, a manual
Plane `Done`, and A1 remaining ineligible until repository H5 acceptance.

### 4. Enforce worker containment

Change `CodexAppServerRunner` and `t480/plane_symphony_agent.py` so the agent
process receives an empty, allowlisted environment and no Plane environment
file, board-state path, broker configuration, MT5 path, or raw evidence path.
Run it with an isolated writable worktree and state-result directory only.
Default to no network access. A named external operation is executed only by a
small controller-side fixed executor after its exact declared preflight passes;
the Codex prompt is advisory, never the enforcement mechanism.

The executor accepts only the H5 and A1 operation names already present in
`docs/milestones/active-delivery-tasks.json`. It rejects generic commands,
broker, MT5, Live, trading, shell, or arbitrary URL surfaces. Add process and
unit tests that prove secret environment values and forbidden paths are absent
from the worker, and that an undeclared operation cannot run.

### 5. Add bounded lifecycle, health, and retry handling

Give every worker a fixed maximum runtime using `systemd-run` limits. The
agent must close its Codex App Server subprocess, atomically write one terminal
status record, and include a timestamp plus redacted diagnostic. The controller
must convert timeout, protocol failure, and unavailable inspection into a
durable `BLOCKED_*` lease and a Plane `Blocked` display only after identity
verification.

Persist a redacted controller-health receipt for failed preflight, board
verification, or transport observations. The receipt is operational evidence,
not task acceptance evidence. When Plane is available, surface the error code
on the matching work item without uploading logs, credentials, or evidence.

Add an explicit fixed `retry-reviewed` operation. It may release a terminal
lease only when the canonical task fingerprint and repository review
disposition changed after the previous lease. Preserve prior lease history;
never overwrite it. Tests must cover timeout, restart recovery, duplicate
worker exclusion, blocked retry refusal, and permitted reviewed retry.

### 6. Complete T480 operator setup and live proof

Install Node.js and the Codex CLI under Chris's T480 user directory, not as a
system-wide service. Verify the download checksum and record only version and
path. Chris completes `codex login` interactively. Verify:

    codex login status
    codex app-server --help
    systemctl --user show-environment

Then create or select a clean, human-approved baseline containing the H5
package. Configure the owner-only `symphony-h5.env` with its exact SHA. Run:

    python3 scripts/plane_symphony_t480.py preflight
    python3 scripts/plane_symphony_t480.py sync-once
    python3 scripts/plane_symphony_t480.py run-once

The first live run is the H5 bounded self-test only. It must reach `Review`,
not `Done`. Repository review then records acceptance; only the controller may
mirror that acceptance to Plane `Done`. A1 becomes selectable only afterwards.

## Validation and acceptance

Run the focused suite from the repository root:

    python3 -m pytest -q tests/test_plane_symphony.py \
      tests/test_plane_symphony_t480.py tests/test_plane_symphony_agent.py \
      tests/test_plane_mcp_wrapper.py

Add tests named for every scenario in this plan. The suite must demonstrate
exact board/task identity verification, no duplicate Plane items, baseline
provenance refusal, worker isolation, timeout cleanup, health receipts,
review-gated retry, and repository-only transitions.

For the live surface, retain redacted observations of authenticated Plane
readback, exact board and task IDs, configured two-worker limits, a blocked
preflight before login, a post-login H5 self-test reaching Review, and the
repository review that precedes Plane Done. These observations validate H5
operation only. They do not prove or close M29.

## Recovery and rollback

`stop` and `disable` leave Plane history, worktrees, lease history, and raw
evidence intact. Revoke the Plane token and remove the user service to stop
future scheduling. Do not delete Plane history or evidence. If an identity or
fingerprint mismatch occurs, mark the task `Blocked`, retain the old lease,
and require repository review before retrying.

## Surprises & Discoveries

- 2026-09-14: Plane v1.4.2 defaulted a created project to network `2`; Chris
  approved the Public board under the existing redacted-metadata boundary.
- 2026-09-14: T480 WSL had no Node.js, npm, or Codex CLI, so preflight failed
  closed before task selection.
- 2026-09-14: The prototype H5 package is untracked, therefore absent from a
  clean `HEAD` clone and not a valid worker baseline.
- 2026-09-14T11:59:21Z: The controlled fixed T480 preflight reached the Forex
  checkout and toolchain but observed revision `195cd47` with 21 worktree
  changes. It started no worker or trading-related process, and confirms the
  clean-baseline gate is currently the real-world H5 stop.
- 2026-09-14: `PrivateNetwork=yes` correctly protects the worker but prevents
  a local Codex App Server from reaching OpenAI. This is a repairable worker
  containment implementation gap, not an external H5 blocker.
- 2026-09-14: The App Server host must retain its authenticated Codex transport
  connection. Its explicit `sandbox_workspace_write.network_access=false`
  setting denies workspace-write tool network access, but is not a claim of an
  OS-level host egress allowlist.
- 2026-09-14: The MVP keeps mode-0700 per-run directories and separates the
  host socket mount from worker prompt/status state. Deeper hostile-local-path
  checks (owner/mode revalidation and no-follow status replacement) are
  deliberately deferred; they must be completed before treating this as a
  hardened multi-user deployment.

## Decision Log

- 2026-09-14: Keep Plane Public by explicit operator decision, but never send
  raw evidence, credentials, broker data, or acceptance authority to it.
- 2026-09-14: Use a repository-specific Symphony-style controller rather than
  a generic autonomous agent. This preserves task schemas, fixed preflights,
  and the Forex safety boundary.
- 2026-09-14: Make clean baseline provenance and OS-level worker containment
  prerequisites for write-capable workers; prompts alone are insufficient.
- 2026-09-14: Treat the fixed Codex egress/IPC repair as the next H5 work
  package. Do not return it as a terminal blocker while its implementation is
  within this plan's scope.

## Outcomes & Retrospective

The live board and its H5/A1 items already provide real delivery visibility.
This follow-on work upgrades that visibility into a safe ongoing controller.
Completion of this ExecPlan is not M29 completion and does not alter trading
authority.
