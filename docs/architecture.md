# Architecture

## Reading this document

This is an architecture and target-boundary document, not a deployment ledger
or proof record. `project_state.json` identifies the formal active milestone;
`milestone_registry.json` defines its contract; and retained raw evidence plus
independent verification establish whether a capability is operating. As of
the repository's current state, M29 is the formal active milestone. Harness
H1–H4 is the active delivery wave and a required repository-structure method;
it operates within that contract, broker authority, and proof gate. H_SLOW
remains deferred unless Chris explicitly reactivates it.

Statements below that describe an execution, scheduler, deployment, or source
integration define a bounded design unless they link to current, contract-bound
evidence. Architecture prose, tests, and workflow history do not prove
deployment, completion, or trading authority.

## Architectural guiding principles

The system separates proof, durable state, deterministic decision-making,
orchestration, and broker access. A component must not silently assume the
authority of another component.

| Capability | Owns | Must not own |
| --- | --- | --- |
| Immutable files and JSON evidence | Original external responses, MT5 exports, hashes, receipts, manifests, and recovery artifacts. These are the source record needed to show what was observed and when. | Mutable operational state, unverified repair of captured evidence, or broad analytics queries. |
| PostgreSQL | Validated, queryable and durable application facts: lifecycle state, idempotency/reservations, normalized broker facts, canonical calendar facts, event/decision/trade joins, reconciliation, and derived analytics. | The only copy of external raw source bytes, arbitrary broker commands, or unvalidated external input. Every SQL fact derived from a source must retain a reference to its source record and digest. |
| Python application services | Deterministic domain rules: parsing and validation, provenance checks, risk/sizing, idempotency, recovery, reconciliation, and report construction. | Visual approval flows, generic integration plumbing, or authority not declared in the component contract. |
| n8n | Bounded integration orchestration: scheduled public-source collection where its node contract is suitable, notifications, human review/exception routing, and read-only report delivery. Workflow execution history is operational evidence, not proof by itself. | MT5 credentials, trade entry/exit/amendment, risk latches, recovery authority, durable financial lifecycle state, or proof authority. n8n workflows are versioned production artifacts and require a fixed deployment/activation contract. |
| systemd and Windows Task Scheduler | Host-local, always-on or precisely timed services with explicit restart and health behavior. | Cross-system business workflows, source-of-truth data, or human approvals. |
| Fixed T480 adapter | Narrow, catalogued access to protected local resources such as MT5, local n8n, and named database operations. | Generic shell, generic SQL, generic source download, or a general MT5 interface. |

### Data and authority flow

```text
External publisher or MT5
  -> immutable raw evidence and receipt
  -> validated PostgreSQL projection
  -> Python decision, reconciliation, or report logic
  -> n8n notification or operator workflow

Only the fixed Demo-only T480 execution path may contact MT5 for a trading
operation. No workflow, report, model, or database query receives implicit
broker authority.
```

### Selection rules

- Retain raw files first when the question is “what did the source say?” or
  the item may be required as proof.
- Project every validated structured calendar fact to PostgreSQL. Use the same
  rule for other facts with lifecycle, idempotency, concurrency,
  reconciliation, repeated joins, or historical reporting requirements.
- Use Python where behavior must be deterministic, testable, fail-closed, and
  governed by application rules.
- Use n8n where the value is integration visibility, scheduling across APIs,
  notification, or a human-in-the-loop workflow; never use it to bypass a
  Python/T480 safety boundary.
- Use a host scheduler for a local service that must survive independently of
  browser sessions and workflow execution history.
- Treat AI output as versioned research context or an advisory only. It cannot
  create trading authority or replace a deterministic risk/execution check.

The implementation map and staged repository-structure target are in
[Capability architecture](capability-architecture.md). That document is the
starting point for all new capabilities; it does not replace a milestone
contract or claim deployment status.

The current M1 decision loop, active gates, and stated M15/timeframe-expansion
rules are in [M1 Demo decision workflow](workflows/m1-demo-decision-workflow.md).
It describes operational behaviour; this document continues to own component
boundaries and deployment architecture.

## High-level system diagram

![High-level Forex repository architecture](assets/forex-architecture-overview.png)

## Completion-review gates

Every milestone needs implementation, verification, and the declared
real-world proof. The active contract in `milestone_registry.json` determines
the required review route. Repository rules additionally require a current
Triad-plus-domain `RECOMMEND_COMPLETE` result bound to the exact contract,
revision, configuration, verifier, and evidence. Reviewers are read-only and
cannot start, approve, or close a milestone.

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

