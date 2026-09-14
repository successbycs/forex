# Harness H5 sub-ExecPlan — execution-work record consistency

This is a living sub-ExecPlan of `docs/plans/harness-h5-production-orchestration.md`.
`PLANS.md`, `AGENTS.md`, the M29 contract, and the parent H5 plan take precedence.
Its machine-readable work record is
`docs/plans/harness-h5-work-record-consistency-work.json`.

## Purpose / Big Picture

H5 has two views of its work: an execution-work JSON record that the
continuation checker reads, and a human-readable Markdown ExecPlan Progress
list. They can currently disagree because neither is checked against the
other. That can make the controller continue work that the plan appears to
have finished, or make a reviewer and Plane operator believe that a completed
item remains pending.

This sub-plan will make the JSON record the one machine authority for granular
work state, and make the matching Markdown Progress section a checked human
projection. An operator will be able to run one fixed local command and see
either `CONSISTENT` or a precise mismatch. A mismatch will fail closed for
work selection, Plane scheduling display, and review handoff; it will never
silently rewrite either source. This is delivery-governance work only. It does
not authorize broker, MT5, trading, Live endpoints, commits, pushes, Plane
acceptance, or formal milestone closure.

## Context and Orientation

An *execution-work record* is a JSON file under `docs/plans/` containing a
task ID and small work items with `PENDING`, `IN_PROGRESS`, `BLOCKED`, or
`DONE` state. `scripts/check_execution_continuation.py` uses that record to
say whether an agent must continue. An *ExecPlan Progress projection* is the
short checklist in the corresponding Markdown plan that people read during
reviews and operational handoff.

The affected H5 pair is
`docs/plans/harness-h5-execution-loop-orchestration.md` and
`docs/plans/harness-h5-execution-loop-orchestration-work.json`. The H5 parent
plan and future H5 subplans use the same convention. The existing selector in
`src/forex/execution_selection.py`, continuation checker, Stop hooks, Plane
controller, and status/report commands must not infer state from Markdown.
They may use JSON only after the new consistency validator reports a matching
projection.

## Scope and Boundaries

- JSON remains authoritative for item identity, title, state, dependencies,
  evidence, and blockers. Markdown is a reviewable rendering, not a second
  scheduler or approval source.
- The validator reads tracked repository files only. It makes no network,
  Plane, Codex App Server, Git, worktree, broker, MT5, or database call.
- A successful consistency check is documentation/governance validation. It
  does not make an item `DONE`, supply review evidence, mark Plane `Done`, or
  close H5/M29.
- A detected mismatch is an invalid work-record condition, not a reason to
  guess which file is right. The system must expose the exact item IDs and
  expected/actual values, then refuse selection and side effects until a human
  or authorised implementation reconciles the Markdown projection to JSON.
- Initial migration is limited to the current H5 execution-loop documents and
  the new sub-plan’s own pair. Generalizing to unrelated legacy plans requires
  a later explicit plan.

## Progress

<!-- forex-work-projection:start task=H5 schema=forex.execution-work-projection.v1 -->
<!-- forex-work-item id=projection-contract state=DONE -->
- [x] projection-contract — Define deterministic JSON-to-Markdown work projection (DONE)
<!-- forex-work-item id=projection-validator state=DONE -->
- [x] projection-validator — Implement read-only fail-closed projection validator (DONE)
<!-- forex-work-item id=projection-gating state=DONE -->
- [x] projection-gating — Gate continuation and H5 scheduling on projection consistency (DONE)
<!-- forex-work-item id=h5-document-migration state=DONE -->
- [x] h5-document-migration — Migrate current H5 plan and work record without changing task state (DONE)
<!-- forex-work-item id=projection-validation-review state=DONE -->
- [x] projection-validation-review — Run focused tests and independent Astra review (DONE)
<!-- forex-work-item id=projection-local-observation state=DONE -->
- [x] projection-local-observation — Record one read-only H5 consistency observation (DONE)
<!-- forex-work-projection:end -->

