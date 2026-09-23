# Discover the authoritative trading operating model

This ExecPlan is maintained under `PLANS.md`. Keep Progress, Surprises &
Discoveries, Decision Log, and Outcomes & Retrospective current. This is a
discovery and design plan, created at Chris's request on 2026-09-23. Creation
does not mean the discovery, prototype, or implementation has been completed.

## Purpose / Big Picture

MVP priority amendment, 2026-09-23: finish the existing M30 protected Demo
lifecycle, proof, required review and approval gates. Reuse valid existing proof;
this discovery adds no requirement for another trade or runtime deployment.
The optional near-term recommendation from this discovery is limited
to clearer explanations in the existing operator view; defer that too if it
would delay M30 completion. Full policy publication
in PostgreSQL, generated playbooks, calendar enforcement and wider consolidation
are deferred until after M30. The requirement to retain all trading information
in PostgreSQL remains; this amendment does not claim that deferred schema work
is implemented. Observed safety defects still block their dependent operations.

Chris needs one understandable operating model that both people and software
can use to explain when the Demo system trades, waits, protects a position,
and needs operator intervention. Today those rules are distributed across
configuration, Python, database records, and documents. The immediate example
is market opening and closing: waiting for a quote does not establish a
scheduled broker closure or a known reopening time.

Discover the best authoritative home and publication path before moving rules
or adding a new policy file. The outcome is an evidence-backed recommendation,
a runnable local demonstration that produces human and machine views of the
same example policy, and a concrete implementation proposal. The demonstration
must identify its examples as synthetic and must never be loaded by the trading
runtime. Discovery success is a reviewable design, not deployed trading behaviour.

## Scope and authority

Chris authorised execution on 2026-09-23. The discovery's
scope is repository inspection, primary-source research, retained evidence
inspection, and isolated local examples. Treat production integration as a
separate delivery decision. Do not migrate the database, change runtime policy,
deploy, release holds, restart MT5, or submit orders as part of this discovery.

Preserve Chris's requirements: all trading information belongs in PostgreSQL;
manual trade attribution and broader account-ledger work remain deferred; the
smallest reliable M30 Demo workflow remains the delivery priority. Investigate
how policy authorship, approval, effective versions, deployed copies, and
decision-time records meet the PostgreSQL requirement without inventing two
independently editable sources of truth. A skill may describe maintenance
procedures but is not the executable authority for trading rules.

## Formal milestone dependency map

At plan creation, `project_state.json` identifies M29 as PROVEN, M30 as
IN_PROGRESS, and M31 as PLANNED. M30 requires a natural protected
`GOMarketsMU-Demo` EURUSD entry, mandatory close, and complete reconciliation.
Its final proof requires retained broker evidence, offline verification,
the registry's review route, and human approval. This discovery satisfies none
of those proof requirements and does not add a market-calendar gate to M30.

The existing M30 unblocking plan records a narrow human M29 applicability
exception for the changed Interactive listener topology. Reuse that record
within its scope; this design work neither repeats recovery proof nor extends
the exception. Revalidate formal state before any later delivery proposal.

Discovery steps D1–D5 are planning support requested by Chris. Production wave
P1 (small operator visibility improvement), P2 (deferred session enforcement), and P3 (deferred broader operating
model and PostgreSQL changes) are proposed follow-ups only. D5 must map each
to an existing suitable contract or specify the exact amendment/new contract
needed. Do not automatically assign these to M31: its number does not establish
scope. No P-wave implementation begins under this discovery plan.

## Progress

- [x] 2026-09-23: Create the discovery plan and inspect initial policy locations.
- [x] 2026-09-23 D1: Mapped source ownership and twelve rule areas in the report.
- [x] 2026-09-23 D2: Read primary sources; exact Demo schedule remains unqualified.
- [x] 2026-09-23 D3: Compared three options; recommend composing existing sources.
- [x] 2026-09-23 D4: Seventeen examples, both CLI formats and nine tests pass.
- [x] 2026-09-23 D5: Separate read-only review accepted the repaired prototype
  and recommendation; P1/P2/P3 proposal recorded with implementation boundaries.

