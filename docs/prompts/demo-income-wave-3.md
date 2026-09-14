# Wave 3: Parallel Demo strategies, observation and refinement

Revised 2026-09-12 at Chris's direction. **Current implementation and Demo
observation plan; not a launch or completion claim.** Read the
[shared guide](demo-income-waves.md), relevant W1/W2 handovers and
[source review](../../Research/2026-09-10-fx-literature-source-review.md).
The [research goal alias](research-trading-wave-goal.md) contains the identical
goal prompt. [Deployment detail](../parallel-demo-streams.md).

Keep the existing M1 stream operating and add one independently owned
longer-hold EUR/USD Demo stream. Use established research and documented
judgment to choose a simple initial rule. Verify correct implementation,
execute under a bounded Demo mandate, observe and refine. Profitability,
statistical significance and replication of academic results are not
prerequisites to Demo entry. Demo outcomes are observations, not Live returns.

This supersedes the earlier mandatory shadow-first, economic-support-before-
Demo and multi-variant holding-study sequence. It does not waive operational
safety, change M1 exits, provision an account or increase approved risk limits.
The purpose is executable learning with low operator effort, not a daily
trade or income quota.

## Activities, success and actual observations

| ID | Deliverable | Acceptance | Demonstration |
| --- | --- | --- | --- |
| W3.1 | Define and implement one longer-hold H_SLOW policy alongside the frozen M1 baseline. Reuse existing execution/data components and add isolated ownership. | Complete executable rules, explicit assumptions, required inputs, account routing, Demo mandate and focused correctness checks. No mandatory profitable backtest, shadow observation duration or forecast model. | Replay suitable retained inputs to check rule behavior; test invalid data, sizing, stops, restart, duplicate refusal and cross-stream isolation. Read back the configured Demo account/release before activation. Tests are engineering evidence, not completed broker proof. |
| W3.2 | Operate the two streams with separate records and low-attention monitoring. Shared data/events serve both without mixing accounts or positions. | Per-stream signals, rejections, attempts, orders, positions, costs and outcomes; combined exposure/risk view; deterministic protection survives absent LLM/T16. | Collect genuine Demo observations through ordinary services. Reconcile exact broker identifiers and costs for each stream. Demonstrate that one stream cannot modify, close or overwrite the other's state. Record missing observations without forced trades. |
| W3.3 | Review execution and economics, decide one bounded refinement, and retain a clear handover. | Separate operational, economic and business verdicts; version every change, preserve losses and uncertain outcomes; no automatic strategy retuning or risk escalation. | Independently reconcile retained records and reproduce the report. Assess observed results at recorded checkpoints; introduce a single versioned refinement only through the applicable Demo deployment checks. Preserve all required milestone reviews and proof. |

These activities are not a requirement to finish all economic analysis before
W3.2 can submit a Demo order. Activation follows W3.1's applicable operational
checks and mandate; W3.3 uses the subsequent observations.

## Dependency rules that support progress

- M1 continues under its existing approved policy. Repair outstanding critical
  exposure/protection/accounting defects before adding another executing stream.
- Reuse W1's valid reliability work and W2's inputs/calculators as needed. A
  whole-wave completion label is not a substitute for checking the specific
  capability, nor is an unrelated pending proof a new Demo-entry gate.
- Historical data must cover the rule's actual warm-up and decision inputs.
  A multi-year evaluation dataset or untouched historical holdout is not
  required to begin prospective Demo observation.
- Broker charges needed for risk/sizing must be observed or covered by an
  explicitly approved labelled Demo estimate. Unknown charges are not zero.
  Existing intraday allowances do not automatically qualify overnight costs.
- Missing business capital, household-income targets, a full billing period
  or statistical precision limits the relevant business claim, not otherwise
  permitted Demo operation.
- Preserve the active formal milestone and exact scope. If isolation, account
  routing or holding changes are outside its contract, prepare the amendment
  before dependent implementation. This plan is not an implicit registry edit.

## Initial strategy scope

**M1 baseline:** retain the actual versioned composite, selection precedence,
minute-scale exits, sizing and risk controls. Do not silently substitute a
different strategy or turn higher-timeframe context into entry authority.

**H_SLOW:** one slower trend-following rule selected on published evidence,
simplicity and feasible inputs, not the best result from a parameter search.
The implementing agent must choose and record the source rule and adaptations,
then specify before the first order:

- signal, lookback, warm-up and completed-bar/availability semantics;
- signal/rebalance clock and eligible entry conditions;
- sizing, minimum-lot feasibility, stop placement and applicable account limits;
- exit/reversal behavior, maximum hold, overnight and weekend treatment;
- financing, conversion and gap assumptions; missing-data and failed-close behavior;
- exact stream/account/terminal identity, release/configuration and review/end conditions.

