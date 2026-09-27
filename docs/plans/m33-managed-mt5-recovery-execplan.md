# Build the held M33 managed-MT5 recovery primitive

This ExecPlan is a living document and must be maintained under `PLANS.md`.
It is an implementation plan within formal milestone M33, not authority to
release maintenance hold, enable Demo entry, place an order, or close M33. Its companion work record is
`docs/plans/m33-managed-mt5-recovery-work.json`.

## Purpose / Big Picture

M33 currently recovers a stopped listener safely while the Demo account is held
and no orders can be submitted. The remaining M33-C7 gap is managed MT5: if
the single approved Session 0 terminal is missing, or if a flat account has
duplicate *attributable* managed terminals, the guardian must be able to make
one fixed recovery effect and prove its result. After this work, a reviewer can
inspect a hash-bound Forex-owned operation that either starts the exact
configured Session 0 MT5 task or removes only attributable duplicates. It must
remain impossible for this path to trade, release the hold, alter risk, target
Live, or terminate an unknown client.

## Formal milestone dependency map

M32 is the proven Demo baseline and remains reusable. M33 is the active formal
milestone, currently `NEEDS_FIX`; its M33-C7 safety criterion requires bounded
recovery of missing managed components and flat-only duplicate cleanup with
exact ownership and post-action reconciliation. M33-C5 and M33-C6 already
have no-order evidence, while the listener-only portion of M33-C7 has a held
recovery receipt. M33-C7 is still incomplete because MT5 absence and duplicate
recovery are unsupported. M33-C8 (final fault/reboot/soak/lifecycle proof) is
blocked until M33-C7 is implemented, independently reviewed, and proven.

The plan fits M33-C7: it adds only fixed T480-local no-order recovery and
evidence controls for the permitted `GOMarketsMU-Demo` / AUD / EURUSD scope.
It does not start another formal milestone. The shared `cs-ai-lab-infra`
repository remains the owner of the transport core. Forex owns the operation
catalogue, policy, evidence and fixed command payloads, as confirmed by
`AGENTS.md` and `config/t480.json`. The old proposal that this primitive must
be shared-owner supplied is a record of an earlier rejected design assumption;
this plan does not treat the local design as approved until its independent
review passes. Project state still records M33's work packages as in
progress/planned. The existing observational receipts are reusable evidence,
not formal C5, C6 or C7 completion claims.

## Scope and authority

Chris subsequently authorised local implementation, verification, the governed
fingerprint refresh preserving M32, fixed staging preparation, and independent
review. Those approvals do not authorize a held MT5 process effect. No task
execution, MT5 start, duplicate termination, fault drill, reboot, hold release,
entry authority, order activity, commit, push, or formal milestone transition
is authorised by this document alone. A later, separate operator approval must
explicitly permit one fixed held M33 MT5 recovery drill and say that it must keep
`entry_eligible: false`, retain the maintenance hold, create no order authority,
and place no orders.

The existing `m20_close_duplicate_terminal` operation is evidence that a
Forex-owned fixed process effect is transport-feasible. It is not reusable as
the new recovery operation because it has no M33 v2 request/ledger binding,
shared mutex, pending/unresolved-work checks, immutable Session 0 startup
binding, or mandatory reconciliation receipt.

## Design

Add `t480/trading_health_managed_mt5_recovery.py`. It must not extend the
listener-only recovery v2 contract in place: current v2 schemas and executor
hard-code `RECOVERING_LISTENER` and listener action names. Add a parallel,
explicitly versioned MT5 request, ledger and receipt contract instead, with
actions exactly matching the existing policy vocabulary: `START_ONE_MT5` and
`RECYCLE_MANAGED_SET_FLAT`. Listener v2 requests and receipts remain valid and
unchanged. The new MT5 contract binds a static task definition digest,
immutable terminal configuration digest and current inventory digest.

Add one durable cross-protocol recovery coordinator record, protected by the
same recovery mutex and written atomically. It carries a common recovery epoch,
protocol name, request identity, generation, boot/release/fingerprint binding
and terminal state. Before either listener-v2 or MT5-vNext publishes, claims,
executes or reconciles a request, it must read this coordinator and both
ledgers. Any valid nonterminal request in the other protocol, a stale/corrupt
coordinator, or a changed epoch/binding makes the new action
`INTERVENTION_REQUIRED`. The coordinator is the single durable lease: the mutex
prevents simultaneous file changes, while the lease prevents two protocols from
remaining active between calls. Existing listener v2 receipt shape remains
unchanged; its guardian/executor integration is extended only to consult this
coordinator.