## Context and Orientation

<!-- forex-work-projection:start task=TRADING-OPERATING-MODEL-DISCOVERY schema=forex.execution-work-projection.v1 -->
<!-- forex-work-item id=D1 state=DONE -->
- [x] D1 — Map rules and ownership (DONE)
<!-- forex-work-item id=D2 state=DONE -->
- [x] D2 — Qualify available broker evidence (DONE)
<!-- forex-work-item id=D3 state=DONE -->
- [x] D3 — Compare authority options (DONE)
<!-- forex-work-item id=D4 state=DONE -->
- [x] D4 — Demonstrate common human and machine views (DONE)
<!-- forex-work-item id=D5 state=DONE -->
- [x] D5 — Review recommendation and delivery proposal (DONE)
<!-- forex-work-projection:end -->

Start in `/home/chris/projects/forex`. `config/runtime.yaml` contains Demo
risk limits and a `financing_policy` whose current qualification basis is
`DEFERRED_FOR_DEMO`; its rollover list is empty. Its schema is
`config/schemas/runtime.schema.json`. Inspect `src/forex/config/` to follow
validation and loading rather than assuming configuration is reread every cycle.

`t480/m20_demo_trading_session.py` implements strategy assessment and execution.
Its strategy-specific `liquid_session = 7 <= observed_hour < 20` is not a
broker-wide opening schedule. `t480/m20_demo_listener_service.py` publishes
`WAITING_FOR_FRESH_MT5_QUOTE`. `src/forex/m20_policy_kernel.py` is another policy
consumer to compare. Trace their actual call paths and release bindings.

`t480/m20_postgres_audit_bridge.py`, `scripts/postgres_pgvector_adapter.py`, and
`sql/migrations/` describe the current persistence surfaces. A migration file
proves repository intent, not deployment. Use retained migration receipts or
existing fixed read-only observations if runtime confirmation becomes necessary;
mark unavailable confirmation as unknown, without inventing generic SQL access.

`docs/workflows/m1-demo-decision-workflow.md` explains the current workflow.
`docs/capability-architecture.md` records an incomplete market/session contract.
`docs/plans/m30-controlled-demo-execution.md` records existing deferrals.
`docs/listener-operator-view.md`, `scripts/listener_workflow_report.py`, and
`scripts/m20_listener_dashboard.py` provide the existing operator-view path.
Preserve unrelated edits in all these files.

An operating model describes rules, responsibilities, and failure handling.
A policy is its executable rule set. A playbook explains the effective rules
and operator actions. An authoritative source is where a fact may be changed;
a published copy is derived from that source and cannot independently override it.

## Evidence Brief

### Decision and hypothesis

Choose where policies are authored, approved, stored, deployed, and explained.
Hypothesis: one versioned policy publication path can give the listener and
operator matching answers while PostgreSQL retains reconstructible trading
facts. Support requires a traced ownership map and examples with identical
rule values, policy identity, and reasons in both outputs. Conflicting values,
untraceable decisions, or two editable masters weaken or reject an option.

### Context and evidence reviewed

The scope is EURUSD on `GOMarketsMU-Demo`, current M1 operation, and repository
state inspected on 2026-09-23. Broker clock rules are unqualified inputs to
discover. Show UTC and Pacific/Auckland where useful, and retain the original
broker time and conversion basis. This is operating design, not a strategy
performance study.

Evidence-supported: `config/runtime.yaml` explicitly defers financing/rollover;
the strategy code contains a limited liquid-session window; the listener has
a wait-for-quote state. Confidence is high for inspected source behaviour,
but this inspection alone does not establish deployed behaviour.

Reasonable inference: those pieces do not supply a complete operator explanation
of scheduled availability. Verify this through all consumers in D1.