The strategy name is not an executable specification. Do not keep asking the
operator to select indicators: exercise judgment within the approved scope.
Request only genuinely missing account, exposure or holding authority. Record
inferences as assumptions; published evidence does not guarantee this adaptation.

H_SESSION, H_EVENT, carry, directional news trading and a calibrated hold/close
forecast model are deferred refinements, not required parallel deliverables.
Start with M1 plus H_SLOW. Review one substantive refinement at a time, retaining
every attempted version. No session × event × timeframe × holding grid.

## Separate ownership and deployment

Preferred initial deployment is a separately configured GOMarketsMU-Demo
account and terminal instance for H_SLOW, in the same repository and on reused
infrastructure where suitable. Account/terminal selection is pending; never
silently select a saved login. Each stream needs separate leases, local files,
monitor jobs, account-scoped reservations/idempotency and broker attribution.

Do not launch two copies of the current single-position executor. Verify that
each monitor can affect only its exact owned tickets. Account separation does
not by itself establish state separation: test filenames, database keys,
restart recovery and routing. One entry writer per account/server remains.

A shared-account alternative requires atomic aggregate reservations, verified
hedging/netting semantics and explicit per-stream/total position and exposure
limits. The current one-position cap is unchanged. Any two-position mandate
must be recorded before activation; this plan does not grant it. Do not double
the total experiment budget merely by creating another Demo account.

Read back account/server, deployed policy and protection configuration before
the first order. Record a deterministic disable-new-entries/rollback path that
preserves management and reconciliation of existing positions. Do not switch
accounts while their exposure or pending attempts are unresolved.

## Proportionate pre-Demo checks

Run focused automated checks for signal direction, completed data and clock
handling, valid lot/stop/margin calculations, account binding, entry persistence,
duplicate refusal, position ownership, restart recovery and broker reconciliation.
Reuse valid prior results where applicable and retest affected behavior after
material changes. Do not rerun unchanged infrastructure merely for a new label.

A short replay or calculation-only shadow run can check code parity. There is
no minimum profitable sample, mandatory shadow-duration gate or requirement to
reproduce a paper before an authorised Demo trial. Use genuine broker responses
to check the actual surface; fault injection does not establish broker behavior.

Keep Demo entry permission distinct from formal proof of its full lifecycle:
the first naturally eligible order generates evidence that cannot exist before
execution. Missing lifecycle proof remains pending for closeout, not falsely
marked complete. Never force an order or bypass a risk pause to obtain evidence.

## Economic-event layer

Wave 2 owns a small reusable module in this repository. Begin with US CPI,
US Employment Situation, FOMC and ECB policy decisions/press conferences.
Retain source, scheduled UTC time, original timezone, currency, first-known
time, revisions and coverage health. Label incomplete coverage explicitly.

Initially annotate M1 and H_SLOW decisions and outcomes. Missing optional
annotations do not block either strategy or manufacture a CLEAR calendar
result. Do not introduce a 30-minute blackout or directional news rule by
default. If an event-based eligibility rule is later activated, version its
coverage, timing and fail-closed behavior before it influences orders. Existing
mandatory eligibility controls remain in force.

## Observe, report and refine

Start a compact versioned trial record before activation: hypothesis/source,
assumptions, rules, account scope, release/configuration, Demo risk/holding
mandate, review clock and stop/end conditions. Reuse the ledger; no new research
service is needed.

Use ordinary T480 services for collection while the operator or coding agent
is absent. Report per-stream and combined exposure, marked-to-market results,
drawdown, financing, rejected opportunities, incidents and coverage. Separate
actual broker net from simulations and execution-cost estimates; do not deduct
spread/slippage twice or count deposits as returns.

Default reporting cadence is daily automated operational summaries and a weekly
human-readable performance review, configured before operation. These are
reporting checkpoints, not minimum trade counts or proof of sufficient data.
Existing configured risk/incident checks continue at their required frequency.
Low counts or slow trades yield a limited/inconclusive economic assessment,
not a manufactured winner or automatic pause. Mandate expiry, risk limits and
explicit stop conditions still apply.

No automatic retuning after losses. Diagnose execution failures immediately;
consider strategy changes at recorded reviews. Explain the proposed change,
keep the earlier version's outcomes, check affected behavior and deploy only
under the applicable versioned Demo authority. Never reset risk anchors or
increase size to recover losses.

## Economic claims and future funded readiness

Record three separate statuses:

- **Operational:** ready, pending or failed, with the exact affected capability.
- **Strategy economics:** observed results and uncertainty; supported, rejected
  or inconclusive only against explicitly recorded criteria.
- **Operator viability:** supported, rejected or inconclusive using actual
  attributable costs and a declared feasible capital/effort basis.

