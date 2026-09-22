# Deliver the first bounded M30 Demo lifecycle

This ExecPlan is a living document. Maintain it and its execution record,
`docs/plans/m30-demo-mvp-unblocking-work.json`, under `PLANS.md`.

## Purpose / Big Picture

The user-visible outcome is one real EURUSD `GOMarketsMU-Demo` lifecycle from a
fresh decision through broker reconciliation. The listener may record ordinary
`NO_TRADE` decisions while waiting for a natural eligible setup; it must never
force, retry, or manufacture an entry. When an eligible entry occurs, the
existing fixed executor applies its capped volume, broker-side stop-loss and
take-profit, monitoring, mandatory close, audit, and reconciliation.

The critical path is deliberately narrow. It is not an unattended-recovery
programme. The existing single-visible-client deployment is used as observed;
the optional post-install diagnostic and restart/desktop recovery work may be
deferred unless an observed failure makes them necessary for the current Demo
workflow. An oversized operation cannot remain in a candidate that will be
deployed: exclude the unfinished change or repair its transport first.

## Formal milestone dependency map

`project_state.json` records M29 as PROVEN and M30 as the active milestone.
M30's registry contract requires one bounded autonomous `GOMarketsMU-Demo`
EURUSD order, its complete close and broker reconciliation. This plan fits that
contract because it does not change strategy, risk, broker route, account,
symbol, or Demo-only boundary; it executes and evidences the declared surface.

M29's recorded PROVEN state does not establish that every later runtime change
preserves its proof. Its registry policy names changes to the pinned listener
payloads, governed configuration and held worker-handoff recovery surface as
invalidation triggers. Before release readiness, compare the adopted and proposed
changes with the pinned M29 evidence. Mark each affected surface as reusable
with a reason, or requiring targeted reproof under the existing contract. If
the dependency no longer remains valid, M30 release waits for that targeted
revalidation or an explicit human exception through the existing governance
route. This plan does not waive the dependency, alter formal state, or require
repeating unrelated proof merely because a repository revision changed.

M31 is outside scope. It remains blocked until M30 is formally proven through
the registry's required evidence, independent verification and human approval.
The stale M29 labels on `docs/milestones/active-delivery-tasks.json` are a
documentation-alignment defect, not a requirement to reopen M29 or a gate on
this M30 execution plan. Correct them only in a separately reviewed governance
documentation change.

## Scope, authority, and safety boundary

Use only the fixed Forex adapter and existing M30 listener/executor. The
permitted server is `GOMarketsMU-Demo`; `GOMarketsMU-Live` is structurally
prohibited. The only symbol is EURUSD. Preserve the one-position cap, existing
risk state, journal-before-submission rule, no-retry rule, broker-held SL/TP,
monitor, append-only audit, and reconciliation rules.

Chris's active M30 goal authorises the normal fixed Demo workflow, not a forced
trade. This plan does not authorise a risk reset, account switch, strategy or
cap change, generic remote shell, new MT5 interface, Live action, push, or
formal milestone closeout. A local commit still needs explicit instruction.

The current instruction is to update this ExecPlan only. The operational steps
below remain unexecuted; this planning revision does not resume the prior goal,
release a hold, deploy changes or submit an order.

The last reported listener state was installed on the one visible client and
intentionally in `MAINTENANCE_HOLD`; this planning review has not refreshed that
observation. The hold prevents assessments and entries. It is an
operational control to release only after the current release/account/risk
preflight passes; it is not a prerequisite for completing deferred resilience
experiments.

## Progress