Create a fixed read-only MT5 inventory/preflight operation before any process
effect. Its receipt must include each candidate's process ID, executable path,
Session ID, command-line digest, parent process ID, creation time and explicit
classification of `PRIMARY_MANAGED`, `ADDITIONAL_MANAGED` or
`UNATTRIBUTABLE`. It must reject ambiguity. A static immutable binding contains
only configured task identity, S4U principal, normalized task XML/action
digest, terminal path/configuration digest and required Session 0 identity; it
never contains a dynamic process ID. The fixed adapter takes no caller-supplied
command, path, process ID, account or credential.

Before any effect, the executor takes
`Global\\Forex-M33-Trading-Health-Recovery`, reads the M33 ledger, and rechecks
the exact request ID, generation, expiry, boot, guardian/listener release,
configuration fingerprint, account/profile hashes and status digest. It also
requires an enabled maintenance hold, `RUN_DEMO` intent,
`GOMarketsMU-Demo`/AUD/EURUSD, zero open positions, zero pending orders, no
unresolved submission, no unresolved monitoring, and no unattributable
`terminal.exe` or `terminal64.exe` process. For `START_ONE_MT5`, an absent
terminal cannot initialise MT5 to prove account flatness. The plan therefore
requires a separate, non-starting authoritative held account witness with a
declared maximum age, exact account/profile binding and proof of no unresolved
work. If that witness cannot exist without the missing terminal, START must
refuse; it must not start merely so it can observe the account afterwards. Any
missing, stale, malformed, ambiguous or changed fact yields
`INTERVENTION_REQUIRED`; it cannot retry or fall back to a generic operation.

The executor persists a claimed attempt and an `INTERVENTION_REQUIRED` receipt
before the one process effect. For a missing client, it starts only the exact
configured Session 0 scheduled task from the static binding and explicitly
handles a queued or already-running task result without a second start. For
duplicates, it stops only additional process IDs selected from the exact
current inventory observed under the mutex after the same preflight; it
never stops the preserved primary, a different executable path, an interactive
unknown client, or any process outside the managed set. It records
`broker_mutation: NONE` and `entry_eligible: false` in every result.

A separate fixed reconciliation operation performs no process effect. It
requires a fresh listener heartbeat, guardian status, current managed inventory
of exactly one terminal, no unknown terminal, idle monitoring, held readiness,
and the same identity fields before replacing `INTERVENTION_REQUIRED` with
`VERIFIED`. Entry remains fenced even after verified recovery.

## Consolidated repair and assumption map

The initial implementation review returned NO-GO. The following repairs are
ordered by safety dependency; a later item cannot be accepted by merely
passing a unit test for itself.

1. Prevent false proof. `VERIFIED` is permitted only after a prior
   `DISPATCHED` request and receipt linked to that exact request, plus schema,
   digest, boot, epoch, generation and freshness checks. It must also prove a
   fresh held listener heartbeat, guardian status with `entry_eligible: false`,
   idle monitoring, a current flat/no-pending/no-unresolved-work witness, and
   one attributable managed terminal. Any missing or stale fact produces
   `INTERVENTION_REQUIRED`, never `VERIFIED`.
2. Put the MT5 executor and reconciler under
   `Global\\Forex-M33-Trading-Health-Recovery`. Under the acquired mutex they
   must re-read the request, both ledgers, coordinator, hold, intent, static
   binding, inventory and account witness. A failed or unavailable lock is a
   refusal; it is never retried through a generic operation.
3. Strengthen ownership before a duplicate stop. The fixed collector must bind
   the exact `CS AI Lab MT5 Start` S4U task XML, principal, action, configured
   terminal path and expected parent lineage. Right before each stop, it must
   re-enumerate under the mutex and match PID, creation identity, path, Session
   0, command-line digest and parent identity. An unrelated or changed process
   is `UNATTRIBUTABLE` and cannot be stopped.
4. Make publication crash-safe. Write a complete MT5 request and its
   ledger/coordinator ownership in an atomic, recoverable sequence. Startup
   recovery must convert any incomplete bundle to intervention-required rather
   than leaving an active lease with no inspectable request.
5. Implement exactly one hash-bound duplicate-cleanup effect after the checks
   above. It may stop only freshly revalidated `ADDITIONAL_MANAGED` identities.
   It cannot invoke `m20_close_duplicate_terminal`, generic `mt5_start`, a
   caller-supplied command, MT5 Python, or an order function.
6. Keep missing-terminal start refused unless a separate authoritative,
   non-starting held-account witness exists. The witness needs a declared
   maximum age, Demo/AUD/EURUSD and account/profile bindings, zero positions,
   zero pending orders, and no unresolved work. It must not be inferred from
   an old listener heartbeat. Without this witness, the duplicate branch may be
   implemented but the absence branch and full M33-C7 proof remain unproven.
