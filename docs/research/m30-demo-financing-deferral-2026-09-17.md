# Evidence Brief: M30 Demo financing-policy deferral

## Decision

Remove financing-calendar and entry-hour restrictions as Demo M1 entry gates.
Retain them as a separate Live-readiness policy.

## Proposed claim or hypothesis

For the fixed `GOMarketsMU-Demo` EURUSD M1 runtime, an explicit deferred
financing status can allow a Demo order to reach the existing safety and cost
gates without asserting any financing, rollover, account-fee, or profitability
claim. The fixed Demo-only server restriction and existing owner exits remain.

## Context

- Instrument / market: EURUSD on `GOMarketsMU-Demo`.
- Timeframe: M1, with existing short owner exits.
- Intended use: M30's bounded Demo integration proof.
- Known constraints: no Live access; no inferred swap, commission, rollover,
  account tariff, or overnight qualification.

## Evidence reviewed

| Source | Type | Relevant finding | Applicability | Limitations |
| --- | --- | --- | --- | --- |
| [10 September broker-blocker resolution](../../Research/2026-09-10-w1-broker-blocker-resolution.md) | Prior internal source analysis | The temporary window expired at 2026-09-17T00:00:00Z and explicitly forbids automatic extension. | Explains the present M30 refusal. | It was a temporary Demo estimate, not account-fee proof. |
| Chris direction, 17 September 2026 | Operator policy decision | Financing policy is deferred from Demo and reserved for later Live readiness. | Authorizes this Demo-only scope change. | Does not establish financing facts or Live readiness. |

## Findings

### Evidence-supported

- The old temporary policy has expired and cannot be extended automatically.
- The old policy never established actual account tariff, rollover, or future
  profitability.

### Reasonable inferences

- An explicit `DEFERRED_FOR_DEMO` journal state is clearer than pretending a
  zero cost or a valid calendar exists.

### Assumptions to test

- Existing spread, stop, target, risk, position, duplicate, broker identity,
  monitoring, and reconciliation gates still prevent an unsafe Demo order.
- Pass measure: focused behaviour tests and a bounded Demo M30 capture on the
  deployed revision.

### Rejected or unsupported claims

- Zero assumed Demo financing is not a statement that broker fees or swap are
  zero.
- The change grants no Live or overnight authority and makes no return claim.

## Risks to validity

- Actual Demo charges remain observable only through later reconciliation.
- The policy must never be copied into a Live configuration without fresh,
  broker- and calendar-qualified evidence.

## Recommendation

Promote to bounded Demo evaluation only. Defer financing qualification to an
explicit future Live-readiness policy.
