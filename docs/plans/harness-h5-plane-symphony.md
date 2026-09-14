# Harness H5 — Plane-connected Symphony-style T480 orchestration

This ExecPlan is a living document maintained under `PLANS.md`. `AGENTS.md`,
the M29 contract, `project_state.json`, and `docs/evidence_and_milestones.md`
take precedence. H5 is delivery-harness work only: it cannot grant broker,
commit, push, or formal-closeout authority.

Step-level continuation and blocker records are maintained in
`docs/plans/harness-h5-execution-work.json`. Run
`python3 scripts/check_execution_continuation.py --work-plan docs/plans/harness-h5-execution-work.json`
before an incomplete H5 handoff.

## Purpose / Big Picture

H5 makes the Plane stack on T480 a visible delivery board for the Forex
repository. A small T480-resident controller follows the Symphony pattern: it
maps the repository's H5 and A1 task records to Plane work items, selects only
an eligible `Ready` item, and runs an isolated Codex App Server worker. Plane
shows status; repository checks, evidence, review, and formal M29 proof remain
authoritative.

H5 has an explicit operational control-plane bootstrap before Symphony may
select any task: T16 access → T480 Plane transport → approved board → protected
UUID retention → display-only task reconciliation → H5 self-test and
repository review → A1 eligibility. This is a delivery capability, not M29
proof and not worker authority.

## Progress

- [x] (2026-09-14) Recorded the H5 design: T480 user service, two worker slots,
  Plane scheduling only, repository approval, and H5 then A1 rollout.
- [x] (2026-09-14) Implemented the repository contract, scheduler, Plane v1
  adapter, protected local configuration, isolated worker runner, and focused
  fake-service tests. The adapter uses `X-API-Key`, refuses redirects, binds
  every run to an exact human-approved clean revision, and creates worktrees
  only in T480-local cache.
- [ ] Independent review of the final adapter and a credential-free T480
  preflight remain required before installation.
- [x] (2026-09-14) Implemented and fake-API-tested the bounded `forex`
  workspace board bootstrap: exact `Forex Delivery` / `FXD` identity,
  approved-project and state reconciliation, conflict refusal, and protected
  non-secret immutable-project-ID retention. This is not a live-board claim.
- [x] (2026-09-14) Transferred the reused Planner credential only into
  ignored, owner-only Forex-local configuration and registered the
  Forex-owned MCP wrapper. The wrapper starts and advertises its tool set
  without sourcing Product Planner configuration.
- [x] (2026-09-14) T480-local Plane health was observed: loopback web returned
  HTTP 200 and unauthenticated API returned HTTP 401. The shared T16→T480
  control path also passed. A Windows loopback-to-WSL bridge was added; its
  T16 SSH-forward readback remains to be verified before it is accepted.
- [x] (2026-09-14) Live T16 API discovery confirmed the `Forex Delivery` /
  `FXD` project with `network: 2` (Public). Chris explicitly approved this
  visibility for the redacted, non-authoritative delivery board. The controller
  accepts only this fixed network value and still refuses identity ambiguity.
- [x] (2026-09-14) Live bootstrap retained the exact board UUID in protected
  T480-local state, verified the five fixed states, and reconciled one
  `[FOREX:H5]` and one `[FOREX:A1]` work item. Reconciliation is display-only
  and created no worktree, lease, worker, broker action, commit, or acceptance.
- [ ] (2026-09-14) T480 fixed preflight correctly refused before selection:
  the Codex CLI is absent, so interactive Codex login/App Server verification
  cannot run. The next operator setup action is Codex installation and login;
  a clean human-authorized Git baseline remains required afterwards.
- [ ] After operator configuration, connect Plane, demonstrate H5 review, and
  make A1 selectable without granting execution authority.

## Decisions

- Plane schedules but never accepts repository work or formal proof.
- Only `H5` and `A1` are in the first rollout; no generic task, shell, MT5,
  broker, or Live surface is accepted.