7. Add adversarial tests for forged/stale records, missing dispatch receipt,
   mutex conflict, changed PID/creation/path/session/command/parent identity,
   non-S4U or changed task XML/action/principal, unresolved exposure/monitoring,
   cross-protocol conflict, crash between publication writes, failed stop and
   failed reconciliation. Tests must prove no `VERIFIED`, order path, or
   `entry_eligible: true` result on any unsafe input.
8. Repair the local Windows/WSL SSH bridge, then retain the raw fixed-preflight
   JSON and stderr. `WSL UtilBindVsockAnyPort:307` is evidence of the local
   transport layer failing before remote execution evidence, not proof that
   T480 is down. Do not stage until preflight succeeds and source binding is a
   committed, reviewed revision.

### Local WSL repair authority

The fixed adapter preflight has twice reached its local Windows/WSL bridge and
failed before remote contact with `UtilBindVsockAnyPort:307`. Read-only checks
are allowed; `wsl.exe --shutdown`, restarting a Windows WSL-related service,
rebooting the workstation, or changing networking is a host mutation outside
the held T480 staging authority. Before any such mutation, obtain an explicit
operator decision naming the permitted repair scope. After it, re-run only the
fixed Forex `preflight`; a successful preflight is transport evidence, not
approval to stage, capture candidate binding, install, recover, release hold,
or submit orders.

On 2026-09-27, following explicit local bridge-repair authority, `wsl.exe
--status` returned normally and the fixed Forex preflight reached T480 with
exit code 0. The local transport blocker is cleared. Source remains
uncommitted and independent implementation review is still required before
any stage or read-only candidate capture.

These repairs rest on explicit assumptions. The exact task name and S4U
Session-0 model must be the approved production MT5 launcher; if not, stop and
amend this plan. Windows must expose stable creation, parent and command-line
identity for this process topology; if it cannot, duplicate cleanup remains
refused. Forex may own fixed payload/catalogue operations while shared
infrastructure owns transport, but this does not permit generic remote access.
The shared mutex must be usable by both task security contexts; otherwise use a
different durable mutual-exclusion design before implementation. Finally, the
active M33-C7 contract requires both absence and duplicate recovery; a missing
witness means the plan cannot redefine completion around duplicate cleanup.

## Progress

- [x] 2026-09-27: identified and rejected the insufficient generic/shared-only
  framing; confirmed Forex catalogue ownership and the narrow existing duplicate
  operation.
- [x] 2026-09-27: wrote this implementation ExecPlan and companion work record.
- [x] 2026-09-27: independent read-only plan review passed after two repair
  cycles; review is design-only and grants no implementation authority.
- [~] Implemented local schemas, MT5-v1 request publication, S4U collector,
  fail-closed executor/reconciler and fixed adapter release surface. Initial
  implementation review found false-verification, mutex, ownership,
  crash-ordering and bounded-effect defects; the repair map above is current.
- [~] Added schema/adapter/catalogue/transport tests and refreshed the governed
  fingerprint under Chris's explicit M32-preservation decision. Fixed T480
  preflight then failed in the local Windows/WSL transport layer before contact.
- [~] Independent implementation review is in progress after its initial NO-GO;
  it must be repeated after every cited repair passes its negative tests.
- [~] Latest Astra implementation re-review identified binding, coordinator,
  Session-0 observation and command-attribution defects. The local repair is
  tested (including a same-path lookalike refusal) and awaits another
  independent review; it supplies no staging or drill authority.
- [~] Added an MT5 partial-bundle startup fence and made MT5 reconciliation
  demand dispatch-linked, post-effect, independently witnessed and freshly
  collected held evidence before `VERIFIED`; focused local tests pass. The
  witness is now produced only by the existing release-bound no-order listener
  assessment. The collector requires a separately provisioned immutable
  expected task binding including the parent executable path. Its actual T480
  value remains unobserved and is therefore an external staging/review gate.
  A separate fixed read-only candidate-capture operation is ready for that
  observation and cannot provision or execute recovery.
- [ ] Obtain specific operator approval, then stage/hash-verify and run one
  held flat-only MT5 absence or attributable-duplicate drill.
- [ ] Reconcile fresh evidence; carry the reviewed final release into M33.4.

