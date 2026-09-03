# M1 multi-strategy execution model

## Purpose

This document defines how the five visible EURUSD M1 strategies should be
treated when their signals agree or conflict. It is an execution and
measurement design, not a profitability claim or investment advice.

The strategies are:

1. Momentum Breakout
2. Compression Breakout
3. Trend Pullback
4. Range Reversion
5. Session Breakout

## MVP decision

M20 operates **one portfolio, one EURUSD position, one active strategy**.
Momentum Breakout is the only order-eligible strategy. The other four remain
shadow assessments and are recorded beside every decision.

This is deliberate:

- Five simultaneous EURUSD buys are not diversification. They are highly
  correlated exposure to the same pair and can multiply loss at the same
  stop event.
- The M20 Demo cap is one open position. It gives the team a clean,
  attributable entry-to-exit ledger while the first lifecycle is proven.
- A shadow signal can be tested against the same market snapshot without
  confusing its performance with the position actually held.

The current active trade therefore has exactly one owner: `momentum_breakout`.
Its broker-side stop loss, take profit, break-even rule, two-opposite-M1-candle
exit, and ten-minute time stop belong to that owner.

## Signal and exit rules

| Situation | M20 MVP action | Why |
| --- | --- | --- |
| Active Momentum Breakout says `BUY` and no position exists | Open one BUY with the active strategy's protective SL/TP. | This is the current tested execution path. |
| Several strategies say `BUY` | Open at most the one active Momentum Breakout position; record the other signals as confirmation/shadow evidence. | Agreement is useful context, not permission to multiply the same EURUSD exposure. |
| A shadow strategy says `SELL` while Momentum owns a BUY | Do not close automatically; record the disagreement. | A range-reversion sell can be a valid counter-signal without invalidating a momentum setup. |
| The owning strategy's defined exit fires | Close that owned position or let its broker-side SL/TP close it. | Entry and exit belong to the same tested strategy contract. |
| A hard account or platform fault occurs | Stop new entries and retain/reconcile the existing broker position. | This is an operational safeguard, not a directional signal. |

There is no `SELL_ALL` rule in M20. A single counter-signal must never turn
into an undiscriminating liquidation command.

## Future options after M20 proof

| Model | Description | Benefit | Main risk | Recommendation |
| --- | --- | --- | --- | --- |
| Single selected strategy | One active strategy; all others shadow. | Clear attribution and the simplest ledger. | May miss useful independent setups. | **Use for M20.** |
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
