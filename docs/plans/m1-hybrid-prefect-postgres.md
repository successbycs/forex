# Deliver the hybrid M1 workflow in bounded waves

This ExecPlan follows `PLANS.md`. Chris approved Wave 1 only on 2026-09-16.
Waves 2–5 remain unauthorised for implementation.
Keep Progress, Surprises & Discoveries, Decision Log, and Outcomes current.

## Purpose / Big Picture


Make the EUR/USD Demo platform explainable from captured inputs through each
trade/no-trade decision to broker-reconciled outcomes. PostgreSQL should show
what was captured, what is missing, why a decision occurred, and what happened
afterward. Prefect should coordinate data pipelines; n8n should handle bounded
external integrations. Neither should replace the protected trading runtime.

The smallest useful first delivery is a measured capture baseline and one
reliable ingestion pipeline, not a migration of every existing job. The final
delivery is a candle-keyed M1 workflow with qualified event-risk handling,
independent position protection, and a joined outcome report.

## Authority and non-goals


This document authorises nothing beyond planning. Do not install services,
change schedules, migrate databases, change runtime rules, deploy, commit, or
place orders while it is under review. M30 remains the active formal milestone;
its bounded Demo proof is governed by `docs/plans/m30-controlled-demo-execution.md`.
Before implementation, map the approved waves to an explicitly authorised
milestone contract; do not silently enlarge M30 or assume M31 covers them.

The waves below are delivery packages, not new formal milestones. Preserve
M29's retained evidence and M30's separate proof. A changed runtime needs only
the affected checks and proof, not an arbitrary repeat of unrelated work or
another fixed 14/24-hour soak. Formal review gates still apply.

## Formal milestone dependency map


The waves depend on existing formal milestones as follows. This is the missing
implementation sequence; it prevents a delivery wave from being mistaken for
an already-authorised registry milestone.

| Formal milestone or contract | Current state | What must happen | Delivery work it unlocks |
| --- | --- | --- | --- |
| M20–M28 | Proven or approved historical exception | Do not reimplement them. Reuse their existing retention, audit and safety surfaces only. | Existing foundation for every wave |
| M29 | Proven, with its retained-evidence policy | Keep its pinned listener/configuration/recovery surface valid. No repeat drill is required for documentation or a separate local reader. | M30 remains eligible |
| **M30** | **In progress** | Complete its existing one bounded Demo order, close and reconciliation proof. Do not add capture-envelope features to M30 by implication. | A new post-M30 capture milestone and M31 entry gate |
| **Capture package contract — new or explicitly amended** | **Not yet created** | Authorise the stable assessment envelope, operational refusals and read-only completeness report; declare its local/raw/DB proof surface and affected M30 evidence policy. | Envelope/completeness implementation before the orchestration pilot |
| **M31** | **Planned; depends on M30** | Its current contract is evaluation, not infrastructure delivery. After the capture and M1 workflow changes exist, explicitly amend M31 if its evaluation surface must include them. | Controlled baseline comparison of the final implemented M1 workflow |
| M32 | Planned; depends on M31 | Leave unchanged until M31 is proven. It is forward evaluation/live-readiness assessment, not a build milestone. | Later forward Demo evaluation only |

The proposed order is therefore:

    M30 proof
      → dedicated capture-package contract and envelope/completeness implementation
      → orchestration pilot (Wave 2)
      → M1 decision-contract implementation (Wave 3)
      → qualified context and reporting (Wave 4)
      → amend/use M31 for controlled evaluation of the resulting workflow (Wave 5)
      → M32 forward evaluation

The registry has no current milestone that explicitly delivers Waves 2–4. A
dedicated capture-package milestone is needed after M30; later decision/context
work needs either its own contract or an explicit amendment that names its
runtime, data-contract and proof impact. Do not use M31 merely because it is
next in numeric order. See
`docs/reviews/m1-capture-scope-reconciliation.md` for the capture-package
choice.

Excluded: Live trading, new strategies, larger risk limits, dynamic sizing,
mandatory higher-timeframe confirmation, M15 execution, Kafka, Kubernetes,
high-availability clusters, and a new custom Python scheduling/retry engine.
Prefect flow definitions still use Python; the benefit is replacing custom
orchestration machinery, not eliminating application Python.

## Progress


