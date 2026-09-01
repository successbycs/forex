# M11-R1 — bounded n8n recovery and real-world check

Status: `PLANNED`. This is a work package within M11, not a new milestone and
cannot make M11 complete. It exists because executions 19–22 showed that the
original and nested n8n designs did not produce a verified database result.

## Goal

Establish one inspectable, successful T480 n8n ingestion of a single closed
UTC hour: exactly four GDELT 15-minute archives, four retained source
provenance records, and one redacted H1 aggregate in PostgreSQL.

## Changes

1. Retire the nested daily-coordinator execution path and remove all active
   `Execute Workflow` nodes. That path triggered n8n's internal
   `workflow_statistics` duplicate-key failure.
2. Make the one fixed M11 workflow a small hourly path: schedule/webhook,
   four archive URLs, HTTP download, ZIP extraction, bounded Code aggregation,
   and fixed PostgreSQL import.
3. Keep its only outputs as source revision/hash/timestamps, article count,
   mean tone, query version, and uncertainty label. It must retain no article
   text, URL, trade recommendation, order, or generic command surface.
4. Its deterministic input is the **last fully closed UTC hour**. It performs
   no automatic backfill or retry; rerunning the exact fixed hour is idempotent
   because source observations and aggregates use deterministic identities.
5. After one verified hourly run, enable the hourly UTC schedule. Historical
   backfill is a later bounded operation and is not bundled into the first
   operational proof.

## Real-world checks (all required)

1. T480 n8n health is green before the run.
2. One fixed manual webhook run reaches a terminal `success` result; an n8n
   summary alone is insufficient.
3. PostgreSQL contains exactly four source observations for the selected UTC
   hour and one `forex.gdelt_h1_aggregate` record linked to the hourly
   provenance record.
4. The aggregate's source revisions cover `:00`, `:15`, `:30`, and `:45`; all
   four payload hashes and UTC availability timestamps are present.
5. A fixed, read-only **M11-R1 verifier** reports the selected execution ID,
   exact four archive revisions, four hashes/availability timestamps, one H1
   aggregate and deterministic linkage, plus no article-text columns and the
   experimental-context-only boundary. It is not M11 proof.
6. The local M11 tests and repository/governance validation pass.

## Failure rule

At most three attempted runs of one unchanged design are allowed. A run counts
as failed when it errors, hangs, returns a false success without the required
PostgreSQL rows, or fails a real-world check. At the third failure, stop the
workflow, record the evidence, and redesign before another execution. Do not
count an execution merely because n8n assigned it an ID.

## Exit

M11 is complete when the six checks above pass, the bound evidence verifies,
the required human review is recorded, and the closeout route succeeds.
