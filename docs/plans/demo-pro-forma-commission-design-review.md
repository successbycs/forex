# Design and review plan: pro-forma Live commission for Demo trades

This is a living ExecPlan governed by `PLANS.md`. Chris authorised execution on
2026-09-23 and M33 `DEMO_PRO_FORMA_COST_ACCOUNTING` is now `IN_PROGRESS`.
Implementation is limited to the closed-trade, Demo-only reporting contract
defined here. It does not authorise Live trading, broker orders, risk/account
changes, MT5 configuration changes, or open-position valuation.

## Purpose

After implementation, an operator will see both actual broker P&L and a
separately labelled commission-only Live comparison for attributable Demo
transactions. For example, a Demo broker result of `+0.45 AUD` on a 0.01-lot
closed trade under the GO Plus+ AUD assumption would display `+0.39 AUD`
pro-forma Live P&L. The broker result remains unchanged.

## Formal milestone dependency map

M30, M31 and M32 are PROVEN reusable Demo evidence. They establish neither an
actual Live account profile nor a right to trade Live. M33 is the active
`DEMO_PRO_FORMA_COST_ACCOUNTING` contract. It authorises the migration, fixed
adapter operations, closed-trade projection, terminal ledger, T480 deployment
and formal proof described here. It does not grant broker/Live authority.

## Progress

<!-- forex-work-projection:start task=DEMO-PRO-FORMA-COMMISSION-DESIGN schema=forex.execution-work-projection.v1 -->
<!-- forex-work-item id=evidence state=DONE -->
- [x] evidence — Record pricing and ledger evidence (DONE)
<!-- forex-work-item id=design state=DONE -->
- [x] design — Specify immutable profile and pro-forma projection design (DONE)
<!-- forex-work-item id=independent-review state=DONE -->
- [x] independent-review — Obtain independent read-only design review (DONE)
<!-- forex-work-item id=design-revision state=DONE -->
- [x] design-revision — Revise design for reconciliation/versioning findings (DONE)
<!-- forex-work-item id=implementation-authority state=DONE -->
- [x] implementation-authority — Start the reviewed M33 implementation contract (DONE)
<!-- forex-work-item id=schema-projection state=DONE -->
- [x] schema-projection — Add immutable M33 pricing profile and closed-trade projection (DONE)
<!-- forex-work-item id=fixed-adapter state=DONE -->
- [x] fixed-adapter — Add fixed hash-bound stage, apply, summary and verification operations (DONE)
<!-- forex-work-item id=terminal-ledger state=DONE -->
- [x] terminal-ledger — Show separate actual and assumed commission-adjusted P&L in the terminal ledger (DONE)
<!-- forex-work-item id=local-verification state=DONE -->
- [x] local-verification — Run targeted unit, migration-contract and governance checks (DONE)
<!-- forex-work-item id=deploy-and-verify state=DONE -->
- [x] deploy-and-verify — Stage and apply only the fixed M33 assets, then collect Demo-only proof (DONE)
<!-- forex-work-item id=proof-review state=IN_PROGRESS -->
- [ ] proof-review — Prepare the M33 proof and obtain independent read-only review (IN_PROGRESS)
<!-- forex-work-item id=human-closeout state=PENDING -->
- [ ] human-closeout — Request the required human closeout decision after implementation and evidence review (PENDING)
<!-- forex-work-projection:end -->

## Context and accounting definitions

The existing `forex.demo_trade_outcome` and `forex.demo_trade_ledger` retain
actual broker price P&L, commission, fee, swap and reconciled result. They are
the audit record and must stay immutable. A **pro-forma** value is a transparent
counterfactual calculation using a declared pricing profile; it is not an MT5
result and must never replace actual P&L.

The first scenario is `GO_PLUS_AUD_V1`: AUD 3.00 per side per 1.00 standard
lot, EUR/USD and AUD account currency. The MVP projects **closed,
broker-reconciled listener trades only**. It does not calculate open position
or mark-to-market P&L. For closed volume `v`:

    per_side = -round(3.00 × v, 2)
    closed_commission = per_side + per_side
    closed_pro_forma = actual_broker_net - actual_broker_commission + closed_commission

`round` means PostgreSQL `numeric` `ROUND(value, 2)`, which rounds half away
from zero. Calculate and round each side first; round trip is the sum of those
two signed side amounts. The calculation is permitted only when one canonical
broker reconciliation version supplies all signed inputs and verifies:

    actual_broker_net = gross_price_pnl + actual_broker_commission
                        + broker_fee + broker_swap