Assumptions to test: a dedicated configuration file is needed; database ownership
is preferable; generated documentation is sufficient; fixed UTC hours express
the broker's schedule; visibility must immediately become an entry veto. D1–D4
must test these rather than adopt them as requirements.

Rejected claim: an interrupted quote stream near rollover proves market closure
or a specific reopening time. It does not distinguish a scheduled break, thin
quotes, disconnection, or feed failure. Do not reuse the earlier conversation's
closure diagnosis as evidence.

Validity risks include stale broker schedules, applying another broker entity's
terms, confusing financing settlement with a trading break, assuming a clock
offset from one timestamp, and presenting proposed rules as already enforced.
Prevent historical leakage by distinguishing effective dates from the dates
facts became known. Consider spread, quote age, latency, and exit availability;
do not infer commissions, swap charges, or profitability from calendar facts.

Recommendation: execute bounded discovery. No external schedule has been
qualified for this plan; D2 must read primary sources and assess applicability.

## Plan of Work

### D1 — Map what exists

Create `docs/research/trading-operating-model-discovery.md`. Inventory market
availability, strategy selection, risk, order submission, protection, exits,
reconciliation, manual/external trade attribution, and operator intervention.
For each rule record its identifier, meaning, current value or unknown value,
authoritative source, loader, runtime consumer, persistence, human description,
relevant test, and source revision or digest. Classify it as enforced,
informational, deferred, or unknown; distinguish local implementation from
verified deployment. Trace actual rule functions rather than relying on prose.

Document conflicts, including architectural priorities that differ from the
current MVP deferrals. Establish the precedence from human instructions and
active contracts; do not silently edit conflicting documents during discovery.
Draw the smallest useful ownership map from authoring to deployment to decision
to PostgreSQL and operator view. No broad redesign is required for the inventory.

### D2 — Qualify market availability facts

Find official GO Markets Mauritius EURUSD session specifications, dated notices,
and platform documentation relevant to what the existing fixed adapter can
observe. Open actual primary pages; search snippets are not evidence. Record
URL, publisher/entity, retrieval date, stated effective period, applicable
server/symbol, timezone convention, and limitations. A different entity's FAQ
may be a lead but cannot establish this Demo server's exact trading breaks.

Separate weekly trading sessions, quote sessions, daily breaks, financing
rollover, holidays/early closes, and strategy-preferred hours. Determine whether
the broker schedule is obtainable through an existing approved observation.
If not, retain the gap and specify the smallest proposed observation; do not
build a remote command surface during discovery. Never promise the next opening
when evidence does not establish it.

### D3 — Compare authority and storage options

Compare A: extend existing governed configuration; B: create a dedicated
versioned operating-policy document; C: author approved policy versions in
PostgreSQL and publish immutable runtime copies. For A and B, explain how full
approved/effective policy versions and decision references would also be retained
in PostgreSQL. For C, explain change review, export, deployment, and recovery.
The requirement for PostgreSQL trading records applies to every option.

For each option state the sole writer for each fact, approval/activation path,
runtime loading behaviour, version/hash identity, database retention, rollback,
database outage behaviour, conflict detection, and human publication path.
Distinguish repository history, intended configuration, effective deployed
configuration, and decision-time observations. Never label multiple mutable
copies as equally authoritative. A cached policy must not bypass existing
journal-before-submission or unknown-account safeguards.

Compare preservation of M30, operator clarity, reproducibility, enforcement
consistency, failure handling, implementation effort, and maintenance burden.
Require explicit pass/fail on single authority, PostgreSQL traceability, and
truthful unknown states before considering convenience. Recommend the smallest
option meeting these requirements, document rejected options and tradeoffs,
and state what evidence would change the recommendation. Do not hard-code a
preferred file location before this comparison.

### D4 — Demonstrate one policy in two views

Create an isolated standard-library prototype under
`research/operating_model_discovery/`, with `demo.py`, `examples.json`, and
`test_demo.py`. It must have no network, MT5, database-write, or production-import
path. Model representative existing rule references plus synthetic session
facts, and render machine JSON and a readable terminal playbook from the same
evaluated object. Preserve maintained explanations separately from generated
values. Include policy version, effective time, source references, enforcement
status, responsibility, reason, and next expected transition when known.

