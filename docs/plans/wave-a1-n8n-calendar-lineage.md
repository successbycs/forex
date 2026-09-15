# Wave A1 — n8n calendar collection and PostgreSQL lineage projection

This ExecPlan is a living document governed by `PLANS.md`, `AGENTS.md`,
`project_state.json`, the M29 contract in `milestone_registry.json`, and
`docs/evidence_and_milestones.md`. Those sources take precedence.

## Purpose / Big Picture

Wave A1 makes approved BLS calendar facts retrievable from
PostgreSQL without losing the original publisher bytes and receipt that explain
each fact. n8n may schedule and display the fixed collection flow, but it is
not the source of truth, broker authority, or proof authority.
FOMC/ECB are the subsequent A2 task, not silently included in A1 closeout.
The existing GDELT collection/import workflows must remain operational.

## Progress

- [x] (2026-09-14T00:45:00Z) Inspected the A1 task, the existing BLS retention
  and projection commands, the n8n GDELT workflow, and the current database
  report.
- [x] (2026-09-14T00:45:00Z) Established that the existing n8n GDELT workflow
  cannot be reused for A1: it has no immutable calendar-payload/receipt store.
- [x] (2026-09-14T00:45:00Z) Ran 44 focused BLS/n8n tests and the read-only
  A1 report; all tests passed and the report truthfully returned
  `NO_STORED_BLS_FACTS`.
- [x] (2026-09-14T00:50:00Z) Rejected a premature inactive workflow draft: it
  handed off HTML bytes without the complete verified collection envelope
  required to create a truthful transport receipt.
- [x] (2026-09-14T01:25:06Z) Built a replacement inactive manual workflow;
  seven tests execute its JavaScript, including exact binary preservation.
  Independent reviewer `/root/review_loop` accepted its implementation and
  deployment boundaries; byte-test strengthening was applied afterwards.
- [x] (2026-09-14T01:25:06Z) Inspected live T480 topology and prepared
  `deploy/bls-n8n/README.md` and its application Dockerfile. n8n is healthy;
  loopback retention port 8091 refuses connections. Shared infrastructure's
  physical-resource hold remains a separate deployment gate.
- [x] (2026-09-14) Review and finish the existing n8n envelope and retention implementation,
  including validation before writes, repeat-request behavior, and provenance
  limits. Existing local tests do not authenticate a publisher response.
- [x] (2026-09-14) Implement and test the HTTP boundary and complete n8n request envelope
  together, including actual status/timing metadata, request limits, error
  handling, and the reachable address in the deployed container topology.
- [x] (2026-09-14) Integrate retained n8n observations with the canonical PostgreSQL
  projection and independently review the implementation. Verify that its
  receipt format is accepted rather than assuming shared-transport equivalence.
- [x] (2026-09-14) Inspect the existing T480 n8n connection and deployment mechanism and
  prepare the concrete workflow/service configuration, migration and rollback.
  Resolve buildable gaps within this plan before escalating missing authority.
- [ ] Configure and activate that workflow on T480 with machine-local n8n
  credentials after the shared-platform capacity gate is cleared.
- [ ] Observe retained publisher material, project verified facts, and confirm
  the read-only A1 report returns lineaged records instead of
  `NO_STORED_BLS_FACTS`.
- [x] (2026-09-14T01:29:28Z) Independent implementation review accepted after
  repair; final parent regression passed 74 focused tests. Governance validation
  and whitespace checks passed. Full-suite regression retains one unrelated
  W2 policy-draft mismatch in unchanged files; it is not reported green.
- [x] (2026-09-14T02:02:57Z) Resumed local deployment preparation: rebuilt
  `forex-bls-retention:a1-reviewed` from the reviewed
  `python@sha256:528257d48c1da0dcecc2e725d1ae34498d60c965f1241e39cd6a85a8859bdf84`
  base after making that existing pin the Dockerfile default (removing the
  ARG/FROM warning). Image ID
  `sha256:dbe16b5c224a6406a2ab79f9c14fd14fa3ef931b6cad9a40cb8917ac0f80c6fc`
  is 47,982,429 bytes; an exported uncompressed root filesystem tar is
  132,645,376 bytes (127,338,758 bytes file payload). An isolated temporary
  private environment/store returned `200 {"execution_authority":false,
  "status":"OK"}` at `/healthz`, with no published ports, network `none`, a
  read-only root filesystem, `cap-drop ALL`, and `no-new-privileges`. The 28
  focused workflow/retention/projection/service/CLI tests and Docker
  configuration consistency check passed. The private temporary test artifacts
  were removed.
