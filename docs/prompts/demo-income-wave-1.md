# Wave 1: Trustworthy Demo execution

## Operator priority amendment — 2026-09-10

Get core Demo execution working first. Backup and isolated-restore proof is
explicitly deferred to [W4.0](demo-income-wave-4.md), before a funded pilot;
its absence is not a Wave 1 deployment, migration or recovery-drill blocker.
This supersedes earlier backup gates in the recovery package and handovers.
Keep Option B, Demo-only access, maintenance entry holds, fresh exposure/audit
checks, ledger/risk-state preservation and required execution evidence.
This amendment does not itself complete Wave 1 or authorise Live trading.


Revised 2026-09-10. **Current plan for the active execution-safety work.**
This documentation update does not resume a goal. Preserve prior implementation,
evidence and explicit approvals; the current handover determines remaining work.

Read the [shared wave guide](demo-income-waves.md). This wave covers original
activities 1–4. Its purpose is reliable exposure and accounting under durable
risk limits; it does not establish a profitable strategy.

## Recovery work package: W1.R

The [T480 reliability and recovery work package](demo-income-wave-1-recovery-work-package.md)
packages the 7 September blocker review into R1–R7: diagnose interruptions,
correct recovery/exposure states, coordinate maintenance, prove T480 continuity,
retain incident alerts, then finish the original broker evidence. It maps to
W1.1–W1.4 below and supplies their proposed remediation schedule; it is not a
new wave or milestone. Shared-platform changes remain owned by `cs-ai-lab-infra`.

Reuse prior Wave 1/W1.R work and explicit approvals. The original package's
7 September observations are historical, not current host status. Revalidate
findings and contract scope before dependent changes, particularly the
no-logon reboot dependency. Do not redo a repaired bug merely because the
original plan still describes it.

## First priority: independently persistent risk pauses

