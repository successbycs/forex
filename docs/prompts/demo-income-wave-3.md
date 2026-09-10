# Wave 3: Evidence of edge and viable operator economics

Revised 2026-09-10. **Current research plan; not an executed experiment.**
Read the [shared guide](demo-income-waves.md), current W1/W2 handovers and
[source review](../../Research/2026-09-10-fx-literature-source-review.md).
This is now the single home of the former R0/E1–E5 research work. Its goal
prompt alias is [research-trading-wave-goal.md](research-trading-wave-goal.md).

Determine whether one simple policy deserves further capital and engineering
attention after broker charges, operating expenses and realistic risk controls.
SUPPORTED, REJECTED and INCONCLUSIVE are honest possible findings. This wave
does not have to manufacture a winning strategy to deliver a valid result.

## Activities, success and real-world tests

| ID | Change and mission value | Success criteria | Real-world demonstration |
| --- | --- | --- | --- |
| W3.1 | Register and evaluate the frozen M1 baseline plus at most two predeclared challengers. Include operator economics and selection-aware inference. | Every trial, failure and variation is retained; policy/data/cost versions and final evaluation are frozen. Reproducible evidence and business verdicts use the declared criteria. No unknown capital/cost value is invented to produce a pass. | Rebuild chronological evaluation from qualified retained data, then collect genuinely future shadow observations and baseline broker outcomes over the declared interval. Reconcile costs with broker records and one actual billing period. Independently reproduce the report from immutable artifacts. |
| W3.2 | Measure low-attention operation and expose state clearly using existing services. | Service health, research evidence, entry permission and broker lifecycle are distinct; risk latches survive restart; operator minutes and recurring AI/resource costs meet the declared allowance. No duplicate entries or unresolved protection failures. | Reuse valid W1.R drills; observe a full liquid session of at least four hours with T16 disconnected and seven calendar days of scheduled collection, within the longer research interval. Retain continuity/gaps, incidents and operator actions. Reboot without sign-in remains a separately verified dependency, not a consequence of T16 disconnection. |
| W3.3 | Independently review economic evidence and, conditionally, qualify the selected candidate's actual Demo execution before any Live readiness claim. | An explicit disposition distinguishes shadow support, executed Demo qualification and operator viability. No candidate is promoted automatically. Formal milestone claims retain their complete bound review gates. | Verify reports without repairing inputs. If a candidate is supported and its exact Demo rule/contract is separately authorised, execute one frozen candidate through the existing fixed adapter and reconcile genuine fills, risk behaviour and costs over a predeclared trial. Otherwise retain rejection/inconclusiveness or the exact pending qualification. |

No trade quota applies. The collection intervals above are engineering
checkpoints, not proof of sufficient independent information or sustainable
returns. Record permissible gaps and recovery targets before collection;
a proposed default is heartbeat gaps below 30 seconds outside recorded
maintenance, with market closures reported as fresh waiting status. Coverage
losses remain in the analysis. Do not fail or pass using retrospectively chosen
uptime thresholds.

## Freeze a small family before evaluation

**Baseline:** the post-remediation deployed M1 composite, including all five
rules, precedence, fees, intended stops, sizing, exits, risk pauses and caps.
Freeze its exact version. Five related EURUSD rules are not independent
diversification. Preserve their required observations.

**H_SESSION:** apply one fixed entry filter to the baseline: intersection of
08:00–17:00 `Europe/London` and 08:00–17:00 `America/New_York`, Monday–Friday,
with every other baseline eligibility rule. These are explicit research
windows, not official exchange hours or a published profit guarantee.
Session closure prevents new entries and adds no new exit rule.

**H_SLOW:** replace the earlier H_H1 proposal with one slow daily technical
rule or long-horizon trend rule selected from an inspected primary paper.
Before its first evaluated trial, specify the paper/rule, any adaptation to
single-pair EURUSD, lookback, signal/rebalance clock, warm-up, intended stop,
position sizing, holding/exit policy, financing, missing-data handling and
minimum-lot feasibility. Select on methodological fit and data availability,
not the best return from an undeclared search. This definition is a required
planning deliverable; the label alone is not an executable strategy.

