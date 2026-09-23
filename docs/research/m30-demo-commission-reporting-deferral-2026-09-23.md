# Evidence Brief: Demo commission-aware P&L reporting deferral

## Decision

Record a deferred follow-on task to add commission amounts to the Demo trading
results view, so an operator can compare gross price movement with a
commission-aware net result. Do not alter the active M30 listener, risk model,
or current Demo proof.

## Proposed claim or hypothesis

When a later account-specific commission schedule and broker-deal observations
are available, the results view can show broker-reported commission and a
clearly labelled estimated live-equivalent commission without treating either
as a promise of Live P&L.

## Context

- Instrument / market: EUR/USD CFD, fixed `GOMarketsMU-Demo` account.
- Timeframe: M1 listener outcomes; result reporting after closure.
- Intended use: a later reporting-only improvement, after M30 closeout.
- Known constraints: Demo and Live account types, base currencies, spreads,
  swaps, slippage, and execution may differ. The active account is not proven
  to be an Australian GO Plus+ account.

## Evidence reviewed

| Source | Type | Relevant finding | Applicability | Limitations |
| --- | --- | --- | --- | --- |
| [GO Markets spreads and fees](https://www.gomarkets.com/en-au/accounts-and-pricing/spreads-and-fees) (accessed 2026-09-23) | Official broker pricing page | It lists GO Plus+ Forex commission per lot by base currency, including AUD 3 per lot; it labels spread data indicative and says actual prices vary. | Identifies a candidate reference rate for a later, explicitly configured AU GO Plus+ comparison. | It is an AU page, does not establish the `GOMarketsMU-Demo` account type or tariff, and does not cover all Live execution costs. |
| M30 Demo financing-policy deferral | Internal evidence brief | Current M30 must not assume commission, swap, rollover, or account tariff. | Directly governs the active Demo proof. | It does not supply a commission amount. |

## Findings

### Evidence-supported

- The broker page currently states an AUD 3-per-lot Forex commission for an
  AUD-base GO Plus+ account, not a universal GO Markets commission.
- Current M30 policy intentionally makes no assumed commission claim.

### Reasonable inferences

- A useful operator report should display the broker-reported commission as a
  separate fact and only calculate a comparison estimate after the account
  type, base currency, rate, lot convention, and per-side/round-turn basis are
  explicitly evidenced.

### Assumptions to test

- The active Demo account exposes commission in closed-deal history.
  Test: retain closed EUR/USD deal records and compare the reported commission
  with the configured account-specific tariff; reject missing or incompatible
  values rather than substitute AUD 3.
- A configured rate can be made auditable without changing entry sizing or
  risk. Test: fixture-based gross/net reconciliation and a retained Demo
  result containing both reported and estimated fields with their provenance.

### Rejected or unsupported claims

- AUD 3 per lot applies to the active Mauritius Demo account.
- Adding a commission estimate makes Demo P&L replicate Live P&L.
- Commission may be silently treated as zero when broker data is absent.

## Risks to validity

- Account type, jurisdiction, currency, rate basis, spread, swaps, slippage,
  fill quality, and financing can make Live P&L differ from Demo P&L.
- A reporting calculation must never alter existing risk, sizing, balance, or
  broker reconciliation logic without separately authorised evidence.

## Recommendation

Defer to the first post-M30 results-reporting or Live-readiness planning wave.
Keep it reporting-only until a specific account tariff is verified. Do not
block M30's natural Demo lifecycle or use the public AU rate as an active
Demo assumption.

## Proposed deferred-task inputs

- Goal: add commission-aware gross/net result fields with source and basis.
- Scope: closed EUR/USD Demo results and read-only operator views.
- Non-goals: changing trading authority, sizing, stops, risk caps, or claiming
  that Demo results equal Live results.
- Acceptance criteria: account tariff evidence; explicit per-lot/per-side
  convention; broker-reported and estimated values never conflated; missing or
  incompatible data is visibly unavailable; fixture and retained-result
  reconciliation tests pass.
- Decision gate: Chris approves the account-specific tariff and a later plan
  whose milestone scope permits reporting work.
