# Forex — M0 repository foundation prompt

## Status of this document

This is an execution prompt for a future Codex run.

Do not treat review notes, aspirations, future architecture, or future milestones as permission to implement beyond M0.

The current request is to implement **M0 only** and then stop.

---

# 1. Role and repositories

You are the primary software-development agent for the existing GitHub repository:

`successbycs/forex`

Project display name:

`Forex`

Python import package:

`forex`

Before changing files:

1. Inspect the Forex repository and its Git status.
2. Preserve all existing and unrelated worktree changes.
3. Prefer existing local checkouts of the reference repositories.
4. Inspect reference repositories read-only.
5. Record the path, branch, commit, and inspection date for each reference repository.
6. If a reference repository is unavailable, record the limitation and do not fabricate findings.

Reference repositories:

- `successbycs/Autonomous-Framework`
- `successbycs/SuccessByCS-Builder`
- `successbycs/cs-ai-lab-infra`

Do not modify the reference repositories.

Do not commit, push, create a branch, or open a pull request unless the human operator explicitly requests it.

---

# 2. Objective and learning purpose

Forex is primarily a learning and research project.

Its intended maturity path is:

```text
research and education
-> observable decision support
-> human-approved trading assistance
-> possible demo automation
-> possible future live-readiness assessment
```

Progression is evidence-dependent. The system may remain a research or decision-support application indefinitely.

The objective is:

> Build a risk-controlled EUR/USD research and trading-assistance platform that combines deterministic quantitative machinery with constrained AI reasoning, protects capital, permits zero-trade days, and measures honestly whether either deterministic or agent-assisted decision-making demonstrates persistent positive expectancy.

An average of approximately USD 10 per trading day or USD 300 per month is only a distant aspirational research benchmark. It is not:

- a daily requirement
- an acceptance criterion
- a position-sizing input
- a reason to increase risk
- a reason to manufacture trades
- a claim of expected performance

The project must be capable of concluding:

`NO SUFFICIENT EDGE HAS BEEN DEMONSTRATED`

That is a valid and successful research outcome.

Priority order:

1. learning quality
2. capital preservation
3. data integrity
4. operational safety
5. reproducibility
6. explainability
7. positive expectancy
8. execution quality
9. profitability

`NO TRADE`, `WAIT`, and `INSUFFICIENT DATA` are valid outcomes.

---

# 3. Fixed MVP boundaries

Canonical instrument:

`EUR/USD`

Expected MT5 broker symbol:

`EURUSD`

The broker symbol must be discovered and validated. Store canonical instrument and broker symbol separately. Never silently select a similarly named symbol.

Trading platform:

`MetaTrader 5`

Broker:

`GO Markets Mauritius`

Permitted development server:

`GOMarketsMU-Demo`

Forbidden server during MVP implementation:

`GOMarketsMU-Live`

Initial research capital assumption:

`USD 1,000 equivalent`

Initial research risk range:

`0.25% to 0.50% of equity per trade`

Maximum concurrent MVP positions:

`1`

These are research defaults, not claims of suitability or profitability.

Live trading must remain disabled and structurally unavailable. A configuration change alone must never enable live trading.

No order operation may exist before the dedicated demo-execution milestone.

---

# 4. Development platform and ownership

The application is developed on the SuccessByCS AI Lab platform, including:

- Windows
- WSL Ubuntu
- VS Code and Codex
- Git and Python
- Docker Compose
- PostgreSQL with pgvector
- n8n
- optional Ollama or other model providers
- MetaTrader 5 running natively on Windows

Ownership rule:

- Cross-project platform services belong in `cs-ai-lab-infra`.
- Forex-specific code, schemas, migrations, workflows, adapters, and evidence belong in `successbycs/forex`.

Expected platform reuse:

- PostgreSQL runtime: shared AI Lab platform
- pgvector capability: shared AI Lab platform, unused until justified
- n8n runtime: shared AI Lab platform, used selectively
- Ollama runtime: optional shared platform capability behind a provider abstraction
- Forex schemas and migrations: Forex repository
- Windows MT5 adapter: Forex repository
- Forex n8n workflow definitions: Forex repository

Do not copy the AI Lab Compose stack into the Forex repository.

Do not modify `cs-ai-lab-infra` during M0.

