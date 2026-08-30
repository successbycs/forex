# M2 proof: historical data contracts and snapshots

M2 defines a small, canonical contract layer for historical research. It does
not add a download API, generic MT5 access, live data, orders, or a trading
model. Its physical persistence definition is the versioned PostgreSQL
migrations `sql/migrations/001_m2_historical_data.sql` and
`sql/migrations/002_m2_sealed_provenance.sql`; M2 claims persistence
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
The second migration prevents updating or deleting a raw observation once a
sealed snapshot references it. The source registry remains a changeable
current catalog; a corrected historical record uses a new raw observation and
new snapshot rather than rewriting the sealed one. Capture includes a real
negative control that attempts the prohibited raw-observation mutation.

The schema stores references and hashes, not credentials or unrestricted raw
broker payloads. PostgreSQL is never exposed to the public internet. Home-LAN
administrator access is a shared-infrastructure convenience, documented in
`docs/database_access.md`; it is not an order or trading interface.

The M1 Demo source is registered as `DEMO_ONLY` and
`UNQUALIFIED_BROKER_TERMINAL_DATA`: this does not claim a licence decision or
external source qualification. Those are later M7 work.

## M2 proof surface

The proof surface is deterministic validation plus the private T480 shared
PostgreSQL service. `capture_m2_evidence.sh` invokes only fixed,
approval-gated operations in the Forex-owned PostgreSQL adapter, using the
locked shared `cs-ai-lab-infra` transport, and retains raw preflight,
migration, import, verification, sealed-provenance negative-control,
dependency, and repository-verification outputs. `verify_m2_evidence.sh` separately validates
manifest/artifact hashes, clean revision/configuration binding, success
markers, and the M2 snapshot tests without contacting MT5 or any external
source.
`check_m2_schema.py` statically checks the required PostgreSQL tables,
lineage, indexes, immutability, no-lookahead triggers, and forbidden
capabilities. It is not a database-connection claim.

The retained M2 bundle records one `DEMO_ONLY` source, one linked raw
observation, one immutable EUR/USD:H1 snapshot, and 720 price bars. Its fixed
T480 query also verifies source-to-snapshot linkage, bar availability against
the decision cutoff, and both point-in-time triggers.

`FOREX_M2_PROOF_OK` means these contracts and snapshot validations passed for
the bound revision and the fixed T480 PostgreSQL query returned the expected
dataset. It does **not** prove a market-data feed, current tick, source
licence, trading edge, order capability, independent remote execution
provenance, or M2 completion. Completion requires explicit human sign-off
before `proven_at`; the Review Board is reserved for phase gates M16, M27,
and M32.