<!-- forex-work-projection:start task=M30-DEMO-MVP-UNBLOCKING schema=forex.execution-work-projection.v1 -->
<!-- forex-work-item id=scope-record state=DONE -->
- [x] scope-record — Record the MVP/reliability split and reconcile plan metadata (DONE)
<!-- forex-work-item id=m29-applicability state=DONE -->
- [x] m29-applicability — Assess changed M29 proof surfaces and resolve any required targeted reproof (DONE)
<!-- forex-work-item id=candidate-transport state=DONE -->
- [x] candidate-transport — Select the reviewed adapter candidate and verify its transport envelope before deployment (DONE)
<!-- forex-work-item id=release-readiness state=BLOCKED -->
- [ ] release-readiness — Revalidate the installed Demo release and resolve or block on fresh account, exposure, risk, and protection checks (BLOCKED)
<!-- forex-work-item id=resume-decisions state=PENDING -->
- [ ] resume-decisions — Release the maintenance hold through the fixed operation and retain fresh decision evidence (PENDING)
<!-- forex-work-item id=bounded-lifecycle state=PENDING -->
- [ ] bounded-lifecycle — Retain a natural protected Demo order, mandatory close, and broker reconciliation (PENDING)
<!-- forex-work-item id=independent-verification state=PENDING -->
- [ ] independent-verification — Verify the M30 bundle and obtain required read-only recommendation (PENDING)
<!-- forex-work-projection:end -->

## Plan of work

### 1. Record the critical-path correction

Record the last reported transport, terminal and held listener observations
with their timestamps and retained evidence references; distinguish them from
the fresh runtime checks still required. Reconcile which execution record owns
the remaining Wave 4 work without changing historical evidence or formal state.
Retain the optional diagnostic and wider recovery improvements as follow-up
work, subject to the candidate and proof checks below.

Recorded 2026-09-22: `m30-wave-4-final-proof.md` and its work record remain
the canonical source for natural-lifecycle capture, evidence verification, and
review. This plan coordinates readiness for the current Interactive listener
recovery only. `config/execution-continuation.json` remains bound to the
unrelated H5 harness record and is intentionally unchanged. No formal milestone,
historical evidence, or existing Wave 4 completion record is superseded.

For `m29-applicability`, compare the listener, runner, governed configuration
and Interactive task/disabled-watchdog changes with M29's pinned manifest and
declared held worker-handoff surface. Record the relevant file or payload hash,
change, affected acceptance check and conclusion for each surface. Reuse
unaffected evidence with its rationale. Where a registry invalidation trigger
applies, specify and complete only the affected reproof through the existing
M29 procedure before marking this item DONE. An unresolved applicability
question or unmet dependency keeps release readiness blocked; no plan-only
assertion can restore proof.

Assessment recorded 2026-09-22: the current listener, runner and audit-bridge
payload SHA-256 values differ from all three corresponding values in M29's
retained baseline. The service is also now an Interactive task rather than the
retained held worker-handoff topology. These are explicit M29 invalidators, not
documentation-only differences. M29 therefore cannot be assumed to remain
valid for M30 entry. The required unblock is explicit human authority either
to begin a targeted M29 reproof under its contract or to record an applicable
human exception; this M30-only plan cannot manufacture either.

Exception recorded 2026-09-22: Chris explicitly approved the applicable M29
exception. It permits this M30 plan to continue on the installed Interactive
listener/disabled-watchdog topology, subject to its own fresh release,
account, risk, protection, lifecycle and reconciliation evidence. It does not
claim the retained M29 worker-handoff proof covers that changed topology,
change M29's formal status or evidence, waive any M30 safety control, or
authorise a risk reset, account switch, Live action, forced trade, generic
remote access, push, or formal milestone closeout.

For `candidate-transport`, first decide whether the already deployed, reviewed
release can be used unchanged. A local diagnostic draft does not itself require
redeployment. Select the reviewed adapter revision that will operate it and
preserve unrelated worktree changes. Before any new deployment, apply
`docs/t480-deployment.md`: every fixed non-fragment command in the actual
candidate must encode to fewer than 7,500 characters. A command at or above
that boundary makes the candidate NO-GO. Either exclude/revert the owned
unfinished diagnostic change from the candidate, or repair it with a short
fixed launcher and staged, SHA-256-verified payload, then rerun the transport
regression check. Record candidate revision, relevant source digests, maximum
encoded length and result. Calling the diagnostic deferred is insufficient
while its invalid operation remains in the candidate to be deployed. This
item does not authorise generic SSH/copy or weakening the transport limit.

Assessment recorded 2026-09-22: no new listener deployment is selected. The
installed release is operated unchanged while M29 applicability is resolved.
The locally invoked fixed operations required for readiness/hold release are
below the envelope: install 7,134, status 7,490, prepare 4,142, terminal
identity 7,406, account identity 3,994, and hold release 1,002 characters.
The unfinished post-isolation probe is 9,430 characters and is excluded from
the operating path; it remains a deployment NO-GO until repaired or removed
from a future candidate. Governance validation passed.