If a shared-infrastructure change appears necessary, document it as a proposed dependency requiring human review.

---

# 5. Physical application boundary

Target topology:

```text
Windows AI Lab machine
|
+-- MetaTrader 5
|   +-- GOMarketsMU-Demo
|
+-- Windows Forex MT5 adapter
|
+-- WSL / application containers
    +-- Forex application
    +-- shared PostgreSQL + pgvector
    +-- shared n8n
    +-- optional shared Ollama
```

MT5 runs on Windows. Most Forex application services run in WSL or application-specific containers.

PostgreSQL and MT5 must not be exposed publicly or to the LAN during MVP development.

Inspect the actual AI Lab networking configuration before selecting an integration method. Do not assume that Windows loopback, WSL loopback forwarding, or a private interface is sufficient without an observed connectivity proof.

---

# 6. Configuration-first operating model

Any non-secret field expected to change over time should have one canonical configuration source that a human operator can edit without changing application code.

Use version-controlled YAML for non-secret operator settings. Validate it with typed Python models and a machine-readable schema.

Bootstrap transport configuration and fixed command catalogs may remain JSON
when that permits validation with the Python standard library before the full
application dependency set is installed. Do not duplicate the same setting in
both JSON and YAML.

Use environment variables or ignored local override files for:

- passwords
- API keys
- account identifiers
- machine-specific addresses
- secret file paths
- other sensitive or host-local values

Do not put secrets in version-controlled configuration.

Initial M0 configuration files:

```text
config/
  project.yaml
  runtime.yaml
  mt5.yaml
  market_data.yaml
  logging.yaml
  schemas/
```

Add later configuration only with the milestone that uses it:

```text
config/database.yaml
config/models.yaml
config/agent.yaml
config/risk.yaml
config/execution.yaml
config/notifications.yaml
```

Configuration examples should include comments or companion documentation describing:

- field purpose
- type and units
- allowed values
- safe default
- whether restart is required
- whether changing it invalidates prior proof
- whether human approval is required

Configuration precedence must be explicit and simple:

```text
version-controlled defaults
-> optional ignored machine-local overrides
-> environment-provided secrets
```

Do not allow undocumented runtime flags to override governed configuration.

Do not duplicate canonical values in application code or verification scripts. Verification must load the same configuration source as the application.

Evidence manifests must record:

- configuration schema version
- a redacted configuration snapshot or safe subset
- SHA-256 fingerprint of the effective non-secret configuration

Safety invariants are not ordinary configuration. The following must be enforced by code and architecture:

- live trading disabled
- live server prohibited
- no order endpoints before the demo-execution milestone
- Risk Engine authority
- explicit human approval before demo execution
- agent has no execution authority

A human-editable value may make safety stricter. It must not silently weaken these invariants beyond hard code-enforced bounds.

---

# 7. Lightweight milestone governance

Reuse only the following ideas from the Autonomous Framework and AI Lab milestone machinery:

- milestone registry
- explicit dependencies
- milestone state machine
- transition contracts
- entry conditions
- bounded scope and out-of-scope declarations
- acceptance criteria
- verification commands
- required artifacts
- observable evidence requirements
- real-world execution proof
- human sign-off gates
- project state
- run history
- proof manifests and raw evidence
- closeout audit

Do not copy:

- controller/planner/builder/reviewer/QA agent hierarchies
- role prompt libraries
- autonomous repair loops
- generic tool ecosystems
- large historical run stores
- framework-specific orchestration

Codex remains the software-development agent.

## 7.1 Milestone as transition contract

Every milestone must declare:

- `milestone_id`
- `title`
- `objective`
- `delivery_type`
- `proof_type`
- `status`
- `dependencies`
- `entry_conditions`
- `from_state`
- `to_state`
- `scope`
- `out_of_scope`
- `operator_config_affected`
- `expected_artifacts`
- `acceptance_criteria`
- `verification_commands`
- `real_world_proof`
- `evidence_requirements`
- `human_review_required`
- `proof_invalidated_by`
- optional `target_date`
- `target_date_owner`
- `notes`

Allowed `delivery_type` values:

- `FOUNDATION_ENABLING`
- `CAPABILITY_DELIVERING`
- `RESEARCH_EVALUATION`
- `OPERATIONAL_SAFETY`

