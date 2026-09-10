# Wave 2: Trustworthy costs, data and executable research

Revised 2026-09-10. **Implementation plan; execute only under an explicit wave
instruction and the applicable approved contract.** Read the
[shared guide](demo-income-waves.md) and current Wave 1 handover. Verify
dependencies rather than assuming a report means completion.

The outcome is a trustworthy way to measure the policy actually traded.
This wave implements review actions A3–A6; it does not establish an edge.

## Activities, success and real-world tests

| ID | Change and mission value | Success criteria | Real-world demonstration |
| --- | --- | --- | --- |
| W2.1 | Qualify costs, market eligibility and final submission checks. Replace favourable placeholders with observations, so a cheap-looking opportunity cannot bypass missing protection or fees. | Versioned applicable commission/swap/conversion and signed reference prices; missing required data refuses entries. Sessions use explicit DST-aware calendars; price volatility is independent of spread. Immediately before submission, validate fresh quote, account/risk authority, volume, stops/freeze distance, margin and allowed deviation. TP feasibility is never labelled expectancy. | Reconcile the next 20 consecutive natural closes plus all intervening attempts/unknown outcomes against broker records, including nonzero charges when available. Capture genuine event-window, spread and refusal observations. Under a controlled Demo plan, delay audit I/O and demonstrate final revalidation. Retain local fault injection separately. |
| W2.2 | Reuse one pure strategy/sizing/protection/exit kernel for replay and execution; qualify its data and simulated fills. This makes research economically relevant. | Same versioned snapshots/state produce matching decisions, volume, SL/TP and exit instructions. Closed-at and available-at are explicit; no future labels. Research uses a complete independent account path per policy, with risk pauses. Intrabar uncertainty and unknown fills remain visible. | Replay retained genuine Demo decisions and lifecycle inputs and compare with deployed outputs. Qualify historical source timestamps, reject the retained M6 closed-bar inconsistency, and rebuild a source-backed dataset. Exercise partial/unknown/rejected/delayed observations and bars touching both stop and target; never select optimistic ordering. |

Twenty closes is an accounting checkpoint, not statistical sufficiency. Define
the start, inclusion rule and rounding before selecting outcomes; use AUD 0.01
per outcome as the proposed reconciliation tolerance and document aggregate
rounding. Do not place extra trades to achieve the sample. Missing nonzero
charge observations remain a stated limitation, with that criterion pending
where required; zero-fee samples do not prove fee handling.

## W2.1 implementation boundaries

- Use the existing fee-complete ledger. Actual fill P&L already reflects fill
  prices; do not deduct estimated spread/slippage again. Preserve original
  currency, conversion source/time and charges posted outside deal rows.
- Record decision and submission bid/ask, side, timestamps, requested/fill
  prices, volume, rejects and latency through the permitted capture surface.
  Missing exit references remain unknown. Derive costs from the exact broker
  account terms and observations, not advertised minimum spreads.
- Define required economic-event coverage, freshness and blackout rules before
  activating them. The existing limited/date-only calendar sample is not a
  complete scheduled-event feed. Required unavailable context blocks entry.
- Preserve current strategy ownership during extraction. A session gate,
  stop/sizing change or event rule affecting orders is a versioned policy
  change, with its exact contract/configuration reviewed before deployment.
- Preserve account-level entry serialization and risk reservation; revalidation
  must not open a second writer or let an expired reservation submit.

## Swap history and policy replay — W2.1 / W2.2

Reuse W1's calculator, evaluator and ledger; do not build a second cost engine.
Read the [holding-rule research](../../Research/2026-09-10-swap-aware-hold-or-close.md).

| Owner | Change and why | Success criteria | Real-world demonstration |
| --- | --- | --- | --- |
| W2.1 | Retain point-in-time swap terms, calculation modes, rollover multipliers/calendar and AUD conversion references alongside permitted execution observations. | Each replay decision uses only terms available at that time. Rate revisions and missing historical coverage are explicit; today's rates never backfill past trades. Retention stays within the approved surface. | Reproduce W1's observed financing adjustments from immutable snapshots and broker records, including applicable special-day handling; retain error/rounding attribution. Missing cases remain pending. |
| W2.2 | Replay close-before-rollover, bounded overnight hold and conditional hold through the shared policy kernel, with independent account/risk state. | Both alternatives share the decision time and evaluation horizon; model stops, targets, time exits, failures, financing and executable closing costs. Sunk entry costs are not charged twice. Missing forecasts produce an unqualified conditional decision. | Replay retained genuine decision inputs and compare policy outputs with deployment; compare realised outcomes only for the action actually taken. Label the alternative as counterfactual, preserve price/path ambiguity and qualify it against subsequent market observations. |