All values must be in AUD. An absent field, non-zero consistency difference,
partial/multiple-fill outcome, invalidated outcome or incomplete repaired
outcome yields `PRO_FORMA_UNAVAILABLE`; it never defaults to zero. The formula
replaces actual commission with the assumption exactly once.

The four currently open account positions are unattributed, so the first release
excludes them at account level: `Open/unattributed positions are excluded from
closed-trade pro-forma reporting.` It must not assume they are manual or
listener positions. A later open-position feature needs a new timestamped,
attributed broker-position snapshot contract.

## Proposed schema and interfaces

Create an additive immutable `forex.demo_pricing_profile` table:

    profile_version_id, scenario_id, account_currency, instrument,
    commission_aud_per_standard_lot_per_side, standard_lot_units,
    source_url, source_retrieved_at_utc, source_content_sha256,
    publisher_entity, jurisdiction, assumed_or_verified, created_at_utc

`assumed_or_verified` is `ASSUMED` or `VERIFIED`. Every profile version is
immutable; there is no mutable status or effective-end field. First release
supports exactly one explicit scenario/version, `GO_PLUS_AUD_V1`. A future rate
or broker entity creates a successor version under a separately approved
scenario-selection policy. It cannot silently change a historical projection.

Create an additive immutable `forex.demo_trade_pro_forma_pnl` table:

    projection_id, proposal_id, profile_version_id, volume_lots,
    actual_broker_commission_aud, estimated_open_commission_aud,
    estimated_close_commission_aud, estimated_round_trip_commission_aud,
    gross_price_pnl_aud, broker_fee_aud, broker_swap_aud,
    actual_broker_net_aud, pro_forma_live_pnl_aud,
    source_reconciliation_id, canonical_source_fingerprint,
    calculation_version, calculated_at_utc

The unique key is `(proposal_id, profile_version_id, calculation_version,
canonical_source_fingerprint)`. A source repair or correction creates a new
projection rather than conflicting with or overwriting the original. The
fingerprint is a hash of the immutable canonical source input record(s), not a
reference to a mutable ledger view. A derived comparison view selects at most
one eligible projection for the fixed first-release profile: the projection
whose fingerprint equals the current canonical source. It returns no projection
when the canonical source is incomplete or changes. This prevents historical
projection rows multiplying ledger rows.

The fixed PostgreSQL adapter gains only named stage/apply/verify and read-only
projection operations. No generic SQL, remote shell, position action or MT5
order surface is permitted.

## Plan of work once authorised

First, capture and hash the selected broker pricing source and insert the
immutable `ASSUMED_GO_PLUS_AUD_V1` profile, including publisher entity and
jurisdiction. It is an accounting assumption until the specific target account
terms are confirmed.

Second, add migration, projection and verifier. Backfill projections only for
closed listener transactions with a recorded full volume, complete canonical
cost components and a verified consistency equation; do not modify past
outcomes. A `REPAIRED` reconciliation needs repaired gross, commission, fee and
swap from the same source revision before it is eligible. Rows missing
attribution, profile, volume, source identity or broker data remain unavailable.

Third, update `scripts/m20_trade_ledger_dashboard.py` and the listener view to
show actual broker net, selected profile, modelled commission and pro-forma
comparison on separate lines. Include broker commission, fee and swap in the
actual-cost presentation. Use the labels `Actual broker P&L` and
`Commission-adjusted Demo P&L — GO Plus+ AUD assumption`; never “real Live
P&L”. Preserve normal/narrow/full readability.

Fourth, deploy only through the fixed T480 adapter after its size/hash preflight.
No listener restart, new execution permission, risk change or trade is needed
to prove the reporting feature.

## Design review route

An independent reviewer receives only this plan, the evidence brief,
`sql/migrations/006_m20_demo_trading_audit.sql`, `009_m20_trade_cost_ledger.sql`,
`018_m20_broker_fee_ledger.sql`, `021_m20_fee_complete_reconciliation_ledger.sql`,
the current ledger query and dashboard. They must answer:

1. Does the formula use a complete canonical reconciliation source and avoid
   double counting actual and estimated commission?
2. Does the schema preserve append-only actual broker evidence and profile history?
3. Are Standard, GO Plus+, current account identification and manual positions
   clearly separated?
4. Do missing, repaired, partial or unverifiable inputs fail visible and safe
   rather than defaulting?
