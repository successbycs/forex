# Trading price-data database: administrator access

The historical EUR/USD price data is stored in PostgreSQL on the T480 AI Lab.
Use the verified SSH tunnel on this laptop rather than an unverified direct
T480 LAN address:

```text
Host: 127.0.0.1
Port: 15432
Database: value of POSTGRES_DB in the T480 shared-lab .env
User: value of POSTGRES_USER in the T480 shared-lab .env
Password: value of POSTGRES_PASSWORD in the T480 shared-lab .env
```

The connection string shape is:

```text
postgresql://<user>:<password>@127.0.0.1:15432/<database>?sslmode=disable
```

Do not put the password in this repository, source code, screenshots, or
evidence bundles.

## Connect with a desktop client

Use DBeaver, pgAdmin, or another PostgreSQL client on this laptop. Create a
PostgreSQL connection with the values above, then browse:

```text
database
  └─ schemas
      └─ forex
          ├─ source_registry
          ├─ raw_observation
          ├─ dataset_snapshot
          ├─ dataset_snapshot_observation
          └─ price_bar
```

The current M2 dataset is one sealed EUR/USD H1 snapshot containing 720
historical price bars. It is `DEMO_ONLY` historical research data, not live
pricing and not an order interface.

## Read-only project adapter

For a reliable project-local inspection path that does not depend on a desktop
database client, use the Forex-owned adapter. It reads credentials from this
repository's ignored `.env` and reaches PostgreSQL through the shared T480
transport. It exposes every Forex table but accepts no arbitrary SQL or trading
operation:

```bash
python3 scripts/postgres_admin_adapter.py status
python3 scripts/postgres_admin_adapter.py tables
python3 scripts/postgres_admin_adapter.py read --table price_bar --limit 20
python3 scripts/postgres_admin_adapter.py schema --table dataset_snapshot
python3 scripts/postgres_admin_adapter.py export-html
```

To write one validated row, create a JSON file beneath this repository whose
fields exactly match the target table's columns, then use explicit approval:

```bash
python3 scripts/postgres_admin_adapter.py write \
  --table source_registry --file local/source.json --approve
```

`source_registry` is upserted because its catalog metadata is editable. The
other tables allow inserts only; sealed snapshots, their links, price bars, and
raw observations remain protected by PostgreSQL constraints and triggers.

## Useful read-only queries

```sql
SELECT snapshot_id, instrument, timeframe, decision_cutoff_utc, sealed_at_utc
FROM forex.dataset_snapshot;
```

```sql
SELECT time_utc, open, high, low, close, volume
FROM forex.price_bar
WHERE snapshot_id = 'm2-m1-eurusd-h1-720'
ORDER BY time_utc
LIMIT 20;
```

```sql
SELECT source_id, approval_status, owner, license, provenance_note
FROM forex.source_registry;
```

## If the connection does not work

First test the verified local tunnel from your Windows laptop:

```powershell
Test-NetConnection 127.0.0.1 -Port 15432
```

If it fails, the SSH tunnel needs to be started again. The direct T480 LAN
endpoint at `192.168.0.210:5432` is not yet verified from this laptop, so do
not use it as a connection address.