### 2. Revalidate the executable state

From `/home/chris/projects/forex`, run the fixed preflight and read-only
listener/account/terminal status operations. Confirm the installed release is
the reviewed bound source, exactly one visible configured terminal is present,
the server is `GOMarketsMU-Demo`, currency is AUD, risk state permits a new
entry, there is no unresolved execution, and any existing exposure has its
required protection and monitor path. Retain raw outputs locally only.

Explicitly check the persistent Option B risk state. The retained Wave 4
observation at 2026-09-17T08:55Z reported an `EXTERNAL_CASH_FLOW` pause which
vetoed an eligible SELL; it is a historical warning, not proof of the current
state. Obtain fresh account balance/equity, current pause reason and the
existing risk evaluator's entry-permission result using the fixed surfaces.
An old assessment, an idle monitor or a resume-request acknowledgement is not
sufficient evidence that risk permits a new entry.

If `EXTERNAL_CASH_FLOW` or another pause persists, reconcile its underlying
account observation and use `m20_listener_resume_risk_policy` only when the
existing governed resume conditions permit it during authorised execution.
Then obtain a fresh risk evaluation showing that entry is allowed and no
applicable limit remains breached. Never delete risk state, reset a balance or
baseline, weaken a cap, or treat the resume request as an override. If current
risk cannot be established, reconciled or permitted, record the exact reason
and unblock condition and leave `release-readiness` BLOCKED with the hold
active. Removing the maintenance hold does not resolve a risk-policy pause.

If exposure, protection, risk, source binding, or account identity is unsafe or
unconfirmed, leave the hold active and repair only that observed blocker. Do
not use an old "flat" observation as proof of current safety.

Readiness observation 2026-09-22T04:46Z: preflight passed and the active
release `a8cb77c771bde649` has a fresh heartbeat in `MAINTENANCE_HOLD`. The
fixed terminal identity found one configured, connected MT5 terminal and a
mapped listener task; terminal capability reports `GOMarketsMU-Demo`/AUD with
all submission permissions true; account identity reports a flat account
(`open_positions: 0`). However, the fixed latest-assessment export failed with
`M20 latest assessment binding is invalid`. That failure means the retained
assessment cannot establish current risk state or entry permission. The hold
remains active. Repair/recreate only the release-bound assessment evidence, then
obtain a fresh valid risk evaluation before this plan can release ordinary
decisions.

Repair candidate recorded 2026-09-22: the circular gate is fixed locally by
adding `m20_listener_held_readiness_assessment`. It runs only while the hold
is present, verifies the active service and runner payload SHA-256 values,
and invokes a runner mode that has no lease, proposal, reservation or
`order_send` path. It reports the existing persistent risk evaluator's
`entry_allowed` result and current EURUSD exposure without releasing the
hold. Focused adapter/service/M30 tests passed; the encoded operation is
3,534 characters. The candidate has not been deployed, so it cannot yet
replace the invalid assessment on T480. Deployment selection and its normal
release procedure remain the next human-authority gate; do not release the
hold from the prior release.

### 3. Resume ordinary M1 decisions

After M29 applicability, candidate transport and all fresh checks in step 2
pass, invoke only the existing fixed operation that
removes the maintenance hold. Verify a fresh listener heartbeat and at least
one new completed-M1 decision record. `NO_TRADE` is a successful ordinary
decision and must continue to the next fresh candle. Capture the release,
configuration fingerprint, decision identity, and no broker mutation for every
`NO_TRADE` result.

If the client disappears, the listener must refuse new work and no replacement
terminal may be launched. Reapply the hold if current monitoring/exit safety
cannot be sustained. This is a runtime safety response, not a reason to create
new recovery infrastructure during this wave.

### 4. Capture the natural protected lifecycle

Wait for an eligible ordinary M1 decision. Do not force a setup or invoke a
submission operation twice after an uncertain result. For an opened position,
retain the persisted proposal, order identity, capped volume, SL/TP confirmation,
monitor observations, close reason/time, complete broker history, costs, and
reconciliation. Run the existing M30 capture and offline verifier only after
inspecting their current prerequisites and arguments.