Keep scheduled state, observed feed state, and entry permission separate.
Exercise a regular opening/closing boundary, a daily break, weekend, seasonal
clock change, holiday override, unknown/expired calendar, connected terminal
with stale quotes during scheduled hours, normal quotes with excessive spread,
conflicting policy versions, and an open position near closure. Distinguish
session-based eligibility from the full production risk decision. Quote freshness
or calendar opening alone must never imply overall permission to trade.

For an open position show that blocked new entries do not disable protection;
an unavailable exit is unresolved and cannot be labelled closed. Do not invent
a new exit deadline or claim that the prototype controls real positions.
All sample broker hours must be explicitly synthetic unless D2 qualified them.

Run meaningful tests asserting boundary behaviour, mismatch detection, and that
both output forms contain the same policy identity, evaluated values and reasons.
Retain a short sample transcript in the research report. This is a local design
demonstration, not proof of a deployed calendar or runtime policy.

### D5 — Recommend and define delivery

Complete the report with the chosen ownership model, unresolved facts,
implementation sequence, and exact affected files/interfaces. Review the design
against the seven assumptions in the Evidence Brief and repair discrepancies.
Obtain a separate read-only review of ownership, PostgreSQL traceability,
calendar uncertainty, and MVP scope, recording reviewer and reviewed digests.
Do not present author self-checking as independent review.

Propose only an optional bounded existing-reader P1 improvement supporting the MVP:
distinguish no qualifying setup, waiting for fresh prices and confirmed closure;
show unknown schedule explicitly. It needs no new store, service, migration or
trading policy, and is not a prerequisite to M30 execution or proof. Defer P2
enforced session behaviour and P3 broader consolidation until after M30, unless
an evidenced safety defect requires a separately scoped earlier repair.
Complete existing M30 proof, required repairs, review and approval gates first;
P1 must not become an intervening delivery wave that delays that outcome.
For each proposed production change identify the existing
formal scope or required amendment, deployment verification, affected proof,
rollback, and real-world acceptance. A concrete recommendation must precede
any request for a consequential operator choice. Discovery may conclude that
existing components are sufficient with a smaller documentation/report change.

## Concrete Steps

Run from `/home/chris/projects/forex`:

    git status --short
    rg -n 'liquid_session|DEFERRED_FOR_DEMO|WAITING_FOR_FRESH_MT5_QUOTE' t480 src config
    rg --files sql/migrations config docs/workflows

When execution begins, add `docs/plans/trading-operating-model-discovery-work.json`
using schema `forex.execution-work.v1`: D1 and D2 independent; D3 requires both;
D4 requires D3; D5 requires D4. Record actual evidence and unresolved dependencies.
The work record was activated by Chris's subsequent instruction to execute.

After the local prototype exists:

    python3 research/operating_model_discovery/demo.py --examples research/operating_model_discovery/examples.json --format json
    python3 research/operating_model_discovery/demo.py --examples research/operating_model_discovery/examples.json --format text
    python3 -m unittest discover -s research/operating_model_discovery -p 'test_*.py'
    git diff --check
    python3 scripts/forex_milestones.py validate
    python3 scripts/check_execution_continuation.py --work-plan docs/plans/trading-operating-model-discovery-work.json

The future executor implements these prototype CLI arguments before running
them. Record actual results; do not fabricate expected test counts. A CONTINUE
result means select the next authorised discovery item. It never activates a
production follow-up wave.

## Validation and Acceptance

Discovery passes when Chris can read the recommendation and identify where a
rule is changed, how it reaches the listener and PostgreSQL, and why the terminal
displays its current explanation. Every inventory row must link to evidence
or be explicitly unknown. All three options must be evaluated; the chosen one
must have no unresolved competing authority for the same fact.

