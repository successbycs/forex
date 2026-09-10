# Research-based trading waves: execution guide

## Operator priority amendment — 2026-09-10

Get core Demo execution working first. Backup and isolated-restore proof is
explicitly deferred to [W4.0](demo-income-wave-4.md), before a funded pilot;
its absence is not a Wave 1 deployment, migration or recovery-drill blocker.
This supersedes earlier backup gates in the recovery package and handovers.
Keep Option B, Demo-only access, maintenance entry holds, fresh exposure/audit
checks, ledger/risk-state preservation and required execution evidence.
This amendment does not itself complete Wave 1 or authorise Live trading.


Revised 2026-09-10 following the repository and literature review. **Current
planning specification; this revision does not execute a wave.** Prior Wave 1
work and explicit approvals remain valid within their scope. Read current
handover/evidence for execution status; do not reset completed work to planned.

The mission is to determine whether the system can deliver sustainable net
returns within explicit capital-risk limits and with low operator effort.
The objective is sustainable small returns after all attributable costs, with
conservative capital risk and low human attention. This is not a daily income
quota. Waves 1–3 establish Demo reliability and economic evidence; Wave 4 is a
separately gated route to a funded pilot. None promises income.

This guide and the numbered wave files are the current execution-planning
source. They supersede the 7 September R0/E1–E5 research schedule and its H_H1
experiment; preserve those documents as historical rationale. The
[10 September review](../../Research/2026-09-10-live-forex-readiness-review.md),
[milestone map](../../Research/2026-09-10-milestone-relevance.md) and
[design review](../reviews/edge_discovery_design_review.md) explain the changes.
Registry contracts, canonical configuration and explicit operator authority
still govern execution. A revised wave plan does not silently amend them.

## Execute one wave at a time

| Wave | Activities | Intended result | Prompt |
| --- | --- | --- | --- |
| 1 | W1.1–W1.4 and W1.R | Repair independent risk latches first; prove broker state, accounting and recovery | [Wave 1](demo-income-wave-1.md); [resume prompt](demo-income-wave-1-resume-goal.md) |
| 2 | W2.1–W2.2 | Qualified costs/data/eligibility and one shared replay/execution policy | [Wave 2](demo-income-wave-2.md) |
| 3 | W3.1–W3.3 | Frozen baseline plus at most two challengers; selection-aware net economics and low-attention operation | [Wave 3](demo-income-wave-3.md); [research alias](research-trading-wave-goal.md) |
| 4 | W4.0–W4.4, future gate | Prepare a default-disabled live mandate; separately authorise and measure one tiny funded pilot | [Wave 4](demo-income-wave-4.md) |

Each wave file contains its activity specification and a fenced, copy-and-paste
goal prompt. The short prompt instructs the executing agent to read the full
wave file and this guide; it does not depend on remembering this conversation.
Run it from this repository's workspace. A wave is an execution grouping, not
a new milestone or an amendment to the registry.

The **W1.R** schedule is: R1 diagnose; R2/R3 correct recovery and
unknown-exposure handling; R4 coordinate maintenance and deploy with R6 incident
recording; R5 demonstrate continuity/recovery and R6 alerts; R7 finish the
original W1.1–W1.4 evidence. Shared T480 work remains an explicit dependency
owned by `cs-ai-lab-infra`, whose own recovery Wave 1 is a different workstream.
Reuse prior R1–R7 results after checking their bindings. Add the newly identified
W1.4 latch repair before final release/proof; do not repeat fixed recovery bugs.
This planning revision does not authorise host maintenance or a new milestone.
Wave 3 reuses valid technical recovery evidence and adds its longer operational
and economic assessment.

Use the selected model with one implementation thread and focused reads/tests.
Reserve additional model work for unresolved risk, statistical or evidence
questions and contract-required review. This plan does not switch models.

