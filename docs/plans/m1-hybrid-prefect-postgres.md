# Deliver the hybrid M1 workflow in bounded waves

This ExecPlan follows `PLANS.md`. Chris approved the bounded M1 hybrid-delivery
packages under M30 on 2026-09-16. M30's Demo lifecycle is the final proof gate,
not a prerequisite for delivery work.
Keep Progress, Surprises & Discoveries, Decision Log, and Outcomes current.

## Purpose / Big Picture


Make the EUR/USD Demo platform explainable from captured inputs through one
terminal M1 decision per closed candle to broker-reconciled outcomes. The MVP
uses the existing listener, PostgreSQL audit path and read-only status surfaces.
It does not need a new orchestration or reporting platform.

The remaining MVP build is candle-keyed M1 decision integrity. The final
delivery is the existing M30 bounded Demo order, close and reconciliation proof
on that resulting version. For the Demo MVP, financing, rollover-calendar, and
UTC entry-hour qualification are explicitly deferred to later Live readiness;
they are not current entry vetoes. Existing Demo risk, cost, position,
protection, monitoring, and reconciliation gates remain in force.

## Authority and non-goals


M30 authorises the bounded delivery packages in this plan. Package D may
prepare, locally verify, and—under Chris's later explicit active-goal execution
instruction—stage and apply one additive decision-identity migration and
matching runtime key. Do not install or activate Prefect/n8n,
change schedules, make other database migrations, change strategy or risk
rules, deploy, commit, or place orders under this plan. M30's bounded
Demo proof remains governed by `docs/plans/m30-controlled-demo-execution.md`.
M31 is not an implementation authority.

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
| **M30** | **Implementation resumed; final proof pending** | Deliver the bounded hybrid M1 packages using existing persistence, then prove the resulting version through one Demo order, close and reconciliation. | Packages A–E below; M31 still waits for M30 proof |
| **M31** | **Planned; depends on M30** | Its current contract is evaluation, not infrastructure delivery. After the capture and M1 workflow changes exist, explicitly amend M31 if its evaluation surface must include them. | Controlled baseline comparison of the final implemented M1 workflow |
| M32 | Planned; depends on M31 | Leave unchanged until M31 is proven. It is forward evaluation/live-readiness assessment, not a build milestone. | Later forward Demo evaluation only |

The delivery and proof paths are deliberately separate:

    A retained-data reporting → B read-only persistence measurement → C measured capture repair
                                             └→ D candle/refusal + final-input handling
    A–D complete → M30 final Demo lifecycle proof → M31 evaluation → M32 forward evaluation

Prefect/n8n is an optional, separately justified branch. It never blocks
candle identity, decision records, protective monitoring, or outcome reporting.

Excluded: Live trading, new strategies, larger risk limits, dynamic sizing,
mandatory higher-timeframe confirmation, M15 execution, Kafka, Kubernetes,
high-availability clusters, and a new custom Python scheduling/retry engine.
Prefect flow definitions still use Python; the benefit is replacing custom
orchestration machinery, not eliminating application Python.

## Progress

<!-- forex-work-projection:start task=M1-PACKAGE-D schema=forex.execution-work-projection.v1 -->
<!-- forex-work-item id=scope state=DONE -->
- [x] scope — Bind Package D to the MVP one-decision-per-candle requirement (DONE)
<!-- forex-work-item id=identity state=DONE -->
- [x] identity — Implement deterministic closed-M1-candle identity at listener and session boundaries (DONE)
<!-- forex-work-item id=persistence state=DONE -->
- [x] persistence — Prepare additive PostgreSQL uniqueness constraint and idempotent bridge contract (DONE)
<!-- forex-work-item id=verification state=DONE -->
- [x] verification — Run focused duplicate, restart, refusal and safety regression checks (DONE)
<!-- forex-work-projection:end -->


- [x] (2026-09-16) Drafted architecture boundaries, waves, dependencies and acceptance criteria for review.
- [x] (2026-09-16) Added the locally scoped `data-pipeline-orchestration` skill at Chris's request; this does not authorise wave execution.
- [x] (2026-09-16) Completed the authorised retained-data envelope/report package.
- [x] (2026-09-16) Completed the read-only capture baseline and minimal data contract in `docs/reviews/m1-capture-baseline.md` and `docs/workflows/m1-data-contract.md`.
- [x] (2026-09-16) Reconciled the next capture package against M30/M31 and recorded its scope in `docs/reviews/m1-capture-scope-reconciliation.md`.
- [x] (2026-09-16) Chris approved M30's hybrid-delivery amendment: implementation may proceed without an old-version M30 trade; the final Demo proof and M31 dependency remain unchanged.
- [x] Package B: capture and qualify the available fixed read-only PostgreSQL summaries. They end on 2026-09-11 and do not cover the 2026-09-15 retained M1 interval; all projection facts for that interval remain `UNKNOWN`.
- [x] Package C: add a fixed, parameter-bound read-only PostgreSQL completeness summary. The retained interval contains 16 persisted `NO_TRADE` proposals and no attempts; all raw-to-projection identities join exactly.
- [x] Package D: implement and locally verify candle identity, durable refusal handling and no-resubmission on an already-persisted candle. On 2026-09-17, Chris's explicit active-goal instruction authorised the fixed hash-bound Demo PostgreSQL migration application; it was staged, applied, and read-only verified. The clean committed listener release was deployed and binding-verified.
- [ ] Package E: deferred after the MVP requirements reset; qualified context and broader reporting are not M30 implementation requirements.
- [ ] Package F: capture M30's bounded final-version Demo lifecycle proof.

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

