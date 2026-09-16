# M1 capture package: scope reconciliation

## Decision

The approved capture package is not within M30's current formal contract, and
M31 cannot yet authorise it. Implementation must wait for an explicit formal
scope decision. Design and read-only contract work may continue.

## Contract comparison

| Contract | What it authorises | Fit for stable M1 envelope package |
| --- | --- | --- |
| M30 — active | One bounded autonomous Demo order, mandatory close and reconciliation using the existing fixed path | No. A new retained-assessment envelope/source contract and completeness surface are capability changes outside its stated proof surface. |
| M31 — next | Evaluate controlled Demo outcomes against predeclared baselines | No, yet. It depends on M30 being PROVEN, which the current state does not show. Its present wording evaluates outcomes; it does not explicitly deliver capture infrastructure. |

The user's goal authorises this package as a delivery objective, but does not
by itself amend `milestone_registry.json` or satisfy M31's M30 dependency.

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

## Required authority before implementation

Choose one of these explicit paths:

1. **Dedicated follow-on capture milestone:** add a new contract after M30,
   with this package's source/projection proof surface. This preserves M30's
   focused execution proof.
2. **Amend M30:** explicitly add the envelope/completeness scope and accept a
   fresh affected M30 proof after the change. This is slower and conflates
   capture infrastructure with the bounded Demo-order proof.
3. **Defer implementation:** retain this design until M30 is proven and M31 is
   explicitly amended to include the capture package.

Recommendation: option 1. It keeps the existing MVP proof narrow and gives the
capture package a clear, testable surface without a needless repeat of
unaffected evidence.

## Current status

Design is ready. Runtime, schema, deployment, schedule and broker changes are
blocked pending one of the above formal scope decisions. No formal state has
been changed by this document.
