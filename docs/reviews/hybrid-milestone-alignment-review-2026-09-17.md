# Hybrid milestone alignment review — 2026-09-17

## Purpose

Align the planned continuous EUR/USD M1 Demo workflow with the repository's
existing formal milestones. This is a read-only contract review. It does not
release maintenance hold, change the listener, alter strategy or risk rules,
deploy software, or submit a broker order.

The desired MVP operating model is a protected continuous Demo listener: every
new completed M1 candle produces one recorded `BUY`, `SELL`, or `NO_TRADE`
decision. A normal `NO_TRADE` is evidence and the listener continues to the
next fresh candle. It is not a broker retry, a direction change, or permission
to weaken a gate in order to collect more trades.

The first naturally eligible completed lifecycle on the resulting release is
M30's real-system proof. Accumulated forward outcomes are then evaluated by
M31. Neither a single Demo trade nor a collection of early outcomes establishes
future profitability.

## Review basis

The review inspected `milestone_registry.json`, `project_state.json`,
`docs/architecture.md`, `docs/agent-workflow.md`,
`docs/workflows/m1-demo-decision-workflow.md`, the M30 and hybrid ExecPlans,
and the M1 runtime entry points. The `trade-decision-engine` review procedure
was applied to preserve the fixed completed-candle, one-owner, one-proposal,
pre-submit persistence, and no-retry decision contract.

## Current contract facts

- M30 is the active formal milestone. Its only declared prerequisite is M29.
- M29 is proven under its retained-evidence policy. No repeat recovery drill is
  needed for this review or the proposed operating-method amendment.
- M20 is **not** formally proven: `project_state.json` records
  `HUMAN_REVALIDATION_EXCEPTION`. Its historic Demo evidence remains useful
  foundation evidence, but it must not be restated as current M30 proof.
- M21 through M29 are formally proven. Their retained interfaces and evidence
  can be reused unless a change touches their declared invalidation surface.
- M30 is in progress and has no current real-world proof bundle. The prior
  M30 collection retained a valid `NO_TRADE`; it did not submit an order.
- M31 and M32 are planned and remain unavailable until their declared
  predecessors are proven.

## Decision-contract finding

The operational workflow says a completed candle should create one terminal
decision, with `NO_TRADE` a normal outcome. The listener service currently
stops assessment while `MAINTENANCE_HOLD` is active, although it continues
open-position monitoring. The current one-shot M30 collector restores that
hold after a valid `NO_TRADE`. Consequently it is suitable for a bounded proof
attempt but not for continuous evidence capture.

This is an operating-method mismatch, not evidence that a strategy is wrong.
The repair must distinguish:

1. a deliberate deployment maintenance hold, which may temporarily suppress
   new assessment;
2. a normal per-candle `NO_TRADE`, stale quote, unsuitable spread, or occupied
   position, which is journalled and then allows evaluation of a later candle;
   and
3. a safety stop such as unknown broker outcome, account mismatch, failed
   durable journalling, unresolved exposure, or active risk pause, which blocks
   new entries while existing position protection continues.

The existing five M1 strategies remain unchanged: momentum breakout,
compression breakout, trend pullback, range reversion, and session breakout.
The session-breakout rule's 07:00–20:00 UTC condition is part of that strategy;
it is not the retired global Demo entry-hours policy.

## Alignment decision table

| Milestone | Current formal state | Relationship to hybrid workflow | Required action |
| --- | --- | --- | --- |
| M1–M19 | Historical foundation; not active dependencies for this delivery | Research, data and earlier design evidence. They do not authorise a new M1 runtime or Demo action. | No review amendment now. Preserve evidence and do not reopen. |
| M20 | `HUMAN_REVALIDATION_EXCEPTION` | Supplies the fixed Demo listener/executor, persistence, monitoring and reconciliation design that the hybrid MVP reuses. | Correct plan wording that calls M20 “proven.” Do not revalidate it solely for this documentation review. Do not use its historic bundle as proof of the changed M30 release. |
| M21 | Proven | Event-context quality evidence exists, but the shipped M1 event policy is annotation-only. | Retain. It is not an active M30 entry veto and must not be silently enabled. |
| M22–M24 | Proven | Historical simulated risk, sizing and intent evidence; not the active Demo execution authority. | Retain as historical foundation; no runtime implementation work. |
| M25 | Proven | Proved an earlier human-approval simulation workflow. The current Demo policy permits autonomous orders under an active ExecPlan and fixed gates. | Add an explicit historical/superseded-for-Demo note so M25 is not misread as per-trade approval required by M30. It remains relevant to any future human approval design. |
| M26 | Proven | Provides prior simulated final-input revalidation evidence. Current M30 still retains real pre-submit freshness, spread, risk and broker checks. | Retain. Do not add a duplicate revalidation system. |
| M27–M28 | Proven | Fresh Demo data, tick and spread safety foundation. | Retain. The continuous listener continues to apply its governed freshness and spread gates. |
| M29 | Proven | Direct M30 prerequisite; proves retained recovery safety. | Retain unchanged. Continuous operation must not weaken recovery or protective monitoring. |
| M30 | `IN_PROGRESS` | Owns the current MVP's final-version autonomous Demo entry, protected close and exact reconciliation proof. | Amend operating method: continuous fresh-candle collection is permitted; the first natural full lifecycle is captured read-only as M30 evidence. Preserve one-position, fixed caps, Demo-only, proposal-before-submission, no-retry and mandatory-close boundaries. |
| M31 | Planned; depends on M30 | Owns evidence-led evaluation after the final workflow is proven. | Amend before starting M31 to require predeclared analysis of versioned forward observations: each strategy's signal count, selection, refusal reasons, costs, realised outcomes and uncertainty. No optimisation or promotion based on early samples. |
| M32 | Planned; depends on M31 | Later forward-Demo evaluation and Live-readiness assessment. | Keep deferred. Replace stale “human-operated Demo workflow” wording with “protected, observable Demo workflow”; M32 still grants no Live authority. |

