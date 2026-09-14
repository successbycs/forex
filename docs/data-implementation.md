# Forex data implementation

## Decision

PostgreSQL is the canonical queryable store for all structured application
data: price bars, calendar facts, decisions, execution state, outcomes and
reconciliation. Immutable files hold original publisher and broker material
with receipts and hashes. A PostgreSQL row must always retain the identifier
and digest of the source evidence from which it was projected.

The repository must not treat an in-memory MT5 response, a dashboard value, or
an n8n execution as durable market data.

## Required data domains

| Domain | Immutable evidence | PostgreSQL canonical record | Consumer | Current state |
| --- | --- | --- | --- | --- |
| M1/M5 execution observations | Hash-bound MT5 assessment/spool records | `demo_decision_snapshot`, `demo_trade_proposal`, `demo_execution_attempt`, `demo_position_event`, `demo_trade_outcome` and reconciliation revisions | M1 execution/reconciliation | Present for M1 only |
| H1 context bars | Retained closed-bar observation with source/capture digest | `raw_observation`, `dataset_snapshot`, `dataset_snapshot_observation`, `price_bar` with `timeframe='H1'` and per-bar `available_at_utc` | M1 multi-timeframe context, H_SLOW research | Historical snapshot exists; continuous capture is missing |
| D1 H_SLOW bars | Retained closed-bar observation with source/capture digest | Same snapshot/bar model with `timeframe='D1'`; distinct snapshot ID and point-in-time cutoff | H_SLOW monthly decision | Adapter exists; continuous D1 capture and deployment are missing |
| Economic calendar | Immutable publisher payload and receipt | `economic_calendar_event_fact`: full normalized payload plus indexed source, event time, qualification, revision and raw/receipt hashes | M1/H_SLOW event context | Schema/adapter prepared; migration and live projection not deployed |
| H_SLOW decision, protection and outcome | Immutable input bundle, broker observations and reconciliation receipt | Dedicated H_SLOW decision/input/protection/outcome tables linked to its lifecycle intent and the H1/D1/calendar snapshot IDs | H_SLOW audit, sizing review, reconciliation | Lifecycle intents exist; this decision/outcome data model is missing |
| Research/backtest dataset | Sealed source snapshots and experiment manifests | Versioned snapshot IDs, feature/decision lineage and result summaries; never mutable live data | Research only | Partial historical/replay implementation exists |

## H data capture requirement

“H data” means completed high-timeframe EUR/USD bars, not a later calculation
from a live quote.

- **H1:** capture each newly closed EUR/USD H1 bar after it is closed and
  available. Persist its source observation and availability time, then project
  it into the snapshot/bar tables. M1 consumes only H1 records whose
  `available_at_utc` is at or before the M1 decision.
- **D1:** capture each newly closed EUR/USD D1 bar after its close and
  availability. H_SLOW consumes only D1 records that satisfy the exact
  point-in-time test in `h_slow_daily_input`; an H1 snapshot must never be
  relabelled as D1 input.
- **Calendar:** retain and project all validated calendar records, including
  quarantined/date-only records. A quarantine is data, not a reason to omit a
  row.
- **Costs and broker state:** capture terms, protection and reconciliation
  observations separately from price bars. They are required for H_SLOW entry
  and ongoing holding, but never replace a bar or calendar observation.

## Required lineage for every decision

Every M1 or H_SLOW decision must be able to name:

1. the exact price snapshot IDs and source hashes used;
2. the exact calendar projection digest and fact IDs available at the cutoff;
3. the governed strategy/configuration revision;
4. the sizing/protection/cost/reconciliation observations; and
5. its resulting proposal, attempt, broker outcome and reconciliation result.

Unknown, stale or unavailable data must remain explicit and block a new entry
where the strategy requires it; it must not be backfilled, silently defaulted
or treated as a valid zero value.

## Time policy: UTC and New Zealand operator time

All persisted instants use `TIMESTAMPTZ` / RFC3339 UTC. This is the only
canonical time used for ordering, bar-close tests, availability, point-in-time
joins and broker reconciliation. Every operator-facing H1/D1, calendar,
decision and outcome report must also render the same instant in
`Pacific/Auckland`, labelled with the actual offset and abbreviation for that
date: **NZST (UTC+12)** in winter and **NZDT (UTC+13)** in daylight saving.

The local display value is derived at query/report time, not stored as a second
mutable timestamp. Raw source/broker receipts retain their original declared
time-zone text as provenance where available. A broker/server time without a
verified offset is never silently treated as NZST or UTC.

## Critical implementation order

1. Apply and verify the reviewed calendar-fact migration, then project retained
   BLS and policy facts to PostgreSQL through fixed non-generic operations.
2. Build the H1/D1 closed-bar retention and idempotent PostgreSQL projection
   path, with per-bar availability and source lineage.
3. Add the H_SLOW decision/input/protection/outcome schema linked to those
   records and its isolated lifecycle intent.
4. Bind read-only M1/H_SLOW reports to those IDs; only then consider the
   separately governed disabled new-entry event gate and H_SLOW activation.

This is a data implementation contract, not a deployment, proof, strategy
performance claim, or authority to trade.
