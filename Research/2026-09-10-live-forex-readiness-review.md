# Review: a practical route to sustainable net FX returns

Date: 10 September 2026. Reviewed checkout: `4cd39e3`. **Review and proposed work only; no engine implementation, deployment, trading, risk change or milestone closeout.**

Read with the [source analysis](2026-09-10-fx-literature-source-review.md), [complete milestone disposition](2026-09-10-milestone-relevance.md) and [review of the supplied 22-part design](../docs/reviews/edge_discovery_design_review.md).

## Verdict

The repository is a useful Demo execution and research foundation. It is **not ready for live trading and has not established positive expected returns after costs**. The largest opportunity is to make research faithfully test the executable policy, then permit only a supported, frozen policy to trade within independently enforced risk limits.

The existing Python, PostgreSQL, fixed MT5 adapter and T480 task can support that mission. A new infrastructure platform, graph database, large agent team or thirteen additional Edge milestones is unnecessary. Sustainable low-maintenance operation is a business outcome to measure, not a consequence of adding autonomous agents.

Current canonical state: M20 `NEEDS_FIX`; M21–M32 planned. M0, M1 and M16 carry `HUMAN_REVALIDATION_EXCEPTION`, which is not current proof. `live_trading_enabled` is false and `GOMarketsMU-Live` is structurally prohibited. Planning a later live product does not amend those boundaries.

## What is worth preserving

- **An actual execution boundary:** persisted proposals, execution reservations, one-position controls, broker-side protection, unknown-position handling and append-only outcomes. See [runner](../t480/m20_demo_trading_session.py), [audit bridge](../t480/m20_postgres_audit_bridge.py) and [audit schema](../sql/migrations/006_m20_demo_trading_audit.sql).
- **Broker-derived financial accounting:** exact position history, opening/closing volume matching, signed commission/fee/swap and separate estimated execution costs. [Fee-complete ledger](../sql/migrations/021_m20_fee_complete_reconciliation_ledger.sql) excludes unavailable fees from reported realised P&L.
- **Conservative risk intent:** Option B supplies explicit per-trade, daily, weekly and drawdown controls. The implementation defect below must be fixed before relying on that intent.
- **Reproducible provenance:** versioned inputs, configurations, releases, retained raw evidence and separate verification. These are useful when a broker result disagrees with a backtest.
- **T480-local operation:** the permanent task can run without a Codex conversation or T16 dashboard. Immutable release deployment and maintenance hold are good foundations; unattended recovery still needs its declared proof.
- **Existing research components:** historical datasets, point-in-time helpers, calendar/macro adapters and lineage can be reused. Their existence does not establish adequate data coverage or economic validity.

## Findings verified against this checkout