- [x] (2026-09-16) Drafted architecture boundaries, waves, dependencies and acceptance criteria for review.
- [x] (2026-09-16) Added the locally scoped `data-pipeline-orchestration` skill at Chris's request; this does not authorise wave execution.
- [x] (2026-09-16) Chris approved the read-only Wave 1 goal only; no formal milestone state changed.
- [x] (2026-09-16) Completed the read-only capture baseline and minimal data contract in `docs/reviews/m1-capture-baseline.md` and `docs/workflows/m1-data-contract.md`.
- [x] (2026-09-16) Reconciled the next capture package against M30/M31 and recorded that runtime/schema implementation needs a new or amended formal contract in `docs/reviews/m1-capture-scope-reconciliation.md`.
- [ ] Wave 2: prove one Prefect/n8n ingestion pipeline and durable projection.
- [ ] Wave 3: implement candle identity, durable refusals and final entry checks.
- [ ] Wave 4: connect qualified calendar context and complete shadow/report lineage.
- [ ] Wave 5: validate the integrated workflow and hand over operating instructions.

## Context and Orientation


`t480/m20_demo_listener_service.py` currently polls on a roughly five-second
cadence and reacts to quote changes. This is not one decision per M1 candle.
`t480/m20_demo_trading_session.py` contains `_strategy_assessments`,
`_market_selection`, `_strategy_trade_plan`, `_project_cost_coverage`,
`_assessment`, and `capture`. It already validates closed M1 data, selects at
most one owner, persists proposals, reserves execution, and protects positions.
Preserve existing minimum-lot sizing, caps, break-even and exit rules.

`t480/m20_postgres_audit_bridge.py` owns fixed application persistence actions.
`src/forex/m20_assessment_spool.py`, `m20_spool_drain.py`, `m20_spool_page.py`,
`event_capture_store.py`, and `event_capture_recovery.py` provide reusable
capture/recovery pieces. A spool is retained local data awaiting database
delivery; it is not permission to place an unrecorded order.

`n8n/forex-bls-calendar-retention.json` and
`src/forex/bls_n8n_service.py` already define a bounded source-retention path.
`src/forex/bls_n8n_projection.py` and
`scripts/project_n8n_bls_retained_calendar_facts.py` support validated projection
into PostgreSQL. Prefer this BLS path for the first orchestration pilot, subject
to Wave 1 verifying that its actual deployment and access make it the smallest
useful choice. BLS alone is not complete EUR/USD economic-calendar coverage.

`src/forex/m1_event_risk_gate.py` has an evaluator, but the trading runner's
enabled calendar path currently refuses as unavailable; merely turning on a
flag does not integrate it. M5/H1 are shadow observations, not entry authority.
`src/forex/m20_replay_report.py` and `m20_replay_batch.py` are starting points
for joined reports, not grounds for introducing another reporting platform.

These are source-review findings, not measurements of today's database or
deployment. The claim that capture is poor must be quantified in Wave 1.

## Proposed architecture


| Component | Responsibility | Boundary |
| --- | --- | --- |
| Prefect | Pipeline schedules, dependencies, bounded data retries, backfills, completion and freshness checks | No broker operations; workflow success is not financial truth |
| n8n | Allowlisted external fetches/webhooks and notifications | No strategy, risk, broker credentials, or duplicate schedule for a Prefect-owned pipeline |
| PostgreSQL | Canonical validated facts, decision identity, reservations, lifecycle and joins | Not the only copy of raw evidence; separate application data from orchestration metadata |
| Immutable evidence | Original bytes, acquisition receipts, hashes and raw broker responses | Never rewrite captured history to make a check pass |
| Forex Python | Validation, deterministic trading rules, persistence contracts and reconciliation | Reuse services; do not build a general scheduler |
| Existing listener/monitor | Fresh broker inputs, protected autonomous Demo execution and independent position management | Must continue protection without Prefect or n8n |
| cs-ai-lab-infra | Shared service hosting, transport, networking, credentials and database operations | Forex owns its schemas, versioned workflows and evidence |

Data path: Prefect run → bounded n8n fetch → raw retention receipt → Forex
validation → PostgreSQL projection → completeness check → optional notification.
Trading consumes validated, point-in-time data locally; it does not await an
n8n request for each candle. A required context outage prevents new entries,
but must not stop protective exits.

## Plan of Work


### Wave 1 — Measure and define capture