<!-- forex-work-projection:start task=M33-MANAGED-MT5-RECOVERY schema=forex.execution-work-projection.v1 -->
<!-- forex-work-item id=plan state=DONE -->
- [x] plan — Create governed managed-MT5 recovery ExecPlan (DONE)
<!-- forex-work-item id=plan-review state=DONE -->
- [x] plan-review — Independent read-only review of plan and boundary (DONE)
<!-- forex-work-item id=implementation state=IN_PROGRESS -->
- [ ] implementation — Implement and test the fixed held no-order managed-MT5 recovery path (IN_PROGRESS)
<!-- forex-work-item id=implementation-review state=BLOCKED -->
- [ ] implementation-review — Independent implementation review (BLOCKED)
<!-- forex-work-item id=held-drill state=BLOCKED -->
- [ ] held-drill — Stage and prove one held MT5 recovery drill (BLOCKED)
<!-- forex-work-projection:end -->

## Plan of work

1. Read the current listener-only guardian, recovery executor, v2 schemas,
   adapter contract and actual MT5 runtime binding. Add
   `config/schemas/trading-health-mt5-recovery-{request,ledger,receipt}.schema.json`,
   `config/schemas/trading-health-mt5-inventory.schema.json`, a static
   task-binding schema and a recovery-coordinator schema. Define a strict
   managed inventory record. It must
   classify each terminal as primary managed, additional managed, or
   unattributable without guessing from process name alone. Add unit tests for
   every ambiguity and a regression proving listener v2 inputs remain accepted
   unchanged.

2. Extend the guardian only to issue the two policy-named MT5 actions through
   the parallel MT5 contract when its observed state is unambiguously eligible.
   An intentional stop, unknown
   process, open/pending exposure, stale data, invalid hold/intent, a missing
   binding, a nonzero retry budget issue, or unresolved work must publish a
   fence/intervention outcome instead. Do not change the existing listener v2
   ledger or receipt schema; add coordinator checks at listener-v2 publication,
   claim, execution and reconciliation boundaries. The parallel MT5 ledger may
   proceed only while the coordinator lease names its exact request and epoch.

3. Implement the managed-MT5 executor and reconciler as separate modules, plus
   a fixed read-only task-binding/inventory/witness collector. The task-binding
   collector must normalize and hash the exact existing Session 0 task XML and
   action. The authoritative absent-MT5 account witness must be independently
   non-starting and have an explicit freshness limit; if none can be designed,
   make `START_ONE_MT5` refuse and leave that C7 branch unproven. Do not infer
   account state from an old listener heartbeat. Make every filesystem update
   atomic; claim and record the attempt before the effect; keep the shared mutex
   for all check-to-effect work; and make the receipt transition monotonic. The
   process-effect adapter functions must be fixed and hash-bound. Do not call
   `m20_close_duplicate_terminal` or generic `mt5_start` from the new path.

4. Add fixed catalogue operations for stage fragments, payload hash verify,
   held-only execution and read-only status/reconciliation. Each command must
   be below the encoded T480 transport limit described in
   `docs/t480-deployment.md`. The execute operation must fail before an effect
   if the hold is not explicitly enabled or the request/action is not exact.
   Name new release-builder helpers and add their paths to the immutable release
   payload list rather than relying on an unstated staging convention.

5. Test ordinary and adversarial cases: zero clients, one client, duplicates,
   unknown client, changed executable path, changed Session ID, stale request,
   expired request, corrupted ledger, mutex conflict, positions, pending orders,
   unresolved submission/monitoring, mismatched account/profile/fingerprint,
   failed task start, failed process stop, lost listener heartbeat and failed
   post-action reconciliation. Add task XML mutation, task principal/action
   mismatch, stale absent-MT5 account witness, dynamic process-ID swap between
   inventory and effect, unknown terminal, queued task, listener-v2
   compatibility, listener-then-MT5 active-request and MT5-then-listener
   active-request cases, stale cross-ledger state and changed common epoch.
   Immediately before each duplicate `Stop-Process`, re-enumerate under the
   mutex and require its PID, creation identity, executable path, Session ID,
   command-line digest and parent identity still match the signed inventory.
   Assert no test exposes an order command or an
   entry-eligible outcome.

6. Run the focused tests, Python compilation, `git diff --check`,
   `python3 scripts/forex_milestones.py validate`, and the active work-record
   continuation check. Record actual output and limitations in the companion
   record. Request an independent implementation review; resolve any findings
   and repeat affected checks.

7. Stop for a specific held process-effect approval. Only after it is given,
   perform the fixed stage/verify/preflight/drill/reconcile sequence and retain
   raw adapter envelopes in a new immutable `runs/evidence/M33/` bundle. A
   successful drill proves only the relevant M33-C7 scenario; it does not close
   M33, release the hold, or begin M33.4 soak automatically.

