# M1 multi-strategy execution model

## Purpose

This document defines how the five visible EURUSD M1 strategies should be
treated when their signals agree or conflict. It is an execution and
measurement design, not a profitability claim or investment advice.

The consolidated M20 operator reference is
[M20-market-regime-strategy-operating-procedure.md](milestones/M20-market-regime-strategy-operating-procedure.md).

The strategies are:

1. Momentum Breakout
2. Compression Breakout
3. Trend Pullback
4. Range Reversion
5. Session Breakout

## MVP decision

M20.11 operates **one portfolio, one EURUSD position, one selected strategy**.
All five documented strategy contracts are eligible for controlled Demo
selection. The other four are recorded beside every decision as context, but
only the one strategy selected by regime precedence can own an order.

This is deliberate:

- Five simultaneous EURUSD buys are not diversification. They are highly
  correlated exposure to the same pair and can multiply loss at the same
  stop event.
- The M20 Demo cap is one open position. It gives the team a clean,
  attributable entry-to-exit ledger while the first lifecycle is proven.
- A shadow signal can be tested against the same market snapshot without
  confusing its performance with the position actually held.

Each current active trade has exactly one immutable owner selected from the
five fixed strategies. Broker-side stop loss, take profit, break-even rule,
two-opposite-M1-candle exit, and ten-minute time stop apply under that owner;
counter-signals never gain authority to close it.

## Market classification comes before strategy selection

An assessment must never start by asking which strategy happened to produce a
signal. It first classifies the shared, closed-candle market snapshot. Only
then can it select **one** strategy as the candidate owner. This prevents a
compression signal, a momentum signal, and a session signal from becoming
three orders on the same EUR/USD move.

### Classification gates and precedence

| Priority | Market category | Observable M1 definition | Selected strategy | Result when the gate fails |
| --- | --- | --- | --- | --- |
| 1 | `UNSAFE_OR_UNTRADEABLE` | Stale quote; spread above its configured normal limit; active news blackout; missing closed candles; inactive lease; or an existing EUR/USD position. | None | `NO_TRADE`; do not classify a direction. |
| 2 | `COMPRESSION_BREAKOUT` | The earlier five-candle range is at or below `max(12 points, 3 × spread)`, then a completed candle breaks that range with a movement larger than spread. | Compression Breakout | Continue only if its own BUY/SELL rule and risk rule pass. |
| 3 | `TREND_PULLBACK` | A short, ordered directional trend is visible; price pulls back; then completed candles resume the original direction with sufficient movement after spread. | Trend Pullback | Fall through only if the trend/pullback/resumption definition is not complete. |
| 4 | `RANGE_REVERSION` | A clear horizontal range has repeated edge tests and the latest completed candle rejects an outer edge; no confirmed breakout is present. | Range Reversion | Fall through if price has escaped the range or the rejection is weak. |
| 5 | `LIQUID_SESSION_BREAKOUT` | A configured liquid session is open, spread is normal, and a defined session range has a confirmed completed-candle break. | Session Breakout | Fall through outside the session or during abnormal spread/news. |
| 6 | `MOMENTUM_BREAKOUT` | Two completed M1 candles agree, the latest close exits the prior five-candle range, and combined movement exceeds spread. | Momentum Breakout | `NO_TRADE` if the rule does not pass. |
| 7 | `NO_CLEAR_REGIME` | No category above is confidently established. | None | `NO_TRADE`; retain the five strategy observations. |

The order is intentional. Safety wins over every signal. Compression wins over
generic momentum because it describes the more specific pre-breakout state.
Range reversion is never selected after a confirmed break; those hypotheses
are mutually exclusive. A liquid trading session is a context filter, not by
itself a directional signal.

### Selection and ownership record

Every persisted assessment and any resulting trade must carry these fields.
They are part of the design contract for the future rules engine; values are
immutable once an order is attempted.

