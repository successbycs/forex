# Demo income waves: execution guide

Status: **PROPOSED — documentation only; execution has not been authorised by
the request to create these documents.** Prepared 2026-09-07.

The mission is to determine whether the system can deliver sustainable net
returns within explicit capital-risk limits and with low operator effort.
Future agentic live operation requires separate authorisation. These waves
establish Demo reliability and economic evidence; they do not promise income.

## Execute one wave at a time

| Wave | Original activities | Intended result | Prompt |
| --- | --- | --- | --- |
| 1 | 1–4, with proposed W1.R remediation | Trustworthy broker state, net accounting, persistent risk boundaries and recovery | [Wave 1](demo-income-wave-1.md); [W1.R work package](demo-income-wave-1-recovery-work-package.md) |
| 2 | 5–6 | Honest eligibility checks and matching replay/deployed decisions | [Wave 2](demo-income-wave-2.md) |
| 3 | 7–9 | A frozen economic experiment, measured operator effort, and verified findings | [Wave 3](demo-income-wave-3.md) |

Each wave file contains its activity specification and a fenced, copy-and-paste
goal prompt. The short prompt instructs the executing agent to read the full
wave file and this guide; it does not depend on remembering this conversation.
Run it from this repository's workspace. A wave is an execution grouping, not
a new milestone or an amendment to the registry.

The proposed **W1.R** schedule is: R1 diagnose; R2/R3 correct recovery and
unknown-exposure handling; R4 coordinate maintenance and deploy with R6 incident
recording; R5 demonstrate continuity/recovery and R6 alerts; R7 finish the
original W1.1–W1.4 evidence. Shared T480 work remains an explicit dependency
owned by `cs-ai-lab-infra`, whose own recovery Wave 1 is a different workstream.
Packaging W1.R does not authorise execution, host maintenance or a new milestone.
Wave 3 reuses valid technical recovery evidence and adds its longer operational
and economic assessment.

Before starting, select the model and reasoning setting in the client. The
usage-conscious recommendation is GPT-5.6 Terra, High reasoning, Standard speed
for implementation, with GPT-6 Astra reserved for difficult risk/reconciliation
analysis or required critical review. These are recommendations, not automatic
model changes or claims of account availability.