If a position is open, prioritise the existing monitor and mandatory exit over
all evidence or reliability work. A broker-held stop-loss is additional
protection, not evidence that the required application close/reconciliation
occurred.

### 5. Verify and hand off

Run focused M30/listener/adapter tests, milestone validation, the M30 offline
evidence verifier, and an independent read-only review. Record actual results
in this plan and work record. A verified lifecycle supports M30's formal proof
route but does not itself mark M30 proven; human sign-off and the registry
closeout procedure remain separate.

## Concrete commands and expected observations

Run only after reading each fixed operation's implementation:

    python3 scripts/t480_adapter.py preflight
    python3 scripts/t480_adapter.py execute --operation m20_listener_status
    python3 scripts/t480_adapter.py execute --operation m20_listener_terminal_identity
    python3 scripts/t480_adapter.py execute --operation m20_listener_account_identity

The expected pre-release state is one configured visible terminal, approved
Demo/AUD identity, and a held listener. The exact hold-release, decision,
capture, and verifier commands must be copied from the reviewed current adapter
and M30 capture tooling into this plan before they are run. Do not substitute a
generic SSH command.

After source or plan changes, run:

    python3 -m pytest -q tests/test_t480_adapter.py tests/milestones/test_m20_listener_service.py tests/milestones/test_m30.py
    python3 scripts/forex_milestones.py validate
    python3 scripts/check_execution_continuation.py --work-plan docs/plans/m30-demo-mvp-unblocking-work.json
    git diff --check

## Idempotence, rollback, and stop conditions

Read-only checks may be repeated. Do not repeat an order submission with an
uncertain remote result; reconcile it first. If release or account binding is
wrong, risk is paused, protection is absent, the client is unavailable, or the
listener cannot monitor an open position, keep or restore the maintenance hold
through the existing governed control and stop new entries. Preserve raw
evidence, risk state, broker history, and the existing client; do not delete
terminal profiles or launch a replacement terminal.

An unresolved M29 applicability/reproof requirement blocks M30 release. An
oversized fixed command blocks deployment of that candidate until excluded or
repaired and verified; it does not justify an unrelated redeployment or a new
hold solely for optional diagnostic work. A still-breached risk limit remains
a release blocker even after an operator resume request.

## Surprises & Discoveries

- Observation: the previous rollout treated a staged post-install diagnostic
  and unattended recovery evidence as an entry gate. The active M30 contract
  instead requires a bounded natural Demo lifecycle and reconciliation.
- Observation: the T480 encoded-command ceiling is 7,500 characters. The
  strengthened post-install diagnostic currently exceeds it and must fail
  closed. Its feature may be deferred, but a candidate containing an oversized
  fixed operation cannot be deployed.
- Historical observation: the Wave 4 plan records `EXTERNAL_CASH_FLOW` vetoing
  an eligible entry. Fresh risk-state resolution or an explicit blocker is
  required before hold release; current risk readiness is unverified.

## Decision Log

- Decision: make the bounded M30 Demo lifecycle the critical path and move
  transport/restart resilience to follow-up work. Rationale: those controls
  improve reliability but are not a declared prerequisite for the smallest
  protected M30 Demo proof. Date/Author: 2026-09-22 / Chris direction.
- Decision: retain the maintenance hold until a fresh executable-state
  preflight passes, then release it through the fixed operation only. Rationale:
  the correction removes unnecessary gates, not account/risk/protection checks.
  Date/Author: 2026-09-22 / Codex.
- Decision: require explicit M29 applicability, candidate transport and fresh
  risk checks before release. Reuse unaffected proof, exclude or repair an
  invalid deployment candidate, and resolve or block on a current risk pause.
  Rationale: the review identified these existing contract requirements as
  missing from the proposed shortcut. Date/Author: 2026-09-22 / Astra review.

## Outcomes & Retrospective

Planning revision only; no execution or fresh runtime observation occurred.
The last reported listener state was installed and held. This plan is complete
only when its evidence and verification results are recorded; formal M30
completion remains a separate human-approved registry action.
