# Demo trading MVP console — parent ExecPlan

This is a living ExecPlan governed by `AGENTS.md`, `PLANS.md`,
`project_state.json`, and `milestone_registry.json`. Chris explicitly
authorised M33.5 implementation on 2026-09-28. It authorises only the registered
read-only Demo visibility scope; deployment, broker action, Live access, commit
and push remain separately governed.

## Purpose

The operator needs one honest, readable Demo view rather than several terminal
reports: what the T480 listener is doing now, what it read, how every strategy
was assessed, why it chose `NO_TRADE` or a trade, the planned entry/SL/TP, and
the reconciled P&L of system-owned trades today, this week, and this month.

After implementation, a browser or terminal operator can observe that path
without issuing an order. The screen is an explanation of the existing fixed
M1 runner; it is not a second decision engine, a trade-control panel, or a
profitability claim.

## Current evidence and smallest change

The observed MVP gap is presentation and a readable execution-time event
stream, not autonomous execution. The fixed
T480 Demo listener is running and already retains a proposal, strategy
assessments, selected owner, rationale, planned prices, execution status,
reconciliation and broker-derived outcome. `scripts/m20_listener_dashboard.py`
and `scripts/listener_workflow_report.py` expose the current decision path;
`scripts/m20_trade_ledger_dashboard.py`, `scripts/m33_daily_pnl_report.py`,
and `scripts/m20_strategy_trial_dashboard.py` expose different slices of the
journal. The smallest MVP change is an actual listener-emitted, redacted
decision-event stream, one read-only composition of authoritative records, and
explicit time-bucket summaries. It must not change
`t480/m20_demo_trading_session.py` decision, risk, sizing, submission, or
monitoring behaviour.

## Demo trading continuity

| Package | Declaration | Reason and evidence check | Hold/re-entry condition |
|---|---|---|---|
| Design phase | CONTINUE | Documentation-only work; verify the existing listener status is fresh before any implementation handoff. | No hold. If a fresh status reports a critical safety fault, only the existing incident procedure may hold entries; re-entry requires that procedure's evidence. |
| Read-only console | CONTINUE | It reads existing fixed reports only and has no broker/control route. Verify its process has no write/order capability. | No hold; a read failure displays `UNKNOWN` and does not alter the listener. |
| Decision trace | CONTINUE | The actual listener emits redacted phase events while it assesses; the console only renders them. Verify final event identity equals the latest proposal/snapshot identity. | No hold; malformed or unavailable trace is visibly unavailable. |
| P&L aggregation | CONTINUE | It only reads reconciled, system-owned closed outcomes. Verify each aggregate is reproducible from journal rows. | No hold; incomplete reconciliation is excluded from realised totals and counted as unavailable. |
| Strategy evaluation | CONTINUE | Analysis is read-only and must not tune or gate the live Demo listener. Verify frozen version and sample boundaries. | No hold; a data-quality failure invalidates an evaluation, not a healthy listener. |

## Formal milestone dependency map

M20 is the reusable Demo execution capability: its fixed listener, proposal
before submission, journal and Demo-only restriction are already the runtime
foundation. M32 is a reusable quality prerequisite. M33 is the current formal
milestone and its existing daily P&L report is reusable. M33's recorded
contract does **not** explicitly authorise a new unified console, decision-event
interface, week/month aggregation, or changed runtime log retention.

Chris explicitly approved the M33.5 amendment and implementation on 2026-09-28.
The decision-trace package is now in progress. Journal analytics and operator
surface work begin only after their child work records are authorised. No new
numerical milestone is created. The later strategy-evaluation package has no
Live authority; a separate Live-readiness decision would be required even after
positive Demo results.

## MVP definition of done

The delivered Demo MVP must meet all of these observable outcomes:

1. A read-only operator page identifies the T480 listener state, heartbeat,
   latest completed M1 decision, Demo server/symbol, current risk/entry state,
   and whether an open position is actually observed or unknown.
2. Each visible decision trace is emitted by the actual `capture()` run as it
   completes each M1 phase and states source time, bid/ask/spread, completed
   candle reference, each of the five strategy signals and reasons, selected
   owner/regime, gates, final `BUY`, `SELL`, or `NO_TRADE`, and the final
   rationale. For an actionable proposal it states **planned** entry, stop
   loss, take profit, size and cost gate. It must never label a planned price as
   a broker fill.
3. The trade journal shows each system-owned lifecycle with proposal/attempt
   identity, strategy and version, entry/exit facts, broker commission, fee,
   swap, gross and actual net P&L. A row without broker match says
   `UNRECONCILED` rather than showing a money result.
4. Today, week and month P&L use the Pacific/Auckland calendar and include only
   `CLOSED` broker-matched, M20-attributed Demo outcomes. Deposits, withdrawals,
   external/manual history and unreconciled rows are excluded and their counts
   are visible. Actual broker P&L is primary; an optional estimated commission
   comparison remains separately labelled `ASSUMED`.
5. The strategy panel identifies strategy/rule version, sample range, attempted,
   rejected, opened and matched-closed counts, wins/losses and actual net P&L.
   It says that the sample does not establish an edge or authorise Live trading.
