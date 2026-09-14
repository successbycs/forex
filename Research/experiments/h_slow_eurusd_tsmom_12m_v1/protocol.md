# H_SLOW EUR/USD 12-month time-series-momentum protocol v1

Status: **disabled research protocol**. This is an unactivated pure decision
component, not a Demo mandate, order specification, account selection or
claim of Demo authority. `GOMarketsMU-Live` remains prohibited.

## Hypothesis and frozen rule

This single-pair, monthly adaptation is informed by Moskowitz, Ooi and
Pedersen (2012), *Time Series Momentum*, as catalogued in
[`Research/2026-09-10-fx-literature-source-review.md`](../../2026-09-10-fx-literature-source-review.md).
That work finds persistence at one-to-twelve-month horizons across a
diversified futures/forwards universe. It does not validate EUR/USD, retail
FX execution, this one-pair adaptation, or profitability.

At the first UTC calendar day of each month, after daily data for the previous
UTC month is both complete and available, compare:

`last completed daily close in the just-finished UTC month / last completed daily close in that month one year earlier - 1`.

- Positive return: `BUY` research target.
- Negative return: `SELL` research target.
- Exactly zero: `NO_TRADE` research target.

There are no filters, optimisation, sentiment, event direction, carry rule or
intra-month override in v1. Economic-event data may later annotate the record;
it does not veto this signal in v1.

## Point-in-time data and decision clock

The policy accepts EUR/USD daily bars only, ordered strictly by UTC opening
time. Each bar must be exactly one UTC day, must have a finite positive close,
and supplies `opened_at_utc`, `closed_at_utc`, and `available_at_utc`. FX
weekends may have no bar; no fabricated weekend candle is required.

The decision timestamp must fall on UTC day 1. All supplied bars must already
be closed and available no later than that timestamp; a future, still-open,
late-available, duplicate or nonchronological bar is rejected. The data must
contain at least 240 completed daily bars and the final completed daily close
for every calendar month from the reference month through the signal month
(13 monthly closes). This makes the warm-up explicit while allowing normal FX
weekend gaps. It also rejects a 12-month result constructed from a missing
month.

Until an explicit, versioned FX-holiday calendar is supplied, the final bar in
each required month must open on that month's final Monday--Friday UTC date.
This deliberately fails closed if a source omits a normal month-end session;
an eventual source adapter may account for published market holidays rather
than silently accepting an older close.

The latest usable daily close is the final close in the prior UTC month. The
component has no mutable state, so it emits a monthly target rather than a
deduplicated trading attempt. An eventual orchestrator must record exactly one
eligible decision/rebalance attempt per signal month and retain the target,
input snapshot and availability timestamps. Rebalancing means target review at
that monthly clock only: no daily reversal, resize or entry decision.

## Proposed initial protection rule (disabled)

The preparation rule `hslow-atr20x3-v1` is recorded in
`config/h_slow_protection.json`: calculate 20 true ranges from the last 21
qualified completed D1 bars, take their arithmetic mean (not Wilder smoothing),
and place the initial stop three times that value below the BUY entry ask or
above the SELL entry bid. True range is the maximum of high minus low,
absolute high minus previous close, and absolute low minus previous close.
Normal weekend gaps are allowed; missing weekdays or the latest required
completed weekday are refused until an explicit holiday calendar is supported.

This is a routine engineering hypothesis for the Demo adaptation, not a
parameter selected by return optimisation or established by the cited paper.
The sizing component rounds the stop away from entry to the broker tick and
sizes against that executable distance plus explicit adverse costs. It refuses
an infeasible minimum lot or stop. A stop is not a guaranteed loss ceiling:
gaps, slippage and financing still require the activation mandate's allowances.
This rule does not trail, widen or alter an existing position's stop, grant
overnight authority, or activate an order route.

## Disabled execution placeholders

These are deliberately not defaults and are not returned by the policy module:

| Item | v1 status |
| --- | --- |
| Account, terminal, server and routing | Pending explicit H_SLOW Demo account/terminal mandate; no saved account may be selected. |
| Size and aggregate exposure | Disabled pending approved per-stream and total Demo limits, minimum-lot feasibility, margin and conversion inputs. |
| Stop/protection | Initial ATR20 × 3 preparation rule specified above; broker validation, account-specific risk budget and ongoing position-protection integration remain pending. |
| Holding/reversal | Intended target is reviewed monthly; maximum hold, treatment of reversal, failed close and deterministic management while disabled remain pending authority. |
| Overnight/weekend | No entry/close rule is active. An activation contract must specify gap treatment and whether holding across each rollover/weekend is permitted. |
| Financing/costs | Never assumed zero. Long/short broker swap, triple-rollover convention, commissions, conversion and spread/slippage must be observed or explicitly approved as labelled estimates before sizing/activation. |

Consequently, `src/forex/h_slow_policy.py` has no order-routing, MT5,
configuration, account, lease, runtime, persistence or network integration.
Its `BUY`, `SELL`, and `NO_TRADE` values are research outputs only and grant no
execution authority.

## Review, end conditions and limitations

Before activation, record a versioned trial record with exact account scope,
release/configuration, risk/holding mandate, protection, cost inputs, daily
reporting and weekly review. Stop/disable-new-entry conditions and management
of any remaining position must be specified there, without abandoning
reconciliation. No automatic retuning follows a loss; any change is a new
version and retains prior outcomes.

Operational status: policy component implemented locally; deployment pending.
Strategy economics: unobserved and inconclusive. Operator viability:
unobserved and inconclusive. Focused unit tests establish deterministic input
qualification only; they are not broker proof, a backtest, a profitability
claim or Demo authority.
