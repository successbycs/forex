# Infrastructure requirements

## Current M2 requirement

All Forex runtime functions execute on the T480 AI Lab. Forex uses the
existing private PostgreSQL 16 + pgvector service owned by
`cs-ai-lab-infra`; it does not create a second project-local database service.
The service is reachable only inside the T480 shared Docker network.

| Component | Location | Required use | Explicitly not allowed |
| --- | --- | --- | --- |
| MetaTrader 5 | T480 Windows | GOMarketsMU-Demo historical observation | Live server, orders, generic automation |
| Forex repository | T480 WSL Ubuntu | contracts, migration, import, evidence | credentials in Git, agent execution authority |
| PostgreSQL 16 + pgvector | T480 shared AI Lab Docker network | Forex-owned schema for source/observation/snapshot storage | LAN/public binding, credentials/order data |
| Shared Docker volume | T480 AI Lab | durable research-data storage | substitute for exported evidence/backup policy |

## Readiness check

Before a real import, the fixed Forex T480 `postgres_status` operation must
show the shared PostgreSQL service and pgvector healthy. The database is not
considered available merely because a migration exists.

## Controlled data path

`runs/evidence/M1/.../capture.stdout.json` → fixed T480 M2 import operation →
shared PostgreSQL `forex` schema (source registry, raw observation, dataset
snapshot, and price bars) → retained M2 migration/import/query evidence.

No component in this path may fetch market data, accept an arbitrary source
or SQL command, expose a network listener beyond localhost, or create an
order.
