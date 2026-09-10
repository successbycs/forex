# Proposed wave: Research-based trading and cost validation

> **Historical specification — superseded for future execution on 10 September 2026.**
> Use the [current wave guide](../docs/prompts/demo-income-waves.md) and
> [Wave 3 specification](../docs/prompts/demo-income-wave-3.md). R0/E1–E5 are
> integrated into Waves 1–3; H_SLOW replaces H_H1. The old time windows, source
> observations, decision wording and implementation sequence below are retained
> as history, not a second execution brief. Correctly enforced risk pauses are
> measured policy behaviour under the current protocol, not automatic failure.
> This supersession changes planning only, not runtime or milestone authority.

Prepared: 7 September 2026. Status: **SPECIFIED AND SELF-REVIEWED; NOT EXECUTED.**

This is the detailed execution specification for the [research proposal](2026-09-07-fx-edge-research-and-proposed-wave.md). Read the [design review](2026-09-07-research-trading-wave-review.md) and the [goal prompt](../docs/prompts/research-trading-wave-goal.md). Saving these documents grants no new trading authority.

## Outcome and scope

Answer a useful business question: can a small, reproducible trading rule produce a credible surplus after broker charges and recurring operating costs, within Conservative Option B, with little operator intervention?

Deliver a reliable T480 research collector, trustworthy accounts, two frozen shadow experiments, and a reproducible decision report. A finding that neither candidate is viable is a successful research outcome. Profitability, production readiness, and milestone completion are separate claims.

The core wave is **R0 plus E1–E5** below. E6 remains a separately authorised research extension. This specification develops the earlier E1–E6 proposal; it does not renumber milestones or silently replace the existing three-wave plan.

| Existing work | Reuse in this wave |
| --- | --- |
| [Wave 1](../docs/prompts/demo-income-wave-1.md) | Lifecycle correctness, actual broker fees, persistent risk controls, deployment and recovery proof. Finish the required dependencies; do not build a second ledger. |
| [Wave 2](../docs/prompts/demo-income-wave-2.md) | Honest eligibility and deterministic replay/execution parity. Retain its scope and policy requirements. |
| [Wave 3](../docs/prompts/demo-income-wave-3.md) | Frozen economic evaluation, operator effort, independent evidence verification. Use the experiment definitions below. |
| M20.12 / M20.13 | Existing read-only M5/H1 context and planned cost-aware analysis. Neither authorises changing execution rules. |
| M13–M16 historical/replay work | Inspect existing data, replay and evaluation before adding code. Their historical proof cannot establish current Demo execution or decision parity. |

At preparation, `project_state.json` names M20 and reports `NEEDS_FIX`. The latest section of the [Wave 1 report](../docs/milestones/demo-income-wave-1-report.md) clears four legacy reconciliation blockers but leaves fresh lifecycle and risk/recovery proof pending. Its older opening paragraphs are historical progress statements, not the latest deployment status.

Before implementation, map each change against the current M20 contract. Prepare any necessary amendment as an exact diff and obtain authority for it before dependent work unless the session already explicitly approves that exact change. Complete independent local analysis while a dependency is pending. Do not start M21 or change M20's five-strategy execution ownership through this wave.

## Activities, acceptance and real-world tests

The numeric checkpoints below are proposed engineering defaults. Authorising this specification adopts them for the experiment; they are not claims from the literature. Operator capital, income requirements and actual expenses must still come from attributable operator inputs.