## Recommended delivery structure

No new formal milestone is needed. Use M30 as the formal outcome and one
amended M30 continuous-Demo ExecPlan for implementation. Its waves are delivery
packages, not milestones:

1. **Wave 1 — Continuous protected Demo operation.** Amend the M30/hybrid
   contracts, implement the minimum listener mode change, verify the existing
   gates, and release only after release-readiness. Ordinary `NO_TRADE` resumes
   with the next completed candle. This wave does not change a strategy, risk
   limit, session-breakout rule, or broker retry rule.
2. **Wave 2 — Fixed account execution profile.** Add one
   `M1_EURUSD_DEMO` profile with an expected locally held account hash. Verify
   it before executable assessment and immediately before submission; mismatch
   must reach neither reservation nor order. Multi-account routing and
   multi-account database partitioning remain deferred until a second profile
   is explicitly authorised.
3. **Wave 3 — Read-only evidence visibility.** Show closed-candle timestamp,
   all five signals, selected owner, refusal/veto reasons, proposal/attempt,
   lifecycle, actual costs/outcome and unresolved joins. Facts that cannot be
   observed remain `UNKNOWN`.
4. **Wave 4 — M30 proof extraction.** Preserve the first naturally eligible
   current-version lifecycle from proposal through broker-confirmed close and
   reconciliation, then run M30's offline verifier and formal closeout path.

Qualified economic context, M5/H1 improvement, M15, Prefect/n8n, multi-account
routing, new strategies, risk expansion and Live execution are explicitly not
part of these waves.

## Required amendments before implementation

1. Amend `milestone_registry.json` M30 notes/scope only to permit continuous
   eligible M1 Demo evaluation as the evidence-producing operating method.
   Its proof surface stays one bounded, protected, reconciled Demo lifecycle.
2. Amend `docs/plans/m30-controlled-demo-execution.md` so its capture path is
   read-only collection of an existing lifecycle, rather than an operation that
   ends continuous assessment after `NO_TRADE`.
3. Amend `docs/plans/m1-hybrid-prefect-postgres.md` to make continuous
   operation Wave 1 and to make final proof depend on completed Packages A–D
   plus the account-profile repair, not deferred Package E.
4. Correct affected wording in `docs/architecture.md` and
   `docs/agent-workflow.md` only where it conflicts with the amended M30
   contract, notably the M20 status and M25 approval history. The runtime
   remains the operational source of truth until the new version is deployed.
5. Create the self-contained M30 continuous-Demo ExecPlan and its Wave 1
   execution-work record. It must name owned paths, acceptance checks,
   deployment rollback, raw evidence, and the release-readiness gate.

## Acceptance for the alignment review

The review is complete when the proposed amendments preserve all of these
invariants:

- only `GOMarketsMU-Demo` / EURUSD can execute;
- exactly one terminal decision exists per completed M1 candle;
- at most one deterministic strategy owner can execute;
- every actionable proposal is durable before submission;
- unknown broker state and database loss cannot create a retry or unjournalled
  order;
- normal `NO_TRADE` continues data capture on the next fresh candle;
- existing open-position monitoring and close protection continue during a
  new-entry pause; and
- M30 proves integration, while M31 evaluates accumulated results without a
  profitability claim.

## Decision and next gate

**Recommendation:** approve the five required documentation/contract
amendments, then create the M30 continuous-Demo ExecPlan and execute Wave 1.
The runtime must remain in its present maintenance state until that plan,
focused tests, independent review, and release-readiness decision are complete.

This review authorises no broker operation, maintenance release, deployment,
or formal state transition.