Inventory actual databases, source collectors, schedules, spool/drain paths,
retention locations and shared service versions read-only. Report missing
access explicitly. Select a bounded existing UTC interval, documenting market
closures, listener uptime and source publication cadence. Compare expected
versus observed candles, decisions, refusals, attempts and reconciled outcomes.
Do not count market-closed minutes as missing candles or equate polling counts
with decisions. Measure write errors, backlog, lag, duplicates and broken joins.

Create `docs/reviews/m1-capture-baseline.md`. Define the required identities and
availability timestamps in `docs/workflows/m1-data-contract.md`, extending
existing schema contracts rather than replacing them. Include source event
time, actual received time, available time, source hash/reference, decision
key, proposal/attempt IDs, strategy/configuration versions and broker identities.

Owned paths: those documents, this plan, and minimal read-only report tooling
under `scripts/` with focused tests. Acceptance: a reproducible report separates
observed gaps, expected absences, duplicates and unknowns, names each writer,
and identifies the smallest useful repair. Unknown is never reported as zero.
Freeze source-specific freshness thresholds before evaluating the pilot; do
not invent one global threshold or tune it after seeing failures.

### Wave 2 — Prove one orchestration and persistence slice


Depends on Wave 1. Inspect shared hosting before selecting a Prefect deployment;
record endpoint, pinned compatible versions, worker location, authentication
and ownership without secrets. Any needed shared-platform change is a separate
owned package in `cs-ai-lab-infra`, not an implicit deployment permission here.

Add `src/forex/orchestration/calendar_ingestion.py` with one Prefect flow around
the existing BLS retention/projection services. Add a deployment/runbook under
`deploy/prefect/` and focused `tests/test_calendar_ingestion_flow.py`.
Use an authenticated bounded HTTP contract to n8n: do not assume its container
mounts this checkout or contains Python. Reuse its existing retention envelope.

Prefect owns the pipeline schedule and retry budget. n8n executes one bounded
fetch per request; no nested automatic whole-pipeline retries. Carry a common
run ID plus a stable source/period/request key. Return retained receipt ID,
raw digest and explicit terminal result; an HTTP acknowledgement alone does
not mean collection succeeded. Duplicate requests reuse the same logical
receipt or report a separately versioned source revision. Validation failures
are terminal until corrected; transient transport/database failures may use
bounded retries of safe data steps only. Keep notifications off the critical
completion path and record their failures separately.

Reuse existing database tables where adequate; add only constraints/columns
needed for provenance and idempotency (repeating work has no duplicate logical
effect). Document migrations, backup and rollback before applying them. Switch
off the old schedule only during an authorised cutover, with one schedule
owner and a reversible switch. Other working pipelines remain untouched.

Acceptance: one actual source fetch has raw bytes, receipt and queryable rows
with matching identities. Repeat delivery, concurrent duplicate requests,
restart after retention, timeout after commit, and temporary database failure
produce no duplicate canonical facts. Invalid payloads remain visible but do
not become valid facts. Inject failures in an isolated environment, not the
running trading database. The operator can follow a run to its retained input
and database output. Stop expanding Prefect if this slice adds more operational
burden than it removes; report the findings before migrating another pipeline.

### Wave 3 — Make M1 decisions candle-keyed and durable


Depends on Wave 1's identity contract and Wave 2's proven persistence pattern.
Edit the listener, trading session and fixed PostgreSQL bridge, plus focused
tests. Introduce a database-enforced decision identity scoped by Demo account,
symbol, timeframe and candle close. Record configuration/strategy versions as
attributes; changing them must not bypass the same-candle execution guard.
Replay/research identities are separate and never executable.

Each eligible closed candle receives one terminal BUY, SELL or NO_TRADE
decision; later quote polls cannot open another decision for that candle.
If data cannot establish a valid candle snapshot, retain a distinct operational
refusal with available provenance, not a fabricated proposal. Record missed
intervals; never backfill executable orders for old candles. Zero actionable
owners means NO_TRADE; an entry requires exactly one owner. Persist the
proposal and execution reservation before contacting MT5.

Immediately before submission, use the newly read quote for freshness, spread,
price drift and cost checks. Refuse a proposal that no longer satisfies its
bound execution terms rather than silently altering its approved prices or
risk. Specify the drift tolerance from existing governed limits, or propose
an explicit tested contract amendment if no limit exists.

