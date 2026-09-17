# Forex Project

## Objective

Build an evidence-led Forex decision and execution platform.

The MVP evaluates explicit trading hypotheses, uses market and external economic
context to support trade/no-trade decisions, and records reproducible evidence.
It begins in research, backtest, and paper-trading modes. Live execution is a
later stage that requires explicit human authorisation and formal safety gates.

Do not claim or imply that the system can guarantee a positive return. Research
and backtest results justify hypotheses and controlled experiments; they do not
prove future profitability.

## Repository map

Use this repository as the system of record. Before beginning material work, read
the sources relevant to the task:

- `docs/architecture.md` — domains, layers, interfaces, and dependency directions.
- `PLANS.md` — ExecPlan format, execution lifecycle, progress records, and stop
  conditions.
- `project_state.json` — current formal state.
- `milestone_registry.json` — active milestone contract, entry gates, and proof
  requirements.
- `docs/evidence_and_milestones.md` — evidence model and milestone policy.
- `docs/t480-deployment.md` — mandatory transport constraint and release
  procedure for every T480 deployment.
- Active ExecPlan — scope, acceptance criteria, risks, and verification steps.
- `.codex/skills/research-evidence/SKILL.md` — use before planning work based on
  external claims, strategy ideas, market behaviour, or research.
- `.codex/skills/qa-verification/SKILL.md` — use before reporting a material
  implementation, integration, strategy, or release as complete.
  - `docs/agent-workflow.md` — roles, delivery loop, review/repair workflow, and
  autonomous demo-execution controls.

`AGENTS.md` is the repository map and non-negotiable operating boundary. Keep
detailed process, templates, workflow status, and changing delivery information
in the documents above rather than expanding this file.

## Architecture and planning

Use Harness engineering principles: make the repository legible to Codex through
clear structure, executable feedback loops, versioned plans, and enforceable
boundaries.

Use `docs/architecture.md` as the architectural source of truth. Prefer explicit,
simple boundaries over unnecessary abstraction. Shared platform transport belongs
to `cs-ai-lab-infra`; this repository owns Forex adapter catalogues, application
schemas, workflows, decisions, and evidence.

For work requiring multiple steps, risk decisions, integrations, or material
changes, use an ExecPlan. Read `PLANS.md` and the active ExecPlan before
execution.

Implement only the active formal milestone. Completing an implementation task
does not itself advance formal milestone state. Starting a new formal milestone
requires an explicit human Goal or instruction and satisfaction of its declared
entry gates.

## MVP delivery standard

Prioritise the smallest reliable implementation that proves the active milestone.

### MVP focus rule

Default to the smallest change that makes the next real Demo workflow more
reliable, observable, or safe. Planning and governance are supporting work;
they must not become the primary deliverable.

Before adding infrastructure, process, or a new artifact, state the current MVP
failure it fixes, the smallest implementation, the observable result it will
produce, and what remains deferred. Do not add a framework, service, scheduler,
migration framework, review layer, new skill, or new documentation process
unless the active milestone cannot advance without it.

Prefer one constraint over a platform, one focused test over a broad test
programme, one retained observation window over endurance testing, and an
existing listener, bridge, or report path over new orchestration. Preserve an
honest `UNKNOWN` rather than adding machinery solely to remove uncertainty.

Do not add production-scale infrastructure unless it is required for:

- data integrity;
- broker and trading safety;
- reproducibility;
- the active milestone’s declared proof surface; or
- an explicit acceptance criterion.

Every bounded task must record:

- owned paths;
- acceptance checks;
- actual test or observation result;
- limitations, risks, or unresolved assumptions.

## Evidence, research, and proof

Use `research-evidence` before creating or materially changing an ExecPlan for a
strategy rule, indicator, model, risk control, economic-data decision, or
product hypothesis.

Research evidence must distinguish:

- evidence-supported findings;
- reasonable inferences;
- assumptions requiring a test; and
- unsupported or rejected claims.

Each formal milestone must declare its proof surface in its registry contract.

“Real-world proof” means evidence captured on that declared surface. Code,
tests, mocks, screenshots, documentation, and narrative JSON are necessary
supporting evidence but are not real-world proof by themselves.

Keep raw evidence separate from derived verification results. Never fabricate,
repair, alter, or overwrite captured raw evidence.

A material implementation, dependency, schema, interface, governed
configuration, or workflow change invalidates affected proof. Record the impact
and the re-verification required; do not invalidate unrelated proof without
reason.

Before formal closeout, require the current review and recommendation gates
declared in the active registry contract and `PLANS.md`. Review roles are
read-only and cannot approve or close milestones.

`target_date` is a human-owned forecast. Only the approved closeout process may
create the actual completion timestamp, `proven_at`.

## Testing and verification

Every code change must move the active milestone towards its declared outcome.

After a meaningful implementation change:

1. Run relevant automated checks.
2. Inspect real outputs, not only command exit codes.
3. Use `qa-verification` for material changes.
4. Capture evidence against each acceptance criterion.
5. Repair in-scope defects before reporting completion.

A passing test suite alone is not sufficient. Verification must include the
relevant end-to-end workflow, data integrity, safety controls, and declared
proof surface.

Before ending an execution turn, run:

```bash
python3 scripts/check_execution_continuation.py
```

- `.codex/skills/release-readiness/SKILL.md` — use before deploying a material
  workflow, enabling autonomous demo execution, promoting a strategy to its next
  stage, or closing a formal milestone.

## Repository change authority

Codex may create local commits for completed, tested, scope-authorised work when
the active milestone or approved ExecPlan explicitly permits it. Before
committing, it must verify the relevant tests, preserve unrelated changes,
include only owned paths, and report the commit hash.

Codex must not push, create branches, open pull requests, change formal
milestone state, or perform Live-trading actions without Chris's explicit
instruction.