| Field | Example | Purpose |
| --- | --- | --- |
| `market_regime` | `COMPRESSION_BREAKOUT` | States the observed market condition before a strategy is selected. |
| `market_regime_reason` | `Prior five-candle range 18.0 points; limit 24.0; bullish close above range.` | Lets a person audit why the category was selected. |
| `selected_strategy_id` | `compression_breakout` | Identifies the sole strategy entitled to propose the trade. |
| `strategy_rule_version` | `compression-breakout.v1` | Binds the exact entry, SL, TP, and exit rule set. |
| `trade_owner_strategy_id` | `compression_breakout` | Written on an accepted trade; gives that strategy exclusive ownership of monitoring and exit. |
| `trade_owner_id` | immutable `proposal_id` | Stable ownership key that joins the later attempt, broker position, lifecycle events, and outcome without inference. |
| `selection_status` | `SELECTED_SHADOW`, `SELECTED_EXECUTABLE`, or `NO_SELECTION` | Makes it explicit whether the selected strategy could actually send an order. |

`trade_owner_strategy_id` is not a broker magic number or a label inferred
after the fact. It is a durable, append-only application record written before
the order. The broker ticket remains evidence of execution; the owner ID tells
the monitor which rule is permitted to change SL, take profit, or close it.

### Strategy ownership rules

| Event | Required behaviour |
| --- | --- |
| A category selects Compression Breakout and it has a `BUY` | Make Compression the single executable owner, subject to all safety and cost gates. |
| Momentum also says `BUY` | Record Momentum as confluence only; it cannot create a second order. |
| Range Reversion later says `SELL` | Record the counter-signal only. It cannot close a Momentum-owned BUY. |
| Owner exit rule fires | The owner may close or amend its own position, subject to the broker-side protective SL/TP and universal risk safeguards. |
| Broker SL/TP fires or a universal emergency fault occurs | MT5 closes/protects the position; reconcile the result under the original owner. |

M20.11 uses deterministic regime precedence to classify one executable owner.
Unselected signals remain context only, which prevents correlated EURUSD
exposure while collecting strategy-owned Demo evidence.

### Planned M20.12 multi-timeframe context

M20.12 is planned as an M5/H1 **shadow-context** experiment.  It does not
give M5 or H1 an entry, amendment, or exit right and does not change an
owner's existing M1 holding time.  Every M1 proposal will later retain its
fixed closed M5/H1 context, native candle-close times, alignment,
`OBSERVE_ONLY`/`NEUTRAL`/`HARD_CONFLICT` disposition, and rule version.  The
initial disposition is measurement only; it cannot secretly filter a trade.

H4/D1 structure and W1 mapping are deferred.  They require separately agreed,
deterministic definitions before entering the fast path.  The detailed scope,
research limitations, independent review, and operator feedback requests are
in [M20.12-multi-timeframe-context-trial.md](milestones/M20.12-multi-timeframe-context-trial.md).

## Signal and exit rules

| Situation | M20 MVP action | Why |
| --- | --- | --- |
| Selected strategy says `BUY` or `SELL` and no position exists | Open one position with that owner's protective SL/TP. | Regime precedence grants only one owner authority. |
| Unselected strategy says `BUY` or `SELL` | Record as context only. | Its signal cannot create a second trade. |
| Several strategies say `BUY` | Open at most the regime-selected strategy's position; record the others as confluence. | Agreement is useful context, not permission to multiply the same EURUSD exposure. |
| A non-owner strategy says the opposite | Do not close automatically; record the disagreement. | A counter-signal can be valid without invalidating the owner setup. |
| The owning strategy's defined exit fires | Close that owned position or let its broker-side SL/TP close it. | Entry and exit belong to the same tested strategy contract. |
| A hard account or platform fault occurs | Stop new entries and retain/reconcile the existing broker position. | This is an operational safeguard, not a directional signal. |

There is no `SELL_ALL` rule in M20. A single counter-signal must never turn
into an undiscriminating liquidation command.

### Net-return and protected-exit rule

For every proposed M1 trade, the selected owner must set the directionally
correct broker-side protective prices before submission and record why they
fit the current completed-candle structure.  A `BUY` has a stop loss below
entry and a take profit above entry.  A `SELL` is the reverse: it opens by
selling at its entry price, then closes by buying; therefore its take profit
is **below** entry and its stop loss is **above** entry.

