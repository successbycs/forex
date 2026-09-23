# Evidence Brief: pro-forma Live commission for Demo transactions

## Decision

Decide how to show a reproducible comparison of an attributable Demo trade's
broker result with the commission that a specified GO Markets Live profile
would charge. This is accounting/reporting only, not a trading decision.

## Proposed claim or hypothesis

Under profile `GO_PLUS_AUD_V1`, the commission estimate is AUD 3.00 per side
per 1.00 standard lot. Therefore a closed 0.01-lot EUR/USD trade has an
estimated AUD -0.06 round-trip commission; an open 0.01-lot trade has AUD
-0.03 incurred at entry and AUD -0.06 if closed now.

## Context

- Instrument / market: EUR/USD, GOMarketsMU-Demo AUD account.
- Timeframe: M1 entries; cost calculation is volume-based, not timeframe-based.
- Data source: broker-reconciled PostgreSQL records and GO Markets pricing.
- Intended use: labelled “Pro-forma Live P&L” in PostgreSQL and terminal views.
- Constraint: inspected Demo broker deals report AUD 0 commission, fee and swap;
  the Demo account's actual pricing profile has not been independently retained.

## Evidence reviewed

| Source | Type | Finding | Applicability | Limitation |
| --- | --- | --- | --- | --- |
| [GO Markets account types](https://gomarkets.com/en-au/accounts-and-pricing/account-types) | Official broker page, accessed 2026-09-23 | GO Plus+ is AUD 3 per side per FX standard lot; Standard is commission-free. | Supports the declared GO Plus+ AUD scenario. | Does not identify this Demo account's profile. |
| [GO Markets spreads and fees](https://www.gomarkets.com/en-au/accounts-and-pricing/spreads-and-fees) | Official broker page, accessed 2026-09-23 | Lists AUD 3 commission per lot for GO Plus+. | Confirms the rate. | Prices may change. |
| `forex.demo_trade_ledger` | Broker-reconciled internal data, read 2026-09-23 | Inspected EUR/USD closes have zero reported broker commission. | Preserves actual Demo P&L. | Not proof of future Live terms. |

## Findings

### Evidence-supported

- `AUD 3 × lots` is the published per-side GO Plus+ AUD commission estimate.
- Standard has no separately charged commission; it must not be treated as GO
  Plus+ merely because the asset is EUR/USD.

### Reasonable inference

- For 0.01 lots, the commission-only pro-forma adjustment is AUD -0.06 on a
  close. This is direct arithmetic, not a forecast.

### Assumption to test

- The selected comparison profile is GO Plus+ AUD. Until confirmed from account
  documentation, persist it as `ASSUMED`, with its source URL, retrieval time,
  content hash and effective period.

### Rejected claim

- The calculated number is not “real Live P&L.” It excludes profile-specific
  spread, fill/slippage, swap, financing and conversion differences.

## Risks to validity

No model may overwrite broker-reported commission or `realized_pnl_account`.
Unattributed/manual positions are excluded. A missing profile, volume, broker
source or attribution must yield `UNAVAILABLE`, never an assumed zero.

## Recommendation

Create the proposed implementation ExecPlan below, but execute it only under a
new formal accounting milestone. It needs an independent design review before
schema work and a second review before any deployment.