| Priority | Finding and repository evidence | Consequence |
| --- | --- | --- |
| Critical | [Audit bridge](../t480/m20_postgres_audit_bridge.py), `enforce_risk_policy`, lines 306–344: a single pause reason is stored; weekly/drawdown checks run only when that reason is empty. A local behavioural probe reproduced a lost drawdown latch; details below. | Option B's required manual review can be bypassed by the daily reset after equity recovers. Repair first in W1.4. |
| High | [Runner](../t480/m20_demo_trading_session.py), `_project_cost_coverage`, line 559, computes the payout **at take-profit**, with zero commission/swap allowances. | `FEASIBLE` is not positive expectancy. It omits loss probabilities, early exits, timeouts and applicable charges. |
| High | Runner lines 1543–1547 set `news_blackout_inactive=True`; the volatility flag repeats the spread threshold. [Calendar adapter](../src/forex/calendar_events.py) supplies date-only US CPI records and a limited ECB sample. | Neither a comprehensive event blackout nor a price-volatility safeguard is established. |
| High | [Historical evaluator](../src/forex/walk_forward.py) tests an H1 advisory with a fixed 08:00–20:00 UTC session and 2 bps cost per side. [Domain module](../src/forex/demo_trading.py) has a different M1/M5 agreement rule. The T480 runner has five M1 rules. | Passing research or domain tests does not validate the deployed trading policy. |
| High | Retained M16 output uses 720 H1 bars, 24 available sessions and 12 evaluated sessions; only seven ML sessions are actionable. Both trading comparators have negative mean net returns under the assumed costs. | This is a small historical engineering result, not evidence of an edge or a return forecast. |
| High | [M6 export](../t480/m6_mt5_multi_timeframe_probe.py), lines 41–44, filters bar **opening** timestamps against capture time, without enforcing opening + timeframe duration ≤ cutoff. The retained H1 final bar is labelled 05:00 UTC at a 05:04 UTC capture. | The declared closed-bar/UTC semantics are insufficient to guarantee no lookahead. Requalify timestamps and datasets before using them for inference; this observation is not a claim that the newer M20 bar filter has the same defect. |
| High | Runner reads a quote/account snapshot before database work; it then reserves and calls `order_send` without another quote/risk validation immediately before sending, lines 1490–1618. | Database/transport delays can make an otherwise valid plan stale. Pre-submit validity must cover quote, risk, authority, stops, margin and symbol constraints. |
| High | Runner `_strategy_trade_plan`, line 587, uses minimum volume and can tighten the technical stop to the cash cap. | A capital constraint can silently change the hypothesis. Prefer an unchanged valid technical stop, risk-based volume rounded down, or refusal. Include expected loss-side charges in planned risk. |
| Medium | Runner `_market_selection`, line 532, names the regime after the first actionable strategy under fixed precedence. Session breakout is a time-filtered version of momentum breakout. | The five rows are not five independent edges. Conditioning results on this regime can be circular; define market features independently of the chosen strategy. |
| Medium | Closed-position cost attribution uses absolute entry-price differences and zero when an exit reference is missing; a later quote can supply an estimated exit spread. | Actual net P&L may still reconcile, but these estimates are not a reliable signed transaction-cost analysis. Preserve reference time/side and unknown values. |
| Medium | Current snapshots/signals and ledger are useful, but there is no general frozen hypothesis/trial family or full stateful counterfactual outcome path. | The four unexecuted signals cannot inherit the selected strategy's broker outcome. Rejected/unknown/missing observations must remain in coverage reports. |
| Medium | Risk state is keyed by policy version, not account; reservation locks are per session while unresolved exposure checks are global. | Before multiple accounts, overlapping workers or Live, bind state to account/server and serialize entry authority at that boundary. This is a design/race concern, not a claim of an observed duplicate order. |
| Planning | M20 prohibits tick-stream retention and fixes M1 execution; later milestones repeat several capabilities M20 now owns. | Better data retention, different timeframes and live capability require explicit contract changes, not silent extensions. |

### Reproduced Option B defect

The existing `enforce_risk_policy` function was executed locally with an in-memory database cursor, the canonical policy, and these inputs. No broker or PostgreSQL connection was made.

| Observation | Inputs/state | Returned result |
| --- | --- | --- |
| Day 1 | Balance, peak, day and week anchors AUD 100,000; equity AUD 97,500; no previous pause; 10 September | Entries refused, but only `DAILY_LOSS` stored, despite exceeding the weekly and peak-drawdown limits. |
| Day 2 | Balance unchanged; equity recovered to AUD 99,900; 11 September; same week; no manual resume | Daily reason cleared; `entry_allowed=true`. The historical 2.5% drawdown did not remain latched. |

Required behaviour: record every breached condition independently; manual-review conditions survive daily rollover, price recovery, process restart and lease renewal. Clearing a daily condition must never clear a weekly/drawdown incident. The example amounts are diagnostic inputs, not the operator's account balance. This is local implementation evidence, **not broker proof**. No fix was executed in this review.

## What the literature changes