| ID | Change and why it matters | Definition of success | Real-world demonstration |
| --- | --- | --- | --- |
| R0 | Complete relevant Wave 1 dependencies and make T480 collection reliable without T16 attendance. An intermittent collector biases samples and cannot support passive operation. | Diagnose the stale heartbeat; fix and test the elapsed-wait defect if confirmed; preserve risk pauses, position recovery and idempotency. Document the actual Windows task, login, power, MT5 and database dependencies. A stale record never means a protected or flat book. | On the exact deployed Demo release, demonstrate recovery with the required Wave 1 safeguards. Then run a full predeclared liquid session of at least four hours with the T16 disconnected, followed by seven calendar days of unattended collection. Retain T480-local continuity records: heartbeat gaps must remain below 30 seconds outside explicitly recorded maintenance; market closures may stop assessments but must leave a fresh waiting heartbeat. Zero duplicate entries, lost pauses or unresolved protective-management failures. Reboot/logoff proof is a separate controlled drill, initially flat. |
| E1 | Extend existing fee-complete accounting into operator economics. Gross wins can conceal an unviable business. | Every included lifecycle reconciles to broker deal IDs and signed charges; missing costs are unavailable, never zero. Report net trading P&L, net operating income, capital, cash-flow adjustments and missing costs separately. | Reconcile the next 20 consecutive post-release closes, including losses, to retained broker history within AUD 0.01 per lifecycle and the documented aggregate rounding bound. Record discrepancies instead of editing raw data. A sample of zero fees does not validate nonzero fee handling; an observed nonzero charge needs its own reconciliation when available. Audit one full billing period of attributable recurring costs. Do not trade to fill the sample. |
| E2 | Produce a daylight-saving-aware broker session-cost map and one fixed session-selection hypothesis. This tests whether execution friction can be reduced. | Include eligible, ineligible and failed observations, quote counts, missingness, spread distributions, executed slippage and rejects, split by session and regime descriptors. State which conclusions apply only to decision-time quotes. Freeze the session rule before evaluating returns. | Collect six calendar weeks prospectively on Demo, with a predeclared end timestamp. Compare actual fills with decision-time bid/ask references and record missing fills. Verify timezone handling against known London/New York transition dates; fresh transition-week coverage stays pending until observed. Publish coverage even if it is insufficient. |
| E3 | Evaluate one H1 alignment filter in shadow mode using existing closed-bar context. This tests incremental value without assuming an academic monthly effect applies to H1. | Reproduce every candidate decision from data available at its decision time; make no change to actual strategy selection, orders, stops or sizing. Compare two independent simulated state machines, with the same risk limits and initial capital. | Replay an untouched chronological holdout and retain six weeks of prospective shadow decisions alongside the baseline. Verify genuine decision snapshots through shared logic, including neutral/opposed/missing H1 cases. Label counterfactual entries/exits as simulated. Only actually executed orders establish broker fills. |
| E4 | Add a small experiment registry, time-safe replay and selection-aware inference. Prevent a lucky variant from becoming an apparent edge. | Retain all attempted rules and parameter variants, hashes, development dates, holdout dates, costs, trials and failed results. Preserve the full family for multiple-comparison testing. Shared deterministic logic passes genuine-snapshot parity. No holdout leakage or optimistic within-bar fills. | An analysis-only verifier rebuilds the report from immutable captures without querying or repairing the source. It reproduces decisions and statistical outputs with the recorded seed and tolerances. Negative controls deliberately introduce future bars, omitted fees and family omission; the pipeline must reject or explicitly invalidate these analyses. |
| E5 | Apply a predeclared economic and operational decision gate. Measure whether research supports the human's income mission. | Deliver SUPPORTED_FOR_FURTHER_DEMO, REJECTED or INCONCLUSIVE with net amounts, uncertainty, drawdown, cost stress, sample limitations and operator minutes. No automatic promotion or production claim. | At the frozen evaluation date, reconcile the executed baseline and evaluate the shadow candidates under the rules below. Independently verify the report. A shadow candidate must subsequently pass a separately authorised executed Demo trial before it can obtain broker-execution support. |
| E6 — deferred extension | Reproduce one diversified monthly currency-momentum benchmark to test whether the M1 strategy family deserves further investment. | Exact source methodology, currency universe, point-in-time membership, financing, turnover, costs and exposure are reproducible. No instrument is added to the executor. | Use licensed, attributable historical data and retain prospective monthly shadow signals. Without executable financing/cost data, results remain a research illustration. Prepare a separate research contract and goal; E6 does not silently enter the core wave. |