This builds measurement capability, not a holding-rule optimisation experiment.
It does not change H_SESSION, expand the candidate family or permit overnight
orders. New quote retention still requires the exact scope amendment below.

## W2.2 data and replay qualification

Keep the actual M1 composite as the initial executable baseline. M15's config
label and existing M5/H1 context do not establish nine-timeframe execution.
Extract existing behaviour first; identify changes separately.

For every dataset record source/licence, retrieval, time convention, timeframe
duration, closed-at, available-at, revisions, bid/ask coverage, warm-up and gaps.
Opening time before capture is insufficient for a closed bar. Where historical
availability is assumed rather than observed, disclose and bound that assumption.

Obtain enough history for the selected research horizon. A slower challenger
may require several years across differing conditions; a fixed year or bar
count alone does not establish adequacy. Do not treat the existing 720 H1 bars
or twelve evaluated sessions as confirming edge evidence.

A bounded quote sample or other additional retention requires an explicit
scope amendment before collection: M20 currently forbids a retained tick stream.
No tick lake is required. When OHLC cannot resolve executable bid/ask or
stop/target order, use finer qualified observations or conservative/indeterminate
outcomes. Never manufacture historical ask prices from today's spread.

Regime descriptors must be observable independently of the selected strategy.
Freeze feature definitions and fit thresholds on past/development data.
Preserve current selection precedence as a policy; do not relabel it independent
regime evidence. Building a large regime classifier is out of scope.

## Dependencies, outputs and completion

Map M13/M16 data/replay and M21/M26/M28 eligibility/retention requirements to
the active approved contract before dependent work. Prepare any exact amendment
with criterion ownership and evidence impact. This wave does not start those
milestones or overwrite historical proof.

Reuse Python, PostgreSQL and the fixed adapter. Deliver shared functions,
qualified input/cost artifacts, focused behavioural checks and
`docs/milestones/demo-income-wave-2-report.md`. Record readiness separately for
the baseline and slower research dataset; incomplete inputs cannot receive a
passing research-readiness verdict.

Run affected runner/kernel/data tests and current contract verification, then
perform the specified real-world comparisons with immutable raw evidence and
separate verification. No profitability claim from parity or tests. Do not
begin Wave 3, expand strategies/instruments, introduce sentiment influence or
connect to Live.

## Copy-and-paste goal prompt

```text
/goal Execute Wave 2: Trustworthy costs, data and executable research. Read docs/prompts/demo-income-waves.md and docs/prompts/demo-income-wave-2.md in full. Read the current Wave 1 report and verify actual dependency evidence.

Include W2.1/W2.2 swap-history and holding-policy replay: preserve point-in-time rates, calendars and AUD conversions, reuse W1 calculators, and distinguish actual outcomes from counterfactuals. Unknown historical costs are not zero. Do not optimise or enable holding rules in this wave.

Scope is W2.1-W2.2 only: qualified broker costs, honest market/event eligibility, final pre-submit revalidation, one shared executable policy kernel, and point-in-time data/replay qualification. Inspect Git status, applicable AGENTS.md, project_state.json, the active milestone contract and docs/evidence_and_milestones.md. Preserve unrelated work and existing approvals.

Map activities to the approved active contract. Prepare exact missing amendments before dependent implementation, especially additional data retention and changed execution semantics. Preserve the approved M1 baseline during extraction; do not treat a refactor as strategy-change authority. Continue independent authorised work while missing decisions are resolved.

Test actual behaviour and compare against retained genuine Demo decisions, fills, costs and lifecycle inputs. Validate source clocks, data availability, negative cases and ambiguous intrabar outcomes. Keep actual broker P&L separate from cost estimates, and unknown charges/fills separate from zero. Do not infer edge from target feasibility, decision parity or sample count.

Complete only when the approved criteria and real-world comparisons are satisfied. Save docs/milestones/demo-income-wave-2-report.md with per-criterion status, exact versions, evidence, limitations and resumption conditions. Respect only an explicitly supplied goal budget; use ordinary collection instead of repeated AI polling.

Preserve Option B, Demo-only EURUSD, one-position control and protection. No Live access, new strategy execution, next wave or next milestone. This prompt adds no commit/push/branch/PR authority; use any existing explicit authorisation only within its scope. Formal closeout still requires every current contract gate and bound review.
```
