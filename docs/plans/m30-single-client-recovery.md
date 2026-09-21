# Recover the M30 listener using one managed visible Demo client

This living ExecPlan follows `PLANS.md`. Its execution record is
`docs/plans/m30-single-client-recovery-work.json`. Update both together;
the JSON owns task states and the Progress block is its exact projection.

## Purpose / Big Picture

Make the existing EURUSD M1 listener operate through one identified, visible
GOMarketsMU-Demo client on T480. Chris manages client availability. The listener
must report unavailable when that client is absent, recover when it returns, and
never silently select or launch a replacement terminal. These are acceptance
requirements, not established capabilities. Prove the connection and disappearance
behaviour before adopting this runtime design.

The MVP failure is an unresolved mismatch between visible Algo Trading settings
and the listener's reported submission permission, compounded by unproven runtime
ownership. The smallest candidate change is to the existing connection and task
configuration. Additional MCP integration, schedulers and services are deferred.

## Formal milestone dependency map

The repository state identifies M29 as PROVEN, M30 as active and M31 as next.
M30 directly depends on M29 and requires a natural, bounded autonomous Demo
entry, protected management, mandatory close and full reconciliation. A diagnostic
order cannot substitute for that surface. Reuse the accepted historical M29
evidence under its registry policy; assess affected proof if runtime changes.
Do not silently waive an entry condition or mark unrelated proof invalid.

This plan supports M30's execution surface. No later milestone or new contract is
started. M31 remains outside scope until explicitly authorised and its entry
gates pass. A client outage cannot waive M30's position protection or mandatory
exit requirements. If the proposed operating agreement cannot meet those
requirements, report that conflict before executable deployment.

## Scope, authority and owned paths

Planning owns this file and its work JSON. Candidate implementation paths are
`t480/m20_demo_listener_service.py`, `t480/m20_demo_trading_session.py`,
`scripts/t480_adapter.py`, `t480/command-catalog.json`,
`tests/milestones/test_m20_listener_service.py`, `tests/test_t480_adapter.py`
and `tests/milestones/test_m30.py`. The bounded feasibility probe also owns
`tests/test_m30_single_client_probe.py` and `t480/m30_single_client_probe.py`.
Update `docs/architecture.md`,
`docs/t480-deployment.md` and `docs/workflows/m1-demo-decision-workflow.md`
only for the operating behaviour actually adopted. Narrow these paths after
discovery; document additions before editing.

Preserve unrelated dirty files, the existing audit journal, leases, risk state,
broker protections and raw evidence. No Live, strategy change, risk reset,
account switching, new broker interface, or generic remote shell is included.
Use prior user authority where applicable; the plan itself grants no authority.
Commits require explicit human instruction. Execution under Chris's active goal
may use the fixed observation, hold and scoped recovery operations described
below. It does not authorize Live orders, terminal closure without the declared
flatness and coordination checks, or formal milestone closeout.

## Context and evidence brief

Decision: can the existing Python listener reliably use only Chris's managed
visible client without adding another terminal or execution service?

Hypothesis: an observation-only worker in the intended interactive context
connects to the approved Demo client, observes its permissions, refuses while
the client is absent, and reconnects to that same approved identity on reopening.
Any replacement launch, ambiguous connection or wrong account fails the hypothesis.

Context: EURUSD, completed M1 candles, GOMarketsMU-Demo, AUD account; observations
use UTC with optional Pacific/Auckland display. This is runtime research on
20 September 2026, not a strategy or profitability study. Existing cost, sizing,
freshness and trading rules remain authoritative.

Evidence reviewed:
- Local source at f73a0c1 plus the preserved dirty documentation: the service,
  adapter and recovery paths contain MT5 initialization and S4U task creation
  or validation. S4U is the current task logon mode used for background execution.
  This is code evidence, not proof of every installed task setting.
- Earlier retained diagnostic deployment:
  `runs/local/m30-binding-deploy-A2HgHXrc/`, referenced by
  `docs/plans/m30-terminal-binding-recovery.md`. It recorded MAPPED listener
  telemetry and false terminal submission permission, not successful trading.
- MetaQuotes initialize reference, publication date unspecified, accessed
  2026-09-20: https://www.mql5.com/en/docs/python_metatrader5/mt5initialize_py .
  It documents that initialize may launch a terminal. Its documented arguments
  do not establish an attach-only or PID-binding guarantee.