If desired, explicitly set a token budget for that wave in the supported goal
controls or your execution instruction. No numerical budget is pre-authorised
by these documents. A goal budget is not a guaranteed percentage of the Pro
allowance. Check the usage display before extending a run. See the official
[usage guidance](https://learn.chatgpt.com/docs/pricing) and
[Goal guidance](https://learn.chatgpt.com/docs/long-running-work).

Do not launch the next wave automatically. A fresh execution instruction is
required. Finish with a concise handover so later work reads the findings and
changed files rather than repeating the whole repository review.

## Shared execution contract

Every wave prompt incorporates the following requirements:

1. Inspect Git status and preserve unrelated work. Read applicable AGENTS.md,
   `project_state.json`, the active contract in `milestone_registry.json`,
   `docs/evidence_and_milestones.md`, this guide, and the selected wave file.
   Re-check previous findings against current code and evidence.
2. Work only within the active approved milestone. At preparation, this is
   M20 and its implementation status is `NEEDS_FIX`. Re-read at execution time.
   If M20 is no longer active, reassess scope with the operator. These goals
   explicitly do not authorise starting a later milestone.
3. Map each proposed change to the active contract. For changes outside it,
   prepare an exact contract amendment and obtain explicit human approval
   before dependent implementation. Continue independent authorised work.
   Do not infer approval from this document, elapsed time, or a review result.
4. Permit orders only on `GOMarketsMU-Demo`, EURUSD, under approved limits and
   the existing fixed adapter. Do not access or enable `GOMarketsMU-Live`.
   Retain one-position, persisted-proposal, idempotency, and broker-protection
   boundaries unless an explicitly approved contract changes a relevant rule.
5. No commits, pushes, branches, or PRs without explicit human instruction.
   Prepare deployment and rollback details before deployment. If a real-world
   proof requires a clean committed release that is not yet authorised, report
   the exact remaining action; do not invent revision provenance or bypass it.
6. Keep changeable non-secret settings in canonical configuration. Keep secrets
   and machine-local values in ignored local files. Reuse shared infrastructure;
   shared transport remains owned by `cs-ai-lab-infra`.
7. Unknown broker state, unreconciled exposure, required stale/unavailable data,
   disabled authority, and breached risk limits must block new entries.
   Preserve protective management of existing positions. Do not introduce
   martingale, loss-chasing, automatic risk escalation, self-modifying trading
   rules, or AI bypasses of deterministic execution controls.
8. Distinguish implementation, automated tests, fault injection, real-world
   proof, economic findings, and production readiness. Simulations are useful
   engineering evidence but cannot replace the declared real-world surface.
9. Preserve raw evidence unchanged and separately from verification. Bind it
   to the contract, release/revision, configuration, verifier, timestamps, and
   exact surface. Recapture affected proof after material changes; retained
   historical evidence remains historical. Independent verification must not
   regenerate missing observations or contact the broker to repair a bundle.
10. Preserve required reviews. Milestone closeout requires a current bound
    Triad-plus-domain `RECOMMEND_COMPLETE` and every other active contract gate.
    Review roles are read-only and cannot approve or close milestones. Only
    the closeout command may generate `proven_at`; leave `target_date` human-owned.

## Operator decisions: do not invent these

Check existing explicit decisions first. Propose concrete options for missing
values and request only the decisions needed for dependent work.

| Decision | Needed before |
| --- | --- |
| Reporting currency and evaluation capital basis, including treatment of deposits/withdrawals | Equity-relative risk and economic reporting |
| Per-trade risk, exposure/leverage caps, daily/weekly loss limits, peak-equity drawdown limit, and reset rules | Changing the risk policy |
| Loss-budget timezone, inclusion of unrealised losses/costs, pause/resume authority | Persistent risk implementation |
| Permitted trading sessions, event exclusions, stale-source policy, cost assumptions | New eligibility rules |
| Recurring cost allocation, operator-time budget, treatment of tax and development costs | Net operator benefit reporting |
| Candidate selection, frozen rules, observation window, sample/coverage requirements, statistical decision criteria | Economic experiment start |
| Maintenance window, drill constraints, and unattended observation conditions | Disruptive Demo drills or extended trial |

Small returns and stop orders do not establish low risk. Record loss limits as
controls and planned risk, not guarantees against gaps or slippage. An income
aspiration must never become an order quota or sizing input.

## Cost and evaluation definitions

- **Broker net trading P&L:** reconcile actual fills and all attributable broker
  commission, fees, and financing/swap. Identify any charges posted separately
  from deal rows. Exclude deposits, withdrawals, and unrelated adjustments.
- **Execution-cost estimates:** retain spread/slippage estimates and their
  reference prices separately. Actual fill-to-fill P&L already reflects execution
  prices; do not subtract the same spread/slippage again.
- **Net operator benefit:** broker net trading P&L less attributable recurring
  infrastructure, data, AI, and relevant conversion costs not already included.
  State allocations and missing inputs. Record operator minutes separately.
- **Tax and development costs:** state inclusion/exclusion explicitly. Do not
  claim after-tax income or "all costs included" if material values are unknown.
- **Economic result:** report net expectancy in initial-risk units, drawdown,
  losing streaks, trade count, exposure, exit reasons, costs, uncertainty, and
  selection effects. Predeclare decision rules and retain failed experiments.
  Demo fills do not establish equivalent live execution economics.

## Usage controls and stopping

Use targeted reads, compact command output, a single primary implementation
thread, focused tests during edits, and required broader checks at completion.
Do not repeatedly review unchanged code or rebuild working infrastructure.
Use the repository's required review workflow; do not spawn extra agent teams
merely to accelerate the wave.

Save a handover before a budget boundary. A budget limit does not make work
complete and does not waive testing or proof. Do not silently expand scope,
increase the budget, or continue into the next wave.

Do not spend repeated AI turns polling for a market event or enough trades.
Use approved ordinary service/scheduler collection where available. Report
pending proof and the exact resumption condition so the operator can pause the
goal and resume after observations exist. The operating service may continue
only within its own existing authority; pausing AI work must not disable position
protection. Never mark an unfinished goal or milestone complete to stop waiting.

## Required activity record and handover

For every activity, record the observed problem with source references, exact
changes, mission value, dependencies/exclusions, measurable acceptance criteria,
real-world test and safety/rollback arrangements, raw evidence, independent
verification, and failure/inconclusive conditions.

Create or update one concise report for the wave in `docs/milestones/` when
executing. Link sensitive raw evidence by its retained location rather than
copying it into tracked documentation. Record implementation and test results
separately from proof status and economic findings. A documentation report is
not itself real-world proof.

Use per-criterion PASS/FAIL/PENDING and explain any BLOCKED dependency. Reserve
SUPPORTED/REJECTED/INCONCLUSIVE for the predeclared economic assessment. Include
remaining operator decisions, proof invalidations, and exact next actions.