- [x] (2026-09-14T02:01:08Z) Evaluated capacity options only through the
  governed read-only T480 status operations. Windows C: now reports 11.3 GiB
  free of 235.6 GiB while Docker is healthy (29.7.2 / Compose 5.4.0). The small
  image measurement does not provide the required representative resource
  evidence, so deploying now remains rejected. The concrete remaining paths
  are shared-platform capacity reclamation/allocation followed by fresh
  physical/resource observations, or a specifically authorised alternative
  host with its own reviewed private n8n/store/rollback topology. Neither path
  was assumed or changed; the T480 capacity-clearance gate remains blocked.
- [x] (2026-09-14T02:04:50Z) Independent deployment review rechecked the
  container package and physical capacity. It confirmed the 47,982,429-byte
  image and 127,338,758-byte rootfs file payload, and found that CPU, memory
  and PID limits must be set from representative platform measurements before
  runtime. The fresh C: measurement was 12.3 GiB free of 235.6 GiB.
- [x] (2026-09-14T20:56:50Z) Refreshed governed shared-platform capacity and
  health observations. Windows C: had 21.67 GiB free (9.2%), but the required
  normal-workday evidence remains incomplete and the shared lab health gate
  failed because its checkout was dirty and configured images were not pinned
  to immutable digests. Existing Docker, PostgreSQL, n8n and Ollama remained
  healthy. A1 deployment remains correctly blocked.
- [x] (2026-09-14) Added and independently accepted a read-only continuation
  record/checker and one-pass Codex Stop hook. It distinguishes a blocked
  deployment step from remaining preparation and refuses malformed metadata.
  It currently returns `BLOCKED` solely for T480 capacity clearance.
- [x] (2026-09-15T09:45+12:00) Re-ran the focused A1 deployment, workflow,
  service, retention and projection suite: 42 passed. The deterministic A1
  package still has archive SHA-256
  `c7540e541b503ef58b0c8e04ebc91fcc5bca49ffffe00dafa1e87d7a56bc6fc8`
  and manifest SHA-256
  `fb60ecd125669b14136ac7e12ba0c042de4045a1e0ba41120ac3190d71f74cc8`.
  The fixed T480 `inspect` operation truthfully returned `exists:false` for
  the retention service. No staging, credential/workflow creation, service
  deployment, n8n activation, or publisher request was attempted because the
  prerequisite capacity-clearance item remains blocked.
- [x] (2026-09-15T10:00+12:00) Deployed the private T480
  `forex-bls-retention` sidecar at 0.20 CPU, 256 MiB and 64 PIDs after an
  initial package-closure repair. It is `running`, has no published ports,
  shares only the existing n8n network namespace, and its in-namespace
  `/healthz` returned `{"execution_authority":false,"status":"OK"}`.
  The fixed manual A1 workflow was created as
  `Forex A1 BLS immutable capture` (`N53yr4T8kKyW3hoc`) and executed once.
  BLS returned an explicit automated-access-denied HTML page for the official
  September schedule URL; the workflow rejected it before retention. No raw
  bytes, receipt, PostgreSQL fact, synthetic record, broker action, or trade
  was created. The current operational blocker is approved publisher access,
  not the service runtime.

## Surprises & Discoveries

- Observation: `n8n/forex-gdelt-daily.json` is a fixed M11 GDELT workflow, not
  a calendar workflow. Its PostgreSQL node stages provenance metadata but does
  not retain immutable BLS/FOMC/ECB source bytes and receipts.
  Evidence: `scripts/n8n_forex_adapter.py` binds only the M11 workflow and
  `docs/data-implementation.md` requires raw evidence before projection.
- Observation: A1's read-only report currently returns zero facts.
  Evidence: `python3 scripts/report_bls_calendar_facts.py` returned
  `NO_STORED_BLS_FACTS` on 2026-09-14.
- Observation: n8n 1.123.76 requires the nested
  `options.redirect.redirect.followRedirects=false` option. Full file responses
  provide status and headers alongside binary data. The replacement workflow
  uses the installed implementation's shape, not the rejected draft's shape.
- Observation: an exact retry previously generated a new receipt timestamp,
  conflicting with its own immutable receipt. Receipt generation is now
  deterministic and validates the observation before publishing bytes.
- Observation: independent review reproduced a millisecond timestamp mismatch:
  n8n `.123Z` and normalized journal `.123000Z` are equivalent times but unequal
  strings. Terra repaired the receipt comparison to bind the original acquisition;
  the existing primary verifier checks journal-time equivalence. The reviewer
  accepted the repair after rerunning the regression.
