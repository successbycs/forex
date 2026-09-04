# M20 market-regime and strategy operating procedure

## Purpose

This is the single operating reference for the M20 EUR/USD M1 Demo listener.
It converts the five displayed strategy signals into one ordered decision:
first establish the market condition, then select at most one strategy, then
either record `NO_TRADE` or submit one bounded Demo proposal.

It is a Demo-only design and research procedure, not investment advice or a
claim that any strategy will be profitable. It applies only to
`GOMarketsMU-Demo`, `EURUSD`, and completed M1 candles.

## Current operating boundary

| Item | Current M20 behaviour |
| --- | --- |
| Account and instrument | `GOMarketsMU-Demo` / `EURUSD` only. |
| Portfolio limit | One account and at most one open EUR/USD position. |
| Strategies displayed | Momentum Breakout, Compression Breakout, Trend Pullback, Range Reversion, and Session Breakout. |
| Order authority today | In M20.11, deterministic regime precedence may grant one of the five fixed strategies one bounded Demo order when every safety and cost gate passes. All other signals are stored as context and cannot submit a second order. |
| Common safety gates | Fresh quote, completed candles, normal spread, active Demo lease, no open position, per-trade and session caps. |
| Position ownership | The strategy that created the accepted proposal owns its SL, TP, monitoring, and exit. A different strategy cannot close it merely by producing an opposite signal. |

### Lot size, notional, margin, and loss cap are different

`Lots` is the trade **volume**, not the cash amount at risk. For the current
EURUSD convention, `0.01` lot is normally 1,000 EUR of contract exposure. At
an EURUSD price near 1.1630 that is about US$1,163 of notional exposure, not
US$100. With the Demo account's 100:1 leverage the required margin is much
smaller (roughly one hundredth of notional, converted into AUD by MT5), while
the actual broker requirement remains authoritative.

The separate M20 `AUD 100` control is a **maximum planned loss at the
protective stop**, calculated from the broker-provided tick size and tick
value. It does not make a `0.01` lot trade a A$100 trade. At this common
EURUSD contract size, a one-pip move on `0.01` lot is approximately US$0.10
before fees and conversion; MT5's symbol specification and realised ledger
remain the source of truth.

### How to read the terminal statements

| Terminal statement | Exact meaning | Is an order sent? |
| --- | --- | --- |
| `<strategy>: BUY [EXECUTABLE]` | Regime precedence selected this one strategy and its fixed entry/SL/TP plan passed its common safety and cost gates. | Yes, subject to lease, one-position, idempotency, and cap checks immediately before submission. |
| `<strategy>: BUY [SIGNAL ONLY]` | The strategy found a candidate setup but another strategy owns this assessment under regime precedence. | No. This is context, not a missed trade. |
| `<strategy>: BUY [BLOCKED]` | The strategy was selected but its plan failed a safety, cap, stop, target, or cost gate. | No. The reason line identifies the failed gate. |
| `Selected: [SELECTED_EXECUTABLE]` | Regime precedence identified the single strategy that owns the current setup. | Yes, only if safety, cost, lease, and one-position gates all pass. |
| `NO_TRADE` | No order was submitted for this assessment. The reason line names the failed safety, authority, or cost condition. | No. |
| `N/A — no countable trade` in the ledger | A legacy record could not be matched to one MT5 position lifecycle. It is excluded from trade count and P&L. | No conclusion about a new order; it is historical data only. |

The regime-selected model is implemented for current M20 assessments and is
persisted append-only in PostgreSQL. Its controlled eligibility must not be
misread as a profitability claim: each strategy still needs broker-reconciled
Demo outcomes and post-cost evaluation before it can be called proven.

## The operating flow

```text
Fresh MT5 bid/ask + completed M1 candles
                │
                ▼
        1. Common safety gates
                │
      unsafe ───┴─── safe
       │                 │
       ▼                 ▼
  record NO_TRADE   2. Classify market regime
                         │
                         ▼
                 3. Select one strategy
                         │
                         ▼
              4. Apply that strategy's entry,
                 SL, TP, and risk rules
                         │
              ┌──────────┴──────────┐
              ▼                     ▼
       record NO_TRADE       persist proposal → one
       with reason            bounded Demo order
                                      │
                                      ▼
                         owner monitors / exits / reconciles
```

An assessment never places five orders because five rows show `BUY`. Strategy
agreement is confluence evidence; it is not permission to multiply exposure.

## Step 1 — common safety gates

These gates take precedence over every directional strategy. If any one fails,
the result is `UNSAFE_OR_UNTRADEABLE` and `NO_TRADE`.

