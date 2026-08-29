# Development platform

The intended platform is the SuccessByCS AI Lab T480: Windows hosts MetaTrader 5; WSL Ubuntu hosts development and future application workloads; shared Docker services provide PostgreSQL, n8n, and optional model runtime capabilities.

M0 inspection confirms a shared T480 transport core exists in `cs-ai-lab-infra` and the Forex adapter imports it through a fixed read-only catalog. The dependency is content-locked by owner repository, full revision and file SHA-256, with tracked-file and clean-worktree requirements. The original untracked-file condition has been resolved: the currently configured shared-core revision and files are tracked and match the lock. This attests only to the dependency boundary while its owner worktree remains clean; it does not prove MT5 API access, Windows/WSL loopback forwarding, a Forex database, or a Forex container deployment. Those require separate real-machine proofs in M1–M5.

## M2 local PostgreSQL requirements

M2 uses PostgreSQL as a local research persistence service on the T480, not
as a Windows desktop application and not as a network service.

Required T480 setup:

1. Docker Desktop installed and running on Windows.
2. Docker Desktop **Settings → Resources → WSL Integration** enabled for the
   Ubuntu distribution containing this repository.
3. The repository run from that WSL distribution, with Docker available as
   `docker` in its shell.
4. PostgreSQL started only through the repository's `compose.yaml`. Its port
   is explicitly bound to `127.0.0.1:54329`, never `0.0.0.0` or a LAN address.
5. The `forex-postgres-data` named Docker volume retained locally under the
   operator's backup policy. It may contain historical data and provenance
   metadata but must not contain account credentials or order information.

After Docker integration is enabled, the controlled M2 procedure is:

```bash
docker compose config
bash scripts/import_m2_postgres.sh
```

The fixed script applies `sql/migrations/001_m2_historical_data.sql` and
imports only the retained M1 720-bar EUR/USD H1 Demo observation. It prints
source, observation, snapshot, and price-bar row counts plus the snapshot
hash. It is neither a generic database console nor a data-download path.

PostgreSQL and MT5 must not be publicly or LAN exposed. A real M2 proof must
retain the migration/import/query output and confirm the local bind before it
can claim database persistence.