## Plan of Work

### 1. Define one narrow, parseable Markdown projection

Add a small module under `src/forex/`, for example
`execution_work_projection.py`. It will accept a validated execution-work
JSON object and create a deterministic Progress block bounded by explicit
markers:

    <!-- example forex-work-projection:start task=H5 schema=forex.execution-work-projection.v1 -->
    <!-- example forex-work-item id=durable-loop-state state=DONE -->
    - [x] durable-loop-state — Implement persisted loop state and receipt transitions
    <!-- example forex-work-projection:end -->

The visible checklist is for people. The item marker is for the parser. Each
marker must contain only a safe item ID and one allowed state. The renderer
must derive checkboxes from state (`DONE` is checked; all other states are
unchecked) and include a short visible state label for blocked/in-progress
items. It must preserve all Markdown outside the bounded marker block exactly.

The JSON schema remains the current `forex.execution-work.v1`; no result,
review, or Plane field is copied into the Markdown block. The implementation
must reject duplicate markers, missing start/end markers, nested blocks,
unknown item IDs, reordered or omitted item IDs, unsafe marker syntax, state
differences, and title differences. It must reject Markdown that contains an
apparently valid checklist but lacks the explicit bounded markers.

### 2. Add a fixed read-only validation command

Add `scripts/check_execution_work_projection.py`. It takes exactly one
repository-relative `--work-plan` JSON path and derives the paired Markdown
path from a new required `markdown_plan` field in the work record. It must
validate path containment below `docs/plans/`, regular non-symlink files,
duplicate JSON fields, task-ID equality, and the projection described above.

On success print one redacted JSON line with `status: "CONSISTENT"`, task ID,
work-plan path, Markdown plan path, and both content SHA-256 values. On a
mismatch print `status: "INVALID_WORK_PROJECTION"` plus bounded error codes
and item IDs only; never print credentials, evidence contents, or arbitrary
Markdown. Exit non-zero for every invalid or unavailable input. The command
does not edit either file.

Add a separate explicitly invoked `render` operation only if it writes a
temporary proposed file or emits the rendered block to stdout. It must never
modify the Markdown plan in place. Reconciliation remains an intentional,
reviewable repository edit that copies the renderer’s output into the marked
block and reruns validation.

### 3. Fail closed before H5 selection and scheduling

Extend `src/forex/execution_selection.py` so selection of a work record first
requires projection consistency. Keep its existing path/task binding checks.
Extend `scripts/check_execution_continuation.py` to surface
`INVALID_WORK_PROJECTION` as invalid metadata (exit 2), never as `CONTINUE`,
`BLOCKED`, or `COMPLETE`.

Use the same validator in `scripts/codex_stop_hook.py` so an invalid projection
cannot allow a final response based on stale JSON. The hook must block with a
concise repair message, while remaining only an interactive guardrail.

Before any H5 controller operation that can reconcile or schedule Plane work,
`scripts/plane_symphony_t480.py` must call the validator for the active H5
work record. `sync-once` may remain display-only only when the contract
explicitly permits stale display; otherwise it too must fail closed. The
default for this sub-plan is to fail all H5 Plane changes closed on mismatch.
The validator itself never contacts Plane.

### 4. Migrate H5 documents without inventing progress

Add `markdown_plan` to
`docs/plans/harness-h5-execution-loop-orchestration-work.json`, pointing to
the paired Markdown plan. Replace only the existing relevant Markdown
Progress entries with the marked renderer output. Use the JSON item titles and
states exactly as they exist at migration time. Do not change JSON state,
evidence, blockers, review dispositions, active milestone state, or Plane
items merely to make the display look complete.

Add the same pair of fields/markers to this sub-plan and
`docs/plans/harness-h5-work-record-consistency-work.json`. This makes the
governance repair itself auditable by the same mechanism without claiming it
is complete before tests and independent review.