| Check | Required condition | Reason for refusal |
| --- | --- | --- |
| Data freshness | The MT5 quote is newer than the last assessed quote and within the configured age limit. | A price that is stale or already assessed cannot justify a new order. |
| Candle integrity | Enough completed M1 candles exist; the forming candle is excluded. | Prevents decisions on unfinished price action. |
| Spread | The observed spread is at or below the strategy’s normal-spread limit. | A small M1 move may not pay for execution cost. |
| Event risk | No configured high-impact-news blackout or abnormal-volatility state. | Price spikes can invalidate ordinary M1 assumptions. |
| Execution state | Demo lease active, broker server/symbol match, no unresolved position, and one-position cap available. | Keeps the bounded Demo contract intact. |
| Risk feasibility | The strategy’s protective stop can remain inside the AUD loss cap and a credible target gives the minimum reward/risk. | Refuses a signal whose risk cannot be protected. |

M20 currently has no connected economic-calendar or news-blackout feed. The
stored `news_blackout_inactive=true` value therefore means **no blackout is
configured**, not that external news risk has been independently checked.
Spread is the current abnormal-volatility proxy. A later, governed news-data
integration must replace this explicit limitation; it must not be inferred
from the absence of a signal.

## Step 2 — classify the market condition

The first matching row wins. Categories are intentionally ordered from safety
to most specific set-up to most general set-up.

| Priority | Market regime | Observable definition on completed M1 candles | Selected strategy |
| --- | --- | --- | --- |
| 1 | `UNSAFE_OR_UNTRADEABLE` | Any common safety gate fails. | None — `NO_TRADE`. |
| 2 | `COMPRESSION_BREAKOUT` | Earlier five-candle range is at or below `max(12 points, 3 × spread)` and price then closes beyond it with movement larger than spread. | Compression Breakout. |
| 3 | `TREND_PULLBACK` | Short ordered trend, identifiable pullback, then a completed-candle resumption in the original direction. | Trend Pullback. |
| 4 | `RANGE_REVERSION` | Repeated tests define horizontal support/resistance; latest candle rejects an outer edge; no confirmed break exists. | Range Reversion. |
| 5 | `LIQUID_SESSION_BREAKOUT` | Configured liquid session, normal spread, defined session range, and confirmed completed-candle break. | Session Breakout. |
| 6 | `MOMENTUM_BREAKOUT` | Two aligned completed candles close beyond the preceding five-candle range and combined movement exceeds spread. | Momentum Breakout. |
| 7 | `NO_CLEAR_REGIME` | No prior category is confidently true. | None — `NO_TRADE`. |

Important exclusions:

- A confirmed break excludes Range Reversion; do not fade an established break.
- Compression outranks generic Momentum because it is the more specific cause
  of the move.
- Session is a quality/context filter, not a directional reason by itself.
- An ambiguous or conflicting classification is `NO_CLEAR_REGIME`, not a
  discretionary tie-break.

## Step 3 — select one strategy and establish ownership

The following fields must be persisted with the assessment. Once an order is
attempted, they are immutable.

| Field | Example | Meaning |
| --- | --- | --- |
| `market_regime` | `COMPRESSION_BREAKOUT` | The condition that caused selection. |
| `market_regime_reason` | `Five-candle range 18 points; limit 24; bullish close above range.` | Human-readable proof of classification. |
| `selected_strategy_id` | `compression_breakout` | The one rule selected by classification. It has order authority only when its own complete plan and every common gate pass. |
| `strategy_rule_version` | `compression-breakout.v1` | Exact rule set used for entry, SL, TP, and exit. |
| `selection_status` | `SELECTED_SHADOW`, `SELECTED_EXECUTABLE`, or `NO_SELECTION` | Whether this strategy had order authority at the time. |
| `trade_owner_id` | Immutable `proposal_id` | Stable join key through attempt, MT5 position, events, and final outcome. |
| `trade_owner_strategy_id` | `compression_breakout` | Written only for an accepted trade; the selected strategy exclusively allowed to manage that trade. |

M20 grants `SELECTED_EXECUTABLE` to the single selected member of the fixed
five-strategy set. Selection is deterministic, no second strategy can submit
while an owner position exists, and the selected identifier is immutable for
the complete lifecycle.

## Step 4 — strategy-owned trade contract

| Owner | Entry | Protective stop | Initial target | Owner exit |
| --- | --- | --- | --- | --- |
| Momentum Breakout | Two aligned M1 candles break the prior five-candle range after spread. | Opposite side of the prior range, tightened if necessary to the AUD risk cap. | 1.5R, reduced only to credible nearby support/resistance; refuse below 1.25R. | Broker SL/TP, +1R breakeven, two opposite completed candles, or ten-minute time stop. |
| Compression Breakout | Confirmed break from the qualified tight range. | Outside the pre-break compression range. | Defined risk multiple and nearby structure. | Return into the range, broker SL/TP, or its defined time stop. |
| Trend Pullback | Trend, pullback, and resumption all align. | Beyond the pullback extreme. | Next structure level or defined risk multiple. | Trend failure, broker SL/TP, or time stop. |
| Range Reversion | Rejection at verified range support/resistance without a confirmed break. | Outside the rejected range edge. | Range midpoint first; opposite edge only if rules allow. | Confirmed breakout, broker SL/TP, or time stop. |
| Session Breakout | Confirmed break of a defined liquid-session range with normal spread. | Back inside the session range. | Defined session expansion target or risk multiple. | Return inside the range, broker SL/TP, session end, or time stop. |