The strategy must reject the trade unless its projected take-profit outcome
clears the configured minimum net-profit floor *after* the estimated
round-trip costs: entry/exit spread, commission, expected swap where relevant,
and the declared slippage allowance. This prevents a visually positive gross
move from being accepted when it is too small to produce a useful net result.

| Before an order is submitted | Required record | Decision rule |
| --- | --- | --- |
| Entry and exit direction | Entry, SL, TP, side, owner strategy and rule version | Reject malformed direction: BUY requires `SL < entry < TP`; SELL requires `TP < entry < SL`. |
| Structural protection | Recent swing/range/volatility rationale for SL and TP | The owner strategy, not an unrelated counter-signal, owns later amendment or exit. |
| Cost-aware profitability | Projected gross at TP, estimated costs, projected net at TP, and configured minimum net | Submit only when projected net at TP is at least the minimum; otherwise record `NO_TRADE`. |
| Actual result | Filled entry, close, gross P&L, fees/costs, net P&L, and exit reason | Reconcile against the original projection to improve the next rule version. |

This is a Demo measurement rule, not a promise of profit: a valid target can
still miss, a stop can still be reached, and realised fills/costs can differ
from the estimate.

## Future options after M20 proof

| Model | Description | Benefit | Main risk | Recommendation |
| --- | --- | --- | --- | --- |
| Single selected strategy | One regime-selected owner; all other signals remain non-owning context. | Clear attribution and the simplest ledger. | May miss useful independent setups. | **Use for M20.** |
| Signal ensemble | Score or vote across strategies, then select one position. | Uses agreement without duplicating exposure. | Can hide which strategy created edge; weights need out-of-sample testing. | First expansion after separate shadow results exist. |
| Independent strategy sleeves | Each strategy has its own position, stop/target, magic ID, risk budget, and ledger. | Measures each strategy honestly. | EURUSD positions are still correlated; total risk can be multiplied. | Later only, after portfolio limits and testing. |
| Net exposure model | Combine all signals into one net EURUSD target. | Limits broker tickets and aggregate exposure. | Netting can conceal incompatible holding periods and exit logic. | Consider after sleeve data proves stable. |

If sleeves are introduced later, each must have its own `strategy_id`,
`position_id`, entry rule version, stop/target version, maximum risk, and
exit reason. A portfolio risk layer must calculate **total loss at all stops**
before accepting another sleeve. Opposite signals should first reduce or block
new exposure; they should not close another sleeve unless that sleeve's own
exit rule or a separately declared portfolio circuit-breaker triggers.

## Research basis

Forex risk guidance consistently distinguishes per-trade protection from
portfolio-level exposure: multiple positions can create correlated or
concentrated risk, so position size and stop-loss should be considered both per
trade and across the whole account. [Vantage Markets risk-management guide](https://www.vantagemarkets.com/en/academy/forex-risk-management/)
and [CMC Markets' forex risk guidance](https://www.cmcmarkets.com/en-gb/forex/forex-risk-management)
describe this practical distinction.

For a multi-strategy portfolio, the useful control is aggregate planned loss
at stops, by strategy and by currency exposure—not the number of individual
tickets. [MyFXGuide's portfolio-risk overview](https://myfxguide.com/academy/risk-management/portfolio-correlation-currency-exposure)
summarises that approach. MT5 also supports strategy ownership through magic
identifiers; its documentation notes that position magic is associated with
the most recent contributing deal, so a future sleeve design must retain its
own durable ownership records rather than infer ownership after the fact.
[MQL5 Programming for Traders](https://www.mql5.com/files/book/mql5book.pdf)

## Evidence to collect before changing authority

Do not make a shadow strategy executable merely because it produced a
plausible signal. For each strategy, collect enough closed Demo trades to
compare:

- realised AUD P&L after commission, swap, spread, and slippage;
- win rate, average win/loss, maximum drawdown, and time in trade;
- trade overlap and total portfolio heat at simultaneous stops;
- performance by session, spread regime, and market regime; and
- behaviour when strategies disagree.

Only then should a separately approved milestone add a second executable
strategy or multi-sleeve portfolio authority.
