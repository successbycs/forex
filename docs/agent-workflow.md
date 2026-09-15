# Agent Workflow

## Purpose

This document defines how Codex carries out authorised work in this repository.

The goal is reliable progress with clear evidence, while keeping human attention
focused on prioritisation, scope, risk appetite, and live-trading authority.

This workflow does not override:

- the active milestone contract;
- `PLANS.md`;
- broker safety rules;
- user instructions; or
- repository access and approval boundaries.

Where documents conflict, apply the stricter safety or evidence requirement and
record the conflict for human resolution.

## Core principles

- Humans define goals, priorities, risk appetite, formal authority, and
  live-trading permission.
- Agents execute bounded, authorised work.
- Agents may autonomously execute within the approved demo-account boundary and
  active ExecPlan.
- The repository is the system of record.
- Every material claim needs inspectable evidence.
- Prefer small, reversible changes with fast feedback.
- Do not convert uncertainty into invented certainty.
- A test pass is evidence of a test pass; it is not automatically evidence of a
  real-world outcome.
- Improve the repository harness when a repeated failure reveals a missing
  instruction, tool, test, boundary, or feedback loop.

## Roles

Roles describe responsibilities, not named models. One Codex session may perform
multiple roles when the task is small and independent review would add little
value.

| Role | Responsibility | May modify files or execute trades? |
|---|---|---:|
| Planner | Clarifies the goal, identifies constraints, creates or updates an ExecPlan. | Planning artifacts only |
| Implementer | Delivers a bounded package of approved work. | Files only |
| Reviewer | Checks scope, architecture, safety, evidence, and regressions. | No |
| Verifier | Independently runs or inspects declared proof and acceptance checks. | Evidence capture only, where authorised |
| Repairer | Fixes a verified defect within the active task scope. | Files only |
| Human operator | Sets priorities, approves formal authority changes, and resolves material judgment calls. | Yes |

## Task entry

Before starting material work:

1. Inspect `git status` and preserve unrelated changes.
2. Read `AGENTS.md`.
3. Read the active ExecPlan and relevant milestone contract.
4. Read the appropriate architecture, product, evidence, and skill documents.
5. Confirm the task is within the active milestone and existing user authority.
6. State the intended outcome, owned paths, acceptance checks, and proof surface.

For tasks based on external claims, strategy ideas, economic-data logic, risk
controls, or performance assumptions, use `research-evidence` before writing or
materially changing an ExecPlan.

Do not begin the next formal milestone merely because the previous task is
implemented.

## Delivery loop

```text
Clarify
→ Plan
→ Implement
→ Verify
→ Review
→ Repair if required
→ Capture evidence
→ Continue or close according to the active contract
```

### 1. Clarify

Translate the request into a bounded outcome.

Identify:

- what will change;
- what will not change;
- dependencies and risks;
- user authority required;
- acceptance criteria;
- the declared proof surface; and
- the next decision gate.

Ask for clarification only when the missing answer materially changes scope,
risk, or implementation.

### 2. Plan

Use a lightweight plan for small, reversible work.

Use an ExecPlan for work involving multiple components, data migrations,
integrations, material strategy logic, broker interaction, new capabilities,
architecture changes, or formal milestone work.

An ExecPlan must include:

- goal and context;
- scope and non-goals;
- owned paths;
- evidence basis and assumptions;
- acceptance criteria;
- verification steps;
- risks and rollback or recovery considerations;
- decision gates; and
- a progress and decision record.

### 3. Implement

The implementer works only within the authorised package.

During implementation:

- make focused, coherent changes;
- follow architecture and dependency rules;
- keep secrets out of the repository and logs;
- update documentation when behaviour or a repository map changes;
- run relevant checks as work progresses; and
- record meaningful deviations from the plan.

If new work is required but outside scope, stop at the boundary and record the
follow-up rather than silently expanding the task.

### 4. Verify

Use `qa-verification` for any material implementation, strategy, integration,
data pipeline, risk-control, scheduled job, dashboard, or release change.

Verification must test the relevant user or system workflow—not only isolated
functions.

For Forex work, verify as relevant:

- source-data validity and timeframe alignment;
- no future data or leakage in decisions;
- deterministic strategy behaviour;
- execution-cost assumptions;
- risk-control boundaries;
- trade/no-trade recording;
- restart, duplicate-event, missing-data, and stale-data behaviour; and
- the active stage’s proof surface.

Capture raw evidence separately from derived verification results.

### 5. Review

Review is read-only and assesses:

- scope adherence;
- architecture and dependency boundaries;
- data and trading safety;
- test quality and coverage of meaningful risks;
- evidence quality;
- documentation accuracy; and
- whether acceptance criteria are actually met.

A reviewer must label findings clearly:

