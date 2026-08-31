# Development platform

The intended platform is the SuccessByCS AI Lab T480: Windows hosts MetaTrader 5; WSL Ubuntu hosts development and future application workloads; shared Docker services provide PostgreSQL, n8n, and optional model runtime capabilities.

M0 inspection confirms a shared T480 transport core exists in `cs-ai-lab-infra` and the Forex adapter imports it through a fixed read-only catalog. The dependency is content-locked by owner repository, full revision and file SHA-256, and requires the locked files to be tracked. Unrelated local changes in the owner repository do not block Forex; a changed locked file or revision does. This attests only to the dependency boundary; it does not prove MT5 API access, Windows/WSL loopback forwarding, a Forex database, or a Forex container deployment. Those require separate real-machine proofs in M1–M5.

## M2 shared T480 PostgreSQL requirements

M2 uses the existing private PostgreSQL/pgvector service in the T480 AI Lab,
not a Forex-owned Compose stack, not a Windows desktop application, and not a
network service.

Required T480 setup:

1. The T480's `cs-ai-lab-infra` PostgreSQL/pgvector service is healthy on its
   internal Docker network.
2. The T480 has the reviewed Forex checkout at `/home/chris/projects/forex`.
3. The shared lab's T480-local `.env` remains local; Forex never reads, copies,
   or stores its database password.
4. The shared database is never exposed to the public internet. Administrator
   access from the home LAN or through a verified laptop-local tunnel is an
   operator convenience, not an application runtime dependency.
5. The shared platform volume is protected under the lab backup policy. The
   Forex-owned `forex` schema may contain historical data and provenance
   metadata but not account credentials or order information.

The controlled M2 procedure runs from the Forex checkout in T480 WSL through
the fixed Forex PostgreSQL adapter after a separate approval. It never accepts
an operator-provided SQL statement, database URL, table name, or source path.

The fixed operation applies `sql/migrations/001_m2_historical_data.sql` to
the Forex-owned schema and imports only the retained M1 720-bar EUR/USD H1
Demo observation. It prints source, observation, snapshot, and price-bar row
counts plus the snapshot hash. It is neither a generic database console nor a
data-download path.

PostgreSQL and MT5 must not be publicly exposed. A real M2 proof must retain
the T480 migration/import/query output and confirm the shared service is
internal before it can claim database persistence. A separately configured
closed-home-LAN administrator connection does not alter this boundary.

The retained M2 bundle now contains that migration/import/query evidence for
the fixed 720-bar EUR/USD H1 snapshot. It proves only the declared historical
database surface; it does not prove M3's MT5 CLI bridge, a current market tick,
or any execution capability.

## M11 daily GDELT collection design

The shared T480 n8n service is the planned scheduler and execution-history
surface for a Forex-owned daily GDELT aggregate job. Its existing adapter is
`cs-ai-lab-infra/scripts/n8n_adapter.py`, adapted from Autonomous Framework;
the API key remains local to T480. Forex never copies it or exposes n8n.

The daily GDELT workflow is n8n-native. It uses n8n's schedule, HTTP request,
ZIP decompression, Code and PostgreSQL nodes; it does not launch a Python job
and does not require the Forex checkout to be mounted in the n8n container.
The workflow retrieves every GKG interval for the previous closed UTC day and
persists only normalized H1 aggregates. This avoids treating a single latest
15-minute GKG file as a daily dataset. Workflow import, PostgreSQL credential
setup and activation remain explicit T480 deployment actions.