Evidence-supported, high confidence: executable-path matching is insufficient
to prove process ownership; the API can launch a terminal; prior diagnostic
success did not establish trading capability.

Reasonable inference: a worker sharing the intended desktop session may simplify
client selection. Actual attachment, saved settings and profile identity remain
unproven.

Assumptions to test: same-client ownership, external API permission, absence
refusal and reconnection. Measure the account/profile identities, process
creation and connection observations in each state. Recheck identity at broker
use, not only startup. A process-exists check followed by initialize has a race
if the client closes between the two calls; do not call that a no-launch guarantee.

Rejected claims: green UI implies listener permission; two sessions prove two
data profiles; heartbeat implies fresh strategy processing; MCP necessarily
exposes the required diagnostic fields; idle monitoring proves flat exposure.

Risks to validity: stale quotes, stale account reads, changing PIDs, concurrent
watchdog restarts and mock APIs that differ from MT5. No market-performance
conclusions are drawn, and this does not alter lookahead or execution-cost rules.
Recommendation: run the bounded connection and closure research spike first.
Its result is the decision gate for implementation, not a promise of feasibility.

## Progress

<!-- forex-work-projection:start task=M30-SINGLE-CLIENT-RECOVERY schema=forex.execution-work-projection.v1 -->
<!-- forex-work-item id=baseline state=DONE -->
- [x] baseline — Establish current task and terminal ownership (DONE)
<!-- forex-work-item id=connection-probe state=IN_REVIEW -->
- [ ] connection-probe — Prove connection to the managed visible Demo client (IN_REVIEW)
<!-- forex-work-item id=closure-recovery state=PENDING -->
- [ ] closure-recovery — Prove client closure and reopening behaviour (PENDING)
<!-- forex-work-item id=implementation-review state=PENDING -->
- [ ] implementation-review — Implement the demonstrated setup and independently review it (PENDING)
<!-- forex-work-item id=deployment state=PENDING -->
- [ ] deployment — Deploy and verify the single-client setup (PENDING)
<!-- forex-work-item id=demo-round-trip state=PENDING -->
- [ ] demo-round-trip — Verify fresh processing and the protected Demo round trip (PENDING)
<!-- forex-work-item id=natural-lifecycle state=PENDING -->
- [ ] natural-lifecycle — Capture and verify the natural M30 Demo lifecycle (PENDING)
<!-- forex-work-projection:end -->

## Plan of work and acceptance

### 1. Establish current ownership

Inspect task principals, actions, triggers, watchdogs, recovery launchers and all
relevant initialize callers. Start with the existing fixed identity and diagnostic
operations; do not invoke SSH-side initialization to establish listener ownership.
Record installation, account/profile and PID/session observations separately.
Refresh positions, pending orders and unresolved executions through an approved,
attributable path before disrupting any runtime. Old flatness is not current
flatness. Finish when the runtime map and exact next probe are inspectable;
unknown attachment must stay explicit.

### 2. Prove the candidate connection

Define the smallest observation-only probe using the existing worker and fixed
adapter. It must be unable to submit orders, and run in the actual intended
interactive context. Prevent competing new entries during the controlled test
using the existing maintenance hold, while preserving monitoring for any exposure.
The initial non-mutating connection observation may coexist with monitoring;
it makes no exclusivity or connection-ownership claim. Terminal closure,
isolation and production migration require the stronger flatness and worker
coordination checks in step 3.
Inspect and review probe bytes and safety before staging; use release-readiness
for any material diagnostic deployment. Record exact fixed commands here before
running them; do not invent a generic launch workaround.

Observe the approved Demo account and client profile, attributable connection,
permissions and process inventory. No wrong-client fallback or newly launched
terminal is acceptable. Record a bounded timeout. If ownership or attach-only
behaviour cannot be established, stop dependent migration and report the measured
limitation and smallest alternative for review.

### 3. Prove closure and recovery

With submission disabled and fresh evidence of flat exposure, no pending orders
and no unresolved execution, close only the identified client through the scoped
test procedure. Observe at least two connection-check cycles: unavailable,
no order attempt and no replacement terminal. Reopen the intended client and
observe at least two cycles of correct account/profile connection and permissions.
Also test the close-during-connect race; a single orderly close is insufficient
to establish a no-launch guarantee. Stop on unexpected process creation.

