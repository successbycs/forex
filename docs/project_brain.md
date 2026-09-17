# Project Brain — Demo Trading

## Purpose and use

This is the concise navigation map for the Forex repository. It tells an
operator or agent what the product is for, which boundaries are non-negotiable,
and where to find authoritative current detail. It is not a milestone contract,
execution plan, runtime status record, or proof artifact.

Use it first to orient yourself, then follow the linked sources of truth before
making a material change or claiming a capability is complete.

## Mission

Build an evidence-led EUR/USD Forex decision and execution platform. The MVP
must make one deterministic and explainable `BUY`, `SELL`, or `NO_TRADE`
decision for each completed M1 candle on the authorised Demo account, retain
the inputs and decision, and reconcile any accepted Demo trade with broker
outcomes.

The MVP question is:

> For this completed M1 candle, what did the system decide, why, did it reach
> the broker, and what outcome was recorded?

The repository does not guarantee or imply profitability. A Demo result proves
only the observed implementation and hypothesis under its recorded conditions.

## Non-negotiable operating boundary

- The current execution scope is `EURUSD` on `GOMarketsMU-Demo` through the
  fixed `M1_EURUSD_DEMO` account profile. Live-account interaction is
  prohibited.
- Deterministic Python code behind the fixed T480 adapter is the only broker
  operation path. A dashboard, database query, n8n workflow, notification, or
  AI output cannot place, amend, or close an order.
- Every new entry must pass data, account, broker, lease, duplicate, position,
  exposure, loss, cost, risk, and terminal-capability gates. Missing or unsafe
  facts fail closed for a new entry; protective monitoring must continue.
- A refusal or `NO_TRADE` is a valid result. The system must never force or
  retry an order merely to collect proof.
- Raw evidence is immutable. PostgreSQL contains validated, queryable facts;
  it is not an arbitrary broker command channel.

## Current delivery focus

Read [project_state.json](../project_state.json) and
[milestone_registry.json](../milestone_registry.json) for current formal state
and proof requirements. The current delivery focus is M30's bounded M1 hybrid
workflow. Its final proof remains a natural, final-version Demo lifecycle:
eligible order, close, and broker reconciliation. Do not force an order to
satisfy this proof.

The current work sequence and progress are in:

- [M30 controlled Demo execution plan](plans/m30-controlled-demo-execution.md)
- [M1 hybrid delivery plan](plans/m1-hybrid-prefect-postgres.md)

M31 and later work do not authorise M30 implementation. They remain planned
until their own contracts become active.

## M1 Demo workflow at a glance

```text
completed M1 candle
  -> validate market data, account binding and safety conditions
  -> assess the five fixed M1 strategies on the same snapshot
  -> deterministically select at most one executable owner
  -> calculate entry, stop, target, capped size and cost coverage
  -> persist exactly one BUY / SELL / NO_TRADE proposal
  -> submit only an eligible persisted proposal to MT5 Demo
  -> monitor accepted positions, reconcile broker history and journal outcome
  -> retain immutable evidence and validated PostgreSQL lifecycle facts
```

The executable operational specification is the
[M1 Demo decision workflow](workflows/m1-demo-decision-workflow.md). The
[M1 hybrid decision flow](workflows/m1-hybrid-decision-flow.md) describes the
target shape, while the [M1 data contract](workflows/m1-data-contract.md)
defines identities, provenance, and retention expectations.

M5/H1 are shadow context only today: they are recorded after an M1 decision
and cannot create, reject, or own a trade. M15 and other timeframes require a
separate versioned workflow, runtime implementation, tests, and milestone
authority before they alter M1 behaviour.

## System and authority map

```text
MT5 Demo / approved external source
  -> immutable raw evidence and receipt
  -> validation and provenance checks
  -> PostgreSQL validated facts and lifecycle joins
  -> deterministic Python decision, risk and reconciliation
  -> fixed T480 Demo-only broker operation
  -> read-only dashboard or optional notification
```

The [architecture](architecture.md) and
[capability architecture](capability-architecture.md) define component
ownership. In short: Python owns deterministic domain logic; PostgreSQL owns
validated lifecycle facts; immutable files own original evidence; T480 owns the
narrow broker boundary; n8n is limited to bounded integrations/notifications;
and Prefect is an optional later data-pipeline branch, not a dependency of the
M1 listener.

## Sources of truth

| Question | Authoritative source |
| --- | --- |
| Non-negotiable repository boundary and user authority | [AGENTS.md](../AGENTS.md) and current user instruction |
| Current formal milestone state | [project_state.json](../project_state.json) |
| Milestone scope, entry gates and proof requirements | [milestone_registry.json](../milestone_registry.json) |
| Authorised plan, work records and continuation rules | [PLANS.md](../PLANS.md) and the active ExecPlan |
| Component boundaries and deployment design | [architecture.md](architecture.md) |
| Current M1 operational behaviour | [M1 Demo decision workflow](workflows/m1-demo-decision-workflow.md) and governed runtime configuration |
| Evidence policy and raw-versus-derived rules | [evidence and milestones](evidence_and_milestones.md) |
| Agent roles, review and verification practice | [agent workflow](agent-workflow.md) |
| Protected runtime interfaces | `t480/` and `scripts/t480_adapter.py`, after reading the documents above |

When sources conflict, apply this precedence: explicit user instruction and
`AGENTS.md`; then formal state, contract, and evidence policy; then active
ExecPlan; then architecture and workflow; then this navigation document. Record
and repair documentation drift rather than inferring a broader permission.

## Where to start by task

| Task | Read first | Required guidance |
| --- | --- | --- |
| Change M1 decision, reason codes, strategy selection, or execution gate | M1 workflow and active plan | `trade-decision-engine` |
| Change ingestion, retention, PostgreSQL projection, Prefect, or n8n | Architecture and active plan | `data-pipeline-orchestration` |
| Make a material implementation, integration, dashboard, or safety change | Active plan and affected workflow | `qa-verification` |
| Deploy or enable autonomous Demo execution | Active plan, contract, and runtime status | `release-readiness` |
| Introduce market, strategy, risk, economic-data, or product claims | Evidence policy and active plan | `research-evidence` |

## Deliberate MVP deferrals

The current MVP does not require Live trading, new strategies, dynamic sizing,
larger limits, M15 execution, higher-timeframe entry authority, mandatory
economic-event/financing/rollover gates, broad reporting, or deployment of
Prefect/n8n for the trading loop. Discord notifications are optional and are
not a decision, execution, or proof dependency.

## Definition of success

The MVP is meaningful when an operator can inspect a completed M1 candle and
reliably answer:

> What was the terminal decision, what evidence and strategy produced it, did
> it reach MT5, and what broker-reconciled outcome followed?

Success requires traceable inputs, one decision per closed candle, explicit
refusals, protected Demo execution where eligible, and durable outcome records.
It does not require a profitable result, a specific trade count, or Live
trading.

## Maintenance rule

Update this document only when a stable mission, boundary, workflow route, or
source-of-truth map changes. Link to mutable state and evidence instead of
copying them here. Last reviewed: 2026-09-17.