6. The console has no control capable of submitting, modifying, closing,
   enabling, retrying or cancelling a trade; it binds only fixed read-only
   adapter/report operations and is loopback-only unless a later security
   decision says otherwise.
7. One natural (not forced) Demo lifecycle can be followed from fresh decision
   trace through broker-matched close into the journal and exactly one period
   total. A `NO_TRADE` decision remains valid evidence of visibility but cannot
   prove the lifecycle path.

## Sub-ExecPlans and delivery sequence

1. [Decision trace](demo-mvp-console-decision-trace.md) defines the redacted
   event shape emitted during the actual listener `capture()` call, then
   retained and rendered by the console. It is first because the console must
   not invent or reconstruct an explanation.
2. [Journal and P&L](demo-mvp-console-journal-analytics.md) defines the strict
   ownership/reconciliation filter and today/week/month calculations. It is
   second because every amount needs a stable membership rule.
3. [Operator console and proof](demo-mvp-console-operator-surface.md) composes
   those two read models with the existing live listener report and verifies the
   operator workflow. It is third and contains no execution capability.
4. [Strategy and edge-case evaluation](demo-strategy-evaluation-execplan.md)
   begins only after the console has produced a clean Demo sample. It is an
   evaluation plan, not a tuning plan and not a Live promotion.

Each implementation package must retain the `CONTINUE` declaration above,
record its own work JSON, run the continuation checker with that JSON, obtain a
separate read-only review, and use the QA verification process. Deployment
requires the release-readiness process and fresh status evidence, but must not
place a development hold on healthy Demo trading.

## Design-phase progress

<!-- forex-work-projection:start task=DEMO-MVP-CONSOLE-DESIGN schema=forex.execution-work-projection.v1 -->
<!-- forex-work-item id=design-evidence state=DONE -->
- [x] design-evidence — Inspect existing listener, journal, P&L and strategy-report surfaces (DONE)
<!-- forex-work-item id=parent-design state=DONE -->
- [x] parent-design — Create consolidated MVP parent ExecPlan with continuity and formal dependency map (DONE)
<!-- forex-work-item id=subplans state=DONE -->
- [x] subplans — Create bounded decision-trace, journal-analytics, operator-surface and strategy-evaluation sub-ExecPlans (DONE)
<!-- forex-work-item id=astra-design-review state=DONE -->
- [x] astra-design-review — Independent Astra review of console and actual-code logging design (DONE)
<!-- forex-work-item id=implementation-authority state=DONE -->
- [x] implementation-authority — Obtain explicit formal-scope authority for the first implementation package (DONE)
<!-- forex-work-projection:end -->

- [x] 2026-09-28: Consolidated Chris's MVP requirements: live T480 visibility,
  readable decision logging, per-trade journal, actual P&L today/week/month,
  and strategy evidence before any later Live discussion.
- [x] 2026-09-28: Inspected the existing decision workflow, listener dashboard,
  workflow report, ledger, daily report, and strategy trial report.
- [x] 2026-09-28: Wrote this parent plan and the four bounded sub-ExecPlans.
- [x] 2026-09-28: Chris instructed execution. M33.5 was registered as a
  `CONTINUE` read-only console package and its actual-code decision-trace child
  package started.

## Decisions and discoveries

- 2026-09-28 — The event stream is emitted from the actual `capture()` path at
  each completed phase and its final proposal/snapshot identities bind it to
  the durable audit. Runtime stdout cannot carry streamed events because the
  listener parses it as one final JSON result. The spool uses one atomically
  published, immutable allowlisted event record per sequence—not JSON lines—so
  a crash cannot create an apparently complete interleaved trace. The browser
  only renders emitted events and durable facts.
- 2026-09-28 — Use `CLOSED` and broker-matched M20-attributed outcomes only for
  system P&L. The broad broker account journal is still useful for account
  visibility, but cannot measure a strategy because it can contain activity
  outside the listener.
- 2026-09-28 — No new execution infrastructure is part of the MVP. Existing
  fixed listener and adapter contracts are reused; a console is read-only.
- 2026-09-28 — Strategy evaluation is downstream of data collection. Neither a
  positive nor negative small Demo sample establishes future performance.

## Risks and recovery

The main risks are displaying stale state as current, confusing a proposal with
a fill, mixing actual and assumed costs, and counting non-system history as
strategy performance. The sub-plans require explicit source times, labels,
identity joins, membership tests and unavailable states to prevent this. All
work is additive. If a reader fails, retain current listener operation and show
`UNKNOWN`; do not cache a prior state as fresh and do not restart MT5.

## Outcomes and retrospective

The design phase is complete and M33.5 decision-trace implementation is in
progress. It deliberately keeps M33 recovery/provisioning
alternatives deferred because they do not improve a healthy Demo listener's
visibility, journal integrity or strategy evidence today.

Revision note: created 2026-09-28 after Chris requested a consolidated MVP
delivery plan and readable M1 decision logging.

Revision note: Astra design review on 2026-09-28 rejected a JSON-lines event
spool as insufficiently atomic. The decision-trace child plan now requires
atomic immutable records, complete-set binding and explicit incomplete status.

Revision note: Chris explicitly instructed execution on 2026-09-28. M33.5 was
registered and started as the CONTINUE-only read-only Demo console package.
