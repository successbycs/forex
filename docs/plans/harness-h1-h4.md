# Complete the Harness H1–H4 delivery wave

This ExecPlan is a living document and follows `PLANS.md`. Repository
governance in `AGENTS.md`, `project_state.json`, `milestone_registry.json`, and
`docs/evidence_and_milestones.md` takes precedence.

## Purpose / Big Picture

The Harness wave gives the operator a reliable repository map, an explicit
delivery sequence, visible task and blocker status, and a safe offline mapping
to the Plane board installed on T480. After this work, a contributor can find
the current task, its owned paths, its checks, and its blocker without using
Plane as an authority source.

This is implementation and delivery evidence under formal milestone M29. It
does not operate MetaTrader, configure Plane, collect market data, prove M29,
or authorize a trade.

## Progress

- [x] (2026-09-14T00:39:14Z) Read the governing state, M29 contract, evidence
  rules, active-task metadata, and ExecPlan standard.
- [x] (2026-09-14T00:39:14Z) Validated H1–H4 with their declared governance,
  focused-test, status, and offline-mapping checks.
- [x] (2026-09-14T00:39:14Z) Reconciled the stale human-facing Harness table
  with canonical `COMPLETE_REVIEWED` task metadata.
- [x] (2026-09-14T00:39:14Z) Confirmed that the task-plan catalog includes H5
  for complete Plane visibility, while H5 remains a separately blocked task
  and is not a dependency gate for Wave A.
- [x] (2026-09-14T00:40:00Z) Re-ran the declared validation sequence: milestone
  governance validated, ten focused tests passed, the task plan was consistent,
  and Plane remained offline and non-authorising.

## Surprises & Discoveries

- Observation: the task metadata already marked H1–H4
  `COMPLETE_REVIEWED`, but the status table still described them as pending.
  Evidence: `docs/milestones/active-delivery-tasks.json` and
  `docs/milestones/autonomous-delivery-status.md` disagreed before this plan.
- Observation: Plane is installed on T480 but still has no verified endpoint,
  credentials, workspace, project, or synchronization path.
  Evidence: operator report recorded in `docs/plane-integration.md`; the
  checked-in Plane contract remains disabled and offline-only.

## Decision Log

- Decision: treat H1–H4 as complete implementation work and reconcile the
  stale display rather than repeat completed work.
  Rationale: canonical task metadata records the reviewed results and the
  declared checks pass again.
  Date/Author: 2026-09-14 / Codex.
- Decision: retain H5 in the complete task catalog but outside the H1–H4 → A
  dependency gate.
  Rationale: the validated schema requires every task in its catalog, while
  Plane connectivity is explicitly parked and must not block the
  repository-only Harness exit.
  Date/Author: 2026-09-14 / Codex.

## Outcomes & Retrospective

H1–H4 are complete as a delivery wave. The repository has a map, canonical
sequencing, a validated status interface, and an offline Plane mapping. The
next delivery work is blocked by external conditions: H5 needs T480 Plane
configuration and acceptance, while A1 needs real lineaged calendar facts in
PostgreSQL. Neither blocker is resolved by a documentation status change.

## Context and Orientation

`docs/repository-map.md` is H1's concise navigation map.
`docs/prompts/demo-platform-wave-structure.md` declares the H1–H4 → A → B → C
delivery order. `docs/milestones/active-delivery-tasks.json` is the canonical
machine-readable task record; it stores status, dependencies, owned paths,
checks, results, review disposition, and evidence class. A *blocker* is an
external condition that prevents a task from proceeding; it is not evidence of
failure. `scripts/delivery_harness_status.py` reads this record without
changing it. H4's `scripts/plane_sync.py` validates the mapping without making
a network request.

The formal M29 contract is separately defined in `milestone_registry.json`.
Its real-world proof surface is a non-trading recovery drill against fresh
`GOMarketsMU-Demo` data. Harness checks cannot satisfy that proof requirement.

## Plan of Work

Keep the canonical task record and its human-facing status document aligned.
The task catalog includes H5 for Plane visibility, but the H1–H4 → A delivery
dependency path does not require H5. Retain H5 as a separate externally blocked
task because Plane installation alone does not prove or enable a board
connection. Keep `config/plane_sync.json` disabled and do not store
machine-local Plane values or secrets in Git.

## Concrete Steps

From `/home/chris/projects/forex`, run:

    python3 scripts/forex_milestones.py validate
    PYTHONPATH=src python3 -m pytest -q tests/test_active_delivery_documentation.py tests/test_delivery_harness.py tests/test_plane_sync.py
    python3 scripts/delivery_harness_status.py
    python3 scripts/plane_sync.py

Expect governance validation, ten passing focused tests, an offline Plane
report with `execution_authority: false`, and a status result that identifies
M29 as blocked without claiming formal completion.

## Validation and Acceptance

Acceptance means the four Harness artifacts are present and their declared
checks pass: governance validates; the documentation, task-status, and Plane
tests pass; the status script reports a canonical plan with no consistency
issues; and the Plane script reports offline preparation with repository-owned
task acceptance. The status table must show H1–H4 `COMPLETE_REVIEWED` and must
show H5 as separately blocked and not an H1–H4 → A dependency gate.

This acceptance is implementation evidence only. M29 completion still needs
its current real-world recovery evidence, independent verifier result,
Triad-plus-domain recommendation, and required human review under its exact
contract.

## Idempotence and Recovery

All validation commands are read-only and safe to repeat. If the status table
and task JSON disagree, correct the stale display to the canonical task record
only after checking its task IDs and dependencies. Do not change the formal
milestone state to repair a delivery display. If Plane configuration is absent
or fails, retain H5 as blocked and continue to use repository metadata.

## Artifacts and Notes

The completion transcript on 2026-09-14 was:

    milestone governance valid
    10 passed
    plane synchronization: NOT_ATTEMPTED_OFFLINE_PREPARATION
    plane execution_authority: false
    formal M29 state: BLOCKED

## Interfaces and Dependencies

The Harness task source is exactly
`docs/milestones/active-delivery-tasks.json`. `src/forex/active_delivery_tasks.py`
validates it and `src/forex/delivery_harness.py` selects only safe work.
`config/plane_sync.json` must remain `enabled: false` and
`execution_authority: false` until a separately authorized H5 configuration
change extends its contract and tests. Plane never owns milestone proof or task
acceptance.

Revision note — 2026-09-14: created this self-contained plan, reconciled the
stale Harness status table, and clarified that H5 remains in the complete task
catalog but is separate from the H1–H4 → A dependency gate.

Revision note — 2026-09-14: re-executed the declared validation sequence and
recorded its passing, read-only result.