- Observation: the active GDELT hourly download workflow's latest inspected
  execution (572) succeeded at 2026-09-14T01:05:11.934Z. Download, context-import
  and historical seed workflows were active. This establishes workflow status,
  not newly verified GDELT database completeness. None was edited or stopped.
- Observation: shared infrastructure's `docs/project-foundation.md` records a
  new-service hold (physical C: headroom, representative resource sampling).
  The existing BLS scheduler is on the orchestrator, not a T480 retention API.

## Decision Log

- Decision: do not activate, copy, or adapt the GDELT workflow for calendar
  ingestion.
  Rationale: doing so would bypass the required immutable raw/receipt lineage.
  Date/Author: 2026-09-14 / Codex.
- Decision: supersede the earlier blanket `BLOCKED_EXTERNAL_OBSERVATION`
  state with `IN_PROGRESS` while building and reviewing missing components.
  Rationale: zero stored facts prevents operational acceptance, not authorised
  implementation. Restore a precise blocked state only after actionable local
  work is finished and reviewed.
  Date/Author: 2026-09-14 / Codex.
- Decision: remove the premature BLS n8n workflow draft rather than represent
  its byte-only handoff as an immutable-retention contract.
  Rationale: the existing store requires a complete observation envelope; the
  draft could not supply it without inventing provenance fields.
  Date/Author: 2026-09-14 / Astra review.
- Decision: after local implementation/review, restore A1's external-observation
  state with precise capacity/capture conditions, not a missing-code
  blocker. Preserve the separate A2 dependency and parked Plane task.
  Rationale: remaining deployment has explicit gates; local work and tests cannot
  clear them. Reviewed file digests are retained in
  `docs/plans/wave-a1-implementation-review.md`.
  Date/Author: 2026-09-14 / Codex.

## Outcomes & Retrospective

The new workflow, authenticated retention service and n8n-specific projection
boundary are implemented and independently accepted after repair. The reviewer
ran 33 focused tests successfully; the broader regression run is recorded below.
A1 is not operationally complete: nothing was deployed, no new live
calendar capture was made, and the repeated database report contains zero facts.
Tests are implementation evidence only; M29 and broker authority are unchanged.

Implementation roles: Terra (`/root/a1_implementation`) implemented the Python
boundary and repaired the timestamp defect on its first review repair attempt;
the primary agent implemented the workflow/deployment assets and reviewed
Terra's code; `/root/review_loop` independently reviewed both packages. No role
approved deployment or formal milestone closeout.

Stop-condition audit: the remaining A1 tasks require installing a new T480
service/configured workflow, obtaining a real n8n capture and projecting it.
Actual read-only checks reached n8n, found no retention service, and found zero
database facts. Local implementation, integration tests, deployment recipe and
independent review are complete. Reusing GDELT, fabricating facts, bypassing the
capacity gates, or relabeling existing shared-transport bytes
as n8n observations would not satisfy the plan. No such alternative was taken.
Fresh governed checks at 2026-09-14T02:04Z confirm the capacity gate is still
closed: Windows C: has 12.3 GiB free of 235.6 GiB (5.2%), down from the prior
16.9 GiB. Docker/n8n are healthy, but WSL's 894 GiB virtual free space cannot
be treated as physical disk capacity. Therefore activating a persistent
retention container now would violate the shared-platform rollout guidance.

## Context and Orientation

`scripts/bls_collect.py` performs one bounded BLS request through the fixed
T480 transport and retains its result. `scripts/persist_bls_retained_calendar_facts.py`
validates one explicit retained store, stages a hash-pinned JSON payload, and
uses fixed SQL to insert only canonical facts. `scripts/report_bls_calendar_facts.py`
is the read-only A1 outcome report. A receipt records the bounded transport
attempt; raw publisher bytes are kept separately from the PostgreSQL fact.

`n8n/forex-gdelt-daily.json` and `scripts/n8n_forex_adapter.py` are M11-only
examples. They must not be generalized into arbitrary shell, URL, credential,
or database interfaces.

## Plan of Work

Define a new fixed inactive calendar workflow that has only declared official
source endpoints, bounded timeout/no-retry behavior, and a handoff to the
existing immutable-retention boundary. It must not use n8n `executeCommand`, a
caller-provided URL, generic SQL, an event-gate mutation, or any MT5/order
operation. Its projector must invoke the existing hash-pinned canonical fact
shape, not build an ad-hoc row. Add tests that reject activation, arbitrary
endpoints, missing receipt/raw digest, and execution authority.