The intended boundary places Forex runtime functions on the T480 AI Lab. Forex
owns the versioned `forex` PostgreSQL schema and its controlled imports;
`cs-ai-lab-infra` owns the private PostgreSQL/pgvector service, Docker network,
volumes, credentials, and backups. Historical M2 evidence records are retained
as evidence artifacts, but their current validity and any closeout state are
determined only by the registry, project state, and their verification record.

The import has a fixed input: the retained 720 closed EUR/USD H1 M1 Demo
observation. It records source, revision, timestamps, hashes, redaction and
lineage; it does not provide a general download, database, MT5, shell,
account, or order interface.

## M20 target operating architecture

For the ordered operational loop and the distinction between active gates and
shadow context, see the [M1 Demo decision workflow](workflows/m1-demo-decision-workflow.md).

```text
T16 / VS Code → read-only M20 terminal dashboard
       │ fixed status operation
       ▼
T480 Scheduled Task target: Forex-M20-Demo-Listener
  every 5 seconds → fresh EURUSD bid/ask/spread + completed M1 candles
       ├─ five strategy assessments → safety then Compression → Trend → Range → Session → Momentum
       ├─ one selected executable owner BUY / SELL → fixed capped Demo executor
       │                         ↘ asynchronous MT5 Demo position monitor
       └─ NO_TRADE → persisted proposal and reconciliation
       ▼
T480 WSL PostgreSQL bridge → audit events and P&L ledger
```

The target listener retains no raw tick stream. It assesses one completed-candle
M1 snapshot every five seconds and reports the prior five-candle range,
last-two-candle direction, breakout checks, combined move, and spread check.
It compares five named strategies on the same snapshot. Deterministic regime
precedence selects at most one as the execution-eligible owner; the others are
recorded confluence or counter-signal evidence. A strategy row can therefore
show a valid signal without receiving authority to place a second EURUSD order.
Assessment must remain independent of position monitoring so an open trade does
not stall later observations. The T16 dashboard is read-only.

### How M20 code is intended to deploy to T480

Before every T480 deployment, follow the mandatory [T480 deployment transport
constraint](t480-deployment.md). The SSH endpoint has a strict encoded command
limit: payloads use hash-checked fragments and operational launchers run from
the released payload rather than embedding large commands.

The repository must not copy arbitrary code to MT5. The target fixed T480
adapter stages exactly three reviewed payloads into a new immutable ProgramData
release:

```text
Forex checkout on T16 / WSL
  reviewed source: listener service + trading runner + PostgreSQL audit bridge
       │ each payload split into fixed-size fragments
       │ Base64 transfer; final fragment verifies SHA-256
       ▼
T480: C:\ProgramData\ForexListener\releases\<release-id>\
  m20_demo_listener_service.payload
  m20_demo_trading_session.payload
  m20_postgres_audit_bridge.payload
       │ prepare: verify all three hashes and write only non-secret local config
       ▼
Atomic Scheduled Task switch
  Forex-M20-Demo-Listener → python.exe <new release>\m20_demo_listener_service.payload
       │ wait for a fresh release-bound heartbeat
       ├─ healthy → retain new task and prior task XML for rollback
       └─ unhealthy → restore the previous Scheduled Task automatically
```

`C:\ProgramData\ForexListener\state` is deliberately separate from immutable
release code in this target design. It holds the Demo lease, status heartbeat,
recovery marker, monitor job, and machine-local configuration; it contains no
tracked secrets. A deployment must not change the Demo-only server allowlist,
EURUSD symbol, caps, or strategy rules. Actual deployment requires current,
contract-bound evidence and does not follow from this description.

## Historical-data and sentiment target design

The M11 design uses GDELT 2.0 public raw GKG files as an *experimental context
source*. Its collector downloads an attributable ZIP artifact, derives a
bounded EUR/USD-relevant aggregate, and retains no article text. It is not a
trading signal, recommendation, or execution surface.

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

The historical design uses the T480 PostgreSQL `forex` schema, a `DEMO_ONLY`
EUR/USD H1 snapshot, bounded GDELT H1 aggregates, and their raw provenance. A
fixed, read-only replay probe may join the sources only at its declared UTC
cutoff while excluding future price records. This is historical research
plumbing, not a trading or forecasting capability. Current availability and
validity must be established from retained evidence, not this document.