### Optional pipeline branch — Prefect/n8n pilot


This branch does not block Packages B–E. Inspect shared hosting before selecting a Prefect deployment;
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

### Package D — Make M1 decisions candle-keyed and durable


Depends on the approved decision contract and existing PostgreSQL persistence;
it does not depend on the optional Prefect/n8n branch or a prior M30 trade.
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

#### Package D execution and controlled application sequence

1. Add one deterministic `decision_key`: `Demo server + EURUSD + M1 + closed
   candle UTC`. Add one additive unique database constraint for it.
2. Add focused tests: repeated poll/restart for one candle creates one terminal
   decision; malformed input safely refuses; an actionable proposal still
   cannot exceed the existing one-order protections.
3. Commit when Chris instructs, then apply the migration and deploy the
   matching listener/bridge together to Demo under an explicit deployment
   instruction.
4. Inspect one short retained M1 interval to confirm one terminal decision per
   closed candle. Do not force an order; M30 remains the later order/close/
   reconciliation proof.

Chris's later active-goal execution instruction authorised the fixed hash-bound
Demo PostgreSQL migration application in step 3. The listener release and the
M30 Demo order remain separately gated by a clean committed release and the
existing fixed autonomous preflight. There is no new service, scheduler,
workflow engine, migration framework, review ceremony, or Live capability in
Package D.

### Package E — Qualified context and useful outcome reporting


Depends on Package D. Wire the existing event-risk evaluator to a validated
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

### Package F — Integrate, prove and hand over


Depends on adopted Packages B–E. Correct the hybrid diagram and current-workflow document
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

The optional pipeline branch adds `python3 -m pytest -q tests/test_calendar_ingestion_flow.py`.
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


- Decision: separate delivery from proof. Rationale: an old-version Demo trade is not a technical prerequisite for bounded M1 correctness work; the final M30 proof demonstrates the resulting version. Date/author: 2026-09-16 / Chris and Astra review.
- Decision: Prefect owns migrated data pipelines, n8n bounded integrations, runtime owns trades. Rationale: clear retry authority without putting broker protection behind an orchestrator. Date/author: 2026-09-16 / proposed architecture.
- Decision: audit then one pilot before migration. Rationale: measure the reported capture problem and constrain MVP complexity. Date/author: 2026-09-16 / proposed delivery sequence.
- Decision: preserve existing proof except changed surfaces. Rationale: no repeat drills without a material reason. Date/author: 2026-09-16 / Chris direction.
- Decision: make the stable assessment envelope the first repair candidate. Rationale: it addresses the measured compatibility gap and enables later completeness measurement without installing orchestration first. Date/author: 2026-09-16 / Wave 1 audit.

## Outcomes & Retrospective


The completed retained-data package is implemented and tested. Remaining
delivery is independent of M30 proof but stays within the M30 hybrid-delivery
scope. No infrastructure, database schema, schedules, strategy/risk policy or
deployment changes are authorised by this plan.

Wave 1 outcome (2026-09-16): local evidence demonstrated a 16-record,
sequence-contiguous, approximately 104-second listener sample—not continuous
coverage—and 33 explicit event-annotation refusals out of 38 inputs. Current
PostgreSQL row counts, lag, duplicates, backlog and write errors were not
locally observable and remain `UNKNOWN`. The next smallest repair candidate is
a stable assessment envelope, not an orchestration installation. See
`docs/reviews/m1-capture-baseline.md` and `docs/workflows/m1-data-contract.md`.

Hybrid-delivery scope outcome (2026-09-16): M30 now authorises the bounded M1
delivery packages; its final Demo lifecycle proof remains required and M31
remains evaluation-only. The pure completeness-report interface is implemented
in `src/forex/m1_postgres_completeness.py`; it awaits a real retained summary,
not a prior trade.

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

Revision note (2026-09-16): the initial review-only serial waves were replaced
by an independent delivery DAG. The optional Prefect/n8n branch no longer gates
M1 data correctness; M30 proof is the final operational acceptance gate.
