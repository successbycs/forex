# Demo Platform Waves — critical strategy delivery

## Active Harness sequence — 2026-09-13

This section takes precedence over the retained W1–W3 planning text below.
It is a delivery sequence only: formal M29 state, broker boundaries and proof
requirements are unchanged.

```text
Harness H1–H4 → Wave A → Wave B → Wave C
```

| Stage | Exit condition | Boundary |
| --- | --- | --- |
| Harness H1–H4 | A concise repository map, this active sequence, a visible task/evidence status interface, the two-loop role rule, and an offline Plane mapping are prepared. Plane connectivity acceptance is explicitly parked. | Plane-independent only; no Plane integration, trading or milestone transition. |
| Wave A | Real BLS, FOMC and ECB calendar records are retrievable from PostgreSQL with source, capture and raw/receipt lineage. | Raw immutable evidence remains authoritative; retrieval is not calendar-policy activation. |
| Wave B | PostgreSQL calendar context is bound into the final M1 decision record and an explainable joined report presents UTC and Pacific/Auckland views. | While the policy remains disabled, this is annotation/audit only; an eligibility-changing veto needs its separately approved activation. |
| Wave C | Recurring protected Demo decision, execution and reconciliation are observable on the declared surface. | Natural operations only; no forced trades or fabricated proof. |

H_SLOW and broad strategy/research work are deferred, not deleted. They do not
compete with this sequence. Every task must retain its scope, paths, commands,
results, review disposition, evidence class and exact external blocker. Tests,
reviews and documentation are implementation evidence—not real-world proof.

### Mandatory Terra/Astra repair loop

Terra implements one bounded task and supplies its task evidence. Astra reviews
the code and focused checks, then returns a precise repair request when needed.
After **two failed Terra repairs of the same defect**, Astra repairs it directly;
an independent read-only reviewer then checks Astra's material fix. No actor can
self-accept, fabricate proof or replace required formal review/sign-off.

### Triad rule reconciliation

`AGENTS.md` requires a current Triad-plus-domain recommendation for closeout,
while formal registry contracts declare their own review gates. This is a
governance ambiguity, not a delivery exemption: until Chris explicitly
reconciles it, closeout must meet the stricter combined requirement. This does
not amend M29 or change any milestone state.

## Objective

Deliver two equally important EUR/USD Demo strategies and the shared platform
they need to operate safely with external economic-event context:

- **M1:** the existing short-horizon strategy stream;
- **H_SLOW:** the isolated longer-hold strategy stream.

The purpose of the Waves is focus, not serialisation. Work may proceed in
parallel across Waves when its own dependencies are satisfied. A market closure
or missing natural observation parks only that exact operation. It never
authorises unrelated work, a Live account, forced trades, altered risk limits
or an unbound change to execution semantics.

## What is on the critical path

Only work that gets a solo operator to a **safe, real, bounded Demo
decision-and-outcome loop**, makes that loop reconcilable, or supplies its
verified economic context belongs in the active Waves. Initial success is
correct, explainable, protected and reconciled decision-making—not a claimed
edge, an arbitrary trade count or a backtest result. When trade-offs arise,
prefer the smallest implementation that advances a real protected Demo
decision over hardening or optimising hypothetical future cases.

Deferred work includes cosmetic dashboards, broad n8n expansion, unneeded
refactors, speculative strategy variants, optimisation tournaments, generic AI
agents, non-primary news sources and Live-trading work. Deferred does not mean
deleted.

## Wave 1 — shared Demo execution trust

This is common infrastructure required by both strategies.

| Critical package | Result |
| --- | --- |
| Durable M29 recovery collector | Append-only recovery observations, fixed read-only collection, and independent continuity/dedup verification. |
| Fresh-Demo recovery drill | Genuine interruption/restart evidence against fresh quotes, without an order. This is parked only until the broker surface is available. |
| MT5 reconciliation baseline | Match retained MT5 history to decisions, attempts, position events and outcomes; unknowns remain explicit and block new entry where required. |
| Operating register | Name each listener, exporter and collector, its owner, cadence, health signal, evidence location and recovery procedure. |

## Wave 2 — economic-event strategy context

This makes external economic information available as trustworthy strategy
context for both M1 and H_SLOW.

| Critical package | Result |
| --- | --- |
| Primary calendar coverage | Retain and qualify the smallest EUR/USD-relevant first-party set: BLS CPI/Employment Situation, Federal Reserve/FOMC, and ECB policy calendars. Raw source bytes and receipts remain authoritative. |
| Validated event projection | Project verified calendar records into queryable PostgreSQL facts with source/capture/digest lineage, while retaining raw files separately. |
| Strategy/event context | Give each decision an exact point-in-time event window and provenance record, never future information. |
| Event-risk eligibility gate | A versioned `ALLOW`/`NO_NEW_ENTRY` input may prevent a new trade around configured events. It cannot choose direction or manage an existing position. |
| Event-aware review | Reconcile strategy decision, gate result, event window, broker outcome and costs for every observed trade. |

