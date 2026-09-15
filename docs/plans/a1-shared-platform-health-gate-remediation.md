# A1 prerequisite — shared-platform health-gate remediation

This ExecPlan is governed by `PLANS.md`, `AGENTS.md`, `project_state.json`,
the active M29 contract, and `docs/evidence_and_milestones.md`. The shared
platform is owned by `cs-ai-lab-infra`; this plan does not authorise changes to
that repository, T480, or A1 deployment.

## Purpose

Remove the specific shared-platform preflight failure blocking the reviewed A1
BLS retention service. “Healthy” must mean reproducible checkout, immutable
images, existing service health, and representative physical-capacity evidence
— not merely that Docker is presently running.

The MVP outcome is a green owner-verified health report and a bounded A1
capacity decision. It is not an A1 deploy, Plane task acceptance, broker
action, trade, or formal milestone proof.

## Operator pause

On 2026-09-15, Chris directed that all Plane and shared-platform remediation
work stop because it is not presently making meaningful progress toward
autonomous trading. This ExecPlan is therefore **PAUSED**, not complete. Do not
push `221bcfa`, reconcile the T480 checkout, roll out Plane images, collect
further capacity samples for this plan, or use its result to deploy A1 unless
Chris explicitly resumes this plan. Preserve the commit, current services, and
recorded observations for a later reassessment.

## Current facts

- At 2026-09-14T21:21Z, T480 had about 21.5 GiB free on Windows C: and 5.6 GiB
  available in WSL; Docker, PostgreSQL, n8n and existing services were healthy.
- `lab_health` failed because its checkout was not clean/equal to `origin/main`
  and its configured images were not all immutable digests.
- The observed remote shared revision was `cab3091`. The local shared repo has
  Plane work ahead of `origin/main`; that does not prove T480 has a clean,
  reviewed equivalent.
- The Plane Compose source and observed runtime use tags, including
  `makeplane/*:v1.4.2`, `postgres:15.7-alpine`,
  `valkey/valkey:7.2.11-alpine`, `rabbitmq:3.13.6-management-alpine`, and
  `quay.io/minio/minio:latest`. The root n8n/PostgreSQL project is already
  digest-pinned.
- The root `health-check.sh` checks the root Compose project, so the first step
  must discover the exact T480 health command and Plane Compose source. Do not
  infer it from similarly named local files.
- Fresh read-only T480 inspection at 2026-09-14T21:38Z established the exact
  cause: the root checkout is `cab3091f3046b396e492b5bfdf6e19dc80f942c8`,
  `compose.yaml` is modified, and `plane/` is untracked. Its root Compose file
  includes `./plane/compose.yaml`; Plane is running under the shared
  `cs-ai-lab` Compose project from that local, uncommitted deployment.
- A local, uncommitted shared-source preparation at 2026-09-15T09:41+12:00
  replaced all thirteen rendered Plane image references with digest pins.
  `docker compose -f plane/compose.yaml config --images` rendered only
  `@sha256` references. It neither pulled nor restarted containers. The MinIO
  pin was resolved from `minio:latest` at preparation time and must be compared
  with T480's currently running image ID before any rollout.
- The reviewed pin set was committed locally in `cs-ai-lab-infra` as
  `221bcfa` (`fix: pin Plane service images by digest`). It changes only
  `plane/compose.yaml` and is an ancestor of the current shared `main`.
  It has not been pushed or applied to T480.

## Boundaries

- Do not reset, clean, stash, overwrite, or delete a T480 checkout to force a
  green result. Identify and preserve all existing changes first.
- Do not replace an unavailable digest with a tag, widen network exposure,
  delete/recreate volumes, or alter Plane/n8n/PostgreSQL data.
- Do not deploy or activate A1, create BLS facts, change broker/MT5 surfaces,
  trade, commit, or push without their separate authorisations.

## Acceptance criteria

1. A redacted owner baseline identifies exact T480 checkout, Compose project,
   rendered images, image IDs, dirty paths, bindings, and health command.
2. Every rendered Plane image is an exact reviewed registry digest; no tag-only
   or `latest` reference remains. The digest is inspected, not just inserted as
   text.
3. Intentional T480 work is safely migrated to a clean, pushed/reviewed
   revision without weakening the health assertion.
4. An owner-authorised controlled rollout leaves Plane, n8n and PostgreSQL
   healthy with their data intact, and the shared health report passes.
5. Redacted `performance_diagnostics`, storage, `lab_health`, and
   `penpot_resource_report` samples are collected at start, representative
   load, and end of one normal workday. A1 limits are chosen from the observed
   minimum headroom.
