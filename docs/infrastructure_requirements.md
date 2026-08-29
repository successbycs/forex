# Infrastructure requirements

## Current M2 requirement

The Forex repository needs one local PostgreSQL 16 instance on the T480 to
persist historical research snapshots. The supported MVP deployment is Docker
Desktop through WSL integration; PostgreSQL runs as the `postgres` service in
`compose.yaml` and is reachable only from the T480 itself at
`127.0.0.1:54329`.

| Component | Location | Required use | Explicitly not allowed |
| --- | --- | --- | --- |
| MetaTrader 5 | T480 Windows | GOMarketsMU-Demo historical observation | Live server, orders, generic automation |
| Forex repository | T480 WSL Ubuntu | contracts, migration, import, evidence | credentials in Git, agent execution authority |
| PostgreSQL 16 | Docker Desktop through WSL | historical source/observation/snapshot storage | LAN/public binding, credentials/order data |
| Docker named volume | local T480 | durable research-data storage | substitute for exported evidence/backup policy |

## Readiness check

Before a real import, `docker version` and `docker compose config` must both
succeed from the WSL repository directory. The database is not considered
deployed merely because `compose.yaml` or a SQL migration exists.

## Controlled data path

`runs/evidence/M1/.../capture.stdout.json` → fixed M2 import builder →
PostgreSQL source registry, raw observation, dataset snapshot, and price bars
→ retained M2 migration/import/query evidence.

No component in this path may fetch market data, accept an arbitrary source
or SQL command, expose a network listener beyond localhost, or create an
order.
