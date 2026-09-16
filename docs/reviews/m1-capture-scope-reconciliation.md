# M1 capture package: scope reconciliation

## Decision

Chris approved the supporting-tooling amendment to M30 on 2026-09-16. The
local capture package is therefore authorised. M30 remains
`AWAITING_REAL_WORLD_PROOF`: this amendment does not prove, waive, or alter
its separate bounded Demo-order requirement. M31 remains planned.

## Contract comparison

| Contract | What it authorises | Fit for stable M1 envelope package |
| --- | --- | --- |
| M30 — awaiting real-world proof | One bounded autonomous Demo order, mandatory close and reconciliation using the existing fixed path; plus authorised local, read-only evidence interpretation | Yes, but only for an envelope and report consuming retained artifacts and already-captured PostgreSQL summaries. No runtime or broker path may change. |
| M31 — next | Evaluate controlled Demo outcomes against predeclared baselines | No, yet. It depends on M30 being PROVEN, which the current state does not show. Its present wording evaluates outcomes; it does not explicitly deliver capture infrastructure. |

The registry amendment authorises this local package. It does not satisfy
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

The chosen path is a narrow M30 supporting-tooling amendment. A pure local
reader/report does not modify the Demo execution surface, so it needs focused
tests and review but no fresh broker drill. Runtime capture, schema,
orchestration, deployment, or context-gate changes remain separately scoped.

## Current status

The local envelope/report implementation is authorised. Runtime, schema,
deployment, schedule and broker changes remain blocked. M30 remains awaiting
real-world proof and M31 remains planned.