Allowed `proof_type` values:

- `REPOSITORY_EXECUTION`
- `REAL_SYSTEM_INTEGRATION`
- `OPERATIONAL_DRILL`
- `EMPIRICAL_RESEARCH`

## 7.2 Milestone states

Use:

- `PLANNED`
- `READY`
- `IN_PROGRESS`
- `BLOCKED`
- `NEEDS_FIX`
- `AWAITING_REAL_WORLD_PROOF`
- `AWAITING_HUMAN_SIGNOFF`
- `PROVEN`
- `NEEDS_REVALIDATION`
- `SUPERSEDED`

Normal flow:

```text
PLANNED
-> READY
-> IN_PROGRESS
-> AWAITING_REAL_WORLD_PROOF
-> AWAITING_HUMAN_SIGNOFF when required
-> PROVEN
```

Failures move to `NEEDS_FIX` or `BLOCKED`. Material changes to a previously proven surface move it to `NEEDS_REVALIDATION`.

Never transition directly from `PLANNED` to `PROVEN`.

## 7.3 Completion timestamp

Use UTC ISO-8601 timestamps.

Track separately:

- `started_at`
- `implementation_finished_at`
- `verification_passed_at`
- `real_world_proof_captured_at`
- `human_signed_off_at`
- `first_proven_at`
- `proven_at`
- `last_validated_at`

`proven_at` is the authoritative milestone completion timestamp.

It must be generated by the closeout command only after every completion gate succeeds. It must not be manually entered, predicted, backdated, or inferred from a commit date.

An optional `target_date` is a human-owned planning forecast, not a completion claim. It may change without rewriting history. Keep it separate from proof timestamps and never use it to force a milestone closed.

`implementation_finished_at` does not mean completion.

If proof becomes stale:

- retain historical proof and `first_proven_at`
- set status to `NEEDS_REVALIDATION`
- explain the invalidating change
- record a new `proven_at` only after fresh proof

## 7.4 Completion gate

A milestone may become `PROVEN` only when all of the following are true:

1. All dependencies are `PROVEN` and still valid.
2. Entry conditions were satisfied.
3. Required capability exists.
4. Every acceptance criterion has a recorded passing result.
5. Tests pass and the test count is greater than zero when tests are required.
6. Milestone verification commands pass.
7. Repository-level verification passes.
8. Required artifacts exist and are non-empty.
9. A proof was captured from the real execution surface declared by the milestone.
10. Raw evidence is retained and independently verifiable.
11. Evidence matches the relevant Git revision and configuration fingerprint.
12. Evidence freshness is within the milestone's declared validity window.
13. Human-observable proof contains a plain-language summary and links to inspectable evidence.
14. Human sign-off is recorded when required.
15. No unresolved critical safety, security, data-integrity, or lookahead issue exists.
16. Project state and run history are current.

Tests, mocks, documentation, file existence, `--help`, or a self-authored JSON document cannot by themselves prove an external capability.

## 7.5 Real-world proof

Every milestone must include at least one check marked:

`real_world_execution: true`

The proof must match the claim:

- Repository foundation: create a clean isolated environment from the repository, install the package, load configuration, run tests, and run verification successfully.
- MT5 connection: interact with the installed Windows MT5 terminal on `GOMarketsMU-Demo` and record terminal/account/symbol/tick observations.
- Local API: call the actual bound API and validate its response and network exposure.
- Windows/WSL boundary: make a real WSL-to-Windows request.
- PostgreSQL: write, read, and safely clean up or retain a uniquely identified synthetic Forex proof record in the actual selected database/schema.
- Recovery: perform an isolated recovery drill.
- Historical replay: prove known future records are unavailable at an earlier replay timestamp.
- Strategy research: run point-in-time backtests with realistic costs and out-of-sample segments.
- Agent evaluation: compare shadow recommendations with a frozen deterministic baseline and subsequent outcomes.
- Demo execution: use only `GOMarketsMU-Demo`, capture broker identifiers, and reconcile broker state.

When a real external surface is unavailable, mark the milestone `BLOCKED` or `AWAITING_REAL_WORLD_PROOF`. Do not substitute simulated evidence unless the milestone explicitly claims only simulation.

## 7.6 Evidence bundle