5. Does the rollout avoid changing execution, risk, broker orders and Live access?

Critical findings must be repaired in the design and reviewed again. Medium/low
findings may be accepted only with an explicit limitation and follow-up. Chris
reviews the final design and authorises or rejects the separate implementation
contract; a design review does not authorise implementation.

## Validation and acceptance

The later implementation must have fixtures proving: 0.01 lot results in -0.03
per side/-0.06 round trip; 1.00 lot results in -3.00/-6.00; actual commission
is unchanged; non-zero actual commission is replaced exactly once; actual
broker net equals the component sum; Standard is zero only when explicitly
selected; invalid/missing/repaired-incomplete/partial source produces
unavailable; repaired canonical source produces a new projection; and retries
do not duplicate a projection for the same source. Run the targeted migration,
cost-accounting, ledger-dashboard, listener-view and adapter tests plus `git
diff --check` and governance validation. Compare every prior actual ledger
field before/after.

## Idempotence and recovery

Migrations are additive. Do not backfill by updating outcomes. If a profile is
wrong, add a corrected successor profile version; retain old projections as the
record of the old assumption. If reconciliation inputs are corrected, retain the
old projection and create a new source-bound projection. If verification fails,
do not deploy or expose a partial pro-forma number.

## Surprises and discoveries

- Current Demo broker-reconciled closes show zero commission, fee and swap;
  this cannot prove the target Live account's terms.
- Current account position count is four, but none is attributable to an open
  listener attempt. The design deliberately excludes them.
- Astra review found that an open mark-to-market projection would freeze after
  its first quote and that repaired net values can be inconsistent with original
  cost components. The MVP is therefore closed-trade-only and source-versioned.
- 2026-09-23: the execution-work checker initially rejected a pending task with
  a narrative blocker. The record now reserves `blocker` for an actual
  unavailable dependency.
- 2026-09-23: the terminal `Fees` value omitted `fee_account`. M33 corrects
  that display to broker commission plus fee plus swap without altering actual
  ledger values.
- 2026-09-24: independent closeout review found that the standalone evidence
  verifier checked content hashes but did not fully bind its manifest contract.
  The verifier now rejects unexpected manifest fields/files, path traversal,
  duplicate or incomplete artifact lists, stale or future captures, and
  revision/configuration binding drift. Targeted negative-path tests cover the
  contract before fresh evidence is collected.
- 2026-09-24: the next independent review required retained fixed-operation
  stage/apply receipts and binding of every adapter and terminal-rendering
  dependency used by the verifier. The capture contract now retains and checks
  hash-bound receipts for both M33 migrations; the Triad fingerprint includes
  the evidence verifier, PostgreSQL adapter, terminal renderer and milestone
  status command.

## Decision log

- 2026-09-23: model commission in a new projection, not `commission_account`.
  This keeps actual MT5 evidence truthful and makes the scenario auditable.
- 2026-09-23: start with an `ASSUMED` GO Plus+ AUD profile. The broker publishes
  the rate, but this account's exact profile is not evidenced.
- 2026-09-23: use actual broker net minus actual commission plus modelled
  commission, with a source-component consistency check. This is robust to
  non-zero broker commission and avoids assuming original costs survive repair.
- 2026-09-23: defer open-position pro-forma reporting. It needs a separate
  attributed, timestamped snapshot contract and is not required for line-item
  closed-trade comparison.
- 2026-09-23: use PostgreSQL `pgcrypto` only to hash the complete canonical
  closed-trade source record, creating an immutable source identity without a
  generic SQL endpoint or mutation of broker evidence.

## Outcomes and retrospective

The evidence brief and Astra's read-only review produced a revised closed-trade
MVP design. M33 implementation started at 2026-09-23T03:47:40Z after Chris
instructed execution. Formal closeout remains pending: it requires deployment
evidence, independent read-only review and Chris's separate human decision.
Local implementation now has an additive migration, fixed hash-bound adapter
and terminal presentation. On 2026-09-23, 69 focused tests passed; governance,
the work projection and whitespace checks passed; T480 PostgreSQL preflight
and inspection were healthy. The fixed migration then staged by SHA-256 and
applied on T480 PostgreSQL, creating one assumed profile and 42 projections.
The fresh `formal-20260923-m33-v4` bundle independently verifies the database
invariants and human terminal rendering; formal M33 verification passed.
Independent review and human closeout remain pending.
Revision note: revised 2026-09-23 following Astra's high-severity
reconciliation and source-versioning findings.