H_SLOW remains a project hypothesis: monthly diversified momentum evidence
does not validate an H1 filter or a single-pair daily adaptation. If suitable
data is unavailable, explicitly reduce the registered family before evaluation
or mark the candidate unready. Do not substitute a different strategy silently.

At most two new confirmatory hypotheses; exploratory development variants
still count in the full search history. No H_SESSION×H_SLOW combination,
regime/session/volatility grid, nine-timeframe search or autonomous optimisation.
Existing H1 observations remain useful context but are not another active
confirmatory candidate. New candidates begin shadow-only.

Compare each complete policy at matched feasible capital/risk against the
baseline and a declared cash/no-FX alternative. Show the running-platform
no-trade comparator separately where common costs matter. Do not invent cash
interest. Every policy has its own position, cash, opportunity, risk-pause and
exposure state; filtering only the baseline's executed trades is insufficient.

## Cost-aware holding study — W3.1, qualification in W3.3

Use the [swap-aware research and decision method](../../Research/2026-09-10-swap-aware-hold-or-close.md)
and W1/W2's qualified calculator, records and shared execution kernel.

| Owner | Change and why | Success criteria | Real-world demonstration |
| --- | --- | --- | --- |
| W3.1 | Compare close-before-rollover, bounded overnight holding and conditional holding for one predeclared entry policy. Test whether retaining exposure adds net value. | Register every variation and contrast. Estimate future net liquidation value across stop/target/time-exit outcomes, with forecast uncertainty; include actual financing and differences in exit costs. Use separate policy account paths and the existing selection-aware inference. | Reproduce chronological results and collect genuinely prospective shadow decisions on ordinary T480 operation. Report realised chosen actions separately from counterfactual estimates, including no-trade periods and cost/rate gaps. |
| W3.1 | Calibrate horizon-specific forecasts and the conservative incremental-benefit threshold using development data only. | Freeze horizon, confidence-bound method, benefit buffer, maximum duration and risk/event constraints before final evaluation. HOLD requires conservative incremental value above the buffer and every Option B/protection gate. Unknown data/evidence uses the approved fallback. | Verify predictions against subsequent observations at the declared horizon; test calibration, net improvement, downside/tail loss, drawdown, turnover and financing sensitivity on untouched evaluation data. Insufficient precision is INCONCLUSIVE. |
| W3.3 | Promote only an economically supported, exactly specified holding policy through the existing Demo qualification gate. | Neither positive swap nor shadow support grants order authority. Final disposition distinguishes forecast support, broker cost qualification, actual Demo execution and operator viability. | Under separately recorded exact Demo authority, reconcile genuine eligible rollover decisions, financing and exits on the frozen release. No forced entries or extended holding solely to gather proof. |

Keep the existing maximum of two new confirmatory challengers. Register the
three-way holding comparison as a bounded development study on one specified
entry policy, count all variants in the search history, and freeze any selected
holding rule within the permitted candidate definition before final evaluation.
Do not take a strategy × session × holding Cartesian product or hide additional
confirmatory policies as benchmarks. H_SESSION remains an entry-only filter;
changing its exits would change that hypothesis. If the intended confirmatory
holding contrasts do not fit the registered family, prepare an explicit
replacement/amendment before evaluation rather than silently enlarging it.

Compare each complete policy with the approved operating baseline and cash
alternative. Conditional holding must demonstrate a worthwhile net advantage
under the predeclared uncertainty/selection criteria while satisfying downside
and operator-effort limits. A result may favour daily closure or bounded holding;
there is no requirement that conditional holding win. No overnight model is
required to complete W1's separately qualified intraday fallback.

## Registration and data protocol

Reuse M19 lineage, M20 observations and PostgreSQL. Add only missing experiment
and trial records plus immutable return artifacts, not a separate service.
Start each trial record before evaluation; record failed/cancelled attempts,
manual variants, parents, code/config/data/cost hashes and seeds. A crashed
job remains visible. A candidate is a view over evidence and review events.

Before opening final outcomes, freeze:

1. Candidate family, complete executable rules, benchmarks, search/compute
   limits and all known prior experimentation.
