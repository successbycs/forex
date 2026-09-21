# Forex Project

Build an evidence-led Forex decision and execution platform. Prioritise the
smallest reliable Demo workflow that advances the active milestone. Research,
backtests and Demo results do not guarantee returns or prove future profitability.

## Read before working

This file contains durable boundaries and the repository map. Read the linked
sources relevant to the task; keep procedures and changing status there.

- `project_state.json` — current formal milestone and state.
- `milestone_registry.json` — scope, entry gates and required proof surface.
- `docs/architecture.md` — component ownership and dependency directions.
- `docs/agent-workflow.md` — required delivery, diagnosis, verification and
  reporting procedure for material work.
- `PLANS.md` and the authorised active ExecPlan — execution scope, steps,
  reviews and stop conditions. Use an ExecPlan for material or multi-step work.
- `docs/evidence_and_milestones.md` — evidence integrity and formal closeout.
- `docs/t480-deployment.md` — mandatory transport limits and release procedure
  before every T480 deployment.

## Scope and authority

- Implement only the active formal milestone. Starting another requires an
  explicit human Goal or instruction and satisfaction of its entry gates.
- Live trading is prohibited. Demo execution requires the active plan's
  authority and existing account, risk and execution controls.
- Shared platform transport belongs to `cs-ai-lab-infra`; Forex owns its fixed
  adapter catalogue, schemas, workflows, decisions and evidence. Use the fixed
  T480 adapter; do not bypass it with a generic remote shell or copy operation.
- Preserve unrelated worktree changes. Local commits require explicit human
  instruction, relevant verification and only owned paths; report the hash.
  Do not push, create branches, open pull requests or change formal milestone
  state without Chris's explicit instruction.

## Engineering and evidence rules

- Prefer existing components and the smallest change that fixes an observed MVP
  failure. Add infrastructure or process only when required by the active
  milestone, data integrity, broker safety, reproducibility or explicit acceptance
  criteria. Apply the MVP focus procedure in `docs/agent-workflow.md`.
- Test critical operational assumptions before dependent implementation or
  deployment. Distinguish observed facts from inference; contradictory evidence
  requires reassessment before continuing work based on that explanation.
- Claim success only at the scope verified. A blocker is removed only when its
  original failing acceptance check passes. Code, screenshots, mocks and
  heartbeats alone do not prove the user workflow.
- Preserve raw evidence unchanged and separately from derived results. Never
  fabricate, repair or overwrite it. Material changes require targeted
  re-verification of affected proof; do not invalidate unrelated proof.
- Formal completion requires the declared real-world surface and the review,
  recommendation and approval gates in the registry and `PLANS.md`. Reviewers
  are read-only and cannot approve or close milestones. `target_date` is human
  owned; only approved closeout may create `proven_at`.

## Verification and task handoff

After meaningful changes, run relevant checks, inspect actual outputs and verify
the affected workflow. Record owned paths, acceptance checks, actual results and
remaining limitations in the existing plan or task report.

Use these skills at the indicated boundaries:

- `.codex/skills/research-evidence/SKILL.md` — before plans based on external
  claims, strategy, model, risk, economic-data or product hypotheses.
- `.codex/skills/qa-verification/SKILL.md` — for material changes and before
  reporting implementation, integration, strategy or release work complete.
- `.codex/skills/release-readiness/SKILL.md` — before material deployment,
  autonomous Demo enablement, promotion or formal milestone closeout.

Run focused tests selected from the active plan. Common repository checks:

```bash
git diff --check
python3 scripts/forex_milestones.py validate
python3 scripts/check_execution_continuation.py --work-plan <active-work-json>
```

Before an execution handoff, follow `PLANS.md` and use the current task's work
record for the continuation check; its default is A1, not a task selector.