## R0: T480 finding and required correction

The repository already deploys `Forex-M20-Demo-Listener` as a Windows Scheduled Task running local Python payloads under `C:\ProgramData\ForexListener`. The runner invokes the audit bridge through local WSL. The T16 dashboards are observers; the scheduled runner does not need an open T16 terminal or an active Codex conversation.

However, the read-only check during preparation returned `state=STALE`, `running=false`, release `073853dd0cce8d57`, last heartbeat `2026-09-07T02:22:25.338491Z`, age 295.5 seconds. Its last monitor record reported an open Demo position. This is a stale observation, not proof of current exposure or current SL/TP. The fixed adapter retains the raw response in its ignored local execution log.

A second read returned the same heartbeat, now 382.8 seconds old, and retained SELL protection metadata. A subsequent fixed account-liquidity probe reported Demo/AUD and zero open positions. That helper uses `positions_get() or ()`, so its zero count alone cannot distinguish a failed position read from a flat account. It also does not establish a broker-matched closed lifecycle. W1 should use the strict position/history path to settle both questions.

There is a concrete defect candidate in `t480/m20_demo_listener_service.py`, in the idle branch of `run()`: `_monitor_update()` can consume the remaining time before `next_assessment_at`, after which `time.sleep(min(POLL_SECONDS, next_assessment_at - now))` can receive a negative duration. That can raise `ValueError`. Confirm the deployed failure through task/process diagnostics; do not call this the proven cause without them. A meaningful regression test should advance the clock across the deadline during monitoring, verify the loop survives, and verify the next assessment and protective monitoring still run.

The installer in `scripts/t480_adapter.py` uses **AtLogOn**, three restart attempts at one-minute intervals, and no execution-time limit. It does not establish unattended cold-boot or logoff recovery. Read back the actual task principal/settings, power and lid behaviour, startup order, local database location, environment and MT5 availability through fixed read-only diagnostics. Secrets stay local. Add a narrowly scoped Forex status operation if necessary; do not create a generic shell or new shared transport.

First establish a reliable logged-in, awake T480 with the screen locked if required. Before calling it unattended after reboot, prove the approved startup model with the T16 absent and with no exposure during the first drill. If MT5 requires a logged-in desktop, document that constraint and use an approved operational procedure; do not silently introduce password storage or automatic login. Retain diagnostics before recovery so repeated restarts do not hide the cause.

The current latest-status file is overwritten, so it cannot alone prove an uninterrupted interval. Retain a small T480-local continuity log or daily gap summary with timestamps and restart events, sufficient to verify the declared test. This is bounded operational evidence, not a tick store or a new monitoring platform. A fresh supervisor heartbeat also cannot substitute for a fresh, successful protective-monitor result.

This preparation does not deploy a fix, restart the task, launch a new lease or resume a risk pause.

## Frozen research protocol

### Two hypotheses and two comparators

Freeze a `baseline_id` identifying the post-remediation deployed M1 strategy family, precedence, risk policy and all parameters. Earlier records affected by accounting or liveness defects remain visible but cannot be silently treated as clean final evaluation data.

- **H_SESSION:** Baseline decisions restricted to the intersection of 08:00–17:00 `Europe/London` and 08:00–17:00 `America/New_York`, Monday–Friday, subject to every existing eligibility rule. These are explicit research windows, not an assertion of official FX exchange hours. No window search or automatic holiday/calendar inference. Session closure prevents new entries; it does not invent an exit rule.
- **H_H1:** Baseline decisions admitted only when the existing H1 context reports `VALID` and `ALIGNED` for the pre-context M1 candidate, using the frozen five-closed-candle calculation. Require all five bars closed and available by the decision timestamp and the latest close no more than 3,600 seconds old. Missing, stale, opposed or neutral context gives no shadow entry. No new H1 threshold optimisation, no M5 filter, and no combination with H_SESSION in this experiment.
- **Comparators:** the frozen unfiltered M1 baseline and holding cash/no FX position. Record both avoided incremental operating costs for the no-platform cash alternative and common costs for a running-platform/no-trade comparator. Assume no unverified cash interest credit; disclose opportunity cost separately.

