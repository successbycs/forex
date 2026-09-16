# M1 PostgreSQL completeness report contract

## Purpose

Define the read-only report needed to compare retained M1 capture with durable
PostgreSQL projection. This is an interface/design contract, not a database
migration, query deployment or live observation.

The report is intentionally separate from the database bridge. A captured
database response is treated as immutable input; the report builder cannot
contact PostgreSQL, T480, n8n, Prefect or MT5.

## Inputs

The builder accepts exactly two versioned inputs for one declared UTC interval:

| Input | Required fields |
| --- | --- |
| Retained envelope collection | interval, envelope contract version, raw reference/digest, terminal disposition, decision/proposal/snapshot/attempt IDs where known, source and receipt timestamps |
| Fixed PostgreSQL summary capture | query contract version/digest, captured-at time, interval, accepted/rejected records, identities, persistence times, terminal write-failure reasons and exact lifecycle/outcome identifiers |

The summary capture must declare its source query and digest. A command exit
code, screenshot or manually copied row count is not a valid input. Unknown or
unavailable input produces an `UNKNOWN` result, not an empty set.

## Output

`forex.m1.completeness-report.v1` contains:

| Field | Meaning |
| --- | --- |
| `interval` | Inclusive/exclusive UTC bounds and declared expected-count method |
| `input_provenance` | Digest/reference for both immutable inputs |
| `counts` | expected, retained, accepted, rejected, duplicate, backlog and unknown counts |
| `lag` | min/max/percentiles only where both relevant timestamps exist; otherwise `UNKNOWN` |
| `write_failures` | Exact terminal reason and affected identity; never silently omitted |
| `joins` | Raw→projection, decision→attempt and attempt→outcome matched/unmatched counts plus unmatched identities/reasons |
| `limitations` | Missing inputs, market closure/uplink assumptions, revision boundaries and unsupported legacy records |
| `execution_authority` | Always `false` |

The report must retain legacy incompatibilities as `OPERATIONAL_REFUSAL` counts
and records. It must not assign a replacement decision, reconstruct missing
timestamps, infer broker identities from price/time, or treat a refusal as a
database write failure.

## Required invariants

- Source/raw evidence is immutable; report output is a derived artifact.
- Every matched join uses a declared identity, never approximate matching.
- Repeated report construction from byte-identical inputs is deterministic.
- Duplicate source revisions remain visible and do not become duplicate logical
  decisions.
- Expected source count is `UNKNOWN` unless the market/session, uptime and
  source-cadence rules for the interval are explicitly supplied.
- Report-generation failure has no effect on listener protection or open
  position management.

## Acceptance cases for later implementation

Focused tests must prove: a complete matched synthetic set; unavailable
PostgreSQL input; duplicate retained envelope; accepted projection with no raw
receipt; raw refusal with no projection; terminal projection failure; and
unresolved broker lifecycle. In each case, output preserves inputs and labels
the limitation rather than repairing or dropping it.

## Current gap

The repository has fixed lifecycle and lineage summaries, but no captured
versioned PostgreSQL completeness summary spanning retained receipt through
projection. Wave 1 therefore reports PostgreSQL counts, lag, backlog, write
failures and joins as `UNKNOWN`. The first authorised implementation should add
only this bounded reader/builder surface after formal scope reconciliation.
