# M11 system design — GDELT EUR/USD context collection

## Purpose and boundary

M11 builds an attributable, historical EUR/USD news-context dataset. It is a
research data capability, not a trading system: it creates no signal,
recommendation, position, order, live-account connection, or automated action.

The runtime is the private T480 AI Lab. n8n, PostgreSQL, credentials, Docker
and transport are owned by `cs-ai-lab-infra`; Forex owns its workflow
definitions, PostgreSQL schema, fixed adapters, verification, evidence and
documentation.

## Capability flow

```text
                    T480 private n8n
┌───────────────────────────────────────────────────────────────────┐
│  Download and stage workflow (hourly)                              │
│  last fully closed UTC hour                                        │
│       ↓                                                            │
│  four GDELT ZIP archives: :00 / :15 / :30 / :45                   │
│       ↓                                                            │
│  HTTP download → ZIP extraction → bounded aggregation              │
│       ↓                                                            │
│  four raw provenance records + one staged-hour record              │
└──────────────────────────────┬────────────────────────────────────┘
                               │ PostgreSQL hand-off only
                               ▼
┌───────────────────────────────────────────────────────────────────┐
│  Import and finalise workflow (independent schedule)               │
│  select one complete, unimported stage record                       │
│       ↓                                                            │
│  validate four expected sources                                     │
│       ↓                                                            │
│  create one linked H1 aggregate → mark stage imported               │
└──────────────────────────────┬────────────────────────────────────┘
                               ▼
                  Fixed read-only Forex verifier
                               ▼
             Operator-visible PostgreSQL result / M11 evidence
```

There is deliberately no n8n `Execute Workflow` link. Workflows communicate
only through durable PostgreSQL data, so a failure is observable at one
capability boundary rather than hidden inside a parent execution.

## Systems and ownership

| System | Capability | Owner | Boundary |
|---|---|---|---|
| GDELT 2.0 public archive | 15-minute public GKG ZIP source | External | Unqualified experimental source; retain derived data only |
| T480 n8n | schedule, HTTP, ZIP, Code and PostgreSQL nodes | Shared lab | Private runtime; no Forex worktree mount or host command nodes |
| T480 PostgreSQL | provenance, staging and final aggregates | Shared lab / Forex schema | Home-lab private service; no public exposure |
| Forex adapters | fixed install, schema and verification operations | Forex | No caller-selected shell, SQL, host, URL, MT5 or order input |
| Operator | observes results and approves milestone closeout | Human | No trading operation in M11 |

## Data design

`forex.raw_observation` contains one redacted provenance record per source
archive: deterministic observation ID, filename/revision, UTC observed and
available timestamps, SHA-256 payload hash and redacted path.

`forex.gdelt_hourly_stage` is the workflow hand-off. One row represents one
closed UTC hour and contains exactly four source records, aggregate hash,
count, tone, query version, uncertainty label and import state.

`forex.gdelt_h1_aggregate` is final research context. It contains one hourly
record linked to deterministic hourly provenance, article count, mean tone,
availability timestamp and `EXPERIMENTAL_CONTEXT_ONLY` label.

No table may contain article body, headline, original article URL, account
data, order data, trade direction, score or model output.

## Functional requirements

1. The download workflow determines the last fully closed UTC hour and builds
   exactly the four expected archive revisions.
2. It records four source provenance records and one stage record; it does not
   write a final H1 aggregate.
3. The import workflow processes only one complete unimported stage record,
   writes one H1 aggregate, and marks that stage imported atomically.
4. Both workflows are idempotent. They have no implicit backfill or automatic
   retry.
5. The fixed verifier reports source count, expected quarters, hashes,
   availability timestamps, one aggregate, lineage, no article columns and
   context-only status.
6. M11 proof requires one complete closed UTC hour: four source archives and
   one linked final aggregate, plus bound evidence and review.

## Operations and failure policy

The schedules run at five minutes past the hour for download/stage and at
twelve minutes past for import. The import only acts on completed stage data.
An operator may use the fixed local run-now operation for a bounded check.

A failed attempt is an error, hang, false success without required database
rows, or failed verifier result. At three failures of an unchanged design,
stop execution, retain the diagnostic evidence and redesign before another
attempt. An n8n execution ID alone is never success.

## Solution-architecture review

The previous nested design coupled parent success to opaque child execution and
encountered n8n internal workflow-statistics failure. PostgreSQL staging is the
smallest useful decoupling: it preserves an inspectable hand-off, makes import
restartable, and avoids a new orchestration service.

