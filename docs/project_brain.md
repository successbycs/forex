# Project brain

Forex is a learning-first EUR/USD research project. Its active M20 MVP is a bounded autonomous Demo-only loop—not a live-trading capability: a permanent T480 listener assesses fresh EUR/USD M1 data every ten seconds, records a proposal, candle metrics, and reason, may act only inside a capped Demo session, then reconciles the result. `NO TRADE`, `WAIT`, `INSUFFICIENT DATA`, and `NO SUFFICIENT EDGE HAS BEEN DEMONSTRATED` are valid results.

The approximately USD 300 monthly figure is an aspiration for research comparison only. It is not a quota, acceptance criterion, sizing input, or profitability claim. Capital preservation, data integrity, safety, reproducibility, and explainability precede return.

Current state is authoritative in `project_state.json`; the milestone registry is the fixed contract. The roadmap retains its three phases, while the active M20 MVP brings forward one narrow real-time Demo function: fresh tick plus closed M1/M5 data, a persisted `BUY`/`SELL`/`NO_TRADE` proposal, fixed session-capped Demo execution, and PostgreSQL reconciliation. It neither creates live access nor a reusable broker-control interface.

M2 has persisted the retained M1 EUR/USD H1 historical observation in the
private T480 shared PostgreSQL service. Its verified evidence records one
`DEMO_ONLY` source, one raw observation, one immutable snapshot, and 720 bars
with lineage and no-lookahead checks. This is historical research data only:
it neither creates a live feed nor permits orders. M2 requires its declared
proof and explicit human sign-off; the Review Board is reserved for phase
gates M16, M27, and M32.

Administrators can inspect the price-data database directly from the home LAN;
see [`docs/database_access.md`](database_access.md). This is direct PostgreSQL
client access to the T480, not a new trading application or order surface.

## Architecture knowledge

The maintained visual overview is
[`docs/assets/forex-architecture-overview.png`](assets/forex-architecture-overview.png).
It records the intended three-zone boundary: Forex owns its application
contracts, evidence tooling, and catalog-locked adapter; `cs-ai-lab-infra`
owns shared T480 transport and platform services; Windows T480 hosts the
fixed M20 Demo-only MetaTrader 5 surface. It also records the current
self-attested evidence path and four-role Triad-plus-domain review.

The diagram is explanatory rather than an assertion that every shown future or
shared component is deployed. `docs/architecture.md` is the narrative source
of truth for the design, while the milestone registry and project state retain
their respective contract and execution roles.

The four-role Review Board is retained for the three phase gates only: M16,
M27, and M32. M20 instead needs a current Triad-plus-domain completion
recommendation and has no human sign-off gate. There is no separate
Builder/Reviewer workflow or automated reviewer runner.

The design-only prompt for the proposed historical market-intelligence and
Ollama-assisted research capability is retained in
[`docs/prompts/advanced-market-intelligence-milestone-prompt.md`](prompts/advanced-market-intelligence-milestone-prompt.md).

### M11 GDELT experimental context data

M11's sentiment prototype uses GDELT raw GKG files. Forex stores only
attributable derived aggregates—UTC H1 article count and mean tone—alongside
a source URL, source-file hash, retrieval/availability time, fixed query
definition and uncertainty label. It does not retain article text or create a
sentiment-driven trading claim.

The target research join is an H1 UTC join between these aggregates and EUR/USD
price bars. A GDELT value is eligible only when it was available before the
decision cutoff; evaluation targets a later bar or session result. This gives
historical replay and future daily collection the same no-lookahead shape.

The T480 shared n8n service is the scheduler/operator surface using the
existing Autonomous-Framework-derived adapter. The future workflow uses n8n
nodes for schedule, download, ZIP extraction, aggregation and PostgreSQL
persistence; it does not launch a Python scheduler or depend on a mounted
Forex worktree. It is not active until an explicit workflow import, PostgreSQL
credential setup and observed T480 execution.
[`system_design.md`](system_design.md) is the technical design and
[`architecture.md`](architecture.md) is the maintained overview.

## Inspected sources

Inspected on 2026-08-17:

- `mp4-to-transcript`, local `main` at `85af3a6`: explicit job lifecycle, persistent failures, verification, and human review patterns.
- `options-learning-kb`, local `main` at `dc12e04`: registry/state separation, dependency gates, evidence freshness, hashing, and independent verification.
- `cs-ai-lab-infra`, local `main` at `e11c27d`: real-world checks, `proven_at`, T480 evidence bundles, and shared transport ownership. Pre-existing edits to its milestone registry and documentation were preserved.
- Autonomous Framework, inspected current `main` at `174226df` through its available checkout/repository material: transition contracts, definition of done, proof-value audit, and human sign-off policy. The local reference directory is not currently a Git checkout, so its present local revision cannot be independently re-read with `git`.

No reference repository was modified as part of M0 governance hardening.
## M20 operational knowledge base

## Demo listener operating model

The M20 listener is a permanent T480 Scheduled Task. It runs the immutable,
hash-checked release under `C:\ProgramData\ForexListener\releases`, while
machine-local lease, status, recovery and configuration state live under
`C:\ProgramData\ForexListener\state`. The listener updates a redacted
heartbeat every second. After its five-second minimum interval, a new MT5
EURUSD quote triggers one assessment; it cannot assess the same quote twice.
It is restricted to
`GOMarketsMU-Demo`; it has no Live-account or generic MT5 command surface.

The dashboard on T16 is read-only: `python3 scripts/m20_listener_dashboard.py`.
It shows UTC/NZST heartbeat, cadence, candle metrics, decision rationale, and
five strategy rows. Momentum Breakout is the only active execution strategy;
the other four strategies are shadow-only comparisons.

The separate read-only trade ledger dashboard is
`python3 scripts/m20_trade_ledger_dashboard.py`. It shows the last ten Demo
attempts as BUY or SELL, their entry, SL, TP, lot size, monitoring state, and
only a broker-reconciled realised profit or loss. A missing P&L is shown as
`Pending`, never guessed.

### M20 SL, profit target, and exit rule

For each eligible M1 momentum-breakout trade, the executor sets broker-side
SL and TP at order submission. The stop begins at the recent five-candle
technical invalidation level, but is moved closer to entry whenever needed to
keep the planned loss at or below A$100 using MT5's tick value, tick size,
minimum lot, and allowed price increment. The initial target is 1.5R, where
R is the actual entry-to-stop distance. The system refuses a trade if the
nearest credible target offers less than 1.25R.

After +1R, the monitor requests a broker-side breakeven stop. MT5 closes at
SL or TP when reached; otherwise the monitor exits after two opposite
completed M1 candles or ten completed M1 candles. PostgreSQL records the
broker-confirmed exit and realised AUD P&L only after reconciliation.

Every proposal, broker attempt, position event, cost component, and closed
P&L outcome is persisted in PostgreSQL. A Demo order is not evidence of a
successful M20 closeout until its lifecycle is reconciled through `CLOSED` and
an immutable outcome record.

### M20 six-step operating procedure

1. **Read the market.** The listener reads a fresh Demo EURUSD quote and only
   completed M1 candles. A quote can be a new MT5 update even when its displayed
   bid and ask are unchanged; the MT5 tick time prevents reuse of a cached quote.
2. **Assess before any order.** Momentum Breakout is the sole executable rule.
   It requires at least six completed M1 candles, two latest candles aligned in
   one direction, a close beyond the prior five-candle high (BUY) or low (SELL),
   and a combined move greater than the current spread. The other four strategy
   signals are recorded as shadow comparisons only.
3. **Open one protected trade when eligible.** A qualifying BUY or SELL uses
   the current executable price with broker-side stop loss and take profit. The
   stop is based on candle invalidation but capped to the A$100 planned-loss
   limit; the initial target is 1.5R. A trade may also exit after two opposite
   completed M1 candles or ten minutes.
4. **Record the lifecycle.** PostgreSQL receives the assessment, proposal,
   reservation, broker response, opening event, stop/target changes, close,
   costs, exit price, and realised AUD P&L. Rejections are terminal non-trades;
   no automatic retry is permitted.
5. **Add a read-only outcome hypothesis later.** A future post-close analysis
   agent should append a separate hypothesis record beside the immutable ledger,
   not change the trade record. It should state its evidence, confidence, and
   `UNTESTED`, `SUPPORTED`, or `REJECTED` status for wins as well as losses.
   This is planned work, not an active M20 execution authority.
6. **Refine rules through versioned experiments.** Keep the live rule fixed;
   run candidate rules in shadow mode against the same assessments, compare
   closed post-cost outcomes, then promote one tested rule version at a time.
   A rule refinement never edits past assessments or trades.