Run each candidate with its own simulated position, cash, risk-pause and exposure state. Filtering the list of executed baseline trades is only a descriptive subset analysis: a skipped trade may free capacity for a later trade the baseline could not take. Reconstruct those opportunities from point-in-time data or report the full policy effect as unmeasurable. Do not equate average P&L per retained trade with higher income per calendar month.

### Data and replay

Reuse retained decision snapshots and closed bars. Do not introduce a continuous tick archive. A fixed bounded quote sample, if additional session coverage is needed, requires an explicit retention/scope decision first. Without it, label the analysis as conditional on captured decision opportunities; do not infer unconditional all-day spread distributions.

Before final evaluation, freeze chronological development and untouched holdout intervals. Use existing historical data only where provenance, historical charges, timezone conversion and decision-time availability are adequate. If the historical holdout has already been inspected during strategy development, call it development data and reserve a fresh interval. Never invent an untouched past.

Preserve warm-up bars without scoring their outcomes. Purge overlapping labelled outcomes across split boundaries according to the strategy's maximum holding horizon. Trades crossing a boundary must follow a predeclared allocation rule. Fill long entries on ask and exits on bid, and reverse for shorts. Model order latency, broker minimum volume/steps, rejection and missing quote conditions. If only OHLC bars exist and both stop and target are touched, use the conservative ordering or mark the result indeterminate; no automatic target-first wins. Do not manufacture historic ask bars from a current spread and call them observations.

Replay all required eligibility rules consistently. Current code hardcodes `news_blackout_inactive=True` and uses spread as its abnormal-volatility test. These do not establish event coverage or measured price volatility. Carry forward W2.1: use approved sources/rules, or explicitly mark missing protection. Required missing/stale inputs must block new entries. Keep the existing AUD 0.10 projected net-at-target setting labelled as target feasibility; it is not positive expected value.

### Costs and capital

Use signed broker amounts:

```text
net_trading_pnl = broker_fill_price_pnl + commission + fees + swap
net_operating_income = net_trading_pnl - attributable_recurring_costs
economic_surplus = net_operating_income - optional_priced_operator_time
```

Broker fill-price P&L already incorporates actual execution prices. Spread and slippage measurements explain those prices; do not subtract them again from realised P&L. Allocate separately posted account charges by a documented rule or leave attribution unresolved. Retain original currency and conversion source/time for each charge. Unknown charges block a fee-complete claim.

Keep the denominator of every attempted and executed trade in the evaluation window. Incomplete outcomes may be excluded from the fee-complete subtotal, but must remain in the coverage report and prevent an overall passing economics claim until resolved. Never improve performance by dropping unresolved losers.

Recurring costs include applicable data, API/model use, hosting, incremental electricity, licences, currency conversion and funding/withdrawal charges. Record actual bills, allocation basis and period. Distinguish unavoidable shared expenses from incremental expenses and show the sensitivity. Track one-off development costs separately. Label results **pre-tax** unless the operator provides an applicable treatment; do not imply after-tax income.

AUD is the approved reporting currency. The roughly AUD 101,000 Demo balance is not the human's intended production capital. Before an income viability conclusion, record intended capital, minimum worthwhile monthly net income and operator-time allowance. If absent, produce clearly labelled capital/cost sensitivity scenarios and an INCONCLUSIVE income finding, not an invented target. Broker minimum trade size and risk caps can make a small account infeasible; do not linearly scale Demo returns past those constraints.

### Observation and inference

Freeze the forward start/end timestamps before collection; proposed duration is six calendar weeks after the required dependencies and collector verification. Twenty accounting closes and six weeks are checkpoints, not statistical proof. Log prospective data availability and operating gaps. Observe the original end even if performance is poor or trade count is low. Any extension is a separately approved, versioned window; never extend automatically until positive.

