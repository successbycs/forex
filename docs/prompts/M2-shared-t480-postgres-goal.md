# M2 goal: shared T480 PostgreSQL persistence

```text
Complete M2 using the shared private PostgreSQL/pgvector service on the T480 AI Lab.

Architecture boundary:
- All runtime operations must execute on the T480 AI Lab.
- cs-ai-lab-infra owns Docker, PostgreSQL/pgvector, credentials, internal network, and backups.
- Forex owns only the forex PostgreSQL schema, its reviewed migration, fixed import workflow, contracts, tests, evidence, and review.
- Do not create or use a Forex-local Docker Compose database. Do not publish PostgreSQL to host, LAN, or public interfaces.

First run read-only T480 checks proving the shared PostgreSQL service is healthy, internal-only, and has pgvector enabled. Retain raw outputs.

Then use only a fixed, approval-gated Forex operation—never arbitrary SQL, shell input, database URLs, table names, or source paths—to:

1. Apply the reviewed sql/migrations/001_m2_historical_data.sql migration to the Forex-owned forex schema on the T480 shared PostgreSQL service.
2. Import only the retained M1 GOMarketsMU-Demo historical evidence: exactly 720 closed EUR/USD H1 bars.
3. Store the source registry record, raw-observation metadata, source revision, timestamps, payload hash/path, redaction declaration, immutable dataset snapshot, and price bars.
4. Run a separate fixed read-only verification query proving:
   - 1 source registry row;
   - 1 raw observation;
   - 1 immutable snapshot;
   - exactly 720 price bars;
   - snapshot hash and source lineage match the retained M1 evidence;
   - no bar or raw observation available after the snapshot decision cutoff is accepted.

Preserve: Demo-only, read-only MT5 access, no GOMarketsMU-Live, no orders, no generic MT5/account/download surface, no credentials in Git or evidence, no trading/performance claims, and no independent-provenance claim.

If the existing shared-lab PostgreSQL adapter cannot safely apply a Forex-owned reviewed migration, implement the smallest fixed, hash-bound extension in the appropriate repository; do not bypass it with ad-hoc remote commands.

Update M2 documentation, infrastructure requirements, tests, capture script, independent verifier, and milestone registry as needed. Keep M5 as the later application integration and idempotent reimport milestone.

Run M2 tests, full repository tests, static migration validation, governance validation, and the T480 real-world capture/verifier. Retain raw migration/import/query outputs and hashes. Obtain a fresh Triad-plus-domain recommendation bound to the exact committed revision, configuration, M2 contract, verifier, and evidence.

You are authorized to create only the reviewed forex schema/tables and the fixed 720-bar M2 import in the shared T480 PostgreSQL database. Request my explicit approval before any commit and again before marking M2 proven.
```