6. Only then may the existing A1 package/inspect/deploy plan resume. Deploy
   still needs explicit authority and a real retained BLS observation.

## Plan of work

### 1. Baseline and source resolution

Using existing bounded shared adapters, capture the four governed reports and
the health result. Identify the running Plane Compose project through labels,
rendered configuration, and service inspection. Record paths, revision, dirty
paths, image references/IDs, and bindings in protected shared evidence; redact
tokens and `.env` content.

If the source or purpose of a local change is unknown, stop. The shared owner
must decide how it is preserved or migrated; Forex must not guess.

### 2. Review an immutable-image migration

In `cs-ai-lab-infra`, resolve each selected Plane release and dependency to an
exact digest. Add an owner-maintained digest map or direct `@sha256` references
that makes the Plane project's rendered image list digest-only. Record the
current rendered list and configuration for rollback. Validate Compose rendering
and focused health tests locally.

This is shared-infrastructure work. It requires the platform owner's explicit
approval before any modification, commit, push, or T480 application.

### 3. Reconcile checkout and roll out safely

The owner migrates intentional machine-local values to ignored local config and
retains a recoverable patch for uncommitted work. Bring T480 to the reviewed
upstream revision via the normal owner workflow, never destructive reset.

After approving the exact rendered diff and rollback record, apply only the
Plane Compose change. Compare services, bindings, volumes, health and image IDs
before/after. Run read-only Plane, n8n and PostgreSQL availability checks. Any
unhealthy service or unavailable data triggers rollback to the recorded prior
configuration/images; never remove volumes to repair startup.

### 4. Health revalidation and capacity decision

Re-run shared health. Its revision and immutable-image checks must pass along
with existing-service checks. Collect the defined three workday samples, retain
raw diagnostics in protected shared evidence, and record a redacted summary in
the Forex A1 work record. If the observed minimum headroom cannot support A1,
keep A1 blocked; adding capacity or choosing another host is a separate owner
decision.

### 5. Controlled A1 handoff

When the gate passes, update `docs/plans/a1-execution-work.json` with evidence
references, decision and chosen CPU/memory/PID limits. Run existing A1
`package` then `inspect`. The private deployment and manual n8n run remain
separately authorised, and A1 still cannot claim an outcome without retained
publisher bytes, receipt verification, PostgreSQL projection, and a report.

## Verification

In the exact shared project and T480 deployment context, retain results
equivalent to:

    git status --porcelain --untracked-files=normal
    git fetch origin
    test "$(git rev-parse HEAD)" = "$(git rev-parse origin/main)"
    docker compose config --images
    docker compose ps
    ./scripts/health-check.sh

The Plane invocation may differ from the root project; identifying that exact
context is mandatory. Verification must prove each rendered image contains
`@sha256:` and resolves to the reviewed image.

## Progress

- [x] (2026-09-15) Operator paused all Plane/shared-platform remediation.
  No push, T480 rollout, A1 deployment, workflow activation, publisher
  collection, broker action, or trading action followed the pause.
- [x] Captured A1-blocking health and capacity observations.
- [x] Identified both health failures and tag-based Plane image declarations.
- [x] (2026-09-14T21:38Z) Established exact T480 Plane Compose ownership:
  root `compose.yaml` includes the untracked `plane/compose.yaml`; the
  checkout also has a modified root Compose file. Existing services remain
  healthy, so no cleanup or rollout was attempted.
- [x] (2026-09-15T09:41+12:00) Prepared local digest pins in the tracked
  shared Plane Compose definition and verified its rendered image list is
  digest-only. This is preparation, not a T480 rollout or owner review.
- [x] (2026-09-15T09:42+12:00) Committed the shared immutable-image migration
  as `cs-ai-lab-infra` revision `221bcfa`; scope is only `plane/compose.yaml`.
- [ ] Push/review the shared revision, retaining the current T480 deployment
  as rollback context, before any controlled rollout.
- [ ] Owner-authorised checkout reconciliation and controlled rollout.
- [ ] Pass health and collect one normal-workday evidence set.
- [ ] Record A1 limits and resume the existing A1 plan.

## Recovery

This plan fails closed. Missing digest, ambiguous checkout, rollout failure,
health failure, or inadequate capacity leaves A1 blocked and preserves existing
services. Rollback restores recorded configuration/images only; it does not
erase Plane history, PostgreSQL data, n8n workflows, raw evidence, or local
changes. This prerequisite cannot close M29 or grant broker authority.