### 5. Test the real behavior and obtain independent review

Add tests under `tests/` for valid rendering and parsing, missing or duplicate
markers, item/state/title/order mismatch, unsafe paths/symlinks, duplicate
JSON fields, rendering idempotence, and redacted error output. Add integration
tests showing that a mismatch prevents continuation selection, the Stop hook
blocks, and the T480 H5 adapter reaches neither Plane client nor runner.

Use temporary fixtures for all mutations. No test calls Plane, Codex, Git,
broker, MT5, or a Live endpoint. The implementer records focused test output
in the work record. Astra performs a read-only review of the validator,
gating order, test coverage, and the migrated H5 pair. Any material Astra
repair receives a separate independent read-only review as required by
`AGENTS.md`.

## Concrete Steps

Run these commands from `/home/chris/projects/forex` after implementation:

    PYTHONPATH=src python3 -m pytest -q \
      tests/test_execution_work_projection.py \
      tests/test_execution_selection.py \
      tests/test_execution_continuation.py \
      tests/test_codex_stop_hook.py \
      tests/test_plane_symphony_t480.py

    python3 scripts/check_execution_work_projection.py \
      --work-plan docs/plans/harness-h5-execution-loop-orchestration-work.json

Expected observation after migration:

    {"status":"CONSISTENT","task_id":"H5",...}

Then intentionally alter a temporary fixture’s marker state and rerun the
checker. It must exit non-zero and report an `INVALID_WORK_PROJECTION` item
mismatch. Confirm fake Plane and fake runner call counts remain zero.

## Validation and Acceptance

The implementation is accepted only when all of the following are true:

1. The H5 JSON record and its marked Markdown Progress block round-trip to the
   same item IDs, titles, states, and order.
2. Any discrepancy yields a bounded invalid-metadata error and prevents
   continuation selection, Plane reconciliation/scheduling, and worker start.
3. The migration changes presentation metadata only; it does not alter H5/A1
   canonical task state, repository acceptance, Plane state, evidence, or
   authority.
4. Focused tests pass and an independent Astra review records its conclusion
   in the work record.
5. A local `CONSISTENT` transcript is retained as implementation observation
   only. It is not formal M29 proof or H5 board acceptance.

## Idempotence and Recovery

Validation is read-only and safe to repeat. The renderer must produce identical
output for identical JSON. If a migration or later edit causes a mismatch,
leave both files intact, inspect the emitted item-level error, make the
Markdown projection match the authoritative JSON through a normal reviewed
edit, and rerun the checker. Never repair JSON from Markdown, delete work
records, rewrite evidence, or use Plane to resolve a mismatch.

## Surprises & Discoveries

- Observation: the existing JSON work record advanced independently of its
  Markdown Progress checklist, leaving a stale human-facing status.
  Evidence: `durable-loop-state` and `fixed-operation-binding` are `DONE` in
  `harness-h5-execution-loop-orchestration-work.json` while the Markdown plan
  previously described corresponding work as incomplete.

## Decision Log

- Decision: retain JSON as the sole granular execution authority and validate
  Markdown as a deterministic projection.
  Rationale: the continuation checker already uses JSON; treating Markdown as
  co-authoritative would create ambiguous recovery and an unsafe path for
  narrative text to control execution.
  Date/Author: 2026-09-14 / Astra review.

- Decision: fail H5 scheduling closed when its work projection is invalid.
  Rationale: stale visible status damages operator trust and can mislead a
  reviewer or Plane operator; no delivery action needs to proceed while its
  governing record is contradictory.
  Date/Author: 2026-09-14 / Astra review.

## Outcomes & Retrospective

This plan is complete only after the migrated H5 pair passes the read-only
consistency command, focused tests, and independent review. The outcome is
trustworthy H5 delivery status, not task acceptance, Plane completion, trading
capability, or formal milestone proof.