The local example commands must show identical effective policy identities and
answers in JSON and text. Unknown schedules must produce an unknown opening
time, not a guessed countdown. Stale quotes during scheduled hours must not
be called a confirmed market closure. The independent review must resolve
design blockers or leave a precise, evidence-backed outstanding decision.

Plan-creation acceptance is narrower: this file contains the assumptions,
discovery sequence, option comparison, output contract, acceptance checks,
scope boundaries and delivery decision. Its unchecked discovery tasks remain
unchecked. No runtime test is necessary to validate a planning-only change.

## Idempotence and Recovery

Preserve existing worktree edits. Discovery writes only this plan, its task
record when activated, the named research report, and isolated prototype files.
Keep source receipts separate from derived interpretation, and never overwrite
raw retained evidence. A failed prototype changes no operational state; repair
and rerun it locally. Do not automatically commit, push, migrate, or deploy.

## Interfaces and Dependencies

The prototype accepts explicit example timestamps and input facts; it must not
use wall-clock time as hidden test input. JSON and text renderers consume one
evaluation result with separate scheduled_state, observed_state,
session_entry_eligibility, reasons, next_expected_transition, policy identity,
and evidence references. Human explanations must distinguish enforced production
rules from proposed examples. Reuse existing schema conventions after D1;
avoid adding a service, framework, or skill solely to perform discovery.

## Surprises & Discoveries

- Source inspection confirms the 07:00–20:00 UTC range is strategy-specific.
- The rollover configuration is explicitly deferred, not a populated schedule.
- Earlier conversation overstated evidence of market closure; the cause remains
  unqualified. This plan requires that uncertainty to be visible.
- Independent review reproduced a misleading next-opening prediction when a
  future interval overlapped. The prototype now suppresses that prediction;
  a regression test covers overlap before and at the boundary and invalid states.

## Decision Log

- 2026-09-23: Plan discovery before choosing configuration or database ownership,
  because the earlier recommendation assumed an architecture without comparing
  existing consumers and Chris's PostgreSQL requirement.
- 2026-09-23: Use a small local demonstration to test human/machine agreement;
  leave production visibility and enforcement as distinct delivery decisions.
- 2026-09-23: Keep this plan separate from the active M30 execution work so that
  discovery does not silently change trading authority or MVP proof gates.
- 2026-09-23: Recommend option A: compose existing authoritative rules, retain full
  publication and activation facts in PostgreSQL, and render one human playbook.
  Separate visibility from later calendar enforcement and broader schema work.
- 2026-09-23, Chris's MVP-focus amendment: the option A architecture is a deferred
  target. Prioritise M30 completion and a small existing-view improvement; do not
  introduce publication infrastructure or new calendar gates as MVP prerequisites.

## Outcomes & Retrospective

D1–D5 completed locally. The report is
`docs/research/trading-operating-model-discovery.md`; the isolated prototype is
`research/operating_model_discovery/`. Nine tests and both CLI formats passed;
17 example outputs were inspected for matching policy identity. Formatting and
milestone validation passed. Independent review found a future-calendar conflict
and the repair passes its regression test; the reviewer confirmed no remaining
discovery blockers. No runtime,
database or broker state was changed. Broker-specific schedule qualification
remains an explicit prerequisite of future enforcement, not unfinished discovery.

Execution revision: 2026-09-23, completed the authorised discovery, recorded
independent review and local checks, and retained production delivery as a separate
proposal. This completion does not resume or close the separate M30 goal.

Recommendation revision: 2026-09-23, updated report and plan to make the immediate
MVP recommendation explicit and defer the larger architecture. The historical
independent review applies to the discovery artifacts it inspected; this subsequent
priority amendment follows Chris's instruction and does not change prototype code.
Further MVP clarification: P1 is explicitly optional and deferred if it delays
M30; completion follows existing proof and approval gates, without requiring
another trade, runtime deployment or operating-model infrastructure.

Revision note: initial plan written on 2026-09-23 to turn the operating-model
discussion into bounded, evidence-led discovery rather than assume a new policy
file is the answer.