Uncertain or negative economics is learning, not an implementation pass or a
guarantee of eventual profitability. An adverse result warrants a review against
the trial's stop conditions; a safety breach blocks the affected execution.

Historical replay and statistical analysis remain available for specific
questions. Do not require a fixed six-week sample, 10,000 bootstrap replications,
White/SPA procedure or simultaneous confidence bounds to launch Demo. If making
a confirmatory edge claim or funded recommendation, specify suitable benchmarks,
evaluation windows, cost stress and uncertainty/selection treatment before
evaluation; preserve all prior trials and avoid holdout tuning. Do not stop the
analysis at the first profitable interval. M1 need not outperform H_SLOW, nor
must H_SLOW outperform M1 to be permitted as a Demo experiment.

Actual financing, fees, recurring expenses, realistic capital and genuine
candidate Demo execution remain relevant to Wave 4. Unknown material costs
or inadequate evidence prevent a supported funded recommendation. The current
GOMarketsMU-Live prohibition and separate funded-approval requirements remain.

## Continuity and completion

Reuse valid W1 recovery evidence. Do not impose a new four-hour/seven-day
observation prerequisite to Demo activation. Measure unattended operation over
the trial and retain missing proof against whichever contract requires it.
A repeat host-reboot drill still needs an authoritative unresolved-attempt and
exposure preflight, approved maintenance conditions and protection continuity;
do not run one just to fill a report.

Save docs/milestones/demo-income-wave-3-report.md and a compact versioned
Research/experiments/<id>/protocol.md and report.md. Keep sensitive raw evidence
in retained ignored locations, separate from verification. Report per-activity
implementation, actual operation, pending proof and economic conclusions.

No full two-stream operational completion claim until both actually execute
through their required broker lifecycle and isolation is demonstrated. No
profitable outcome is required for an honest economic report. Only the formal
closeout command may close a milestone after its declared real-world proof,
current bound Triad-plus-domain review and required sign-off. No new milestone
or goal is started by editing this plan.

## Copy-and-paste goal prompt

```text
/goal Execute Wave 3: Parallel Demo strategies, observation and refinement. Read docs/prompts/demo-income-waves.md and docs/prompts/demo-income-wave-3.md in full, the relevant W1/W2 handovers, docs/parallel-demo-streams.md and Research/2026-09-10-fx-literature-source-review.md. Use this revised wave, not the superseded research-first sequence.

Preserve the operating M1 Demo stream and finish applicable critical execution dependencies. Define and implement one isolated longer-hold H_SLOW stream using published evidence and documented judgment. Specify the exact rules, warm-up, sizing, protection, holding/financing treatment, account routing, review/end conditions and Demo mandate. H_SESSION, H_EVENT and conditional holding-model studies are deferred; no broad strategy search.

Inspect Git status, AGENTS.md, project_state.json, the active milestone contract and docs/evidence_and_milestones.md. Map implementation to the active approved scope and prepare exact amendments where needed. Reuse existing approvals; request only genuinely missing authority. This goal does not waive formal milestone dependencies or authorise the next milestone automatically.

Run proportionate correctness and isolation checks, reuse valid prior evidence, then enable the exact authorised Demo stream without requiring a profitable backtest, statistical significance, academic replication or a mandatory shadow-performance period. Do not bypass account identity, fresh required data, exposure, protection, risk, persistence or reconciliation checks. Keep first-order eligibility separate from lifecycle proof generated by subsequent operation.

Use separate account-scoped stream state and preferably separately configured Demo accounts/terminals. Do not select a saved account or relax the current one-position/aggregate risk caps implicitly. No second copy of the single-owner executor. Initial economic-event work annotates observations; it does not silently veto trades.

Collect and reconcile both streams through ordinary services. Report daily operational summaries and weekly performance reviews unless an existing approved cadence applies. Keep actual costs, unknowns, rejected opportunities, losses and every strategy version. Review one substantive refinement at a time; no automatic retuning, risk escalation or LLM order overrides.

Continue independent authorised work when a market observation is pending. Do not repeatedly poll or wait for arbitrary sample counts. Save exact pending proof and resumption conditions in docs/milestones/demo-income-wave-3-report.md and compact versioned trial records. Report operational readiness, strategy economics and operator viability separately; missing evidence remains pending or inconclusive.

Preserve Option B, GOMarketsMU-Demo-only EURUSD, deterministic protection and the GOMarketsMU-Live prohibition. No Live access, new milestone, unspecified risk/holding authority, commit, push, branch or PR is granted by this prompt. Honour only explicit existing authority within scope. Formal closeout retains real-world proof, current bound Triad-plus-domain review and required sign-off. Respect only an explicitly supplied goal budget.
```
