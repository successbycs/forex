# Infrastructure requirements

## Shared-platform requirement

All Forex runtime functions execute on the T480 AI Lab. Forex uses the
existing private PostgreSQL 16 + pgvector service owned by
`cs-ai-lab-infra`; it does not create a second project-local database service.

Forex invokes the database through its local
`scripts/postgres_pgvector_adapter.py` adapter. It exposes fixed schema and
verification actions, including M20's append-only Demo audit schema. Shared transport,
credentials, Docker, PostgreSQL, and backups remain owned by
`cs-ai-lab-infra`.
The service is reachable inside the T480 shared Docker network and on T480
port 5432 for administrator clients on the closed home LAN.

| Component | Location | Required use | Explicitly not allowed |
| --- | --- | --- | --- |
| MetaTrader 5 | T480 Windows | historical observation and M20's one fixed bounded Demo EUR/USD session path | Live server, generic automation, generic order interface |
| Forex repository | T480 WSL Ubuntu | contracts, migration, import, evidence | credentials in Git, `GOMarketsMU-Live`, generic MT5/order authority |
| PostgreSQL 16 + pgvector | T480 shared AI Lab Docker network and T480 port 5432 | Forex-owned schema for source/observation/snapshot storage | Public internet exposure, credentials/order data |
| Shared Docker volume | T480 AI Lab | durable research-data storage | substitute for exported evidence/backup policy |

## Readiness check

Before a controlled import, the fixed Forex adapter `preflight`, `inspect`,
and `vector-probe` operations must show the shared PostgreSQL/pgvector service
healthy. The M2-specific `forex-m2-apply-schema` and `forex-m2-import`
operations require explicit `--approve`; `forex-m2-verify` is read-only. The
read-only `forex-m2-provenance-negative-control` attempts an update to the
sealed raw observation and requires rejection without persisting any change.
Source-catalog metadata remains editable. The database is not considered available merely because a
migration exists.

## Controlled data paths

`runs/evidence/M1/.../capture.stdout.json` → fixed T480 M2 import operation →
shared PostgreSQL `forex` schema (source registry, raw observation, dataset
snapshot, and price bars) → retained M2 migration/import/query evidence.

No component in this path may fetch market data, accept an arbitrary source
or SQL command, expose a public internet listener, or create an order.

M20 adds a separate, non-generic path: fixed T480 M1/M5 snapshot → persisted
proposal → fixed session-capped Demo executor → append-only PostgreSQL
attempt/position/outcome records → reconciliation/evidence. The machine-local
lease and credential remain on T480; no live server or reusable MT5/order API
is introduced.

For this MVP, an administrator may connect a PostgreSQL client directly to
`192.168.0.210:5432` from the home LAN. Credentials remain in the T480 shared
lab `.env`; they are not stored in this repository.

The retained M2 evidence confirms that this controlled path imported the
single M1 snapshot: one `DEMO_ONLY` source, one linked raw observation, one
EUR/USD:H1 snapshot, and 720 price bars. That does not create a generic
ingestion service; M5 owns application-level idempotent reimport.
