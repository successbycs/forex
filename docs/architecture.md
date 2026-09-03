# Architecture

## High-level system diagram

![High-level Forex repository architecture](assets/forex-architecture-overview.png)

## Completion-review gates

Every milestone needs implementation, verification, and the declared
real-world proof. The active contract then determines review: M16, M27, and
M32 require the Review Board (Triad plus Financial Domain Expert); M20 needs
a current Triad-plus-domain `RECOMMEND_COMPLETE` result but has no human
sign-off gate. Reviewers are read-only and cannot start, approve, or close a
milestone. There is no separate Builder/Reviewer workflow or automated runner.

## T480 deployment boundary

```text
T480 Windows host
  MetaTrader 5 on GOMarketsMU-Demo only
  PostgreSQL published on port 5432 for home-LAN administrator access

T480 WSL Ubuntu
  Forex repository, fixed T480 adapter, evidence tooling
  shared AI Lab Docker runtime
    private PostgreSQL + pgvector service on the internal Docker network
    shared platform volume and T480-local credentials
```

All runtime functions run on the T480 AI Lab. Forex M2 owns the versioned
`forex` PostgreSQL schema and first controlled import of retained M1 historical
evidence; `cs-ai-lab-infra` owns the private PostgreSQL/pgvector service,
Docker network, volumes, credentials, and backups. The M2 evidence bundle
records one `DEMO_ONLY` source, one linked raw observation, one immutable
EUR/USD:H1 snapshot, and 720 closed price bars. This is verified persistence
evidence, not a completion claim: Triad recommendation and human sign-off
still remain before `proven_at` can be written.

The import has a fixed input: the retained 720 closed EUR/USD H1 M1 Demo
observation. It records source, revision, timestamps, hashes, redaction and
lineage; it does not provide a general download, database, MT5, shell,
account, or order interface.

## Current historical-data and sentiment design

M11 uses GDELT 2.0 public raw GKG files as an *experimental context source*.
The Forex collector downloads an attributable ZIP artifact, derives a bounded
EUR/USD-relevant aggregate, and retains no article text. It is not a trading
signal, recommendation, or execution surface.

```text
GDELT public raw GKG files
        │
fixed Forex collector
        │  source URL, SHA-256, retrieval and availability times
        ▼
hourly GDELT aggregate (article count, mean tone, query version, uncertainty)
        │
        ├───────────────┐
        ▼               ▼
point-in-time join   provenance/audit
        │
        ▼
EUR/USD H1 research dataset → replay, hypothesis and offline ML (M13–M16)
```

The price side exists in the T480 PostgreSQL `forex` schema: one `DEMO_ONLY`
EUR/USD H1 snapshot with 720 closed bars. M11 also persists bounded GDELT H1
aggregates and their raw provenance. M13's fixed, read-only T480 replay probe
uses both sources: at its UTC cutoff it observed the 720 price bars and five
eligible context aggregates, while excluding future price records. This is
historical research plumbing, not a trading or forecasting capability.

The join key is the UTC H1 bucket. A feature can be used only when its
`available_at_utc` is at or before a decision cutoff; the target is a *later*
bar or a pre-declared session outcome. This prevents future information from
leaking into historical backtests.

### Daily collection and n8n boundary

The T480 shared lab has `scripts/n8n_adapter.py`, adapted from Autonomous
Framework. It routes through the existing T16-to-T480 transport to n8n's
private loopback API and can health-check, list, import/update, activate,
deactivate, and inspect workflows. n8n credentials remain T480-local.

The Forex workflow definition is currently an **inactive design artifact**.
It must not be activated as-is: the shared n8n container does not mount
`/home/chris/projects/forex` or promise a Python runtime. The deployable
design is therefore:

```text
n8n daily schedule → n8n HTTP / Compression / Code / PostgreSQL nodes
  → raw observation + GDELT H1 aggregate → n8n execution history
```

The daily job must retrieve all GKG intervals for the preceding closed UTC day
(or collect every 15 minutes and roll up). Reading `lastupdate.txt` once per
day captures one 15-minute slice, not a daily aggregate. The recommended MVP
is a once-daily n8n workflow. It uses built-in n8n nodes rather than a Python
scheduled job. Its PostgreSQL credential, workflow import and activation are
still explicit future deployment actions.

See [`system_design.md`](system_design.md) for database and adapter details.