Record what disconnect, logoff and reboot mean in the operating agreement.
Only claim resilience for events tested. Client absence removes application
monitoring and scheduled exit capability; broker-held stops are not equivalent.
Document prevention and response for outages while exposed before enabling entries.

### 4. Implement and independently review

Adopt only the proven mechanism. Update the listener, monitor, diagnostic and
recovery callers consistently; a watchdog must not recreate the former background
topology. Preserve bounded execution, deduplication and audit/reconciliation.
Do not introduce a new broker API to work around failed attachment evidence.

Run focused tests for wrong account/profile, absent client, ambiguous clients,
lost connection, no unintended launch, recovery and unchanged trading controls.
An independent reviewer must inspect source, actual runtime evidence and remaining
limitations; record findings, repairs and reviewed hashes before completing this
item. Local tests cannot replace the probe.

### 5. Deploy the demonstrated setup

Use release-readiness and the fixed deployment process. Validate fully encoded
commands below 7,500 characters, stage reviewed fragments, verify hashes and bind
the release to committed source. Preserve the previous release and task definitions.
Refresh safety checks, switch the existing task, and retire only the positively
identified redundant task/terminal after proving it is unused and flat. Do not
delete installation or profile data. Verify one intended client, expected listener
context, advancing heartbeat and account/profile binding on the installed release.
Repeat the closure/reopening acceptance on that release under the same controls.

### 6. Verify fresh processing and the diagnostic round trip

When fresh broker inputs are available, observe successive completed M1 candle
decisions and their persisted records. Retained old quotes or heartbeat alone
do not pass. Resolve any remaining permission or risk refusal through its existing
approved procedure; do not reset a latch to make the test pass.

Use only the existing authorised M30 fixed diagnostic drill, with its exact
broker-path lock, minimum bounded Demo volume, required protection, close and
broker-history reconciliation. Reread `docs/plans/m30-demo-execution-drill.md`
and its current prerequisites before invocation. Retain source/configuration
binding, order and close identifiers and actual broker costs. This completes
a diagnostic round trip only.

### 7. Capture the natural M30 lifecycle

Continue ordinary eligible fresh-candle evaluation. Valid NO_TRADE outcomes are
normal; do not force or replay a signal. Capture a natural protected entry,
mandatory close and full reconciliation on the final deployed version using
`scripts/capture_m30_natural_lifecycle_evidence.sh` and the existing verifier,
after inspecting their current arguments and prerequisites. Record the registry
acceptance results and independent recommendation/review requirements. Formal
closeout is a separate authorised action, never implied by this work record.

## Concrete steps and verification

Work from `/home/chris/projects/forex`. Initial observations use:

    python3 scripts/t480_adapter.py execute --operation m20_listener_terminal_identity
    python3 scripts/t480_adapter.py execute --operation m20_listener_status

Select additional diagnostics from the fixed catalogue after inspecting their
implementation; some account readers can initialize MT5 and are not passive
process inventory. Record all runtime outputs unchanged in a new directory under
`runs/local/m30-single-client-recovery/` with timestamps and SHA-256 hashes.
Keep derived conclusions separate. Do not retain credentials.

After code changes, run the relevant subset of:

    python3 -m pytest -o addopts='' -q tests/test_t480_adapter.py tests/milestones/test_m20_listener_service.py tests/milestones/test_m30.py
    python3 scripts/forex_milestones.py validate
    git diff --check

Check progress consistency and next work using:

    python3 scripts/check_execution_continuation.py --work-plan docs/plans/m30-single-client-recovery-work.json

CONTINUE identifies actionable pending work; it is not evidence the work ran.
BLOCKED requires a concrete observed constraint and unblock action. Never use
the completed terminal-binding repair record to claim this recovery is complete.

## Idempotence, rollback and stop conditions

Before each remote change inspect current state and retain exact prior settings.
Do not repeat a broker submission on an uncertain response. Use existing history
and reconciliation to resolve it. Rollback restores reviewed source and task
settings; it must not unexpectedly resume entries or recreate a topology already
found unsafe. Preserve any pre-existing hold, and establish current exposure
before stop/restart or terminal closure.

Stop dependent work on ambiguous ownership, unexpected terminal launch, missing
protection, unresolved broker state, failed durable audit or failed release binding.
Continue independent authorised investigation. A missing probe is implementation
work; fresh-market evidence may await quotes without blocking local repairs.

## Decision Log

