# M2 proof: historical data contracts and snapshots

M2 defines a small, canonical contract layer for historical research. It does
not add a download API, generic MT5 access, live data, orders, or a trading
model. Its physical persistence definition is the versioned PostgreSQL
migration `sql/migrations/001_m2_historical_data.sql`; M2 claims persistence
only after the fixed T480 shared-adapter migration, import, and verification
operations have actually succeeded.

## Contract objects

- **Source registry entry** — owner, licence/cost posture, version, endpoint
  policy, retention, historical/revision support, timezone/outage policy,
  approval status, secrets reference, and provenance limitation.
- **Raw observation** — source and source revision, observation,
  availability, and retrieval timestamps, UTC policy, content hash, retained
  path, and redaction declaration.
- **Price bar** — canonical EUR/USD OHLCV, raw-observation lineage, and the
  earliest timestamp at which the bar is usable.
- **Dataset snapshot** — a content-addressed, chronological collection with a
  fixed UTC decision cutoff. Every included bar must have been available no
  later than that cutoff.

## PostgreSQL physical schema

The migration creates `forex.source_registry`, `forex.raw_observation`,
`forex.dataset_snapshot`, `forex.dataset_snapshot_observation`, and
`forex.price_bar`. Foreign keys preserve lineage; checks enforce UTC,
canonical EUR/USD, allowed timeframes, hashes, positive OHLC values, and
valid OHLC ranges. A trigger rejects bars whose availability exceeds the
snapshot cutoff; a second trigger rejects later raw-observation lineage.
Sealed snapshot headers, bars, and lineage links cannot be updated or deleted.

The schema stores references and hashes, not credentials or unrestricted raw
broker payloads. PostgreSQL is not exposed to the LAN or public internet.

The M1 Demo source is registered as `DEMO_ONLY` and
`UNQUALIFIED_BROKER_TERMINAL_DATA`: this does not claim a licence decision or
external source qualification. Those are later M7 work.

## M2 proof surface

The proof surface is deterministic validation plus the private T480 shared
PostgreSQL service. `capture_m2_evidence.sh` invokes only fixed,
approval-gated operations in the `cs-ai-lab-infra` PostgreSQL adapter and
retains their raw preflight, migration, import, verification, dependency, and
repository-verification outputs. `verify_m2_evidence.sh` separately validates
manifest/artifact hashes, clean revision/configuration binding, success
markers, and the M2 snapshot tests without contacting MT5 or any external
source.
`check_m2_schema.py` statically checks the required PostgreSQL tables,
lineage, indexes, immutability, no-lookahead triggers, and forbidden
capabilities. It is not a database-connection claim.

`FOREX_M2_PROOF_OK` means these contracts and snapshot validations passed for
the bound revision and the fixed T480 PostgreSQL query returned the expected
dataset. It does **not** prove a market-data feed, current tick, source
licence, trading edge, order capability, or independent remote execution
provenance.