Use daily marked-to-market AUD net returns, including no-trade days and unrealised exposure, with common calendar dates across candidates. Do not count thousands of five-second observations as independent return samples. Retain intraday equity peaks for risk-policy evaluation; daily returns alone understate intraday drawdown.

Before opening final holdout outcomes, record:

1. The complete tested family, benchmark definitions, expected economically meaningful effect, development-only estimate of variability/dependence, and a power/precision assessment. If the available window cannot resolve that effect, describe it as a feasibility pilot.
2. A dependence-aware block bootstrap with 10,000 replications and a recorded seed. Select primary block length using development data and freeze it; report half/double-length sensitivity where statistically meaningful. Do not choose the most favourable length after evaluation. Too few effective blocks means INCONCLUSIVE.
3. A family-level Hansen SPA or White Reality Check at 5%, using a reviewed implementation and aligned net-return/loss definitions. Choose one method before results, never whichever passes. A family rejection does not identify a winning individual candidate. Individual promotion claims additionally require simultaneous 95% one-sided confidence bounds across the tested contrasts, with the same time-block resampling scheme. If implementation cannot be validated, publish descriptive results only.
4. Separate effect estimates against cash and the M1 baseline. Beating a losing baseline is insufficient. Report historical holdout and forward results separately; do not pool them to erase a failure.
5. Base costs, a +50% variable execution-cost stress, and a 2× severe stress. Apply stress to reconstructed simulated costs, or add only the incremental adverse cost to observed net P&L. Include adverse financing where positions can cross rollover; never invent observed financing. Freeze alternative assumptions before evaluation if these defaults are unsuitable.

The goal is a small, inspectable analysis command and report, not a custom statistics platform. Reuse qualified libraries where appropriate, pin the relevant version, and validate their inputs and test interpretation. Preserve all explored variants in the family; undisclosed historical search means the historical significance claim has a known limitation.

### Decision rule

**SUPPORTED_FOR_FURTHER_DEMO** requires all of the following:

- Reproducible, sufficiently complete data; validated inference; positive simultaneous lower confidence bounds for net benefit versus cash and incremental benefit versus M1 on the final evaluation specified in advance. Both historical and forward reports must meet their predeclared roles; if no qualified historical holdout exists, explicitly use a prospective-only design with an adequate predeclared window.
- Positive operator net income under base costs and +50% variable execution-cost stress, at the stated feasible capital, meeting the operator's minimum worthwhile income. Report the 2× stress and its failure point even if it rejects the business case.
- No Option B breach in the claimed passing experiment, no unresolved exposure/protection/accounting incident, and operator effort within the approved budget. Stops constrain entry authority; gaps and slippage can exceed planned losses, so limits are not guarantees.
- Enough elapsed time, effective independent information and market-condition coverage under the frozen protocol. Six profitable weeks alone cannot establish sustainable income.

**REJECTED** means a predeclared material criterion is demonstrably failed: for example, a risk/safety breach, nonpositive realised net income over the stated evaluation window, or an uncertainty bound excluding the economically worthwhile effect. State whether it rejects the observed business case, the implementation, or a stronger statistical hypothesis. A negative estimate with wide uncertainty does not prove the true edge is negative.

**INCONCLUSIVE** covers missing costs/capital, inadequate coverage or precision, corrupted/leaky data, or uncertainty crossing the required effect. Neither an insignificant p-value nor an unobserved rare event is a pass. Keep all unsuccessful results and propose exactly one next action: retire/revise, a separately approved longer observation, or a bounded executed Demo candidate trial.

Shadow support never authorises strategy promotion. The next executed Demo trial needs its own exact rule/scope approval and broker-cost validation. Real-money production remains outside this wave.

## Risk and agent authority

Preserve `config/runtime.yaml` Conservative Option B: planned per-trade loss is the lesser of AUD 100 and 0.10% policy equity; daily loss pause 0.50%; weekly loss pause 1.00%; peak adjusted-equity drawdown pause 2.00%. Preserve Auckland boundaries, approved cash-flow accounting, durable anchors and manual-resume rules.

