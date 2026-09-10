# Milestone relevance to a viable live FX system

Reviewed 10 September 2026 at `4cd39e3`. This is a proposed disposition, **not an edited registry, a dependency waiver or new execution authority**. Read the [readiness review](2026-09-10-live-forex-readiness-review.md) and [design review](../docs/reviews/edge_discovery_design_review.md).

The existing roadmap was written around historical learning followed by controlled Demo operation. M20 subsequently absorbed several future capabilities. Continuing M21–M32 mechanically would duplicate work while still ending without a live implementation contract.

“Keep” means preserve the capability and relevant evidence, not repeat a completed milestone. “Merge” means reuse existing code and map remaining acceptance criteria explicitly. Historical `PROVEN` states below are what the registry/state record; this review does not re-certify every earlier surface. `EXCEPTION` abbreviates `HUMAN_REVALIDATION_EXCEPTION` and does not mean proven.

## Complete M0–M32 disposition

| ID | Recorded state | Capability | Proposed disposition and mission relevance |
| --- | --- | --- | --- |
| M0 | EXCEPTION | Repository/configuration/evidence foundation | **Keep, simplify operational use.** Preserve fail-closed configuration and proof integrity. Do not turn every research iteration into a full historical revalidation cycle. |
| M1 | EXCEPTION | Bounded 720-bar H1 Demo export | **Retain as historical import proof.** Its exact sample is not the production research dataset. Expand data through a separately defined data capability. |
| M2 | PROVEN | Data contracts and PostgreSQL import | **Keep.** Reuse existing database/schema and lineage. |
| M3 | PROVEN | Fixed historical MT5 bridge | **Keep.** Reuse transport boundaries; extend only named data operations when needed. |
| M4 | PROVEN | Application historical ingestion | **Keep.** Use as integration boundary rather than a second data platform. |
| M5 | PROVEN | Idempotent historical persistence | **Keep.** This Forex M5 is distinct from shared `cs-ai-lab-infra` M5 recovery work. |
| M6 | PROVEN | Multi-timeframe dataset | **Keep capability; requalify inputs used for research.** Current retained data is 720 M15, 720 H1 and 365 D1 bars. Correct closed-time/UTC semantics and obtain adequate history. |
| M7 | PROVEN | External-source qualification | **Keep as a small checklist.** Apply licence, timestamp, revision and coverage checks to sources actually needed. |
| M8 | PROVEN | US macro vintages | **Optional feature research.** Reuse if a frozen hypothesis requires it; not a prerequisite to testing price-only edge. |
| M9 | PROVEN | Euro-area macro versions | **Optional feature research.** Same rule as M8; do not rebuild merely because it exists. |
| M10 | PROVEN | Economic calendars | **Keep and strengthen in W2/M21.** Current samples are not complete event-risk coverage. |
| M11 | PROVEN | Experimental historical GDELT sentiment | **Defer expansion.** No demonstrated incremental after-cost trading value. Preserve historical artifacts. |
| M12 | PROVEN | Normalisation and quarantine | **Keep and extend narrowly.** Validate bid/ask, time, coverage and late/revised inputs needed by the selected experiment. |
| M13 | PROVEN | Point-in-time alignment/replay | **Keep; extend to strategy replay.** Current alignment helpers are not an executable-policy backtester. |
| M14 | PROVEN | Historical regimes/event windows | **Keep concepts; revise classifier role.** Context must be observable before selection and independent of the strategy label. |
| M15 | PROVEN | Daily hypothesis/ML baseline | **Retain as a baseline, not a production model.** No need for more ML until its incremental net benefit is established. |
| M16 | EXCEPTION | Walk-forward evaluation | **Essential, substantially strengthen through W2/W3.** Same trading policy, correct clocks, realistic costs, independent holdouts and selection control. Current 12-session result cannot supply edge evidence. |
| M17 | PROVEN | Non-executing agent context | **Keep.** Reuse schema validation and authority isolation. |
| M18 | PROVEN | Ollama sentiment assistance | **Defer expansion.** Optional bounded shadow enrichment; exclude from live critical path unless separately validated. |
| M19 | PROVEN | Decision/model lineage | **Keep and extend.** Add trial/family/data/cost/report linkage rather than a second provenance service. |
| M20 | NEEDS_FIX | Continuous capped Demo loop | **Finish as the operational foundation.** Resolve the risk-latch defect and required lifecycle/recovery proof; do not demand profitability from this operational contract. |
| M21 | PLANNED | Event-context quality | **Relevant; merge into W2.1.** Prioritise schedule coverage, exact availability, DST and outage behaviour. Forecast/surprise data can wait unless a strategy uses them. |
| M22 | PLANNED | Simulated risk engine | **Merge with real risk implementation and replay.** Do not build a second simulated engine with different rules. Include simultaneous pauses and loss-budget reservation. |
| M23 | PLANNED | Simulated sizing | **Merge into shared W2 planning.** Size from the intended stop and remaining budget; refuse infeasible minimum lots. |
| M24 | PLANNED | Simulated intent orchestration | **Merge.** Existing proposals/reservations provide much of this; add replay parity and transition checks. |
| M25 | PLANNED | Expiring human approval before Demo orders | **Rewrite.** Human approves the strategy/release/account/risk operating mandate and material changes. Requiring approval of every order conflicts with low-attention autonomous operation and the existing continuous Demo mandate. |
| M26 | PLANNED | Offline pre-execution revalidation | **Merge into W2.1 and deployed submission checks.** Offline checks alone cannot validate a quote that ages during database I/O. |
| M27 | PLANNED | Fresh read-only Demo tick | **Absorb the applicable proof into M20/data qualification.** Much of this is already exercised. Preserve/reassign its required review gate explicitly if the registry is amended. |
| M28 | PLANNED | Tick/spread collection | **High value; bring bounded cost collection into W2/W3.** Specify retention/coverage. Current M20 forbids retaining a tick stream, so amend that scope explicitly before enabling one. Prefer bounded quote samples plus around-trade records where sufficient. |
| M29 | PLANNED | Recovery/idempotent collection | **Merge into W1.R plus W3 unattended observation.** Do not rebuild shared host recovery; reference its verified dependency evidence. |
| M30 | PLANNED | Controlled Demo execution/reconciliation | **Mostly overlaps M20.** Preserve any genuinely missing acceptance case; retire the duplicate sequencing only by approved contract amendment. |
| M31 | PLANNED | End-to-end Demo baseline comparison | **Keep as W3 economic evaluation.** Compare complete policies at matched risk and capital, including pauses and all costs. |
| M32 | PLANNED | Forward Demo/live readiness assessment | **Keep as a go/no-go decision.** Require actual operating economics and execution limitations; passing grants no Live authority. |