The join key is the UTC H1 bucket. A feature can be used only when its
`available_at_utc` is at or before a decision cutoff; the target is a *later*
bar or a pre-declared session outcome. This prevents future information from
leaking into historical backtests.

### Daily collection and n8n boundary

The A1 BLS implementation is separate from GDELT:
`n8n/forex-bls-calendar-retention.json` submits an authenticated, fixed monthly
response envelope to `src/forex/bls_n8n_service.py`. The service retains exact
publisher body bytes and an immutable, explicitly client-asserted receipt.
`scripts/project_n8n_bls_retained_calendar_facts.py` verifies the expected
workflow binding and receipt/acquisition/raw chain before the existing canonical
PostgreSQL writer. It has no broker or event-gate authority. Deployment remains
gated; see `deploy/bls-n8n/README.md`. Existing GDELT workflows were observed
active on 2026-09-14; the older daily-design description below is not their
current operational acceptance record.

The target shared-lab integration uses `scripts/n8n_adapter.py`, adapted from
Autonomous Framework. It routes through the existing T16-to-T480 transport to
n8n's private loopback API and can health-check, list, import/update, activate,
deactivate, and inspect workflows. n8n credentials remain T480-local.

The Forex workflow definition is a design artifact, not an activation claim.
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
components. Forex is designed to reach MT5 only through its fixed Demo-only
catalog operation and PostgreSQL only through a fixed, approval-gated T480
operation. For this home-network MVP, the intended PostgreSQL exposure is T480
port 5432 for administrator clients on the closed LAN, never a public internet
service. M5 later proves application-level database integration and idempotent
reimport; M2 is only the controlled initial snapshot.

## Historical market-intelligence roadmap

![Historical market-intelligence architecture](assets/advanced-market-intelligence-architecture.png)

This diagram visualises the approved three-phase, historical-first roadmap. It
is a design overview, not evidence that any future adapter, source, Ollama
task, real-time feed, or Demo execution capability is deployed.

Amber ticks mean **built, but not proven**. They do not change milestone state.
The current execution record is authoritative: consult `project_state.json`,
the active registry contract, and their bound verification records for current
state. All roadmap components remain planned or subject to their current
contract state.

### Component-to-milestone map

| Diagram component | Delivering milestones |
| --- | --- |
| Governance, evidence, review, self-attested integrity | M0 revalidation; required throughout M1–M32 |
| Demo historical export, fixed read-only bridge, persistence, multi-timeframe price data | M1–M6 |
| Source qualification and candidate macro/calendar/sentiment adapters | M7–M11 |
| Normalisation, provenance, point-in-time alignment, replay, deterministic hypotheses, one explainable offline ML baseline, walk-forward evaluation | M12–M16 |
| Continuous Demo-only data-to-outcome MVP: fresh tick/candles, five-strategy assessment, recorded decision, capped execution, monitoring and reconciliation | M20 |
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

The roadmap retains its historical foundation through M19. M20 defines the
contracted Demo-trading architecture: a fixed `GOMarketsMU-Demo` EUR/USD loop
from fresh bid/ask/spread and closed M1 candles to a recorded assessment, a
continuous-lease Demo result, and PostgreSQL reconciliation. It does not
supersede the formal active milestone. Historical bars never substitute for
fresh-tick, current-spread, or execution proof.

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

M20 deliberately keeps the first assessment narrow: its target versioned rule
reads a fresh bid/ask/spread plus completed M1 candles and emits `BUY`,
`SELL`, or `NO_TRADE`, with its rationale and input hashes persisted before an
execution attempt. The documented next rules-engine design classifies the
market regime first, selects at most one strategy, and gives any accepted
trade an immutable `trade_owner_strategy_id`. Only that owner’s SL, TP,
monitoring, and exit rules may manage it; counter-signals are evidence, not
cross-strategy liquidation instructions. The MVP is not a claim of trading
edge or profitability.

The M20 design permits a Demo action only through a fixed, fail-closed executor. A
Demo-only authority lease with duration `0` is continuous rather than
time-expiring; it remains constrained to one open EUR/USD position, USD 10,000
notional per trade, USD 100,000 cumulative notional, and AUD 100 theoretical
loss per trade. The executor refuses an absent or disabled lease,
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
`GOMarketsMU-Demo` execution path; the continuous lease, fixed caps, and audit
requirements constrain it. It is not deployed or proven merely because this
architecture describes it. Broker credentials and machine-local account data
remain outside the repository and evidence summaries. The evidence signature
is self-attested integrity, not independent execution provenance.