The Windows MT5 terminal and shared PostgreSQL service are separate T480
components. Forex code reaches MT5 only through its fixed Demo-only catalog
operation and reaches PostgreSQL only through a fixed, approval-gated T480
operation. For this home-network MVP, PostgreSQL is also published on T480
port 5432 for administrator clients on the closed LAN; it is not a public
internet service. M5 later proves application-level database integration and
idempotent reimport; M2 is only the controlled initial snapshot.

## Historical market-intelligence roadmap

![Historical market-intelligence architecture](assets/advanced-market-intelligence-architecture.png)

This diagram visualises the approved three-phase, historical-first roadmap. It
is a design overview, not evidence that any future adapter, source, Ollama
task, real-time feed, or Demo execution capability is deployed.

Amber ticks mean **built, but not proven**. They do not change milestone state.
The current execution record is authoritative: M0 currently needs
revalidation after later material changes, M1 has a recorded human
revalidation exception rather than fresh `proven_at`, and M2 has verified
T480 evidence while awaiting the final review/sign-off route. All later
components remain planned or subject to their current contract state.

### Component-to-milestone map

| Diagram component | Delivering milestones |
| --- | --- |
| Governance, evidence, review, self-attested integrity | M0 revalidation; required throughout M1–M32 |
| Demo historical export, fixed read-only bridge, persistence, multi-timeframe price data | M1–M6 |
| Source qualification and candidate macro/calendar/sentiment adapters | M7–M11 |
| Normalisation, provenance, point-in-time alignment, replay, deterministic hypotheses, one explainable offline ML baseline, walk-forward evaluation | M12–M16 |
| Bounded Demo-only data-to-outcome MVP: fresh tick/candles, decision snapshot, recorded assessment, session-capped execution, monitoring and reconciliation | M20 |
| Event quality, richer risk/sizing/intent/approval/revalidation controls | M21–M26 |
| Additional fresh-data, tick/spread and recovery hardening | M27–M29 |
| Broader controlled Demo workflow evaluation and forward assessment | M30–M32 |

The diagram is a maintained overview of the intended ownership and trust
boundaries. It distinguishes the Forex repository, shared `cs-ai-lab-infra`,
and the Windows T480 / MetaTrader 5 environment. It also shows the evidence
path: the fixed local evidence runner self-attests a captured bundle; the
repository verifier checks its signature, schema, policy, and reproducibility;
then, at a phase gate, the four-role Review Board produces a recommendation
for a human decision.

This is an architecture map, not proof that a shared service or future
capability is currently deployed. The mutable execution record remains
`project_state.json`.

The roadmap retains its historical foundation through M19. M20 is now the MVP
critical path: it must prove a fixed `GOMarketsMU-Demo` EUR/USD loop from a
fresh bid/ask/spread and closed M1/M5 candles to a recorded assessment, a
bounded Demo result, and PostgreSQL reconciliation. Historical bars never
substitute for M20's fresh-tick, current-spread, or execution proof.

M17 is the entry boundary for Phase 2. Its context builder accepts only historical EUR/USD bars available at a supplied UTC cutoff and research-only derived features. It excludes future data, account and credential data, MT5 controls, orders and execution fields. The result has no model, network, MT5 or order capability; later M18+ components may consume this bounded context but cannot widen it.

The operator-focused target-state flow, including the future human-operated Demo path, is documented in [future_user_journey_architecture.md](future_user_journey_architecture.md). It is intentionally a roadmap view, not proof that its future components are deployed.

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

M20 deliberately keeps the first assessment narrow: a versioned rule or
model reads only the persisted point-in-time M1/M5 snapshot and emits `BUY`,
`SELL`, or `NO_TRADE`, with its rationale and input hashes persisted before an
execution attempt. The MVP is not a claim of trading edge or profitability.

M20 may automate a Demo action only through a fixed, fail-closed executor. A
human first enables a short session lease; the initial contract caps it at ten
trades in sixty minutes, one open EUR/USD position, USD 100 notional per trade,
and USD 1,000 cumulative notional. The executor refuses an expired lease,
server mismatch, missing or duplicate proposal, cap breach, stale data, or
unknown order state. Every attempt and `NO_TRADE` outcome is retained for
reconciliation and later back-testing.

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

The hard boundary remains: no `GOMarketsMU-Live`, no real-money order path,
and no unrestricted MT5 interface. M20 is the sole contracted, fixed
`GOMarketsMU-Demo` execution path; it is bounded by the session lease and
audit requirements above. It is not deployed or proven merely because this
architecture describes it. Broker credentials and machine-local account data
remain outside the repository and evidence summaries. The evidence signature
is self-attested integrity, not independent execution provenance.