The [10 September review](../../Research/2026-09-10-live-forex-readiness-review.md#reproduced-option-b-defect)
reproduced a W1.4 defect in `enforce_risk_policy`: simultaneous daily, weekly and
peak-drawdown breaches retain only the daily reason. Equity recovery followed
by a new day can clear it without required manual review. Verify against the
current implementation first, then repair before final release/proof.

Acceptance requires all applicable breaches to be recorded independently.
Manual-review reasons survive equity recovery, day/week rollover, process
restart, lease renewal and maintenance release. Resume clears only the reasons
and anchors allowed by the approved policy and records its authority. A fresh
breach immediately blocks entry again. Do not change Option B thresholds to
make this work or increase risk to compensate for pauses.

## Activities, success, and real-world tests

| ID | Change and mission value | Success criteria | Real-world demonstration |
| --- | --- | --- | --- |
| W1.1 | Align M20, runtime limits, deployment, and operator documentation. The operator approved no total trade-count ceiling during development; retain the independent exposure and loss limits. | The approved unlimited development count policy matches contract, canonical config, effective release, and displayed limits; no unresolved contradictory execution rule. | Read back effective Demo limits and deployed release/configuration identity through the fixed surface; independently compare with approved artefacts. |
| W1.2 | Correct API-error, empty-position, open, partial-fill, rejected, and unknown states. Reconcile exact broker identifiers and opening/closing volume. This prevents false closures and unmanaged exposure. | API error never means flat/closed; partial or uncertain execution remains exposure-aware; entry-only history cannot close a position; retry/restart cannot duplicate an order. | Capture a genuine Demo OPENED-to-CLOSED lifecycle and controlled connection interruption/recovery. Compare application state with broker positions/deals. Retain actual partial-fill proof if observed; otherwise label that real-world condition pending and retain fault-injection coverage separately. |
| W1.3 | Reconcile fills, close volume, commission, fees, swap, and currency P&L; separate actual amounts from estimates. Trustworthy net results are necessary for strategy selection. | Every reported closed outcome matches attributable broker transactions within predeclared currency-rounding tolerance; no entry-as-exit, balance-as-profit, or duplicated execution cost. Incomplete history stays unresolved. | Independently recompute a predeclared sample of genuine closed Demo outcomes and aggregate totals from retained broker records. Include nonzero charge examples where actually available; zero-cost rows cannot prove nonzero-fee handling. |
| W1.4 | Repair independent durable risk latches and enforce remaining loss headroom, including applicable charges and reserved exposure. Size down from the intended valid technical stop or refuse an infeasible minimum lot; do not tighten the stop simply to fit the cash cap. | Simultaneous breaches persist independently; daily reset/recovery cannot erase a manual-review reason. Budgets survive restart/session renewal; account cash flows are classified; fees/reservations cannot overspend headroom; unknown state blocks entries while protection continues. | Reproduce overlap/recovery/day-rollover with the actual risk function and isolated persistent integration state. Separately retain a real protected Demo listener restart and deployed refusal under the approved temporary AUD 0.01 cap, followed by immediate Option B restoration. Never induce losses or seed fabricated state into the operating account to demonstrate a breach. |

### Swap and holding safeguards — W1.1–W1.4

Added by operator planning instruction on 10 September. Read the
[swap-aware hold/close research](../../Research/2026-09-10-swap-aware-hold-or-close.md).
These are subactivities of the existing four activities, not a new wave or
permission to activate an overnight strategy. W1 supplies accurate costs,
deterministic controls and an approved fallback; W3 supplies evidence of edge.
Do not block otherwise qualified intraday Demo execution on a W3 forecast.

| Owner | Change and why | Success criteria | Real-world demonstration |
| --- | --- | --- | --- |
| W1.1 | Version the holding mandate in canonical configuration: maximum duration, broker rollover/calendar, review and entry cutoffs, freshness, fallback exit and weekend policy. | Effective deployment matches the approved settings; no assumed zero financing or silent forced-close rule. Identify exact contract amendments before dependent implementation. | Read back configuration/revision from T480 and compare with the approved policy and recorded decision. |
| W1.3 | Add one signed AUD swap calculator and reuse the fee-complete ledger. Capture side, volume, calculation mode, rates, day multipliers, currencies, conversion sources and timestamps. | Support the observed broker mode first; missing/unsupported data is unknown. Projected, accrued and posted charges remain separate; each actual adjustment is attributed once, including partial closes. | Compare estimates recorded before rollover with genuine authorised Demo postings, within a predeclared currency-rounding tolerance. Ordinary and triple/holiday cases need actual observations where applicable; unobserved cases remain unqualified, never inferred from zero-swap closes. |
| W1.4 | Include adverse financing through the maximum holding horizon in planned loss and entry cost feasibility. | Option B and valid SL/TP remain intact; uncertain swap credits do not increase risk capacity. Reject entries whose required costs are unknown or exceed headroom. TP feasibility is not expected return. | Retain deployed refusals with real broker inputs; separately test signed charges, currency conversion and cap crossings through the actual calculator/reservation path. Do not manufacture trades or losses. |
| W1.2 / W1.4 | Add a deterministic pre-rollover position review and approved fallback, using the existing protected close/recovery path. | Record HOLD, CLOSE or REVIEW_REQUIRED with inputs, policy version and reasons. Without qualified horizon evidence, do not grant new overnight authority. Pending/failed exits preserve protection, block new entries and retain incidents; they never mean CLOSED. | Observe the approved boundary on a genuine eligible Demo position, reconcile any close with the broker, and retain recovery evidence. Failure injection is separate engineering evidence. If no eligible position occurs, record the missing proof and resumption condition. |

Qualification is specific to the approved holding mandate. Unobserved overnight
or special-day charges prevent claiming those cases qualified; they do not
require opening or extending a trade for proof. State which criteria apply to
the approved intraday fallback and which remain pending for overnight eligibility
in the exact contract amendment. Do not waive applicable accounting or exit proof.

Use one calculator, one evaluator and the existing execution/ledger components.
Run checks at entry, sufficiently before rollover for normal execution, and on
material risk/cost changes. An approved intraday fallback may permit qualified
intraday entries with enough time to exit; inability to confirm an exit remains
an exposure incident, not a guarantee that swap cannot occur.

The conditional evaluator uses the shared guide's incremental-value rule.
W1 must not fabricate a return estimate, use an LLM confidence score or convert
a TP target into expectancy. A qualified model is not a W1 deliverable: record
EVIDENCE_UNQUALIFIED and apply the approved fallback until W3 authorises an
exact policy after its evidence and Demo qualification gates. Preserve any
existing explicit authority while mapping the amendment; this document alone
does not change exits. M20.13 currently permits protected-exit analysis only,
so an execution-influencing holding/exit change needs an exact contract amendment.

### W1.4 verification matrix and scope

Cover daily+weekly+drawdown simultaneously; recovery before next check;
day/week rollover; restart; maintenance release; session renewal; cash-flow
pause overlap; permitted resume; and a current breach immediately after resume.
Use actual function behaviour and an isolated database fixture for synthetic
equity paths, labelled as engineering evidence. These checks supplement the
required real Demo lifecycle, refusal and persistence observations; they do
not claim an actual broker drawdown occurred. Any additional broker-surface
drill beyond existing approvals needs its exact constraints agreed first.

Bind persisted risk and entry serialization to the approved account/server
where required to avoid cross-session ambiguity. Do not introduce multi-account
execution. Preserve valid technical stop semantics during sizing; document
any exact rule/contract amendment before deploying a changed plan.

Order of work: read current status without restarting a healthy listener;
reproduce the latch defect and remaining lifecycle issues; perform narrow
repairs and local verification; coordinate W1.R deployment/recovery; freeze one
reviewed release; capture only the missing W1.1–W1.4 proof. Reuse the existing
AUD -0.29 cash-flow confirmation solely for that close.

## Starting points to revalidate

- `t480/m20_demo_trading_session.py`: position queries, order result mapping,
  history selection, monitoring, sizing, and cost capture.
- `t480/m20_postgres_audit_bridge.py` and `sql/migrations/`: reservations,
  durable state, outcome integrity, and cap enforcement.
- `t480/m20_demo_listener_service.py`: restart and stop behaviour.
- `config/runtime.yaml`, schemas, and `milestone_registry.json`: effective
  operator policy and contract consistency.
- Actual runner behavioural tests and active milestone verification commands;
  source-string assertions alone do not prove runtime behaviour.

These references are investigation starting points, not authorisation to
rewrite every component. Keep changes narrow and preserve historical records.

## Completion and exclusions

Prepare the activity plan and missing operator decisions first. Option B is
already approved; do not request those same tolerances again. Do not change
them or amend the contract beyond existing authority.
Complete independent authorised fixes while dependent work awaits decisions.

Wave completion requires its approved acceptance criteria and declared proof,
with no unresolved critical exposure or accounting defect. If a rare condition
cannot be observed, report the precise proof gap; do not silently weaken the
criterion. A progress handover does not claim completion.

Exclude new strategies, new AI trading influence, parameter optimisation,
additional instruments/positions, live access, and new infrastructure platforms.
Do not start Wave 2 or close M20 merely because Wave 1 tests pass.

## Copy-and-paste goal prompt

```text
/goal Execute Wave 1: Trustworthy Demo execution in this repository. Read docs/prompts/demo-income-wave-1.md, docs/prompts/demo-income-waves.md and docs/prompts/demo-income-wave-1-recovery-work-package.md in full and treat their activity specifications, shared boundaries, evidence rules, and usage controls as this goal's execution brief. Use W1.R's R1-R7 dependency schedule for the reviewed recovery work, preserving completed work and W1.1-W1.4 acceptance. Check the current cs-ai-lab-infra state and coordinate shared-platform dependencies without automatically starting another milestone.

Include the swap/holding subactivities under W1.1-W1.4: qualify actual broker financing, version the holding mandate, include adverse financing in entry/risk checks, record deterministic reviews and implement only the approved protected-exit fallback. Do not invent overnight expectancy or wait for W3 to permit otherwise qualified intraday Demo operation. Obtain the exact holding/exit amendment before changing execution semantics.

Scope is W1.1-W1.4 only: align approved contract/configuration/deployment; correct order and position lifecycle handling; reconcile net broker P&L and costs; enforce approved persistent capital-risk boundaries. Verify previous findings against current code before editing.

Prioritise the reviewed independent-risk-latch defect in W1.4. Simultaneous daily/weekly/drawdown breaches must retain every applicable pause; recovery, day/week rollover, restart, maintenance release and lease renewal must not erase manual-review reasons. Reuse Option B, unlimited development trade count and the remaining exposure caps. Verify remaining loss headroom and preserve valid technical stops; document any exact amendment before changing deployed rule semantics. Synthetic equity-path checks remain engineering evidence, separate from genuine Demo refusal/persistence proof.

First inspect Git status, applicable AGENTS.md, project_state.json, the active milestone contract, and docs/evidence_and_milestones.md. Prepare a concrete activity plan and identify missing operator risk decisions or exact contract amendments. Obtain required decisions before dependent changes; continue independent authorised work.

Implement narrowly, test actual runtime behaviour, and demonstrate success on the declared GOMarketsMU-Demo surface with retained raw evidence and separate independent verification. Never substitute mocks for broker proof. Preserve existing position protection throughout drills and budget checkpoints.

Complete only when the approved Wave 1 criteria and proof are satisfied. If evidence, approval, or an external condition is missing, report the exact pending criteria and resumption condition without claiming completion. Save a concise handover in docs/milestones/demo-income-wave-1-report.md. Respect any explicitly supplied goal budget; do not invent or increase one. Avoid repeated market polling and unchanged-code review.

Do not start another wave or milestone or enable Live access or new strategy expansion. This prompt adds no commit, push, branch or PR authority; honour any existing explicit authorisation within its scope. M20 closeout remains subject to its complete contract and bound review gates; passing this wave alone is insufficient.
```