2. Development/internal chronological validation and untouched final holdout.
   Treat previously inspected history as development, not fresh OOS. If there
   is no qualified historical holdout, declare a prospective-only design.
3. Forward start/end and review date, effective-sample/coverage requirements,
   worthwhile effect, uncertainty/inference method, safety stops and
   inconclusive conditions. Six calendar weeks is a default collection
   checkpoint; slower rules may require much longer to resolve an effect.
4. Broker/account-specific cost model, base/+50%/2× variable execution-cost
   stress and financing sensitivity. Unknown rates or fills cannot become zero.
5. Intended capital, minimum worthwhile net income, recurring-cost allocation,
   operator-time allowance and tax/development-cost treatment. Independent
   engineering can proceed while these human-owned inputs remain pending,
   but a supported business case cannot.

Validate available-at and closed-at, past-only feature fitting, warm-up,
overlapping outcome labels, gaps and ambiguous OHLC fills. Purge labels that
cross evaluation boundaries; base any additional separation on actual
information/outcome spans. Predeclare treatment of open trades at interval
boundaries. Do not introduce arbitrary random splits or optimistic fills.

## Economic and statistical decision rules

Report cash-flow-adjusted daily marked-to-market returns on common dates,
including flat days/open exposure; retain intraday peaks for Option B. Report
net AUD, initial-risk units, exposure, drawdown, time under water, pause
frequency/duration, turnover, effective information, coverage and uncertainty.

Broker net P&L includes signed deal profit, commission, fees, swap and other
attributable trading charges. Operator net income deducts attributable data,
infrastructure, AI, electricity, licences and conversion/transfer costs not
already included. Audit one billing period; show incremental and allocated
shared costs. Report operator minutes and development costs separately, and
label results before personal tax unless an applicable treatment is provided.

Use one reviewed family method, White's Reality Check or Hansen SPA, selected
before results, with aligned net comparisons and dependence-aware resampling.
Proposed protocol defaults are 5% family significance, 10,000 seeded block
bootstrap replications and development-selected block length, with declared
sensitivity. Validate the implementation and interpretation before any
confirmatory claim. Few effective blocks or invalid assumptions mean
INCONCLUSIVE, not a forced p-value.

A family rejection does not identify a winner. Individual support requires
predeclared simultaneous one-sided 95% bounds for the relevant candidate
contrasts, including positive net benefit versus cash and improvement versus
the M1 baseline under matched risk/capital. State how recurring expense and
capital enter each contrast. Report historical and prospective findings
separately. If these default criteria are changed, freeze the replacement
before final evaluation and explain why; never choose whichever test passes.

DSR/PSR and PBO/CSCV/CPCV are deferred, not mandatory gates. Retain aligned
returns so justified diagnostics can be added later. Raw Sharpe is descriptive,
not a substitute for net economic evidence.

Record two separate verdicts:

- **Evidence:** SUPPORTED_FOR_FURTHER_DEMO, REJECTED or INCONCLUSIVE under the
  frozen effect/precision criteria. Lack of significance is not proof of no
  edge; a negative noisy sample must not become a universal rejection.
- **Operator viability:** SUPPORTED, REJECTED or INCONCLUSIVE at the stated
  feasible capital. Support requires positive net operator income meeting the
  declared target under base and +50% variable costs, acceptable drawdown/
  pause behaviour and operator effort. Report 2× stress and break-even costs.
  Unknown material inputs prohibit support.

Correctly triggered Option B pauses remain in the evaluated policy. They are
not automatically implementation failures; their commercial impact must meet
the predeclared tolerance. Failure to enforce a pause, unauthorised resume,
unresolved exposure, protection or accounting failures block progression.
Never remove pauses or scale beyond feasible lots to make performance pass.

Do not inspect results repeatedly and stop at the first profitable interval.
Retuning consumes the holdout and creates a new registered version. Any
extension has a new approved window and validity assessment; no automatic
extension until significant.

## Collection, agent boundaries and executed qualification

Use ordinary T480 services within their existing mandate, with bounded storage
and resources. Record experiment events locally while T16/Codex are absent.
Checkpoint once collection is verified; resume AI analysis at the declared
condition. Pausing AI work must not disable protection.

