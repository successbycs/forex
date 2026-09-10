# Wave 1 broker blocker resolution — 10 September 2026

The operator instructed resolution using other sources and inference where
needed. This supersedes the earlier demand that the human obtain every broker
calendar detail before any intraday Demo work. It does not establish the actual
account tariff or grant Live/overnight authority.

## Sources and conclusions

- [Mauritius FAQ](https://www.gomarkets.com/en/faqs): platform offsets are
  UTC+2/+3, rollover is around platform midnight, Wednesday normally has triple
  swap, and settlement holidays can change multipliers. Checked 10 September.
- [Published fees](https://www.gomarkets.com/en/accounts-and-pricing/spreads-and-fees)
  and [Mauritius disclosure](https://lp.gomarkets.com/docs/mu/MU-Disclosure-Statement.pdf):
  Plus+ AUD 3 per side, AUD 6 round-turn per standard lot. Public material does
  not identify this Demo account's tariff. Earlier observed zero-charge deals
  are evidence only for those deals; they are compatible with Standard pricing.
- The disclosure's 23:59 wording and FAQ's 00:00 wording differ by a minute.
  Excluding the entire evening rollover region avoids relying on that distinction
  or an unverified DST transition convention.

## Implemented resolution

Use AUD 6/lot round-turn as a temporary **estimate** for Demo sizing and cost
feasibility; at .01 lots reserve AUD .06. This covers the two published ordinary
account alternatives, but is not a guaranteed bound on every bespoke fee.
Broker-posted P&L remains actual and must not have this allowance deducted again.
Any observed excess cost or unexpected swap requires investigation before
further qualification; no actual-cost or profitability claim follows from it.

Allow new entries only on UTC weekdays from 06:00, with the existing maximum
ten-minute horizon ending strictly before 18:00. Thus latest eligibility is
strictly before 17:50 for the ten-minute horizon. At either published offset,
normal rollover is almost three hours or more later. No settlement holiday
multiplier is needed for a horizon that does not reach rollover. This does not
guarantee closure if the host/broker fails; current protection, recovery and
unresolved-entry exclusion continue, and accidental rollover costs remain
unqualified until reconciled. It does not enable a holding forecast.

Validity ends 17 September 2026 00:00 UTC; no automatic source extension.
Missing sources, expired coverage, stale quotes, unsupported swap mode,
non-Demo surface, weekends, wider hours or longer horizons refuse entries.
Results carry `DEMO_ESTIMATE`, never `QUALIFIED_INPUTS`; the conditional holding
evaluator continues to reject such estimates as a basis for overnight HOLD.

## Gate corrections

The earlier pre-entry packet incorrectly included a fresh lifecycle and a
protected-position restart as prerequisites for any entry. Those are evidence
to collect during authorised operation, not proof that can precede the first
eligible order. Existing exposure reconciliation and tested protection remain
entry gates. Real lifecycle/restart evidence is still required for Wave 1/M20
completion. Formal final review requirements remain unchanged.

The new window supersedes the proposed 15-minute/weekend-event rule. In
particular, do not ban all of Friday merely because its *next* rollover precedes
the weekend; reject positions whose allowed horizon would approach that event.
No holiday calendar or account-specific fee agreement is fabricated.

## Review scope and limitations

This is implementation and source analysis performed in response to the latest
operator instruction. It is not an independent review of the resulting code.
Before normal entries are released, review the final implementation/configuration
and deployed identity. Retain current Demo proof separately; passing tests and
resolving these source questions do not complete Wave 1.