Store milestone evidence beneath:

`runs/evidence/<milestone_id>/<UTC-run-id>/`

Each proof bundle should contain, as applicable:

- immutable raw output
- a manifest
- capture start and finish timestamps
- Git revision and dirty-worktree flag
- execution host role, without sensitive host details
- executed command or bounded operation identifier
- exit codes
- redaction record
- effective non-secret configuration fingerprint
- expected and observed result
- artifact SHA-256 hashes
- independent verification result
- human-observable summary

Capture and verification must be separate operations. The verifier should not silently repair, replace, or regenerate captured evidence.

Include at least one negative-control test for important proof gates so the verifier is shown to reject missing, stale, mismatched, or fabricated-looking evidence.

Do not commit secrets, account numbers, private addresses, or unnecessarily sensitive broker information in evidence.

---

# 8. Project state

Create `project_state.json` with a validated schema.

Minimum fields:

- schema version
- project
- repository
- project purpose
- phase
- last proven milestone
- current milestone
- next milestone
- milestone status
- canonical instrument
- broker
- permitted MT5 server
- forbidden MT5 server
- runtime mode
- live trading enabled
- agent authority mode
- development platform
- implementation status
- known blockers
- verification status
- last successful verification
- configuration fingerprint
- important architectural decisions
- last updated timestamp

Initial runtime values:

```text
project: Forex
repository: successbycs/forex
phase: FOUNDATION
current_milestone: M0
next_milestone: M1
canonical_instrument: EUR/USD
expected_broker_symbol: EURUSD
broker: GO Markets Mauritius
permitted_mt5_server: GOMarketsMU-Demo
forbidden_mt5_server: GOMarketsMU-Live
runtime_mode: RESEARCH
live_trading_enabled: false
agent_authority_mode: DISABLED
development_platform: SuccessByCS AI Lab
```

After successful M0 closeout:

```text
last_proven_milestone: M0
current_milestone: null
next_milestone: M1
M0 status: PROVEN
M1 status: READY
```

Do not automatically begin M1.

---

# 9. Run history

Create lightweight append-only run history beneath `runs/`.

Each run records:

- run ID
- start and finish timestamps
- milestone
- purpose
- Git revision and worktree state
- configuration fingerprint
- files changed
- commands executed
- tests and test count
- verification results
- evidence bundle paths
- result
- blockers
- notes

Run history is an audit index. It is not proof by itself.

---

# 10. Runtime modes and agent authority

Runtime modes:

- `RESEARCH`
- `BACKTEST`
- `OBSERVE`
- `DEMO_APPROVAL`
- `DEMO_EXECUTE`

Initial runtime mode:

`RESEARCH`

Unknown runtime mode fails closed.

Live trading is a separate capability flag and remains false.

Future agent authority modes:

- `DISABLED`
- `SHADOW`
- `ADVISORY`
- `FILTER`

The first implemented agent mode must be `SHADOW`.

In `SHADOW`, the agent recommendation is logged and evaluated but cannot:

- create a trade candidate
- remove or modify a deterministic candidate
- approve or reject execution
- change risk
- change position size
- place an order
- change runtime mode

Promotion to another authority mode requires a dedicated milestone, empirical evidence, configuration change, and explicit human approval.

---

# 11. Deterministic and agentic boundary

Deterministic responsibilities:

- MT5 connectivity
- market-data ingestion
- timestamps and candle construction
- data-quality checks
- features and indicators
- point-in-time replay
- hard event blackouts
- risk limits
- loss and drawdown limits
- spread limits
- position sizing
- uniqueness and idempotency
- execution revalidation
- broker reconciliation

Agentic responsibilities:

- synthesize trusted multi-timeframe evidence
- choose among constrained read-only analytical tools
- interpret conflicting evidence
- identify missing information
- explain reasons to wait
- identify invalidation conditions
- produce a typed recommendation

An LLM must not perform authoritative financial arithmetic or override deterministic safety logic.

Free-form model prose must never become an executable trading instruction.

---

# 12. Target application architecture

The long-term destination includes:

1. Windows MT5 integration
2. local read-only MT5 API
3. WSL adapter client
4. market-data ingestion
5. data-quality validation
6. PostgreSQL persistence
7. multi-timeframe context
8. feature calculation
9. deterministic regime classification
10. deterministic strategy evidence
11. point-in-time replay and backtesting
12. Forex Analyst Agent in shadow mode
13. read-only analytical tools
14. controlled agent memory
15. agent evaluation
16. economic-event context
17. deterministic Risk Engine
18. position sizing
19. trade intent and lifecycle
20. human approval
21. execution revalidation
22. MT5 demo execution
23. position monitoring and reconciliation
24. journal, observability, and recovery

Target flow:

```text
GO Markets demo
-> MetaTrader 5 on Windows
-> Windows read-only adapter
-> WSL client
-> PostgreSQL
-> data quality
-> multi-timeframe context
-> features
-> regime
-> deterministic strategy evidence
-> point-in-time baseline evaluation
-> Forex Analyst Agent in shadow/advisory mode
-> deterministic Risk Engine
-> human approval
-> execution revalidation
-> MT5 demo execution
-> reconciliation and journal
-> empirical evaluation
```

Do not create target classes or packages until the milestone that uses them.

---

# 13. Initial milestone sequence

Create the registry with the following initial sequence. Each entry must use the transition-contract fields and include a real-world proof requirement. Small refinements are permitted when documented; safety boundaries must not be weakened.

## M0 — Repository foundation proven

Establish a small, configuration-first, evidence-gated Codex project. Prove it from a clean isolated Python environment. No MT5 access.

## M1 — Windows MT5 read-only connection proven

Prove Windows-native Python can initialize the installed MT5 terminal, validate `GOMarketsMU-Demo`, inspect terminal/account metadata safely, discover the exact EUR/USD broker symbol, obtain symbol metadata, and retrieve the latest bid/ask tick with freshness classification. No order imports or operations.

## M2 — Local read-only MT5 API proven

Expose health, safe account summary, symbol, tick, and candle endpoints. Prove actual local binding, access control, response schemas, and absence of order endpoints.

## M3 — WSL-to-Windows MT5 path proven

Prove the WSL Forex client can reach the real Windows adapter with timeout, retry, schema validation, and safe failure behavior.

## M4 — AI Lab application integration proven

Prove Forex can use the selected shared PostgreSQL path without public exposure or duplicated infrastructure. Confirm n8n remains separate and operational.

## M5 — PostgreSQL persistence foundation proven

Create versioned Forex schemas/migrations and prove an isolated synthetic write/read round trip.

## M6 — EUR/USD M15 end-to-end data slice proven

Retrieve real historical M15 candles through the full path, validate them, persist them, query them, and repeat ingestion without duplicates.

## M7 — Multi-timeframe historical data proven

Extend point-in-time-safe ingestion to MN1, W1, D1, H4, H1, M30, M15, M5, and M1.

## M8 — Tick and spread collection proven

Capture bid, ask, timestamp, and spread with an explicitly selected collection method and measured limitations.

## M9 — Data-quality blocking proven

Detect duplicates, ordering errors, missing bars, invalid OHLC, staleness, bad bid/ask, abnormal spread, timezone errors, and incomplete current bars. Prove bad data blocks downstream eligibility.

## M10 — Incremental collection and restart safety proven

Prove last-known timestamp recovery, new-bar retrieval, deduplication, restart behavior, and ingestion logging.

## M11 — Multi-timeframe context proven

Build and verify the structural, regime, directional, setup, entry, and execution context without treating timeframes as independent votes.

## M12 — Feature engine proven

Implement a small versioned feature set, initially ATR, selected moving averages, momentum, volatility, spread, and session context.

## M13 — Historical replay and no-lookahead proven

Reconstruct only information available at a requested timestamp. Include negative tests containing known future records.

## M14 — Deterministic regime engine proven

Implement and evaluate versioned deterministic regime classifications. `UNKNOWN` is valid.

## M15 — Deterministic strategy evidence proven

Produce versioned `BUY`, `SELL`, or `NO_SIGNAL` evidence. Do not execute trades.

## M16 — Deterministic backtesting and walk-forward baseline proven

Build a point-in-time backtest using realistic spread, transaction-cost, and slippage assumptions. Report in-sample and out-of-sample results, sample size, drawdown, expectancy, sensitivity, and limitations. Do not claim profitability from inadequate evidence.

## M17 — Agent context contract proven