- A task-declared external operation requires its named fixed preflight. The
  system starts with two one-CPU, 1536 MiB, 128-PID worker slots.
- A clean human-authorized Git baseline is required before an agent can start
  write-capable work. The service never creates commits.
- Transport is shared-infrastructure owned: Plane remains T480-loopback-only.
  Any T16 route must be a fixed, authenticated, loopback-only bridge; no LAN
  listener, firewall exception, router forwarding or public ingress is an H5
  remedy.
- Plane v1.4.2 REST project creation defaults to the explicitly approved Public
  board network. Plane receives only redacted delivery metadata; a board never
  carries raw evidence, credentials, broker data, or task-acceptance authority.

## Context and Orientation

`docs/milestones/active-delivery-tasks.json` remains the canonical task source.
`config/plane_sync.json` declares Plane's visibility-only authority; the
separate `config/plane_symphony.json` pins the H5 controller policy. T480
secrets live only in an ignored, mode-0600 copy of
`t480/symphony_h5.local.example.env`; it also records the exact clean baseline
approved by the human operator. The user service
template is `t480/forex-symphony-h5.service` and does not expose a port or
mount Docker's socket.

## Work and Acceptance

### Operational control-plane bootstrap

The bootstrap command is distinct from worker installation and execution. It
must perform only these ordered actions:

1. Verify T480 Plane loopback health, the governed T16 bridge, and the
   authenticated projects collection. Retain redacted status/receipt metadata.
2. Verify exactly one approved Public `Forex Delivery` / `FXD` project in `forex` with
   `external_source=forex-h5` and `external_id=forex-delivery-v1`. It must not
   delete, rename, or repair a conflicting board.
3. Persist only the verified immutable project UUID in the protected T480
   board-state file, bound to origin and workspace.
4. Reconcile only `[FOREX:H5]` and `[FOREX:A1]`, then read them back. This is
   display-only: it creates no worktree, lease, worker, evidence, commit or
   broker action.
5. Emit a redacted bootstrap receipt. An unapproved board network, unavailable bridge,
   non-exact identity, or failed readback fails closed.

Only after bootstrap is accepted may fixed T480 preflight and user-service
installation be considered. `run-once` still requires capacity, Codex login,
the exact clean human-approved baseline, repository eligibility, and the
task's named preflight.

### H5 self-test and A1 release

H5 becomes `Ready` only after bootstrap. Symphony then performs H5's bounded
non-writing self-test and displays `Review`. Repository review—not Plane—may
accept it; only that accepted result can display Plane `Done`. A1 becomes
selectable after this repository acceptance, never after a Plane-only state
change.

Implement a standard-library controller and fixed CLI that validate both
configuration documents, redact Plane requests and local results, reconcile
only `[FOREX:H5]` and `[FOREX:A1]`, write durable non-secret leases, and start
at most two isolated worktrees through Codex App Server. Restart may resume a
lease only when task ID, baseline revision and policy fingerprint still match.
A Plane `Done` state without repository acceptance evidence is reported as an
inconsistency, not a completed task.

Unit and fake-service integration tests must cover contract rejection,
idempotent reconciliation, dependency selection, duplicate-lease exclusion,
restart recovery, redaction, dirty-baseline refusal, unsafe-operation refusal,
and Plane non-authority. The H5 preflight must check Plane health, protected
local configuration, Codex App Server, Git, Python, `systemd --user`, Windows
C: free space, and WSL available memory before a task is selected.

Operational acceptance requires an authenticated read-only Plane observation,
the `Forex Delivery` board with H5/A1 mappings, two configured but bounded
worker slots, H5 reaching `Review` then repository-reviewed `Done`, and A1
becoming eligible only after that result. This remains implementation and
operational evidence, not M29 proof.

## Recovery

Stopping the service retains Plane history, local leases, worktrees, evidence,
and task metadata. Restart refuses mismatched or incomplete leases. Rollback
stops/disables only this user service and revokes the Plane token; it never
deletes evidence, touches n8n/MT5, or changes formal milestone state.