Recommended MVP controls:

- Keep one source, one instrument-context query and one hourly aggregate.
- Keep stage records small and redacted; JSON provenance is sufficient for four
  archive records.
- Make source completeness a database/import gate rather than trying to infer
  completion from a workflow summary.
- Use fixed verification queries, not a generic database console exposed to
  workflows.
- Defer historical backfill batching, enrichment, ML features, alerts and any
  n8n retry framework until the hourly path has a verified T480 result.

Potential fixes if the first real run fails:

| Symptom | Likely cause | MVP response |
|---|---|---|
| Fewer than four archives | unavailable/archive HTTP failure | retain failed stage state; fix source handling, do not finalise |
| Stage exists but import does not | schedule/credential/query issue | inspect fixed workflow execution and run the read-only verifier |
| Duplicate aggregate | missing deterministic key/idempotency | enforce unique stage/hour and aggregate identities |
| n8n parent/child error | accidental nested workflow | remove `Execute Workflow`; retain PostgreSQL hand-off only |
| Data has no matching terms | valid zero-count hour | retain count zero and tone zero with uncertainty label |

## Out of scope

This design does not establish a trading edge, live quote quality, execution
quality, broker API access, sentiment-model validity, forecasting, order
placement or live trading. Those are later milestones.

## Step-by-step implementation and deployment plan

### A. Local implementation

1. Create the `gdelt_hourly_stage` migration with deterministic `stage_id`,
   unique UTC bucket, four-source payload, aggregate values and nullable
   `imported_at_utc` marker.
2. Implement the download-and-stage workflow JSON. It must contain only
   schedule/webhook, HTTP, ZIP extraction, Code and PostgreSQL nodes; reject
   both host-command and `Execute Workflow` nodes in tests.
3. Implement the separate import-and-finalise workflow JSON. It uses a fixed
   PostgreSQL query to select one complete unimported stage record, insert its
   final aggregate, and mark it imported.
4. Update the fixed n8n installer so it upserts the two named workflows and
   binds the existing T480-local PostgreSQL credential without exposing it.
5. Update the Forex PostgreSQL adapter with fixed operations to apply the
   staging migration and inspect the most recent completed hour. Do not add a
   generic SQL interface.
6. Update architecture, M11 proof notes, recovery plan and tests together.
7. Run JSON validation, Python compilation, M11 tests, repository tests as
   appropriate, and milestone registry validation. Resolve all failures before
   committing.

### B. Commit and deploy to T480

1. Inspect `git status`; preserve unrelated work.
2. Commit only the verified Forex M11-R1 files and push the exact revision.
3. Update the shared fixed T480 deployment pin to that revision. Do not add a
   generic transport operation.
4. Run the fixed Forex deployment operation. Confirm the T480 checkout is at
   the exact committed revision.
5. Apply the existing M11 aggregate migration and then the M11-R1 staging
   migration using the fixed Forex PostgreSQL adapter.
6. Run fixed schema verification and confirm both aggregate and stage tables
   exist.
7. Upsert the two workflows through the fixed Forex n8n adapter, bind the
   existing T480-local credential, then activate their independent schedules.
8. Confirm T480 n8n and PostgreSQL health before any run.

### C. Bounded real-world acceptance check

1. Trigger the fixed download-and-stage workflow once on T480 for the last
   fully closed UTC hour.
2. Inspect its terminal execution result and confirm one stage record plus
   four source provenance rows exist.
3. Allow the independent import workflow to process that stage record, or use
   its fixed operator trigger if one is explicitly implemented.
4. Run the read-only M11-R1 verifier. It must report four expected quarters,
   hashes, availability timestamps, one linked aggregate, no article fields
   and `EXPERIMENTAL_CONTEXT_ONLY`.
5. Record the result as M11 evidence readiness.
6. If any check fails, record its execution ID and diagnostic output. After
   three failures of the same design, disable further runs and redesign.

### D. M11 completion path after readiness

1. Use the working hourly collection to retain one complete closed UTC hour:
   four source archives and one final aggregate.
2. Capture a fresh M11 evidence bundle bound to the commit, configuration and
   fixed verification results.
3. Independently verify that bundle.
4. Obtain current read-only Solution Architect, Senior Developer, AI Engineer
   and Financial Domain Expert reviews; apply only MVP-value findings.
5. Perform delegated human sign-off and the repository closeout command only
   when all M11 contract requirements genuinely pass.