M20.11 permits the single regime-selected member of the five fixed strategies
to execute. Other rows remain visible context; they are not permissions to
open another position.

## Step 4a — cost coverage before entry

For an otherwise executable selected strategy, M20 estimates the complete
round-trip cost before it reserves an order slot:

```text
estimated round-trip AUD cost = entry spread + expected exit spread
                                 + expected slippage
                                 + commission allowance + swap allowance

expected net profit at TP = gross profit at take profit - estimated costs
```

The current fixed M20 policy uses the observed entry spread again as the
expected exit spread, half an observed spread as slippage allowance, and zero
pre-trade commission/swap allowance. Actual commission and swap are still read
from MT5 after close. An order is refused with
`COST_COVERAGE_NOT_FEASIBLE` unless expected net profit at TP is at least the
fixed `0.10 AUD` minimum. The persisted proposal records all projected values
and the later ledger keeps them distinct from broker-derived outcome costs.

## Ownership and counter-signal procedure

| Situation | Required action |
| --- | --- |
| Compression Breakout is selected and says BUY | Create one Compression-owned proposal with its proposed SL/TP and rationale; submit only if all gates pass. |
| Momentum Breakout owns a BUY; Range Reversion says SELL | Record the counter-signal; do not sell or close the Momentum position. |
| The owner’s own exit condition fires | Owner may close or amend its position within the fixed risk contract. |
| Broker SL or TP fires | Reconcile under the original owner; do not reinterpret the trade using a later signal. |
| MT5/account/heartbeat fault | Stop new entries, leave broker-side protection in force, and reconcile before further action. |

There is no `SELL_ALL` behaviour in this procedure. A universal emergency
circuit breaker must be independently specified and must be operational—not a
directional strategy signal.

## Operator dashboard requirements

Every assessment should make the decision inspectable in this order:

1. Current UTC and NZ time, quote age, bid/ask, spread, and candle integrity.
2. `market_regime` and its plain-English reason.
3. Selected strategy, selection status, and whether it can execute.
4. All five strategy rows showing `BUY`, `SELL`, or `NO_TRADE` with reasons.
5. Proposal/order/reconciliation state.
6. For an open or closed trade: owner strategy, actual broker entry, SL, TP,
   exit price, close reason, costs, and realised AUD P&L once verified.

## Evidence and ongoing review procedure

Every executable strategy requires continuing evidence, including:

- its deterministic classification, entry, SL, TP, monitoring, and exit rules;
- schema and immutable ownership records;
- focused unit, integration, and negative-path tests;
- broker-reconciled Demo trades with post-cost AUD P&L;
- comparison against the active strategy across chronological, out-of-sample
  observations; and
- evidence that one-position, risk, lease, and Demo-only boundaries remain
  intact.

Measure post-cost expectancy, win rate, average win/loss, drawdown,
consecutive losses, holding time, spread/slippage, and outcomes by regime and
session. Do not promote a strategy solely because it wins a short sequence.

## Research basis and limitation

The procedure is a testable hypothesis, not a forecast. Academic research
supports the relevance of currency momentum, technical-rule variation across
market regimes, support/resistance behaviour, and intraday FX market
microstructure; it does not prove that this broker-specific EUR/USD M1 system
will profit after costs.

- Menkhoff, Sarno, Schmeling, and Schrimpf, *Currency Momentum Strategies*,
  Journal of Financial Economics (2012): [BIS working-paper version](https://www.bis.org/publ/work366.pdf).
- Osler, *Currency Orders and Exchange-Rate Dynamics: Explaining the Success
  of Technical Analysis* (Federal Reserve Bank of New York Staff Report 125):
  [paper record](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=923370).
- Hsu, Taylor, and Wang, *Technical Trading: Is It Still Beating the Foreign
  Exchange Market?*, Journal of International Economics (2016):
  [publisher record](https://www.sciencedirect.com/science/article/pii/S0022199616300472).
- Piccotti et al., *Macroeconomic Announcements and Price Discovery in the
  Foreign Exchange Market*, Journal of International Money and Finance (2017):
  [publisher record](https://www.sciencedirect.com/science/article/abs/pii/S0261560617301687).

Related detailed references are retained in
[m1_trading_strategy.md](../m1_trading_strategy.md) and
[m1_multi_strategy_execution.md](../m1_multi_strategy_execution.md).