Before activation, run the complete test suite for the workflow contract,
retention, projection, and report. On T480, use only the existing local n8n
credential mechanism; do not place credentials in Git. After capacity clearance
and deployment under the existing execution authorization, capture a natural
collection, verify its raw material and
receipt, project the facts, then run the read-only report.
The first deployment is manual only: no new schedule may bypass the existing
BLS scheduler's claim/backoff rules. A separate authenticated handoff receipt
records configured workflow identity and client-claimed timing. It is explicitly
not a shared-transport receipt or independent publisher authentication.

## Concrete Steps

From `/home/chris/projects/forex`, first establish the existing baseline:

    PYTHONPATH=src python3 -m pytest -q tests/test_bls_collection.py tests/test_bls_calendar_projection_persistence.py tests/test_bls_calendar_fact_report.py tests/test_n8n_forex_adapter.py
    python3 scripts/report_bls_calendar_facts.py

Expect passing tests and `NO_STORED_BLS_FACTS`. That result is a blocker, not
a reason to insert synthetic data.

Verify the complete local implementation:

    python3 -m pytest -q tests/test_bls_n8n_workflow.py tests/test_bls_n8n_envelope.py tests/test_bls_n8n_retention.py tests/test_bls_n8n_service.py tests/test_bls_n8n_projection.py tests/test_validate_bls_n8n_handoff_cli.py tests/test_persist_bls_retained_calendar_facts_cli.py

Use `deploy/bls-n8n/README.md` for concrete deployment gates, network namespace,
private configuration, health check and rollback. After approved deployment
and a real manual capture, copy the dedicated store without altering it to an
explicit trusted path on the orchestrator. Verify/project read-only first:

    python3 scripts/project_n8n_bls_retained_calendar_facts.py --store <retained-store> --workflow-id <approved-workflow-id> --workflow-sha256 sha256:<approved-definition-digest>

Inspect facts and hashes and compare the configured workflow binding with the
retained approved export and actual execution observation. Only then invoke
the fixed writer and read-only report:

    python3 scripts/project_n8n_bls_retained_calendar_facts.py --store <retained-store> --workflow-id <approved-workflow-id> --workflow-sha256 sha256:<approved-definition-digest> --persist
    python3 scripts/report_bls_calendar_facts.py

The report must contain real lineaged BLS facts. Repeat projection to establish
idempotence. Neither synthetic fixture facts nor an empty report count as this
operational result. Do not use the generic retained-store command for n8n stores:
the n8n-specific command additionally verifies the handoff receipt chain.

## Validation and Acceptance

Repository acceptance requires tests for the fixed workflow contract and the
existing retention/projection/report boundaries. A1 operational acceptance
requires a real retained source payload and receipt, a successful fixed
projection with its hashes, and a read-only report containing those lineaged
facts. n8n execution history, tests, or documentation alone are insufficient.

## Idempotence and Recovery

Use unique capture identifiers. Retention must refuse overwrite; projection
must be idempotent on canonical fact hashes. If n8n is unavailable, keep the
workflow inactive and retain the blocker. Never repair or replace raw evidence.

## Artifacts and Notes

Current baseline: `NO_STORED_BLS_FACTS`; A1 has no execution authority and no
broker impact. M29 remains formally blocked and this plan cannot close it.

## Interfaces and Dependencies

The source allowlist is `config/event_sources.json`; BLS collection policy is
`config/bls_collection.json`; canonical persistence uses
`src/forex/bls_calendar_projection_persistence.py`; and PostgreSQL reporting
uses `src/forex/bls_calendar_fact_report.py`. New n8n assets must be fixed to
these interfaces and remain inactive by default.

Revision note — 2026-09-14: created after confirming that the existing M11
n8n workflow cannot satisfy A1's immutable calendar-evidence requirements.

Revision note — 2026-09-14: recorded the passing focused-test baseline and the
real zero-fact PostgreSQL observation.

Revision note — 2026-09-14: added the inactive BLS calendar workflow contract
and its safety test; 45 focused tests passed.

Revision note — 2026-09-14: Astra review removed that draft because its
byte-only handoff could not create the existing store's truthful receipt.

Operational review note: restored the missing implementation and integration
steps between the rejected draft and deployment. An unavailable final database
observation does not prevent this authorised implementation work. These steps
remain unchecked until executed and reviewed; earlier test results do not
establish their completion.

Revision note — 2026-09-14: executed the restored build steps, replaced the
byte-only draft with an observed-envelope workflow, reconciled A1 with the
canonical BLS-only task, and documented verified live topology and deployment
gates. New-service capacity clearance remains required; it cannot be
manufactured by a passing local test. Chris's existing execution authorization
remains in force; an agent-authored plan clause does not create a new approval
requirement.