## Validation and evidence

Local implementation validation must include:

    pytest -q tests/test_trading_health.py tests/test_trading_health_guardian.py \
      tests/test_trading_health_recovery_executor.py \
      tests/test_trading_health_managed_mt5_recovery.py tests/test_t480_adapter.py
    python3 -m py_compile t480/trading_health_managed_mt5_recovery.py
    python3 scripts/forex_milestones.py validate
    git diff --check

The later operational evidence requires raw fixed adapter envelopes for the
before inventory/readiness/guardian state, exact request and claimed attempt,
one fixed task/process effect, and after inventory/readiness/guardian status.
The final receipt must show exactly one attributable managed Session 0 terminal,
zero positions and pending orders, hold enabled, `entry_eligible: false`,
`broker_mutation: NONE`, and monitor `IDLE`. These receipts are required proof
of the original failing acceptance condition, not a substitute for M33.4's
two final-release boots, T16-independent soak, natural lifecycle/P&L evidence,
independent final review, or Chris's closeout decision.

## Review and stop conditions

The first independent review is a plan review. It must confirm that the local
catalogue ownership does not bypass the shared transport boundary and that
the proposed fixed process effects cannot reach order authority. The second
review is after implementation and before staging. A reviewer may recommend
changes but cannot approve deployment, a process effect, hold release, entry
authority or milestone closeout.

Stop immediately and report intervention required if an inventory is
ambiguous, the current binding cannot identify the Session 0 startup task, a
new operation exceeds the transport limit, a required schema/test is missing,
the governed fingerprint needs a new preservation decision, or the specific
held MT5 process-effect authority is absent. Do not use an older receipt,
generic shared operation, or manual cleanup to bypass any stop condition.

## Terms and identity glossary

`S4U` is Windows Scheduled Task logon without an interactive desktop password
session. `Session 0` is the non-interactive Windows service session used by the
approved MT5 task. An `immutable binding` is an atomic local record of static
task/configuration identity, protected by hashes; dynamic process IDs must
never be embedded in it. An `attributable process` is a terminal process whose
path, Session ID, command-line digest, parent and creation identity match the
current fixed inventory and static binding. `Flat` means zero current positions
and zero pending orders, established by a fresh authoritative account witness.
The `recovery mutex` is the named Windows lock that prevents two recovery
attempts from checking state and acting at the same time.

## Surprises & Discoveries

- 2026-09-27: the existing `m20_close_duplicate_terminal` is a Forex-owned
  fixed OS process effect under maintenance hold. It proves local catalogue
  feasibility but is deliberately rejected as M33-C7 implementation evidence
  because its checks are weaker than this plan requires.
- 2026-09-27: Astra plan review returned NO-GO. It identified listener-v2
  action incompatibility, absent-MT5 circular evidence, insufficient process
  identity and invalid continuation metadata. The repairs are recorded above;
  no implementation is permitted until a second independent review passes.
- 2026-09-27: Astra second review confirmed those four repairs but returned
  NO-GO for authority wording and durable cross-protocol exclusion. The plan
  now requires a common recovery coordinator lease and exact pre-stop creation
  identity re-enumeration; it awaits final re-review.
- 2026-09-27: Astra final read-only plan review returned GO. It confirms the
  plan is safe to implement only after Chris explicitly instructs that next
  step; it does not approve any remote staging or MT5 process effect.

## Decision Log

- 2026-09-27: replace the earlier shared-only dependency framing with a
  Forex-owned fixed catalogue implementation, while keeping `cs-ai-lab-infra`
  transport code untouched. This follows the repository ownership boundary and
  avoids using generic `mt5_start`.
- 2026-09-27: separate implementation/testing from any T480 MT5 process
  effect. The latter remains a material, separately approved held drill.
- 2026-09-27: use a parallel versioned MT5 contract rather than silently
  broadening the listener-only v2 request/ledger/receipt protocol.
- 2026-09-27: make the coordinator lease the cross-protocol authority. A shared
  mutex alone is not sufficient because two nonterminal requests could persist
  after separate operations release the mutex.

## Outcomes & Retrospective

Local implementation, schemas, focused tests and the governed fingerprint
refresh have occurred under this ExecPlan. The first implementation review
correctly prevented staging because the code is still a fail-closed scaffold,
not a C7-capable bounded MT5 recovery. The local fixed preflight also failed
before remote contact in the Windows/WSL transport layer. The next outcome must
be the repair-map acceptance tests and a new independent GO review; only then
can a committed source-bound release be staged, and only a later specific held
drill approval can permit a process effect.
