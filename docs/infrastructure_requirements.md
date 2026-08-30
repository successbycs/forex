# Infrastructure requirements

## Current M2 requirement

All Forex runtime functions execute on the T480 AI Lab. Forex uses the
existing private PostgreSQL 16 + pgvector service owned by
`cs-ai-lab-infra`; it does not create a second project-local database service.

Forex invokes the database through its local
`scripts/postgres_pgvector_adapter.py` adapter. It exposes only the fixed M2
preflight, schema, import, and verification actions. Shared transport,
credentials, Docker, PostgreSQL, and backups remain owned by
`cs-ai-lab-infra`.
The service is reachable only inside the T480 shared Docker network.

| Component | Location | Required use | Explicitly not allowed |
| --- | --- | --- | --- |
| MetaTrader 5 | T480 Windows | GOMarketsMU-Demo historical observation | Live server, orders, generic automation |
| Forex repository | T480 WSL Ubuntu | contracts, migration, import, evidence | credentials in Git, agent execution authority |
| PostgreSQL 16 + pgvector | T480 shared AI Lab Docker network | Forex-owned schema for source/observation/snapshot storage | LAN/public binding, credentials/order data |
| Shared Docker volume | T480 AI Lab | durable research-data storage | substitute for exported evidence/backup policy |

## Readiness check

Before a controlled import, the fixed Forex adapter `preflight`, `inspect`,
and `vector-probe` operations must show the shared PostgreSQL/pgvector service
healthy. The M2-specific `forex-m2-apply-schema` and `forex-m2-import`
operations require explicit `--approve`; `forex-m2-verify` is read-only. The
read-only `forex-m2-provenance-negative-control` attempts updates to sealed
provenance records within PostgreSQL and requires rejection without persisting
any change. The database is not considered available merely because a
migration exists.

## Controlled data path

`runs/evidence/M1/.../capture.stdout.json` → fixed T480 M2 import operation →
shared PostgreSQL `forex` schema (source registry, raw observation, dataset
snapshot, and price bars) → retained M2 migration/import/query evidence.

No component in this path may fetch market data, accept an arbitrary source
or SQL command, expose a network listener beyond localhost, or create an
order.

The retained M2 evidence confirms that this controlled path imported the
single M1 snapshot: one `DEMO_ONLY` source, one linked raw observation, one
EUR/USD:H1 snapshot, and 720 price bars. That does not create a generic
ingestion service; M5 owns application-level idempotent reimport.