Define the typed, point-in-time-safe context and read-only data available to the Forex Analyst Agent.

## M18 — Forex Analyst Agent shadow mode proven

Implement provider abstraction, prompt registry, bounded read-only tool registry, typed output validation, and shadow recommendations. Invalid output fails safely.

## M19 — Agent decision persistence and controlled memory proven

Persist prompts, model provenance, context, tool calls, decisions, and timestamps. Prevent future-outcome leakage.

## M20 — Offline agent evaluation proven

Compare the frozen deterministic baseline, shadow agent recommendation, and subsequent outcome. The result may show no value.

## M21 — Economic-event context proven

Ingest versioned US and Eurozone event information with publication/revision timestamps. Deterministic blackout rules remain authoritative.

## M22 — Deterministic Risk Engine proven

Implement and exhaustively test runtime, position, risk, loss, drawdown, spread, event, stale-data, expiry, deviation, and duplicate-intent rules.

## M23 — Position sizing proven

Validate sizing against MT5 symbol properties, broker volume constraints, and independently calculated examples. Desired profit is never an input.

## M24 — Trade intent and decision orchestration proven

Create durable `trade_intent_id` lifecycle state. Connect strategy evidence, shadow/advisory agent output, and risk assessment without execution.

## M25 — Human approval workflow proven

Require unambiguous approval tied to one current trade intent. Expired or mismatched approval fails closed.

## M26 — Execution revalidation proven

After approval, re-check freshness, price, spread, events, data quality, account, positions, risk, runtime mode, and idempotency.

## M27 — MT5 demo execution proven

Only now add order-check and order-send capability. Enforce `GOMarketsMU-Demo`, idempotency, trade locking, broker result verification, and explicit human approval. `GOMarketsMU-Live` remains blocked in code.

## M28 — Position monitoring and reconciliation proven

Prove startup and ongoing reconciliation against MT5 as broker-state authority.

## M29 — End-to-end agentic demo workflow proven

Prove the complete demo path from real market data through journal and reconciliation.

## M30 — Forward demo evaluation completed

Operate long enough to meet a predeclared minimum observation period and sample policy. Report reliability, decisions, risk behavior, execution quality, failures, and outcomes.

## M31 — Agent-versus-baseline analysis completed

Evaluate expectancy, drawdown, profit factor, filtered winners and losers, WAIT behavior, regime/session performance, and out-of-sample persistence.

## M32 — Live-readiness assessment completed

Produce a formal human-reviewed assessment. Do not enable live trading. There is deliberately no live-enablement milestone.

---

# 14. M0 scope

Implement only M0.

M0 objective:

> Establish a small, configuration-first, evidence-gated Forex repository that future Codex sessions can operate safely and prove from a clean isolated environment.

## M0 required artifacts

Create only the useful foundation:

```text
README.md
AGENTS.md
pyproject.toml
.gitignore
.env.example
src/forex/__init__.py
src/forex/config/
tests/
config/project.yaml
config/runtime.yaml
config/mt5.yaml
config/market_data.yaml
config/logging.yaml
config/schemas/
docs/project_brain.md
docs/architecture.md
docs/development_platform.md
docs/implementation_plan.md
docs/codex_guardrails.md
docs/definition_of_done.md
docs/decisions.md
docs/security_model.md
docs/testing_strategy.md
docs/configuration.md
docs/evidence_and_milestones.md
project_state.json
milestone_registry.json
runs/run_history.json
scripts/verify_project.sh
scripts/capture_m0_evidence.sh
scripts/verify_m0_evidence.sh
config/t480.json
t480/command-catalog.json
t480/README.md
scripts/t480_adapter.py
tests/test_t480_adapter.py
```

Do not create empty domain packages or future component classes.

## M0 acceptance criteria

M0 can be proven only when:

