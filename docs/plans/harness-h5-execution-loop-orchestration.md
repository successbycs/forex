# Harness H5 sub-ExecPlan — durable execution-loop orchestration

This is a living sub-ExecPlan of
`docs/plans/harness-h5-production-orchestration.md`. `PLANS.md`, `AGENTS.md`,
the M29 contract, and the parent H5 plan take precedence. Its machine-readable
work record is `docs/plans/harness-h5-execution-loop-orchestration-work.json`.

## Purpose / Big Picture

Codex stop hooks can remind one interactive session to continue, but they do
not schedule later turns or survive an untrusted or absent client hook. This
sub-plan separates two loops that were previously conflated: repository
execution-work records govern implementation continuation, while the H5
controller service governs only canonical H5/A1 runtime scheduling. Plane
remains display-only; the repository remains acceptance authority.

After implementation, an operator can start the H5 user service and see it
poll a named H5 task every 30 seconds. It will not silently stop after a
progress message. It will either begin the next permitted step, wait on a
durable lease, present an exact blocker, or require an independent review. It
cannot start broker, MT5, Live, commit, push, arbitrary shell, or formal
closeout activity.

## Scope and boundaries

- The hook remains a local interactive-session guardrail. It is not the
  scheduler and grants no authority.
- The H5 user service is the only durable scheduler for canonical H5/A1
  runtime tasks. It must not interpret an ExecPlan item as an operation.
- The execution-work record, its checked Markdown projection, and hooks govern
  implementation continuation only; they grant no runtime scheduling authority.
- A loop iteration may call only fixed adapter operations declared by the
  canonical task record after its named preflight succeeds. It may never turn
  a text field, agent result, or Plane field into a shell command.
- Repeated failures do not create unbounded retries: this first state layer
  permits no retry at all and becomes `Blocked` with a fixed receipt code. A
  later fixed-operation adapter may add retry only after it verifies the
  changed canonical task fingerprint and independent repository review.
- No current task is accepted merely because the service loop ran. Plane Done
  continues to require repository acceptance evidence.

## Progress

<!-- forex-work-projection:start task=H5 schema=forex.execution-work-projection.v1 -->
<!-- forex-work-item id=selected-work-manifest state=DONE -->
- [x] selected-work-manifest — Add validated shared active-work selection (DONE)
<!-- forex-work-item id=durable-loop-state state=DONE -->
- [x] durable-loop-state — Implement persisted loop state and receipt transitions (DONE)
<!-- forex-work-item id=fixed-operation-binding state=DONE -->
- [x] fixed-operation-binding — Bind loop selection to catalog-fixed operations and leases (DONE)
<!-- forex-work-item id=service-loop-integration state=DONE -->
- [x] service-loop-integration — Separate runtime controller polling from implementation continuation (DONE)
<!-- forex-work-item id=loop-integration-review state=DONE -->
- [x] loop-integration-review — Run integration tests and independent Astra review (DONE)
<!-- forex-work-item id=t480-no-worker-observation state=BLOCKED -->
- [ ] t480-no-worker-observation — Observe one bounded T480 loop cycle without worker start (BLOCKED)
<!-- forex-work-projection:end -->

## Implementation plan

### 1. Make the selected work record explicit

Replace the single-purpose stop-hook selector with a versioned, tracked
manifest under `config/` that maps one active task ID to one repository-relative
execution-work JSON path. Validate task ID equality, path containment below
`docs/plans/`, unique selection, and digest. Hooks and implementation tooling
use the same selector library. A malformed selector is a visible implementation
continuation failure, never a runtime H5/A1 scheduling gate.

### 2. Add a durable implementation-loop state machine

Add a small module under `src/forex/` that persists owner-only records for:

- selector digest and exact work-record digest;
- task/item ID, baseline revision, configuration fingerprint, lease ID and
  attempt count;
- `SELECTED`, `PREFLIGHT_PASSED`, `RUNNING`, `IN_REVIEW`, or `BLOCKED` local
  lease state. `COMPLETE_REVIEWED` remains a repository task-record state and
  cannot be written by the loop; and
- timestamped, redacted controller receipts.

The transition table rejects skips, stale record digests, duplicate active
leases, manual Plane Done, and all local retries. A later adapter may add
retry only with independently verified repository review provenance and a
changed canonical fingerprint.

### 3. Bind fixed runtime operations and worker lifecycle

Map only canonical H5/A1 tasks to controller-owned fixed operation names. The
adapter validates the name against the existing task catalog before invoking a
preflight or worker. ExecPlan item IDs are never runtime operations. The
controller must inspect an existing worker/host lease before selecting new work,
create no more than two leases, and must not launch a worker while the IPC
containment review or clean-baseline gate is pending.

### 4. Integrate the bounded service loop

Keep `scripts/plane_symphony_t480.py run-once --loop` and the user service on a
30-second runtime polling cadence. They use controller worker leases and
canonical H5/A1 state only. The service must not read, lease, or execute the
currently selected implementation-plan item. An expected runtime gate failure
becomes a controller/Plane `Blocked` display with a redacted code; it does not
bypass dependencies.

### 5. Test and observe

Use fake Plane and fake runner integrations to demonstrate:

1. H5 is selected when the active manifest names H5, not because a hook happens
   to run.
2. A `CONTINUE` record causes repeated controller iterations until its concrete
   state changes; it cannot end on a progress-only result.
3. A blocked external prerequisite is visible, while an independent pending
   repair still runs.
4. Stop and SubagentStop hooks are advisory mirrors of the same selector, not
   the only continuation mechanism.
5. A duplicate lease, stale digest, unreviewed retry, Plane Done, generic
   operation, broker/MT5/Live operation, and secret-shaped receipt are refused.
6. Restart restores exactly one matching lease and does not begin a duplicate.
7. A controlled T480 no-worker observation emits a redacted eligibility or
   blocker receipt and does not start a broker or trading operation.

## Surprises & Discoveries

- 2026-09-14: The prior hook checked only A1 and intentionally allowed a final
  answer after one corrective pass. It therefore could not sustain H5 work.
- 2026-09-14: Codex hooks depend on local trust and a running client, so they
  cannot provide durable service orchestration by themselves.

## Decision Log

- 2026-09-14: Use the H5 controller service, not a prompt or hook, as the loop
  owner. Hooks remain a useful visible backstop for interactive sessions.
- 2026-09-14: Keep all execution selection repository-governed and fail closed;
  Plane may display state but never select or accept a task.

## Outcomes & Retrospective

This sub-plan is complete only when the durable service loop has passed its
fake-adapter tests, independent review, and one controlled T480 no-worker
observation. That is orchestration implementation evidence only; it neither
closes H5/M29 nor changes Forex trading authority.
