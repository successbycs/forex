# M1 capture baseline

## Scope

This is the Wave 1, read-only baseline for the proposed hybrid M1 workflow. It records what was observable in the checkout and retained local evidence on 2026-09-16. It neither queries a live database nor claims that a service is currently running. It changes no runtime, schema, schedule, broker state or formal milestone.

The required future comparison is:

    expected source facts → retained raw evidence → validated PostgreSQL facts
      → decision/refusal → attempt → broker lifecycle → reconciliation

This baseline establishes the first two columns where local evidence permits; PostgreSQL observation is explicitly unknown rather than estimated.

## Evidence reviewed

| Surface | Evidence inspected | Establishes | Does not establish |
| --- | --- | --- | --- |
| M1 listener spool export | `runs/local/m20-current-assessments/`, `src/forex/m20_{assessment_spool,spool_page,spool_drain}.py` | Immutable, hash-bound local capture and contiguous sequence checks exist | Continuous listener/exporter availability |
| M1 event annotation | `runs/local/m1-event-reports/m1-event-service-report-20260916T021026263Z-f7d1b430833538589dd7bf7200a19672f2ab9e62387e357d544c1612bdc5b47a.json` | Inputs are attached or refused with a reason | An event veto is enabled; it remains annotation-only |
| BLS retained calendar | `runs/local/bls-event-store/`, `src/forex/event_capture_store.py`, BLS n8n assets | Raw, metadata and journal records are retained | Complete EUR/USD event coverage or active n8n deployment |
| M20 lifecycle history | `runs/local/m20-history-captures/` and fixed history/reconciliation tooling | Historical execution and reconciliation outcomes are retained | Current account state or database rows |
| PostgreSQL contract | `sql/migrations/006_m20_demo_trading_audit.sql`, later M20 migrations, `t480/m20_postgres_audit_bridge.py` | Intended durable proposal-to-outcome model and fixed write actions | Current table contents, write lag, backlog or duplicates |

## Observed measurements

### Listener assessment capture

The local capture root contains **16** complete assessment directories for listener release `43fc2c9331b2fa5e`, sequences **37511–37526**. The sequence is contiguous within this retained sample; each directory has one source record, extracted operation payload and hash-bound receipt. All 16 proposals are `NO_TRADE`, and inspected proposal and snapshot identities are unique.

The sample begins at `2026-09-15T03:11:03Z` and ends at `2026-09-15T03:12:46Z`: about **104 seconds**. It is a valid short sample, not proof of continuous M1 coverage. The exporter is designed to run every two minutes (`deploy/m20-assessment-export/` and `config/operating_schedule_register.json`), but that register marks deployment `DEPLOYED_OBSERVATION_NOT_ASSERTED`.

| Measure | Result | Classification |
| --- | --- | --- |
| Expected listener assessments in a declared continuous interval | Unknown; no uptime/candle-coverage interval was retained | Unknown, not zero |
| Observed retained assessments | 16 | Measured |
| Missing records inside retained sequence | 0 | Measured only after sequence 37511 begins |
| Duplicate local capture identities | 0 observed | Measured only in this 16-record sample |
| Capture delay / backlog | Unknown; source receipt and local retention time are not comparable metrics yet | Unknown |
| Database projection or write failure | Unknown; no live PostgreSQL query was authorised or available | Unknown |

The source reader deliberately permits its first record to be a baseline. It cannot claim anything about records before 37511. This is an expected absence of evidence, not proof that 37,510 records were missing.

### Event-context compatibility

The most recent completed retained annotation report processed **38** assessment artifacts: **5 attached** and **33 refused**. Refusals were explicit: 24 `UNSUPPORTED_SNAPSHOT_SCHEMA`, 5 `ASSESSMENT_OPERATION_OUTPUT_NOT_JSON`, and 4 `ASSESSMENT_CLOCK_ORDER_INVALID`.

This is a measured compatibility/provenance gap. It is not a claim that underlying decisions are invalid, nor evidence that a calendar gate blocked a trade. Current event context is non-executing annotation.

### BLS retained input

The BLS store has **141** acquisition files, **141** raw files, **141** metadata files and **141** immutable journal generations. Its newest inspected journal contains 141 captures and four derived records. Matching counts demonstrate local store completeness by object count, not publication completeness, freshness, source authenticity or EUR/USD calendar completeness.

### Lifecycle and reconciliation baseline

The retained historical M20 lifecycle summary contains **70** rows: 60 closed and 10 terminal rejections. Of the closed rows, 37 are `CLOSED_MATCHED` and 23 are `CLOSED_RECONCILIATION_ERROR`. This is a historical reconciliation signal that future joined reporting must expose. It is not a current database measurement and must not be used to infer a present error rate.

## Expected absences, gaps and unknowns

| Category | Finding | Required treatment |
| --- | --- | --- |
| Expected absence | No retained evidence before the first spool sequence | Keep the baseline boundary; do not call it a gap |
| Confirmed gap | 33/38 annotation inputs refused for explicit format/schema/clock reasons | Preserve refusal reasons and define a stable assessment envelope |
| Confirmed limitation | 16 records cover only about 104 seconds | Do not claim continuous coverage; measure a declared market-open interval later |
| Unknown | Current PostgreSQL counts, duplicate facts, write failures, lag and backlog | Obtain a fixed read-only projection report before Wave 2 cutover |
| Unknown | Live timer/host health | Observe its declared health surface without altering schedules |
| Out of scope | Broker execution availability and profitability | Do not infer either from retention records |

## Current path and ownership

The current M1 path is T480 listener → immutable release-namespaced spool → fixed paged read → local mirror → local immutable capture. The listener and monitor own trading and protection. The local exporter owns capture only. The fixed PostgreSQL bridge owns catalogued persistence actions. n8n has no trading or recovery authority. Prefect is not installed or used in this baseline.

## Smallest repair candidate

Before adding an orchestrator, define and validate one stable **assessment envelope** that every retained M1 assessment can expose. It must carry identity, timestamps, source digest, contract version and explicit terminal outcome described in [M1 data contract](../workflows/m1-data-contract.md). The change must preserve raw records and report an unsupported historical record as a refusal, not rewrite it.

This is smaller and more informative than installing Prefect: it resolves the measured 33/38 compatibility failure and makes the later PostgreSQL comparison possible. It is a Wave 2 candidate only after explicit scope approval.

## Wave 2 decision gate

Proceed with one pipeline pilot only when a read-only report can provide, for a declared UTC interval: expected source count with market-closure/uplink rules; retained count; PostgreSQL accepted/rejected count; duplicate count; oldest unprojected receipt; write-failure reasons; and exact decision-to-attempt-to-outcome join coverage. A missing measurement remains `UNKNOWN`.

## Audit record

Owned paths: this review, `docs/workflows/m1-data-contract.md`, and the Wave 1 progress note in `docs/plans/m1-hybrid-prefect-postgres.md`.

Read-only checks: source/path inventory; local sequence/receipt inspection; retained annotation report inspection; BLS object-count comparison; migration and bridge review. The existing default continuation checker currently refuses because its default plan resolves to the repository directory; that unrelated issue was not changed under this read-only audit.

Limitations: no live database, host-health, broker or n8n observation was performed. No raw evidence was altered.
