# M1 capture package: scope reconciliation

## Decision

Chris approved the hybrid-delivery amendment to M30 on 2026-09-16. Retained
reporting, read-only persistence measurement, measured capture repair,
candle/refusal handling, final input checks, qualified context and outcome
reporting may proceed without an old-version Demo trade. M30's final bounded
Demo-order requirement remains unchanged; M31 remains planned.

## Contract comparison

| Contract | What it authorises | Fit for stable M1 envelope package |
| --- | --- | --- |
| M30 — hybrid delivery / final proof pending | One bounded autonomous Demo order, mandatory close and reconciliation; plus bounded M1 delivery using existing persistence | Yes. Delivery precedes and is proven by the final-version M30 lifecycle. No migration, scheduler, Live, strategy/risk, generic interface or broker-retry change is authorised. |
| M31 — next | Evaluate controlled Demo outcomes against predeclared baselines | No, yet. It depends on M30 being PROVEN, which the current state does not show. Its present wording evaluates outcomes; it does not explicitly deliver capture infrastructure. |

The registry amendment authorises these delivery packages. It does not satisfy
M31's M30 dependency or change M30's `proven_at` requirement.

## Proposed bounded package

The package may change only local, non-broker capture interpretation and its
focused tests:

1. Define `forex.m1.assessment-envelope.v1` as an immutable wrapper around
   an existing retained source artifact. It binds raw source reference/digest,
   listener release/sequence where present, observation and receipt times,
   known decision identity and terminal disposition.
2. Emit `TERMINAL_DECISION` only when an existing `BUY`, `SELL` or `NO_TRADE`
   proposal and its snapshot validate without repair. Emit `OPERATIONAL_REFUSAL`
   for unsupported schema, malformed operation output, impossible clocks,
   missing required provenance, or unavailable assessment.
3. Retain unsupported historical artifacts untouched and generate a separate
   derived refusal record referencing their exact digest. Never rewrite raw
   assessment files or synthesise a proposal.
4. Add a pure, read-only completeness-report builder. It consumes retained
   envelope records and an already-captured fixed PostgreSQL summary; it never
   opens a database connection, invokes an adapter, or sends a broker command.

This package does not add candle-level execution uniqueness, database fields,
Prefect, n8n activation, a calendar veto, strategy behaviour, risk behaviour
or a broker retry.

## Proof impact

Changing the listener's retained source shape, fixed adapter output, database
schema, or governed runtime configuration is a material M30 proof invalidator.
A purely local interpreter that consumes already-retained raw artifacts must be
tested and documented, but does not by itself change the declared M30 execution
surface. This distinction must be preserved in the implementation plan and
review record.

## Authority disposition

The chosen path is the M30 hybrid-delivery amendment. A pure local reader/report
does not modify the Demo execution surface. Adopted runtime changes require
targeted tests and are demonstrated by M30's final-version broker proof; they
do not require a prior old-version drill. Migration, orchestration/deployment
and scheduler changes remain separately scoped.

## Current status

The local envelope/report is complete. Read-only persistence measurement and
the bounded M1 delivery packages are authorised. Migration, deployment,
schedule, Prefect/n8n and broker-authority changes remain blocked. M31 remains
planned until M30 is proven.