The appropriate conclusion is neither “technical rules always work” nor “technical rules are dead.” The supplied papers contain both positive and negative results, with very different cost assumptions. In particular, [Coakley et al.](https://repository.essex.ac.uk/16362/1/1-s2.0-S1057521916300400-main.pdf) omit trading costs, while [Hsu et al.](https://hub.hku.hk/bitstream/10722/229640/1/Content.pdf) include estimated costs and out-of-sample checks. See the [source analysis](2026-09-10-fx-literature-source-review.md) for inspected versions and limitations.

My proposed research order is:

1. Measure whether the current M1 composite has any realistic cost margin. Retain it as a benchmark; do not keep adding indicators to rescue it.
2. Test one fixed session/cost filter with a complete independent simulated state path. Reduced spread is an execution improvement; profit remains a separate test.
3. Compare one slow daily technical rule or long-horizon trend challenger, selected from a primary paper before evaluating it. Do not assume an H1 filter reproduces published monthly momentum.
4. If a supported single-pair candidate exists, evaluate limited currency diversification using risk-normalised comparisons, financing and currency-level exposure. Carry and value can remain later research options.

The prior [research wave](2026-09-07-research-trading-wave.md) already proposes a session filter and H1 shadow filter. Reuse its measurement work. Replacing the H1 experiment with a slow challenger would be a **versioned proposal**, not authority supplied by this review. Limit initial new confirmatory hypotheses to two; record any development variants and do not search the full cross-product of strategy, regime, session, volatility and direction.

## Proposed changes, success and demonstrations

These are work-package recommendations within the existing wave structure. Numeric test checkpoints are proposed engineering defaults, not academic guarantees or fresh trading authority.

| ID / wave | Change and why | Success definition | Demonstration |
| --- | --- | --- | --- |
| A1 — W1.4 | Correct independent persistent risk latches and remaining risk budgets. | Any weekly/drawdown breach remains paused until its approved resume; daily rollover cannot erase it. Fees and reserved exposure count toward planned headroom. | Reproduce the overlap/recovery/day-rollover scenario locally, then use an approved non-loss-inducing Demo drill and restart with retained policy state. Keep raw outputs separate from verification. |
| A2 — W1.R/W1.2 | Finish lifecycle, reconciliation and unattended recovery proof. | Account identity/exposure is known; accepted-but-unknown orders block resubmission; monitor health is distinct from process health. | Retain a real Demo lifecycle, disconnect/restart drill, verified backup/restore and T16-detached interval. No forced loss to create evidence. A post-reboot heartbeat after user logon does not prove pre-logon startup. |
| A3 — W1.3 → W2.1 | Complete broker accounting and version the executable cost model. | Match consecutive outcomes and account-level charges; estimates use signed side-aware references; unavailable costs stay unavailable. Distinguish broker P&L from operator income. | Reconcile the next 20 naturally occurring closes plus all intervening failed/unknown attempts, including genuine nonzero charges when available, to statements within documented rounding. Report missing categories; do not trade for the sample. |
| A4 — W2.1 | Replace favourable placeholder gates with qualified event, volatility and session observations. | Required missing/stale context blocks entries; volatility uses prices; sessions use London/New York local calendars and DST. | Genuine event-window and wide-spread captures; recorded calendar coverage; replay transition dates and outages. Test latest valid observations immediately before submission after deliberately delayed audit I/O on Demo. |
| A5 — W2.2 | Extract one pure decision/exit implementation shared by replay and T480. Preserve the rule while extracting it. | Same snapshots and state yield the same action, size, SL/TP and exit instruction; policy changes have separate versions. Ambiguous intrabar stop/target ordering is never resolved optimistically. | Replay retained genuine decisions and lifecycle inputs against deployed records; verify every difference before promotion. Include unknown, partial, rejected, delayed and ambiguous-bar cases. |
| A6 — W2.2/data preparation | Qualify bar clocks and acquire an adequate cost-aware dataset. | Closed-at and available-at are explicit; warm-up and evaluation data cover the chosen horizon; bid/ask and coverage gaps are identified. | Reject the retained M6 timestamp inconsistency in validation; qualify replacement data from the source. For slower research, target several years and multiple regimes; label adequacy by effective sample/precision rather than declaring a fixed year count sufficient. |
| A7 — W3.1 / E4 | Add an append-only experiment/trial register and one reproducible report command. | Rules, filters, exits, costs, data, search budget, evaluation dates and all failures are traceable. Final holdout is access-controlled until review. | Rebuild from retained artifacts; fail on missing trials, changed dataset hashes or future labels. Start trial records before evaluation so crashes cannot hide failed trials. |
| A8 — W3.1 / E2–E5 | Run the baseline and at most two predeclared challengers with selection-aware inference. | Independent simulated accounts use matched capital/risk and complete calendar returns; economic result is supported, rejected or inconclusive. | Chronological validation, untouched final evaluation and frozen prospective shadow window; evaluate one candidate subsequently with actual Demo fills before attributing execution results to it. Six weeks is a collection checkpoint, not sufficient proof by definition. |
| A9 — W3.1 | Add an operator economics and feasibility report. | After-broker-cost P&L covers attributable recurring expense at feasible capital; uncertainty and operator minutes are visible. | Reconcile one actual billing period and the full trading evaluation interval; test base, +50% and 2× variable execution costs without double-counting observed fills. Use a meaningful cash alternative benchmark. |
| A10 — W1.R/W3.2 | Publish one compact state view and run bounded maintenance automatically. | The operator can see why entries are allowed/blocked, freshness, exposure, risk latches and evidence version. | Kill/restart the process, interrupt the database, replay duplicate events and observe stale status from outside the failed process. Unknown exposure never becomes flat; protective management remains available. |
| A11 — later W4 proposal | Design an account-bound live adapter and explicit promotion contract. | Exact account/server, strategy/release, capital, loss budget and supported order types are bound; default is disabled; Demo evidence remains separate. | First verify refusal/rollback without Live access. Only after an approved live contract, run a tiny funded pilot and reconcile actual live statements, fees, slippage and account cash flows. |
| A12 — later W4 proposal | Operate one frozen live candidate with deterministic monitoring and human-controlled promotion. | Real net income and operational effort meet predeclared criteria; risk incidents pause entries; model/risk increases require review. | Fixed pilot end/review conditions; compare actual live costs against Demo estimates and retain all results. Scaling requires a later decision; no automatic risk increase after wins or losses. |

## The economic gate

Use two distinct accounts:

`broker net P&L = sum(signed broker deal profit + commission + fee + swap) + other attributable broker trading charges`

`operator net income = broker net P&L − recurring infrastructure/data/AI costs − conversion/transfer costs not already included`

Deposits and withdrawals are external cash flows. Actual fill-to-fill P&L already contains the execution prices: do not subtract spread/slippage estimates again. Estimates support attribution and counterfactual stress. Use marked-to-market, cash-flow-adjusted equity for risk and interval returns, including open positions and accrued costs.

For a simple two-outcome illustration, with gross win `W`, loss magnitude `L`, win probability `p`, and average cost `c`, expectancy is `pW − (1−p)L − c`. The real runner also has timed exits, invalidations and gaps: use its observed/simulated outcome distribution rather than forcing this simplified model. A TP payout above AUD 0.10 does not establish positive expectancy.

Report statistical precision around net performance, dependence, cost margin, drawdown, time under water, risk-cap utilisation and probability of pause estimated under declared assumptions. Compare the full policy with its risk pauses enabled. A strategy that earns money only after removing Option B fails this mission. Stop orders and a 2% entry-pause threshold do not guarantee losses are capped at 2% during gaps.

The operator's intended live capital, minimum worthwhile income, recurring cost allocation and acceptable attention budget are not established by a large Demo balance. Keep the business verdict `INCONCLUSIVE` until those values are supplied. State tax treatment; default reports should say before personal tax, with development costs and operator time separately disclosed.

An illustrative arithmetic check: to net AUD 300/month after AUD 50 recurring expense, a hypothetical 0.25% monthly return after broker costs would require AUD 140,000; 0.50% would require AUD 70,000. These are neither forecasts nor recommended returns. They show why capital and cost assumptions matter and why an income aspiration must not become a trade quota or leverage target.

## Autonomy and state

Use ordinary code continuously for data capture, eligibility, order state, reconciliation, risk, health and schedules. Use LLM agents intermittently for literature assessment, controlled experiment proposals and concise explanations. The agent boundary and suggested graphs are specified in the [design review](../docs/reviews/edge_discovery_design_review.md).

An explicit **state-transition graph is useful**. A graph database is not needed: reuse PostgreSQL records and event history, with a generated view/diagram. Keep service health, entry authority, position lifecycle and research evidence as separate state dimensions. A single green `RUNNING` badge cannot represent all four.

## Validation performed and limits

- Inspected Git status, AGENTS, canonical state, registry contracts, evidence rules, current code, schemas, previous waves/research and the supplied design brief. Unrelated `runs/run_history.json`, research/prompt work and `home/` were preserved.
- Ran the existing M20 trading, listener, M16 and configuration test files: 50 tests passed. Governance validation passed. These checks did not detect or waive the independently reproduced risk-latch defect.
- Read the retained M6 and M16 source outputs named in canonical state and matched their file SHA-256 values to their retained manifests. This checks file integrity, not current contract validity, independent provenance or profitability.
- Earlier conversation observations show successful RDP recovery and a fresh maintenance-hold heartbeat after a user-initiated reboot. This review did not reconnect to the broker, release the hold or certify pre-logon/T16-detached continuity. The W1 report still lacks complete recovery/closeout proof.

Local validation commands used:

```bash
python3 -m pytest -q tests/milestones/test_m20_demo_trading.py tests/milestones/test_m20_listener_service.py tests/milestones/test_m16.py tests/test_config.py
python3 scripts/forex_milestones.py validate
```

Documentation checks passed for local links, whitespace, balanced code fences and coverage of all 22 design sections and all 22 repository questions.

**Next work:** repair and prove the risk-latch issue within the active W1/M20 work, finish required execution/recovery evidence, then execute W2's shared decision and eligibility work. Prepare the small W3 research protocol alongside that work. Do not start the thirteen proposed Edge milestones or enable Live from this review.