- **Blocker** — prevents safe or correct completion.
- **Required repair** — within scope and necessary before completion.
- **Follow-up** — valid improvement but outside the current scope.
- **Observation** — non-blocking note.

### 6. Repair

The repairer addresses verified blockers and required repairs within the active
task scope.

After repair, re-run the affected verification. Do not claim that an issue is
resolved merely because code was changed.

Escalate when repeated repair attempts do not create new diagnostic information,
when repair requires a material architecture or scope change, or when evidence
is insufficient to determine correctness.

Use `release-readiness` before deploying a material capability, enabling
autonomous demo execution, or reporting a formal milestone ready to advance.

### 7. Continue or close

Before ending an execution turn, run the continuation check required by
`PLANS.md`.

Continue with the next authorised in-scope action when the result is `CONTINUE`.

Close only when:

- the requested outcome is met;
- acceptance criteria have evidence;
- required review and verification are complete;
- formal gates in the milestone contract are satisfied; and
- no remaining authorised work is actionable.

A blocked deployment does not prevent independent authorised preparation,
verification, documentation, or review.

## Forex stage gates

| Stage | Permitted activity | Required evidence | Prohibited activity |
|---|---|---|---|
| Research | Hypotheses, literature review, data assessment | Evidence brief with sources, assumptions, and limitations | Performance claims or broker orders |
| Backtest | Reproducible historical simulation | Versioned data/configuration, bias checks, baseline comparison | Claiming future profitability |
| Paper trading / demo execution | Autonomous signals, risk checks, demo orders, and outcome tracking | Signal, risk decision, order lifecycle, and outcome journal | Any live-account interaction |
| Live execution | Only if a later formal contract permits it | Explicit authority, operational controls, and declared proof | Any activity outside that contract |

## Autonomous demo-execution controls

Autonomous execution is permitted only on `GOMarketsMU-Demo`.

The system may place, modify, and close demo orders without per-trade human
approval when the active ExecPlan authorises the workflow and all configured
risk controls pass.

Before submitting any demo order, the execution workflow must verify:

- the resolved broker account is explicitly identified as the approved demo
  account;
- the environment is not production and is not `GOMarketsMU-Live`;
- the strategy and configuration version are recorded;
- required market data is current and valid;
- the signal has not expired or already been executed;
- position-size, stop-loss, maximum-loss, exposure, drawdown, and duplicate-order
  controls pass; and
- the broker request is journalled before, or atomically with, submission.

The system must fail closed when account identity, environment, market data,
strategy configuration, risk state, or broker response is missing, malformed,
or ambiguous.

A startup check and a pre-order check must independently enforce the
live-account block. A configuration flag alone is not sufficient authority to
trade live.

Demo execution may be paused or disabled through canonical operator
configuration. Disabling execution must preserve data collection, signal
generation, and journalling unless the active ExecPlan specifies otherwise.

Every autonomous demo order must record:

- strategy and configuration version;
- market-data reference;
- rule trigger and rationale;
- risk checks and their outcome;
- broker request and response;
- order identifier and lifecycle events; and
- realised outcome.

## Live-account boundary

Live trading is prohibited.

No code path may place, modify, cancel, or close an order on
`GOMarketsMU-Live`.

Live execution may only be considered after a future formal contract explicitly
changes this policy and declares the required authority, controls, proof surface,
and verification gates.

Never present research, a backtest, demo-account performance, or a generated
recommendation as financial advice or proof of future profitability.

## Evidence standards

Evidence must be:

- attributable to a source, run, dataset, configuration, or observation;
- time-stamped where relevant;
- reproducible or independently inspectable where practical;
- bound to the relevant milestone contract and revision; and
- stored separately from interpretation or recommendation.

Never fabricate, overwrite, or “repair” raw evidence.

Where evidence is weak, incomplete, or contradictory, state that plainly and
recommend the smallest safe next test or decision.

## Repository improvement loop

When an agent encounters a recurring ambiguity, defect pattern, or expensive
manual step, consider whether the repository needs a durable improvement:

- a clearer architecture rule;
- an updated source-of-truth document;
- a targeted skill;
- a deterministic script;
- a test fixture or evaluation;
- a linter or structural test; or
- improved observability.

Only add these when they solve a demonstrated recurring problem or are required
by the active milestone. Avoid framework work that does not advance the current
goal.

## Reporting format

At the end of a material work package, report:

```md
## Outcome
What changed and the user-visible or system outcome.

## Scope
- Owned paths:
- Out-of-scope work deliberately not performed:

## Verification
- Checks run:
- Actual results:
- Evidence location:

## Risks and limitations
- Known limitations:
- Assumptions:
- Follow-up work, if any:

## Status
- Complete
- Complete with limitations
- Blocked
- Needs human decision

## Next authorised action
The next concrete action, if one remains.
```