Acceptance: repeated ticks, two competing workers and a restart for the same
candle yield one terminal decision and at most one broker submission. A stale
or materially changed final quote refuses entry. A lost broker response enters
unknown/reconciliation state with no resubmission. Database loss blocks new
unjournaled entry; existing protective monitoring continues and retains its
outcomes for later reconciliation. Existing sizing, stops, targets and caps
remain unchanged.

### Wave 4 — Qualified context and useful outcome reporting


Depends on Waves 2–3. Wire the existing event-risk evaluator to a validated
point-in-time context artifact. Define qualified sources, USD/EUR coverage,
event identity, impact mapping, source freshness and blackout policy explicitly
before enabling a blocking gate. A BLS-only feed must not be labelled complete.
In required-context mode, stale/missing/ambiguous required context refuses new
entries; annotation mode remains explicitly non-blocking. Safety policy does
not require a claim of improved profitability, but exact blackout parameters
must be disclosed and tested. Never enable the current unavailable stub.

Complete M5/H1 provenance with actual receipt/availability times and retained
raw references, including H1. Keep shadow collection off the latency-critical
entry path; missing shadow context must not veto M1 entries. No information
received after the decision may be portrayed as available to that decision.
Do not invent a regime classifier: current precedence is strategy selection,
and a spread check is not an independent volatility detector.

Extend the existing replay/report modules to join decisions, vetoes, selected
owner, execution attempts, broker outcomes, costs and source provenance.
Report unresolved joins and missing costs explicitly rather than estimating
them as observed facts. Any strategy/filter performance comparison uses a
predeclared chronological holdout and realistic costs; no automatic promotion.

Owned paths: existing event/context/report modules, runner integration, relevant
tests and workflow documents. Acceptance: event-window boundaries and missing
context produce correct reasons; future data cannot affect a past decision;
missing shadow data has no entry authority; each reported trade joins by exact
broker identity. M15 stays paused.

### Wave 5 — Integrate and hand over


Depends on Waves 1–4. Correct the hybrid diagram and current-workflow document
to distinguish implemented from proposed behavior, exactly-one-owner entry,
pre-submit journaling, submission rejection, unknown responses and recovery.
Update `docs/architecture.md` and supporting links only to reflect accepted
implementation. Add a short operational runbook covering run inspection,
capture lag, replay, schedule ownership, failure recovery and rollback.

Use qa-verification, an independent read-only review and release-readiness
before declaring implementation/deployment complete. Bind results to actual
revision/configuration and retain raw observations separately. Demonstrate the
changed surfaces with a bounded real integration run under authorised Demo
conditions, including a reconciled lifecycle where the approved proof requires
one. Never force a trade to satisfy the diagram. Reuse valid unaffected proof;
no arbitrary endurance test. Formal closeout remains a separate contract action.

Acceptance: the operator can trace a decision from raw inputs to database rows,
reason codes and reconciled outcome; inspect a failed ingestion and safe replay;
and see that orchestration failure does not disable position protection.

## Concrete Steps and Validation


After approval, create a step-level execution-work JSON for the approved scope,
record dependencies, owned paths and actual independent review results, and
use `scripts/check_execution_continuation.py --work-plan <that-file>`.
No execution-work record is activated by this draft.

Run commands from `/home/chris/projects/forex`, in the repository environment.
These existing focused suites are starting points, not claims of current passes:

    python3 -m pytest -q tests/test_bls_n8n_retention.py tests/test_bls_n8n_projection.py tests/test_m20_spool_drain.py
    python3 -m pytest -q tests/milestones/test_m20_listener_service.py tests/milestones/test_m20_demo_trading.py
    python3 -m pytest -q tests/test_m1_event_risk_gate.py tests/test_m20_multi_timeframe_context.py tests/test_m20_replay_report.py
    python3 scripts/forex_milestones.py validate

Wave 2 adds `python3 -m pytest -q tests/test_calendar_ingestion_flow.py`.
Update this plan with exact read-only observation/report commands and actual
outputs when Wave 1 discovers deployed interfaces. Do not invent connection
details. Tests must cover the failure cases specified in each wave; inspect
database rows and raw receipts as well as exit status. Synthetic tests do not
substitute for the approved real-system proof surface.

## Idempotence and Recovery