2026-09-20: Chris selected one managed visible client and asked for this plan and
tracking. Keep the completed diagnostic repair historical. Use existing tracking
and evidence paths, with no new service or tracker.
2026-09-20: Source inspection and primary API documentation require testing
initialize auto-launch and all recovery callers before adopting the new design.

2026-09-20: The Session0 topology was safely isolated, but the child-process
restriction prevents MT5 initialization and an unrestricted attach-only attempt
times out. Keep the former listener and watchdog disabled under maintenance hold.
Do not call either result an attachment proof. The next smallest diagnostic is a
human-visible MT5 client restart, followed by the same bounded attach-only probe;
this tests whether the changed external-Python setting needs a client restart.

2026-09-21: A reported recovery of T480 access conflicts with three fresh fixed
read-only SSH observations from the repository host, all timing out before remote
execution. Retain the raw observations and resume the attachment probe only once
a fixed read-only operation actually reaches T480.

## Surprises & Discoveries

2026-09-20 execution baseline: three fresh fixed observations are retained under
`runs/local/m30-single-client-recovery/baseline-20260920T094717Z/`. The task is
S4U, the listener worker is in Session 0, and terminals exist in Sessions 0 and 2.
Permission remains false. The unchanged quote establishes no fresh processing.
The fixed watchdog status also reports an S4U task that invokes the listener.
Connection ownership is still not established by these process observations.

2026-09-20 10:03Z: with an acknowledged maintenance hold, a one-shot scheduled
task ran in Session 2, the sole interactive configured-terminal session. Its
hash-bound probe first enforced Windows child-process restriction (the canary
was blocked), then made a read-only MT5 observation. It found the approved
Demo/AUD account, zero positions and zero pending orders; its before/after
inventories were identical. It also found `terminal_trade_allowed=false`.
The result deliberately records `attribution=UNVERIFIED`: Session 0 still has
the same-installation terminal, so the API cannot be honestly attributed to a
specific terminal PID. The maintained hold remains active.

Independent source review identified Windows child-process restriction as a
candidate to test in an isolated observation-only worker. The initial fixed
operation `m30_child_process_policy_probe` tests whether this Windows host can
set/read back that restriction and block a harmless Python child; it never
imports MT5. Its compiled payload and encoded transport test pass locally.
No terminal or task mutation is part of that operation.

The current trading runner's `_bridge` launches `wsl.exe` for required audit and
reconciliation. A permanent child-process ban on that runner would break the
workflow. A successful isolated restriction probe therefore cannot justify
adoption without a compatible, reviewed bridge path. SetProcessMitigationPolicy
support and MT5 compatibility are unverified. Primary source accessed 2026-09-20:
https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/ntddk/ns-ntddk-_process_mitigation_child_process_policy
(updated 2024-02-22). It documents process-local child creation prohibition, not
MT5 compatibility or protection against every delegated launch mechanism.

A task-mode change alone cannot prove attach-only behaviour. Existing service
recovery code explicitly expects or recreates S4U tasks, and several reader paths
initialize MT5. These must be included in the discovery boundary.

2026-09-20 10:34Z: the production runner candidate can retain its audit path
without weakening no-launch isolation. A staged-but-uninstalled runner started
one existing WSL audit bridge before applying the irreversible Windows
child-process restriction; it then completed two fixed read-only audit calls.
The interactive task returned FOREX_M30_AUDIT_ISOLATION_SPIKE_OK with zero
open positions on both reads and no MT5 call. The first task command was rejected
by T480's length limit before Windows execution; a two-fragment, hash-verified
launcher reduced the final fixed command to 6,202 encoded characters. This
proves bridge compatibility only. It does not prove that the runner attaches to
the visible terminal or that WSL cleanup survives abnormal process termination.

## Outcomes & Retrospective

Fresh baseline observations and independent source review are recorded. The
isolated Windows policy probe passed on T480: policy flags 1 read back and
child creation failed with the specific Windows error 367. Raw result is
`child-policy-probe.json` in the baseline directory. No MT5 call occurred.
The observation-only interactive MT5 probe was independently reviewed, staged
as eight raw Base64 fragments and hash-verified on T480. Its first remote
observation completed with no broker mutation. It proves neither PID ownership
nor closure/recovery; production migration and Demo execution remain unverified.