## M20 work packages and the existing waves

| Existing group | Recommendation |
| --- | --- |
| M20.1–M20.10 | Finish only unresolved operation, deployment, lifecycle, accounting and evidence items. Reuse completed work. Correct stale retrospective descriptions rather than treating old defects as current without checking. |
| M20.11 five-strategy trial | Keep versioned current behaviour as the comparison baseline. Signal diversity is not portfolio diversification; freeze expansion until the baseline is measurable. |
| M20.12 M5/H1 shadow context | Reuse captured inputs and lineage. Do not promote the context to execution merely because it is available. |
| M20.13 cost-aware exit analysis | Relevant to research economics. Analyse the full exit policy and costs; don't change stops/targets to maximise the same holdout. |
| M20.14 macro/event agent shadow trial | Defer discretionary sentiment/macro judgement. Reliable event-risk gating belongs earlier in W2 and can use deterministic sources. |
| W1.1–W1.4 and W1.R | Continue the existing active work, adding the discovered latch defect to W1.4. Recovery and complete accounting precede meaningful forward evaluation. |
| W2.1–W2.2 | Highest next implementation value: honest eligibility plus one shared decision/exit kernel. Include pre-submit freshness and historical time qualification. |
| W3.1–W3.3 | Use for the small trial register, frozen comparison, operator economics, unattended observation and independent findings. |
| Research R0/E1–E5 | Treat as detailed W1–W3 acceptance work, not a parallel engine/ledger/roadmap. |
| Research E6 | Optional research extension. A slow single-pair challenger may be a cheaper first comparison; a diversified benchmark must specify currency universe, financing and comparable risk. |

## How to amend the roadmap without losing controls

Prepare one proposed contract diff after the operator selects the intended path. For every merged criterion, identify its new owner, existing evidence, remaining proof and invalidation dependencies. Keep milestone IDs and historical outcomes intact; use explicit supersession notes rather than retroactively marking unproven work complete. Schema changes may be required if a new supersession state is desired.

The current top-level `known_blockers: []` must not be read as live readiness. M20 still says `NEEDS_FIX`, and operational handovers contain pending proof. Derive a concise readiness view from the actual criteria, not from a single summary field.

The prompt's proposed **EDGE-M0–EDGE-M12 should not be added as a second mandatory sequence**. Map registry/outcomes/costs/temporal tests into W2/W3, defer advanced statistics and sentiment, and retain the active milestone rule. Finishing the scientific review can yield an inconclusive or rejected strategy; successful engineering does not require manufacturing a winning strategy.

## The missing live stage

M32 ends at assessment. A later **Wave 4: gated live pilot** would need a new, separately approved milestone contract. The name here is a proposal, not a created milestone or goal.

| Gate | Required outcome | Demonstration |
| --- | --- | --- |
| L1 — supported candidate and business case | Frozen strategy has reproducible historical/prospective evidence, feasible lot sizing under approved risk, complete recurring cost assumptions and a supported Demo execution result. | Rebuild evaluation and reconcile actual Demo fills; report all inconclusive risks. |
| L2 — live boundary implementation | Exact approved account/server and release are bound; isolated state/credentials; deterministic sizing/protection; human-controlled mandate; default-disabled order access. | In a non-Live test surface, reject wrong account/server, expired/revoked authority, mismatched config and uncertain state. Review the ready-to-enable configuration and rollback. |
| L3 — authorised funded pilot | Operator separately approves capital, account, pilot duration/end conditions and maximum loss. No automatic promotion or risk increase. | Actual tiny Live fills and statements establish live cost/fill/recovery behaviour. Demo cannot substitute for this evidence. |
| L4 — operating review | Net income and operator effort are viable over the declared review window, with uncertainty and drawdowns reported. | Fixed-date report and capital review; retain failures. Scale, continue, revise or retire by explicit decision. |

The current `GOMarketsMU-Live` prohibition remains effective throughout this review and all existing Demo waves. Live configuration cannot be created simply by changing a boolean: approved contracts, configuration validation, account-bound state, adapter capability and evidence surfaces must agree.

**Recommended next activity: W1.4 risk-latch repair and remaining W1 proof, followed by W2.** The review does not authorise executing the proposed milestone changes.
