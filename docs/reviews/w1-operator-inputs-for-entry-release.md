# Wave 1 operator inputs for fee and rollover qualification

Prepared 2026-09-10. This is a fact-collection form, not a request to enable
entries. Leave the listener in maintenance hold while it is completed.

## Required records

Provide a dated account record, broker support response, account agreement or
other broker-issued source that identifies all of the following for the exact
`GOMarketsMU-Demo` AUD account:

| Required fact | Acceptable value | Why it is needed |
| --- | --- | --- |
| Account pricing arrangement | `STANDARD`, `GO_PLUS`, or a named documented alternative | Public account pages describe alternatives but do not identify this account. Historical zero commission is not enough. |
| Round-turn EURUSD charge | AUD per 100,000 units, including every commission and fixed fee | Becomes `round_trip_charge_aud_per_lot`; use zero only if the account record expressly confirms commission-free EURUSD trading. |
| Charge source and effective date | Broker document URL/reference, capture date, and expiry/change condition if stated | Becomes `charge_source`; lets later reconciliation distinguish a changed schedule. |
| Rollover time | Platform/server local time and timezone or explicit UTC time | The public disclosure says trading-day close is 23:59 platform time; this must be tied to the actual Demo server clock. |
| Calendar coverage | UTC start/end covering each intended release/operation window | Prevents stale or assumed rollover inputs. |
| Rollover events | ISO-8601 UTC timestamps and multiplier for each event in the coverage window | Becomes the canonical `rollovers` list. Include normal, Wednesday/triple and any broker-declared holiday event. |
| DST/holiday source | Broker calendar or support confirmation for the coverage window | Prevents a server offset from being assumed across a clock or holiday change. |

Do not send credentials, account numbers, screenshots containing credentials,
or a broker portal export with unrelated personal data. A redacted document or
a written transcription of the fields above is sufficient.

## Proposed canonical configuration shape

After the values are verified and the M20.13 amendment is approved, Terra will
replace only the `null`/empty financing values in `config/runtime.yaml` with a
reviewable record of this form:

```yaml
financing_policy:
  policy_version: forex.m20.financing.v1
  exit_mode: EXISTING_OWNER_EXITS
  maximum_quote_age_seconds: 10
  calendar_valid_from_utc: "YYYY-MM-DDTHH:MM:SSZ"
  calendar_valid_until_utc: "YYYY-MM-DDTHH:MM:SSZ"
  calendar_source: "broker-issued reference and capture date"
  rollovers:
    - at_utc: "YYYY-MM-DDTHH:MM:SSZ"
      multiplier: 1
    - at_utc: "YYYY-MM-DDTHH:MM:SSZ"
      multiplier: 3
  round_trip_charge_aud_per_lot: 0.00
  charge_source: "account-specific fee reference and effective date"
```

The example numerical charge is a placeholder, not a recommendation. The
actual value must be the documented account value. A nonzero other fee belongs
in this all-in round-turn allowance; it must not later be duplicated in the
actual broker ledger.

## Decision to record

Approve or amend the proposed [M20.13 rollover boundary](w1-m20.13-rollover-amendment-proposal.md): reject new entries when the next qualified rollover is
under 15 minutes away, reject entries ahead of weekend/public-holiday rollover,
and preserve existing broker protection if a close is uncertain. This is the
intraday fallback; it does not authorise holding over rollover.

## What happens after receipt

Terra will validate the source values, update the configuration and exact M20
contract amendment under maintenance hold, run the targeted calculator/risk
tests, and provide the fixed release/configuration/evidence package for Astra's
read-only pre-entry review. Only after that review and all existing Wave 1 entry
gates are satisfied can normal Demo entry release be considered.