Retain immutable original evidence. Replay validation/projection from retained
receipts using database uniqueness, not only Prefect caching. Source revisions
are new versioned observations. Use additive migrations and isolated failure
tests. Roll back schedules/configuration without deleting captured facts.
Never route broker order retries through Prefect or n8n. Ambiguous submission
requires reconciliation; a fresh process or configuration cannot release the
execution guard. Preserve protective exits during data/orchestration outages.

## Surprises & Discoveries


Source review found polling rather than candle uniqueness, an unavailable
enabled calendar path, and final quote refresh whose output is not fully used
for the existing proposal. These need focused regression tests. Actual database
completeness and Prefect hosting remain unmeasured. Existing n8n workflows and
capture/replay modules make a wholesale rewrite unnecessary.

## Decision Log


- Decision: plan first, no implementation. Rationale: Chris explicitly requested review before execution. Date/author: 2026-09-16 / Chris.
- Decision: Prefect owns migrated data pipelines, n8n bounded integrations, runtime owns trades. Rationale: clear retry authority without putting broker protection behind an orchestrator. Date/author: 2026-09-16 / proposed architecture.
- Decision: audit then one pilot before migration. Rationale: measure the reported capture problem and constrain MVP complexity. Date/author: 2026-09-16 / proposed delivery sequence.
- Decision: preserve existing proof except changed surfaces. Rationale: no repeat drills without a material reason. Date/author: 2026-09-16 / Chris direction.
- Decision: make the stable assessment envelope the first repair candidate. Rationale: it addresses the measured compatibility gap and enables later completeness measurement without installing orchestration first. Date/author: 2026-09-16 / Wave 1 audit.

## Outcomes & Retrospective


Planning only. No infrastructure, trading behavior, database schema, schedules,
formal milestone state or deployment changed. Implementation checks and actual
capture measurements remain pending. Review should settle wave scope before
execution; hosting details are discoverable Wave 1 work, not guessed here.

Wave 1 outcome (2026-09-16): local evidence demonstrated a 16-record,
sequence-contiguous, approximately 104-second listener sample—not continuous
coverage—and 33 explicit event-annotation refusals out of 38 inputs. Current
PostgreSQL row counts, lag, duplicates, backlog and write errors were not
locally observable and remain `UNKNOWN`. The next smallest repair candidate is
a stable assessment envelope, not an orchestration installation. See
`docs/reviews/m1-capture-baseline.md` and `docs/workflows/m1-data-contract.md`.

Capture-package scope outcome (2026-09-16): M30's bounded execution proof does
not include a source-contract/envelope change, while M31 depends on M30 proof
and currently states evaluation rather than infrastructure delivery. The pure
completeness-report interface is documented in
`docs/workflows/m1-postgres-completeness-report.md`; implementation awaits an
explicit formal scope choice.

Draft checks (2026-09-16): both planning files exist and `git diff --check`
reported no tracked whitespace errors. No runtime tests were needed or run for
this planning-only change. The mandated default continuation check exited 2:
its existing A1 metadata resolves the Markdown plan to the repository directory
(`Is a directory`). That unrelated metadata was not changed or used to activate
this draft. No independent review of this draft has yet been recorded.

## Artifacts, Interfaces and Dependencies


Planning-owned files are this document and
`docs/research/m1-orchestration-evidence-brief.md`. Existing uncommitted workflow
and review documents are preserved. Runtime file ownership is proposed per
wave, not permission to edit them now.

The pilot interface carries `run_id`, a stable `request_key`, fixed source ID,
requested UTC period and contract version; its result carries status, receipt
reference, source digest and error reason. It accepts no arbitrary URLs, SQL,
shell commands or broker operations. Reuse existing envelope field names where
equivalent and document any additive version change. Secrets stay outside Git.
Shared hosting and library compatibility are verified before deployment.

Supporting evidence: [orchestration evidence brief](../research/m1-orchestration-evidence-brief.md).
Agent guidance: `.codex/skills/data-pipeline-orchestration/SKILL.md` covers
pipeline ownership, capture, safe retries and verification. The local `.codex/`
directory is Git-ignored; this skill is not yet a versioned delivery artifact.
Design context: [hybrid diagram](../workflows/m1-hybrid-decision-flow.md) and
[end-state review](../reviews/m1-decision-workflow-end-state.md). Their simplified
flows are not substitutes for the failure and persistence contracts above.

Revision note (2026-09-16): initial review-only plan packages the hybrid workflow,
PostgreSQL capture priority and Prefect/n8n split into five bounded waves.