The state display must distinguish service health, data freshness, evidence
stage, operating authority and broker exposure, with timestamps and all pause
reasons. Reuse PostgreSQL/events and simple transition diagrams. No graph
database or new dashboard platform.

LLMs may prepare research proposals and explain verified findings under fixed
call/cost/retry limits. No order authority, risk override, self-promotion,
unrecorded strategy search or sentiment feature expansion. Missing LLM service
must not stop deterministic protection/reconciliation.

Shadow support qualifies a candidate only for the next bounded Demo decision.
W3.3's executed trial requires an exact strategy/configuration/contract and
operator authority before changing the executor. Freeze duration, loss budget,
cost tolerances and success/end criteria before its first order. Missing that
authority leaves executed qualification pending; it does not erase completed
research or authorise Live. A selected candidate needs this proof before W4.

## Completion and handover

Save `docs/milestones/demo-income-wave-3-report.md` and a versioned
`Research/experiments/<id>/protocol.md` and `report.md`. Keep sensitive raw
captures in existing ignored evidence locations, separate from verification.
The old research-wave report, if present, is an input rather than a second
required closeout report.

W3 can deliver a completed rejected/inconclusive research result after its
declared evaluation and required operational checks. For a supported candidate
progressing toward Live, actual candidate Demo qualification is required and
must remain explicitly pending until demonstrated. Never claim full completion
with required proof missing. Only the formal closeout command may close an
eligible milestone after all current contract gates and bound reviews.

## Copy-and-paste goal prompt

```text
/goal Execute Wave 3: Evidence of edge and viable operator economics. Read docs/prompts/demo-income-waves.md and docs/prompts/demo-income-wave-3.md in full, the current W1/W2 handovers, and Research/2026-09-10-fx-literature-source-review.md. This is the canonical research wave; do not also execute the superseded R0/E1-E5 schedule.

Include the bounded W3.1 holding study and W3.3 qualification: compare daily closure, bounded holding and conditional holding on one predeclared entry policy; record every variant and keep the two-challenger limit. Freeze horizon-specific forecasts, uncertainty, benefit buffers and all financing costs before final evaluation. No automatic overnight authority or change to the entry-only H_SESSION hypothesis.

Scope is W3.1-W3.3 only. Inspect Git status, applicable AGENTS.md, project_state.json, the active contract and docs/evidence_and_milestones.md. Verify dependencies and reuse existing components/approvals. Prepare exact amendments and missing operator decisions before dependent work; do not start another milestone.

Register the frozen M1 baseline and at most two new challengers: H_SESSION and one fully specified literature-derived H_SLOW. H_SLOW replaces H_H1; do not expand the search grid. Freeze all rules, data/cost versions, trial family, capital/risk basis, temporal windows, selection-aware inference, decision criteria, compute limits and operator economics before final evaluation. Preserve every trial and failure, independent policy state and unknown observations.

Use qualified replay and prospective ordinary T480 collection. Reconcile actual broker charges and recurring expenses; include risk pauses and no-trade days. Do not double-count execution costs, infer capital from the Demo balance, tune on holdout or extend until profitable. Missing precision or material costs yields INCONCLUSIVE. Correct risk pauses are measured behaviour; failed enforcement blocks progression.

New candidates are shadow-only initially. Execute W3.3 candidate qualification only after the exact Demo rule/contract and operating authority are recorded; research code never gains order authority. Verify genuine candidate fills before claiming executed support or Live readiness.

Deliver separate evidence and operator-viability verdicts with independent verification. Save docs/milestones/demo-income-wave-3-report.md and versioned experiment conclusions under Research. Missing required proof stays pending. Use ordinary collection and a precise checkpoint/resumption condition instead of repeated AI polling. Respect only an explicitly supplied goal budget.

Preserve Option B, Demo-only EURUSD and exposure caps. No Live access, next wave/milestone, strategy self-promotion or LLM overrides. This prompt adds no commit/push/branch/PR authority; honour existing explicit authorisation only within scope. Formal closeout remains subject to the complete active contract and bound review.
```