1. The initial repository state and reference repository revisions are documented truthfully.
2. The retained Autonomous Framework subset and excluded machinery are documented.
3. Existing AI Lab services, boundaries, networking constraints, and unresolved dependencies are documented from inspected evidence.
4. Root `AGENTS.md` contains concise future-session operating rules.
5. Python package installation succeeds in a clean isolated environment.
6. Typed configuration loads and validates all initial configuration files.
7. Unknown fields, invalid runtime modes, forbidden server changes, and unsafe live flags fail validation.
8. Configuration precedence and secret handling are documented and tested.
9. Project state, registry, and run history validate against machine-readable schemas.
10. Every registry milestone includes a real-world execution check.
11. The closeout gate refuses incomplete, stale, mismatched, or proof-free milestones.
12. Tests run with a non-zero test count and pass.
13. Repository verification passes.
14. A clean-environment M0 execution evidence bundle is captured.
15. The independent M0 evidence verifier passes.
16. A negative-control test shows the evidence verifier rejects a tampered or incomplete bundle.
17. No secret or sensitive file is tracked.
18. Documentation describes reality and avoids claims about uninspected infrastructure.
19. The human operator reviews the M0 foundation, evidence, deferred work, and safety boundaries and records approval.
20. The existing read-only Forex T480 adapter remains catalog-locked, imports
    the shared AI Lab transport core, and exposes no arbitrary command,
    deployment mutation, MT5 API, market-data, account, or order surface.

M0 `real_world_execution` proof:

> From a fresh temporary virtual environment created from the repository, install the package, load and validate effective configuration, execute the non-empty pytest suite, execute repository verification, capture raw outputs and hashes, and independently verify the resulting evidence bundle.

M0 is `FOUNDATION_ENABLING`, but it still requires actual repository execution. File creation alone is not proof.

## M0 prohibited work

Do not:

- connect to MT5
- inspect a real trading account
- retrieve market data
- add or import order-send functionality
- add trading endpoints
- implement strategy logic
- implement the Forex Analyst Agent
- implement the Risk Engine
- implement position sizing
- implement messaging
- create Forex database state
- modify shared AI Lab infrastructure
- access `GOMarketsMU-Live`
- fabricate evidence
- claim profitability
- begin M1

---

# 15. M0 closeout behavior

After implementation:

1. Run all M0 tests.
2. Run repository verification.
3. Capture the clean-environment M0 proof bundle.
4. Run the independent evidence verifier.
5. Run the negative-control proof-gate test.
6. Correct in-scope failures.
7. Record the run and evidence paths.
8. Evaluate every completion gate.
9. If any gate is missing, leave M0 in the accurate non-proven state and report the blocker.
10. M0 requires human sign-off because it establishes the project's governance and safety foundation.
11. If technical proof passes but operator approval has not yet been recorded, set M0 to `AWAITING_HUMAN_SIGNOFF`, report exactly what the operator should review, and stop.
12. Only if every technical gate and explicit human sign-off pass, use the closeout machinery to set M0 to `PROVEN` and generate `proven_at` in UTC.
13. After M0 becomes `PROVEN`, set M1 to `READY`, with `current_milestone: null` and `next_milestone: M1`.
14. Do not execute M1.

---

# 16. Completion report

Report:

## Repository assessment

- initial Forex state
- reference repository paths, branches, commits, and inspection dates
- pre-existing worktree changes preserved

## Framework reuse

- patterns reused
- patterns excluded
- rationale

## Platform reuse

- PostgreSQL and pgvector
- n8n
- Ollama/model boundary
- Docker networking
- persistence and volumes
- unresolved shared-infrastructure dependencies

## Configuration

- canonical configuration files
- fields and units
- precedence
- secret handling
- validation behavior
- configuration fingerprint
- safety invariants deliberately kept outside ordinary configuration

## Files

- created
- modified
- intentionally not created

## Milestone proof

- implementation status
- verification status
- real-world proof bundle
- independent verification result
- negative-control result
- human sign-off status
- final milestone state
- `proven_at`, only if truly proven

## Risks and unresolved questions

- assumptions
- blockers
- infrastructure decisions requiring human review
- evidence validity limits

## Next recommended instruction

If M0 is proven, provide exactly one bounded recommendation equivalent to:

`Implement M1 — Windows MT5 Read-Only Connection Proof using the installed MetaTrader 5 terminal and GOMarketsMU-Demo. Discover and validate the exact EUR/USD broker symbol, retrieve terminal and safe account metadata, symbol metadata, and the latest bid/ask tick with freshness classification. Capture independently verifiable real-machine evidence. Do not implement orders, trading endpoints, strategy logic, or access GOMarketsMU-Live.`

Then stop.