Demo only: `GOMarketsMU-Demo`, EURUSD, one open position, USD 10,000 per-trade notional and USD 100,000 cumulative lease notional. Development duration is continuous and `maximum_trades` is null. The cumulative notional cap can still stop entries. Do not create replacement leases to bypass it. The process can stay alive while trading is paused.

New research code has no order authority. No live server, new instruments, automatic risk increases, martingale, averaging down, autonomous parameter search, LLM trade selection or self-modifying production rules. Preserve protective management during failures and deployments. AI can implement, analyse and explain evidence; deterministic code enforces risk.

## Implementation sequence and deliverables

1. Inspect state, current release and safety. Close required W1 dependencies and repair R0 within existing authority; record any exact scope amendment first. Diagnose liveness before a long research run.
2. Reuse W2 accounting/eligibility/parity work, add only missing E1/E4 functions, and verify genuine captures. Publish unresolved policy/data dependencies without inventing values.
3. Create and validate the frozen experiment configuration; add E2/E3 shadow outputs and E5 reporting. Human-owned capital/expenses can remain explicitly pending while independent engineering proceeds.
4. Verify the T480 collection/recovery tests, freeze the observation window, and checkpoint. Ordinary code collects between AI sessions. Do not keep Codex polling for six weeks or run repeated reviews of unchanged code.
5. At the declared review condition, independently verify retained evidence and deliver E5 with precise limitations. No automatic next wave or milestone.

Prefer these small artifacts, adapting names to existing modules at execution:

- `config/research_experiment.yaml`: nonsecret hypotheses, versions, calendar, statistical protocol and confirmed economic assumptions; register/schema-validate it if governed. Do not create an enabled runtime configuration during preparation.
- Existing SQL ledger/views plus a small research export/report command; add a migration only where existing fields cannot support required lineage or costs. Existing Python replay functions should supply calculations.
- `Research/experiments/<experiment-id>/protocol.md`, `trials.jsonl` and final `report.md`: versioned rules and redacted conclusions. Freeze the protocol by hash before evaluation; corrections are new versions.
- `runs/research/<experiment-id>/`: ignored immutable raw captures and manifests, with verification results in a separate location. Export under the existing evidence-retention policy. No secrets or raw machine records in Git.
- `docs/milestones/research-trading-wave-report.md`: implementation, test results, raw-evidence references, verification, economic decision, remaining proof, operator minutes, exact resumption condition.

Do not add a message bus, Kubernetes, an LLM agent team, a new database platform, a tick lake, a dashboard rewrite, or an optimisation service. Add a dependency only when an existing component cannot safely do the necessary job.

## Completion and review

An implementation checkpoint may be complete while collection and economic proof remain pending. Full wave completion requires the applicable R0/E1–E5 real-world checks and the frozen evaluation, with honest REJECTED/INCONCLUSIVE outcomes allowed; missing operational proof still prevents a completion claim.

Use existing milestone verification and bound Triad-plus-domain review only when claiming a governed milestone result. This document's self-review is not that recommendation. Reviews cannot close milestones. Only the closeout command can write `proven_at`, and only after every active contract gate passes. Do not repeatedly refresh unchanged reviews merely to consume time while waiting for markets.

## Research basis

The [source review](2026-09-07-fx-edge-research-and-proposed-wave.md) explains why published monthly currency-factor results do not validate H1 or M1 rules. The [Neely–Weller paper in the Federal Reserve archive](https://fraser.stlouisfed.org/docs/publications/frbsl_wp/1999-016.pdf) finds no excess returns for its tested intraday rules after realistic costs and trading hours; this motivates fee-complete experiments, not a universal impossibility claim. [Hansen's SPA paper](https://doi.org/10.1198/073500105000000063) supplies a family-level testing approach; it does not turn a short sample into sufficient evidence or establish an individual winner.