The staged runner/audit compatibility spike also passed on T480. It made two
fixed load-open-positions calls after the runner had verified child-process
restriction, returning zero positions in both results. No MT5 method, order,
or broker mutation occurred. The next acceptance test is the runner's own
restricted MT5 read in the interactive session, followed by controlled
Session-0 isolation and closure/reopen observations.

2026-09-20 10:59Z--11:07Z: the required Session0 and durable-state preflight
now has fresh evidence. A hash-bound S4U Session0 observation retained result
`sha256:cdc7f793c6ad810d7b46eb4fb3c3d4f3a2b8af2a3a4f4dd6fea9805ed33e3a21`:
the approved hashed Demo account scope, zero positions, zero pending orders,
verified child restriction, and unchanged inventory (Session0 PID 15056 and
interactive Session2 PID 6440). It records
`SESSION_SCOPED_NOT_PID_BOUND`; this is account/exposure attribution within
the process session, not a false native PID-binding claim. A separate restricted
bridge read returned `FOREX_M30_PRE_ISOLATION_READINESS` with zero durable
open positions and zero unresolved execution attempts. At capture the listener
was in a fresh acknowledged hold, `monitor=IDLE`, and no assessment was in
flight. The first readiness invocation safely failed because its new command
had not been included in the runner's fixed allow-list. The allow-list repair
and tests were completed before hash-bound restaging and the passing second
invocation. No order, terminal closure, or listener installation occurred.

The next operation remains guarded Session0 isolation. It must preserve both
task definitions/enabled states; validate their exact actions/principals;
recheck the held, idle status, account/exposure and durable state immediately
before action; disable watchdog then listener; confirm their cessation; and
stop only the positively identified Session0 configured-terminal PID with its
creation time unchanged. It must retain the hold on every result, leave the
visible Session2 terminal unchanged, and report fail-closed partial completion.
Independent review is required before executing that destructive operation.

The interactive probe uses eight fixed raw Base64 staging fragments, an
assemble/hash verification, one fixed Interactive task and a read-only result
operation. Task ownership must match the one visible configured-terminal
candidate. The task has no trigger and a one-minute execution bound; existing
listener/watchdog tasks are untouched. Each result is an immutable UUID-named
JSON file in its hash-named diagnostic directory. It does not claim PID
attribution from installation matching.

2026-09-20 11:29Z--11:41Z: the reviewed isolation task completed successfully.
It snapshotted both original task definitions, disabled and stopped the S4U
watchdog and listener, and stopped only Session0 terminal PID 15056. Its retained
before/after inventory shows only the existing visible Session2 PID 6440 after
the action. Independent fixed postflight reads report both former tasks Disabled,
maintenance hold present, no Forex listener Python process, and exactly that one
configured terminal. No broker mutation occurred.

2026-09-21 05:57Z: the first post-report access check did not reach T480. The
fixed `m20_listener_status`, `m20_listener_terminal_identity`, and
`m20_listener_terminal_capability` operations each returned an SSH connection
timeout after about 10.5--10.8 seconds. The exact receipts are retained in
`runs/local/m30-single-client-recovery/t480-access-20260921T055701Z/`; they
show transport unavailability from this host, not terminal state.

The stronger connection criterion remains open. A post-isolation observation
with Windows child creation prohibited completed but reported
`INITIALIZE_FAILED`; the inventory stayed at the single visible client. The
corresponding restricted runner task failed without a result. An attach-only
variant that relaxed the process policy, while retaining pre/post terminal
inventory comparison, ran until its fixed one-minute task limit and was stopped
without an observation record. Postflight still showed only PID 6440 and no
worker. Therefore there was no replacement terminal, but there is not yet
evidence that the MT5 Python API can attach to that client. Restart the visible
MT5 client once, leave Algo Trading and external Python API permitted, and rerun
the exact bounded attach-only observation before attempting client closure.

After review, execute `m30_single_client_probe_stage_1` through
`m30_single_client_probe_stage_8`, `m30_single_client_probe_verify`, then
`m30_single_client_probe_run` through the fixed adapter. Poll
`m30_single_client_probe_status` for the exact one-shot task and retained result.
Require a nonzero interactive session, verified child restriction, correct Demo
account/profile, unchanged process inventory and reported permission. This
observation cannot close the full connection-ownership criterion while a second
same-installation terminal exists. No order path is present in the probe.

Revision note, 2026-09-20: created the recovery plan and dependency tracker with
an embedded evidence brief; acceptance tests precede dependent implementation.
