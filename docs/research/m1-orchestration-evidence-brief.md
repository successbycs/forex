# Evidence Brief: M1 data capture and orchestration

## Decision

Whether to pilot Prefect for data-pipeline coordination, n8n for external
integration and PostgreSQL for validated durable facts, preserving the existing
protected M1 runtime. This brief supports a review-only ExecPlan, not deployment.

## Proposed claim or hypothesis

A single migrated ingestion pipeline can retain attributable raw inputs,
produce complete canonical rows and recover from repeat delivery or interruption
without duplicate logical effects. It should reduce bespoke scheduling work
without making trading protection depend on either orchestrator.

## Context

- Instrument: EUR/USD, GOMarketsMU-Demo only.
- Timeframes: M1 decisions; M5/H1 shadow; M15 paused.
- Data sources: existing MT5 path and existing public-source collection; BLS is the proposed pilot, not a complete EUR/USD calendar.
- Period examined: repository design and documentation inspected on 2026-09-16; no new database observation period or performance study.
- Intended use: delivery architecture and data-integrity experiment.
- Constraints: preserve broker authority, caps, immutable evidence and current milestone boundaries.

## Evidence reviewed

| Source | Type | Relevant finding | Applicability | Limitations |
| --- | --- | --- | --- | --- |
| [Prefect flows](https://docs.prefect.io/v3/concepts/flows), accessed 2026-09-16; publication date not stated | Official documentation | Python-defined flows expose tracked execution state and deployment options | Supports use as an orchestration layer | Does not prove local hosting, compatibility or exactly-once effects |
| [Prefect retries](https://docs.prefect.io/v3/how-to-guides/workflows/retries), accessed 2026-09-16; publication date not stated | Official documentation | Retry behavior can be bounded and configured | Supports safe data-step recovery design | A retry can repeat external effects; application idempotency remains required |
| [n8n Webhook](https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.webhook), accessed 2026-09-16; publication date not stated | Official documentation | HTTP-triggered workflows provide an integration boundary | Supports a bounded fetch interface | Response semantics must distinguish acknowledgement from completed retention |
| `docs/architecture.md`, BLS retention/projection modules, M20 listener/session and spool/report modules | Repository source/design | Existing boundaries and reusable ingestion/trading components | Avoids replacing working domain logic | Source inspection is not operational proof; database completeness unmeasured |

## Findings

### Evidence-supported

Prefect is Python-based orchestration, not a no-code replacement for application
logic (high confidence, official documentation). n8n can expose bounded HTTP
integration steps (high confidence). Existing repo components provide a starting
point for retention, validation, projection and protected execution (source-level
confidence; deployment not established by this brief).

### Reasonable inferences

One orchestration owner per pipeline and a stable request identity should reduce
conflicting retries and schedules. Keeping the monitor independent limits the
impact of integration outages. These are architecture recommendations, not
measured reliability improvements or evidence of profitable trading.

### Assumptions to test

Shared hosting can support the pinned Prefect deployment: inspect actual
resources, versions and access. Existing capture is incomplete: quantify gaps,
duplicates, lag and broken joins over a declared interval. The BLS path is the
smallest viable pilot: inventory its deployed services and receipts. Pass means
repeat delivery/restart yields the same canonical logical facts, corruption is
visible and rejected, and every valid fact links to retained input.

### Rejected or unsupported claims

Prefect guarantees exactly-once broker execution; every external call belongs
in n8n; a successful workflow proves complete data; higher-timeframe filters
necessarily improve M1 returns; the current database is known to have a specific
failure rate. None follows from this evidence.

## Risks to validity

Data quality: wrong expected-count denominators can turn closures into false
gaps. Bias/leakage: revised calendar data and later shadow observations cannot
be treated as earlier available inputs. Execution realism: quote drift, spread,
commissions, slippage, financing and latency remain runtime/report concerns.
Generalisability: one ingestion pilot does not prove all feeds or strategy edge.
Operational risk: two orchestration products add maintenance; stop expansion
if the bounded pilot does not justify that cost.

## Recommendation

Create the review-only ExecPlan, then, if approved, audit and run one bounded
integration pilot. Do not change trading hypotheses or promote a new filter on
the strength of infrastructure evidence. Any performance hypothesis needs its
own cost-aware out-of-sample or walk-forward evaluation.

## Proposed ExecPlan inputs

- Goal: traceable capture-to-decision-to-outcome workflow.
- Scope: measured capture, one pilot, candle identity, qualified context and joined reporting.
- Non-goals: Live, M15 authority, risk expansion or wholesale platform migration.
- Acceptance: retained provenance, safe duplicate/restart behavior, visible failures and independent protection.
- Metrics: expected/observed facts, missing joins, duplicates, capture lag, backlog and write failures.
- Decision gate: Chris reviews the plan before implementation; approved scope must fit the formal contract.
- Evidence links: sources above; [ExecPlan](../plans/m1-hybrid-prefect-postgres.md).