If desired, explicitly set a token budget for that wave in the supported goal
controls or your execution instruction. No numerical budget is pre-authorised
by these documents. A goal budget is not a guaranteed percentage of the Pro
allowance. Check the usage display before extending a run. See the official
[usage guidance](https://learn.chatgpt.com/docs/pricing) and
[Goal guidance](https://learn.chatgpt.com/docs/long-running-work).

Do not launch the next wave automatically. A fresh execution instruction is
required. Finish with a concise handover so later work reads the findings and
changed files rather than repeating the whole repository review.

## Shared execution contract

Every wave prompt incorporates the following requirements:

1. Inspect Git status and preserve unrelated work. Read applicable AGENTS.md,
   `project_state.json`, the active contract in `milestone_registry.json`,
   `docs/evidence_and_milestones.md`, this guide, and the selected wave file.
   Re-check previous findings against current code and evidence.
2. Work only within the active approved milestone. At preparation, this is
   M20 and its implementation status is `NEEDS_FIX`. Re-read at execution time.
   Map work to whichever approved contract is active at execution time. These
   prompts do not themselves start a later milestone or waive dependencies.
3. Map each proposed change to the active contract. For changes outside it,
   prepare an exact contract amendment and obtain explicit human approval
   before dependent implementation. Continue independent authorised work.
   Do not infer approval from this document, elapsed time, or a review result.
4. Permit orders only on `GOMarketsMU-Demo`, EURUSD, under approved limits and
   the existing fixed adapter. Do not access or enable `GOMarketsMU-Live`.
   Retain one-position, persisted-proposal, idempotency, and broker-protection
   boundaries unless an explicitly approved contract changes a relevant rule.
5. No commits, pushes, branches, or PRs without explicit human instruction.
   Prepare deployment and rollback details before deployment. If a real-world
   proof requires a clean committed release that is not yet authorised, report
   the exact remaining action; do not invent revision provenance or bypass it.
6. Keep changeable non-secret settings in canonical configuration. Keep secrets
   and machine-local values in ignored local files. Reuse shared infrastructure;
   shared transport remains owned by `cs-ai-lab-infra`.
7. Unknown broker state, unreconciled exposure, required stale/unavailable data,
   disabled authority, and breached risk limits must block new entries.
   Preserve protective management of existing positions. Do not introduce
   martingale, loss-chasing, automatic risk escalation, self-modifying trading
   rules, or AI bypasses of deterministic execution controls.
8. Distinguish implementation, automated tests, fault injection, real-world
   proof, economic findings, and production readiness. Simulations are useful
   engineering evidence but cannot replace the declared real-world surface.
9. Preserve raw evidence unchanged and separately from verification. Bind it
   to the contract, release/revision, configuration, verifier, timestamps, and
   exact surface. Recapture affected proof after material changes; retained
   historical evidence remains historical. Independent verification must not
   regenerate missing observations or contact the broker to repair a bundle.
10. Preserve required reviews. Milestone closeout requires a current bound
    Triad-plus-domain `RECOMMEND_COMPLETE` and every other active contract gate.
    Review roles are read-only and cannot approve or close milestones. Only
    the closeout command may generate `proven_at`; leave `target_date` human-owned.

## Mission-focused scope and dependency map

| Review actions / earlier research | Wave owner | Contract treatment before implementation |
| --- | --- | --- |
| A1, A2; R0 recovery | W1.4 and W1.R/W1.2 | Repair current M20 safety; preserve exact approved risk limits. Shared host recovery remains an owned dependency. |
| A3; E1 accounting | W1.3 actual ledger; W2.1 cost model; W3.1 operator economics | One ledger and one cost convention, reused throughout. |
| A4, A5, A6; E4 replay/data | W2.1–W2.2 | Map M21/M26/M28 and M13/M16 capabilities into the active approved contract. Additional quote retention conflicts with M20's no-tick-stream scope until explicitly amended. |
| A7, A8, A9; E2/E3/E4/E5 | W3.1 | One trial register and report. H_SESSION retained; H_SLOW replaces H_H1 in the current plan. No automatic change to M20's execution ownership. |
| A10; R0 extended operation | W1.R technical recovery; W3.2 economic/attention interval | Reuse valid recovery evidence and extend observation, not infrastructure. |
| Review/closeout | W3.3 | Preserve required current reviews and historical milestone records. |
| A11, A12 | W4.1–W4.4 | New exact Live contract and explicit account/capital authority required; current Live prohibition remains. |
| E6 diversification, sentiment, DSR/PBO/CPCV expansion | Deferred | Separate evidence-based proposal only; not prerequisites to testing a small price-based family. |

Reuse M2–M7, M10, M12–M14, M17 and M19 capabilities where fit. Merge overlapping
M22–M24/M26/M27/M29/M30 requirements into their wave owners through explicit
criterion mapping; do not build a second risk engine or erase old milestones.
Reframe M25 as a bounded operating mandate rather than per-order approvals.
M31/M32 inform W3 and the Live go/no-go; they do not grant Live access. Defer
M8/M9/M11/M15/M18 expansion unless the frozen experiment needs it. These are
planning dispositions, not edits to the registry or its recorded proof.

Before dependent execution, record each activity's owning criterion, required
amendment if any, evidence surface and approval reference. A change of strategy,
timeframe, retention or account cannot hide inside a refactor. Missing authority
blocks only dependent work; use existing session approvals rather than asking
again. A goal budget is distinct from the experiment's search/compute budget.

## Existing operator risk decisions

Preserve Conservative Option B: planned per-trade loss is the lesser of
AUD 100 and 0.10% policy equity; daily loss pause 0.50%; weekly pause 1.00%;
peak adjusted-equity drawdown pause 2.00%; Auckland boundaries and existing
cash-flow/manual-resume policy. Each breached reason must remain independently
latched for its own approved reset. A daily reset cannot erase a weekly or
drawdown incident. Correctly triggered pauses remain part of the evaluated
policy; bypasses or failed enforcement are safety failures.

Keep `maximum_trades: null`, continuous duration, one open position, USD 10,000
per-trade notional and USD 100,000 cumulative lease notional. Unlimited count
does not remove these independent caps. Do not replace leases to bypass them.
Reuse the temporary AUD 0.01 planned-loss refusal-drill approval only for that
drill and restore Option B immediately. The operator's no-cash-flow statement
applies to the specific AUD -0.29 close, not future unexplained differences.

## Operator decisions: do not invent these

Check existing explicit decisions first. Propose concrete options for missing
values and request only the decisions needed for dependent work.

| Decision | Needed before |
| --- | --- |
| Reporting currency and evaluation capital basis, including treatment of deposits/withdrawals | Equity-relative risk and economic reporting |
| Per-trade risk, exposure/leverage caps, daily/weekly loss limits, peak-equity drawdown limit, and reset rules | Changing the risk policy |
| Loss-budget timezone, inclusion of unrealised losses/costs, pause/resume authority | Persistent risk implementation |
| Permitted trading sessions, event exclusions, stale-source policy, cost assumptions | New eligibility rules |
| Recurring cost allocation, operator-time budget, treatment of tax and development costs | Net operator benefit reporting |
| Candidate selection, complete H_SLOW rule, frozen rules, search budget, observation window, sample/coverage requirements and statistical decision criteria | Economic experiment start |
| Intended live capital and minimum worthwhile net income | A supported business-case claim; never infer these from the Demo balance |
| Maintenance window, drill constraints, and unattended observation conditions | Disruptive Demo drills or extended trial |

Small returns and stop orders do not establish low risk. Record loss limits as
controls and planned risk, not guarantees against gaps or slippage. An income
aspiration must never become an order quota or sizing input.

## Cost and evaluation definitions

- **Broker net trading P&L:** reconcile actual fills and all attributable broker
  commission, fees, and financing/swap. Identify any charges posted separately
  from deal rows. Exclude deposits, withdrawals, and unrelated adjustments.
- **Execution-cost estimates:** retain spread/slippage estimates and their
  reference prices separately. Actual fill-to-fill P&L already reflects execution
  prices; do not subtract the same spread/slippage again.
- **Net operator benefit:** broker net trading P&L less attributable recurring
  infrastructure, data, AI, and relevant conversion costs not already included.
  State allocations and missing inputs. Record operator minutes separately.
- **Tax and development costs:** state inclusion/exclusion explicitly. Do not
  claim after-tax income or "all costs included" if material values are unknown.
- **Economic result:** report net expectancy in initial-risk units, drawdown,
  losing streaks, trade count, exposure, exit reasons, costs, uncertainty, and
  selection effects. Predeclare decision rules and retain failed experiments.
  Demo fills do not establish equivalent live execution economics.

Use cash-flow-adjusted marked-to-market calendar returns, including flat days,
open positions and the actual risk pauses. Preserve intraday peaks for risk;
daily returns alone cannot measure intraday drawdown. Model a cash alternative
and recurring expenses honestly. Missing capital/cost inputs yield an
INCONCLUSIVE business case, while independent engineering may continue.

## Swap-aware hold/close policy across Waves 1–3

The operator requested this planning addition on 10 September. The
[research specification](../../Research/2026-09-10-swap-aware-hold-or-close.md)
provides primary sources and detailed reasoning. This updates wave scope only;
it does not deploy a policy, choose numerical thresholds or authorise a new exit.

| Wave owner | Deliverable | Boundary |
| --- | --- | --- |
| W1.1–W1.4 | Canonical holding mandate, broker swap calculator, financing-inclusive risk/entry checks, decision audit and approved protected-exit fallback. | Accurate costs and safe execution; no invented overnight edge and no dependency on completing W3 before qualified intraday operation. |
| W2.1–W2.2 | Point-in-time financing/conversion/calendar history and matched hold/close replay through the shared kernel. | Qualify data and counterfactual limitations; no retroactive current-rate substitution or policy optimisation. |
| W3.1 / W3.3 | Bounded holding-rule study, calibrated horizon evidence and conditional Demo qualification. | Remain inside the declared search budget; no automatic promotion or added order authority. |

At decision time t and a declared horizon H, compare the two net liquidation
outcomes in AUD:

    incremental hold value = E[net liquidation value at H | information at t]
                             - net liquidation value now

Include possible stop/target/time exits, signed future swap and differences in
closing costs. Already incurred entry costs/accrued charges are common to both
choices; retain them in lifetime P&L without deducting them twice. A TP target,
current unrealised gain or positive swap is not a validated expected benefit.

HOLD requires fresh supported costs, qualified horizon evidence, a conservative
lower confidence bound above a predeclared net-benefit buffer, and all Option B,
protection, duration and eligibility gates. Otherwise use the approved close or
incident-handling fallback. Unknown account/quote state never authorises blind
flattening or a false closure. Do not fund additional risk from uncertain swap
credits or widen stops. Record inputs, decision, reasons, policy/data/model
versions, estimates and actual outcomes in the existing durable ledger.

Before execution, resolve only missing holding mandate values: maximum duration,
weekend treatment, broker rollover/calendar, cutoffs, freshness, fallback exit and
failed-close behaviour. Before economic evaluation, freeze the forecast horizon,
confidence method and benefit buffer. Reuse established approvals; adding this
plan does not approve any unspecified numerical rule. Current M20.13 is analysis
only: map any execution-influencing exit change to an explicit contract amendment.

## Minimal architecture and autonomous operation

Reuse Python, PostgreSQL, the fixed adapter and T480 scheduler. Add only a
shared pure policy kernel, qualified data/cost inputs, small append-only
experiment/trial records and reproducible reports. Do not add a graph database,
message bus, separate engine service, nine-timeframe search or dashboard rewrite.

Deterministic code owns collection, execution, protection, reconciliation and
risk. Use explicit state-transition diagrams and existing durable records;
show service health, evidence state, entry permission and broker lifecycle
separately. There must be one entry writer per account/server. Unknown exposure
never becomes flat because a service restarted or a timeout expired.

LLMs may propose research and explain verified results under recorded call,
cost and retry limits. They cannot alter evidence, risk, strategy versions or
operating authority. An LLM veto changes a trading policy and requires its own
evaluation. No always-on LLM is needed for the execution loop.

## Usage controls and stopping

Use targeted reads, compact command output, a single primary implementation
thread, focused tests during edits, and required broader checks at completion.
Do not repeatedly review unchanged code or rebuild working infrastructure.
Use the repository's required review workflow; do not spawn extra agent teams
merely to accelerate the wave.

Save a handover before a budget boundary. A budget limit does not make work
complete and does not waive testing or proof. Do not silently expand scope,
increase the budget, or continue into the next wave.

Do not spend repeated AI turns polling for a market event or enough trades.
Use approved ordinary service/scheduler collection where available. Report
pending proof and the exact resumption condition so the operator can pause the
goal and resume after observations exist. The operating service may continue
only within its own existing authority; pausing AI work must not disable position
protection. Never mark an unfinished goal or milestone complete to stop waiting.

## Required activity record and handover

For every activity, record the observed problem with source references, exact
changes, mission value, dependencies/exclusions, measurable acceptance criteria,
real-world test and safety/rollback arrangements, raw evidence, independent
verification, and failure/inconclusive conditions.

Create or update one concise report for the wave in `docs/milestones/` when
executing. Link sensitive raw evidence by its retained location rather than
copying it into tracked documentation. Record implementation and test results
separately from proof status and economic findings. A documentation report is
not itself real-world proof.

Use per-criterion PASS/FAIL/PENDING and explain any BLOCKED dependency. Reserve
SUPPORTED/REJECTED/INCONCLUSIVE for the predeclared economic assessment. Include
remaining operator decisions, proof invalidations, and exact next actions.