The event-risk gate changes entry semantics. Build and test it behind disabled
configuration, then deploy only after an exact operator-approved policy,
configuration binding and affected-contract treatment are recorded. Initial
external data is a risk/exposure context, not a directional trading oracle.

## Wave 3 — H_SLOW strategy completion and isolated Demo trial

H_SLOW is an equal strategy stream, not a nice-to-have. It reuses Wave 1 trust
and Wave 2 context, but remains account, state and lifecycle isolated from M1.

| Critical package | Result |
| --- | --- |
| Complete strategy contract | Explicit entry, exit, holding/rebalance clock, stop/target, financing, weekend, invalidation and review/end rules. |
| Initial fixed-risk sizing | Start the Demo trial at its human-approved conservative fixed cap. Account/notional/protection/cost caps always win; no recent wins/losses, confidence, hindsight, reload capacity or self-modification may enlarge risk. |
| Isolated durable lifecycle | PostgreSQL-backed intent/reservation/position/outcome lifecycle and immutable input provenance; no shared M1 ownership or hidden aggregate exposure. |
| Event-aware H_SLOW context | Apply the same verified source/event-window model while keeping H_SLOW-specific holding and protection semantics explicit. |
| Dedicated Demo activation | Bind the designated Demo terminal/account, limits, protection and resume authority; keep the worker disabled until that mandate is complete. |
| Reconciled parallel observation | Produce separate and combined exposure/outcome reports without allowing one stream to control the other. |

## Delivery sequence

```text
Wave 1: make both streams trustworthy
   ├── Wave 2: give both strategies verified economic-event context
   └── Wave 3: complete and activate the isolated H_SLOW strategy

Then: operate M1 and H_SLOW on Demo, reconcile outcomes, and change one
versioned hypothesis at a time.
```

Wave 2 and Wave 3 implementation begin now alongside the market-dependent
portion of Wave 1. Deployment/activation remains individually gated: a source
must be qualified, an event gate must have an approved policy, H_SLOW sizing
must meet its fixed hard cap and H_SLOW must have its exact ongoing, revocable
Demo mandate. Verifier-backed forward/OOS tiering is a post-trial refinement,
not an entry prerequisite.

## Demo strategy readiness

The target is met when M1 and H_SLOW each have: bounded Demo authority;
recovery and reconciliation; a fixed strategy contract; verified point-in-time
event context; protected broker-side risk controls; and a retained outcome
record. This is readiness for Demo learning, not proof of profitability or
permission for Live trading.

## Future-wave intake — capability-derived work

This is the authoritative intake list when a later Wave is created. It is
**not an active Wave**, does not change the M29 contract, and must not displace
the present M1/H_SLOW Demo critical path. Create a package only when its stated
trigger is true and give it an explicit evidence surface.

| Candidate capability block | Why it becomes a Wave | Earliest creation trigger | Must not become |
| --- | --- | --- | --- |
| Market reference, session and decision-snapshot contract | Makes every decision reconstructible from broker constraints, market-open/rollover state, freshness and exact point-in-time inputs. | Before relying on unattended M1 decision quality beyond the initial bounded loop. | A second market-data platform or a reason to infer missing facts. |
| Strategy lifecycle and controlled promotion | Records strategy, parameter, feature and data versions; supports a measured challenger, rollback and retirement. | After a meaningful set of reconciled Demo outcomes exists. | Automated rule changes, risk expansion or an AI deployment path. |
| Outcome attribution and edge monitoring | Attributes results to decision, event regime, costs, spread/slippage and strategy version; detects deterioration. | Once retained reconciled outcomes are sufficient to analyse. | A profitability claim or automatic sizing increase. |
| Shared portfolio and aggregate exposure control | Enforces cross-stream loss, notional, concurrency and directional-concentration caps while preserving stream isolation. | Before concurrent M1 and H_SLOW Demo activation. | A controller that changes either strategy's direction or operates its positions. |
| Unified order/position lifecycle and protection monitor | Covers submitted, rejected, partial, filled, amended, closed and unknown broker states, including confirmed broker protection. | Before H_SLOW submission is enabled; improve M1 only on observed lifecycle gaps. | A generic broker router or permission for an unbound terminal. |
| Operational control and recovery plane | Provides scoped pause/resume/kill, release/rollback identity, health objectives, alert routing and incident handover. | After the current M29 recovery evidence is obtained and any observed fault identifies a real gap. | Cosmetic dashboards or a replacement for broker reconciliation. |
| AI advisory governance | Retains model, prompt, data, evaluation and recommendation lineage for research/review assistance. | Only if an AI result is proposed as input to a human strategy review. | AI order authority, broker credentials, autonomous strategy promotion or risk changes. |

The preferred order is: finish the current bounded Demo loop; add shared
exposure and H_SLOW lifecycle before concurrent operation; then build
attribution and strategy-lifecycle governance from actual outcomes. AI remains
advisory and optional throughout.
