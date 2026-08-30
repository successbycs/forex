# Architecture

## High-level system diagram

![High-level Forex repository architecture](assets/forex-architecture-overview.png)

## Human-controlled development review

An optional fresh Reviewer context can inspect a committed Builder revision
before expensive evidence capture. It is advice for the human and Builder, not
a new workflow gate or a completion claim.

```text
Milestone agreed
     ↓
Builder worktree: /home/chris/projects/forex
     ↓
human-approved commit
     ↓
read-only Reviewer worktree: /home/chris/projects/forex-reviewer
     ↓
review findings
     ↓
human-authorised Builder fixes, if required
     ↓
existing evidence → Triad → human sign-off → prove
```

Separate contexts provide logical review separation, not independently
controlled provenance. The existing evidence-bound Triad remains the only
structured completion recommendation, and only the human may approve a commit,
sign off, or invoke `prove`. See
[`docs/governance/review-workflow.md`](governance/review-workflow.md).

## T480 deployment boundary

```text
T480 Windows host
  MetaTrader 5 on GOMarketsMU-Demo only
  no database port exposed on LAN/public interfaces

T480 WSL Ubuntu
  Forex repository, fixed T480 adapter, evidence tooling
  shared AI Lab Docker runtime
    private PostgreSQL + pgvector service on the internal Docker network
    shared platform volume and T480-local credentials
```

All runtime functions run on the T480 AI Lab. M2 owns the versioned `forex`
PostgreSQL schema and the first controlled import of retained M1 historical
evidence; `cs-ai-lab-infra` owns the private PostgreSQL/pgvector service,
Docker network, volumes, and credentials. The import has a fixed input: the
retained 720 closed EUR/USD H1 M1 Demo observation. It records source,
revision, timestamps, hashes, redaction and lineage; it does not provide a
general download, database, MT5, shell, account, or order interface.

The Windows MT5 terminal and shared PostgreSQL service are separate T480
components. Forex code reaches MT5 only through its fixed Demo-only catalog
operation and reaches PostgreSQL only through a fixed, approval-gated T480
operation. PostgreSQL is internal to the shared Docker network and has no
published host, LAN, or public port. M5 later proves application-level
database integration and idempotent reimport. M2 does not claim persistence
until the T480 service, migration, import, and retained query evidence pass.

## Historical market-intelligence roadmap

![Historical market-intelligence architecture](assets/advanced-market-intelligence-architecture.png)

This diagram visualises the approved three-phase, historical-first roadmap. It
is a design overview, not evidence that any future adapter, source, Ollama
task, real-time feed, or Demo execution capability is deployed.

Amber ticks mean **built, but not proven**. They do not change milestone state:
M0 is the recorded `PROVEN` standing baseline, M1 is
`NEEDS_REVALIDATION`, and all later phase components remain planned or subject
to their current contract state.

### Component-to-milestone map

| Diagram component | Delivering milestones |
| --- | --- |
| Governance, evidence, review, self-attested integrity | M0 revalidation; required throughout M1–M32 |
| Demo historical export, fixed read-only bridge, persistence, multi-timeframe price data | M1–M6 |
| Source qualification and candidate macro/calendar/sentiment adapters | M7–M11 |
| Normalisation, provenance, point-in-time alignment, replay, deterministic hypotheses, one explainable offline ML baseline, walk-forward evaluation | M12–M16 |
| Non-executing context, bounded Ollama assistance, lineage, simulated risk/sizing/intent, approval and revalidation | M17–M26 |
| Fresh Demo tick, tick/spread collection, recovery safety | M27–M29 |
| Human-approved Demo execution and reconciliation | M30 |
| End-to-end comparison, forward Demo evaluation, live-readiness assessment | M31–M32 |

The diagram is a maintained overview of the intended ownership and trust
boundaries. It distinguishes the Forex repository, shared `cs-ai-lab-infra`,
and the Windows T480 / MetaTrader 5 environment. It also shows the evidence
path: the fixed local evidence runner self-attests a captured bundle; the
repository verifier checks its signature, schema, policy, and reproducibility;
then the four-role Triad-plus-domain review produces a recommendation for a
human decision.

This is an architecture map, not proof that a shared service or future
capability is currently deployed. The mutable execution record remains
`project_state.json`.

The roadmap is historical-first: closed MT5 Demo history supports the data and research layers through M16, offline shadow/risk/approval controls follow through M26, and fresh real-time Demo validation is deferred to M27–M32. Historical bars never substitute for a fresh tick, current spread, or execution proof.

The historical research layer will preserve source and availability timestamps,
revision lineage, source hashes, and dataset snapshots before aligning macro,
calendar, market-context, or sentiment observations with EUR/USD decisions.
This is necessary to prevent future leakage. Ollama, if adopted under M18, is
limited to fixed-version, offline, schema-constrained analysis of permitted
captured data; it has no transport, provider, MT5, or execution authority.

M15 adds one small, explainable ML baseline to the historical research layer.
It consumes only versioned, point-in-time-valid snapshots and produces
research probabilities plus a model card. M16 tests it chronologically against
no-change and deterministic baselines. It is not an autonomous strategy, does
not retrain online, and cannot create, approve, or execute orders.

The initial strategy shape is one EUR/USD intraday session: at a defined UTC
decision time the research layer returns `BUY`, `SELL`, or `NO_TRADE` with a
0–100 advisory score. A later Demo workflow may open at most one
human-approved position and must close it by the configured UTC cutoff or an
earlier predefined risk exit. The score is evidence for a human decision, not
an approval or execution instruction.

Target ownership boundary:

```text
cs-ai-lab-infra
  shared T480 transport, PostgreSQL, n8n, optional Ollama, internal network

Forex
  application configuration, read-only MT5 adapter, PostgreSQL historical-data schemas and migrations,
  research logic, workflows, decisions, and evidence

Windows T480
  installed MetaTrader 5 terminal; later, the Forex-owned MT5 adapter
```

Capabilities are introduced vertically, one milestone at a time. Shared infrastructure is referenced rather than copied. Fixed safety invariants remain in schemas and code, even when related operator settings are visible in configuration.

The hard boundary remains: research only; no live trading, no
`GOMarketsMU-Live`, and no order surface before M27. Actual Demo execution is
separately gated at M30. The evidence signature is self-attested integrity,
not independent execution provenance.
