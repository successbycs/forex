# Build and prove the M33 investor-password observer

This ExecPlan is a living document. Maintain it in accordance with
`PLANS.md`. It is a child plan within the active M33 reliability milestone and
has the companion work record
`docs/plans/m33-investor-observer-work.json`. It creates no authority to
release the maintenance hold, enable entry, place an order, create or rotate a
credential, provision a T480 task, deploy a payload, commit, push, or close a
formal milestone.

## Purpose / Big Picture

M33-C7 requires the recovery guardian to start a missing managed MT5 terminal
only when it can first establish that the Demo account is flat and has no
pending or unresolved work. A missing terminal cannot be used to establish
that fact. This plan builds a separate MT5 observer that uses an MT5 investor
password: it may inspect the account but has no trading rights. The observer
will run as a separately identifiable Windows scheduled task, use its own MT5
data directory, and produce a fresh fixed no-order snapshot. A reviewer will
be able to see an immutable binding to that task and a snapshot proving
`GOMarketsMU-Demo` / AUD / EURUSD, no positions, no pending orders, no
unresolved work, `entry_eligible: false`, and no possible order submission.

The result is a safe prerequisite for the existing `START_ONE_MT5` branch. It
does **not** implement or authorize the terminal-start effect itself. If any
observer identity, credential protection, account fact, freshness, or hold
fact is uncertain, the branch must refuse and retain the existing monitoring.

## Formal milestone dependency map

`M32` is the proven Demo baseline. It remains reusable and must remain
preserved; this plan does not replace the account, risk, order, or execution
controls that M32 established.

`M33` is the active formal milestone and is currently `NEEDS_FIX`. This plan
belongs specifically to the work package **M33.3 — Recover safely**, whose
plain-language purpose is to recover a failed local component without trading
or touching an unrelated program. It fits `M33-C7` because that safety
criterion requires a bounded start of a missing managed component only when
the account is flat, with precise ownership and a reconciliation before entry
could ever be considered. The observer supplies the independent, non-starting
account-state prerequisite that the missing-terminal branch otherwise lacks.

`M33-C5` (unattended Demo runtime) and `M33-C6` (local health observation) are
reusable inputs; this plan does not claim to re-prove them. `M33-C7` remains
unproven until a separate reviewed, explicitly authorised held recovery drill
has captured before/action/after evidence. **M33.4 — Prove and release the
workflow**, including `M33-C8` cold boots, T16-disconnected soak, and natural
Demo lifecycle/P&L evidence, remains blocked behind completion of M33.3. No
numbered work package grants authority merely by being next in sequence.

The existing registry contract fits the local observer design and no amended
milestone is required for its code, schemas, fixed read-only collector, or
tests. The following delivery waves are blocked until explicit human authority
because they mutate an external account or T480 host:

- Creating or rotating the Demo investor password, placing it in Windows
  protected storage, and provisioning the observer task/data directory.
- Staging or installing the release on T480, including read-only collection.
- Any held recovery drill that starts the managed execution terminal.

If the platform cannot create a genuinely isolated observer that reports the
required facts without a trading-capable credential, do not weaken M33-C7 or
invent a local witness. Stop the missing-terminal wave and request either a
formal scope amendment or an independently researched broker-native read-only
surface.

## Scope and authority

Chris selected the investor-password observer as the primary solution after an
independent comparison with a duplicate-only scope amendment and a broker API.
That selection authorizes this design, local build, and local verification.
It does not authorize T480 staging, release installation, changing a scheduled
task, creating/rotating/using an investor password, changing Windows ACLs,
starting MT5, terminating a process, releasing the hold, entry authority, or
an order. `GOMarketsMU-Live` is prohibited in every path.

Use only `python3 scripts/t480_adapter.py` and its fixed operation catalogue
for later T480 work. Do not use a generic remote shell, SCP, a copy operation,
or a caller-supplied PowerShell command. Before every later deployment, read
`docs/t480-deployment.md`; its encoded command envelope must stay below 7,500
characters and large payloads must be hash-verified numbered fragments.

The observer credential is a secret. It must not appear in Git, a plan, a
schema instance, a fixed payload, command arguments, logs, raw evidence, test
fixtures, or status records. A SHA-256 digest of an opaque Windows credential
target name may be recorded only after the target is separately provisioned;
the digest does not disclose the credential.

## Context and Orientation

`t480/trading_health_managed_mt5_recovery.py` owns the parallel M33 managed
MT5 recovery contract. `t480/trading_health_managed_mt5_inventory.py` reads
the configured execution-terminal task and classifies terminal processes.
`t480/trading_health_managed_mt5_recovery_executor.py` claims an exact request
and currently refuses `START_ONE_MT5` unless
`_independent_observer_witness()` accepts a fresh observer record. It still
returns `MT5_START_FIXED_EFFECT_NOT_INSTALLED`; there is no MT5 import,
connection, task start, or order path in the local skeleton.

The initial schemas are
`config/schemas/trading-health-mt5-observer-binding.schema.json` and
`config/schemas/trading-health-mt5-observer-witness.schema.json`. They express
the desired data shape, but a mutable local JSON file with a self-hash is not
provenance. This plan replaces that trust shortcut with a release-bound,
producer-owned record and an independently re-observed T480 task/ACL/terminal
snapshot.

In this plan, a **binding** is the immutable expected identity of the observer:
task name, task XML/action digests, principal, Session 0, exact terminal path,
separate data-directory digest, opaque credential-target digest, release
digest, and protected state location. A **witness** is the short-lived factual
result from that bound observer. An **authorized observer** is exactly the one
process that matches that binding; it is never an execution terminal and is
never eligible for duplicate cleanup. A **held snapshot** runs while the
existing maintenance hold is enabled, keeps `entry_eligible: false`, and has
no order capability.

## Design

The design has two separately reviewed releases. **Release A** is a binding-free
bootstrap collector. It can inspect one fixed observer task only after that
task has been separately provisioned; it cannot issue a witness trusted by the
recovery executor. Its only durable output is a candidate report. After an
independent review of that candidate report, **Release B** embeds the resulting
expected binding and contains the strict parser and fixed snapshot collector.
Mutable state contains only an atomically written witness and a collector
receipt. The executor may trust a Release-B witness only after it
re-validates the release binding, the witness schema, a one-way receipt chain,
the configured account/profile/fingerprint/boot values, and a 30-second
freshness window. A witness must fail closed on an unknown field, duplicate
JSON key, wrong type, malformed timestamp, future timestamp, missing source
digest, changed binding, or mismatched account scope.

The bootstrap collector re-observes rather than accepts supplied facts. It uses
`Get-ScheduledTask`, `Export-ScheduledTask`, `Get-Acl`, and `Get-FileHash` on
fixed paths only, plus `Win32_Process` for process path, command-line digest,
parent path, Session ID, and creation identity. It must not claim that process
inventory proves a data directory or release identity: data-directory identity
comes only from the fixed task action/working directory and its ACL; release
identity comes only from the staged payload digest. If either source is absent
or ambiguous, it emits `INTERVENTION_REQUIRED`.

The observer task runs as one dedicated non-administrator local account whose
SID is captured in the candidate report and is neither `S-1-5-18` (SYSTEM),
`S-1-5-32-544` (Administrators), nor the managed execution-terminal principal.
It is an S4U Session-0 task. Its one task action starts the isolated observer
installation with the literal `/portable` argument and no login, password,
credential-target, script, interpreter, redirection, or arbitrary argument.
The observer's authenticated MT5 profile is established once by an authorised
operator while signed in as that account, using the Demo investor password only
in the MT5 UI. The fixed task later starts that protected portable profile;
neither release reads, injects, or passes a password. The profile is the
Windows-protected secret location: it is accessible only to the observer SID,
SYSTEM, and Administrators. Candidate evidence records a digest of its path
and ACL, never a password or a Credential Manager value. If MT5 cannot resume
that investor profile without a password argument, this solution is infeasible
and the plan must stop rather than add automated secret injection.

The allowed ACL policy is exact. The immutable release directory and binding
file are owned by `S-1-5-32-544`; only `S-1-5-18` and `S-1-5-32-544` may write
them, while the observer SID has read/execute access only. The protected MT5
profile and observer state directories are owned by `S-1-5-32-544`; only the
observer SID, `S-1-5-18`, and `S-1-5-32-544` may read or write them. All paths
reject inherited or explicit write access for `Everyone`, `Users`,
`Authenticated Users`, the execution-terminal principal, or an unrecognised
SID. The collector emits the owner SID, sorted ACE tuple digest, path digest,
and inheritance flag for each path. A mismatch is a refusal, never a warning.

The snapshot topology is fixed. The sole observer task starts the already
profiled portable terminal. That profile contains exactly one Release-B
`M33InvestorObserverSnapshot` Expert Advisor on one chart. On `OnInit` it
starts a timer; on `OnTimer` it reads native MT5 status and writes one canonical
JSON snapshot to the profile's fixed `MQL5\\Files\\m33-observer` directory by
write-then-rename. It has no trade include, no `OrderSend`, `OrderSendAsync`,
`CTrade`, position modification, DLL, shell, or socket call. The host-side
Release-B collector never attaches to MT5 and never starts/stops a process: it
first proves that exactly one existing process matches the bound observer task
path, `/portable` command digest, parent, Session 0 and creation identity, then
reads only that fixed snapshot file and validates its source/receipt hashes.
Zero/multiple/mismatched processes, missing chart EA, missing snapshot, or a
snapshot not produced after the matched process creation time is a refusal.

Release-B's fixed collector records Release-B payload digest, immutable binding
digest, task XML/action/principal/ACL/profile source digests, writer task SID,
collection start/end UTC timestamps, canonical witness digest, and a refusal
reason when any source is unavailable. It writes the witness atomically only
after all checks pass. It may read account status through the observer only;
supported output is server, currency, configured symbol, positions, pending
orders, unresolved submission/monitoring, and `STRUCTURALLY_UNAVAILABLE` only
when all native flags are present and exactly false:
`ACCOUNT_TRADE_ALLOWED`, `ACCOUNT_TRADE_EXPERT`, `TERMINAL_TRADE_ALLOWED`, and
`MQL_TRADE_ALLOWED`. The EA also records `MQL_DLLS_ALLOWED: false`. A null,
unsupported, true, or mismatched field is a refusal. These flags are direct
status observations, not an attempted order; static source/binary review also
must prove the EA exposes no trading API. It must not invoke a trade API, order
command, task mutation, credential read, or process-control operation.

The inventory collector must classify exactly one binding-matched observer as
`AUTHORIZED_OBSERVER`. Runtime process attribution uses the fixed task's
already-bound executable path, literal `/portable` command digest, parent
identity, Session 0, and creation identity; data-directory and release checks
remain task/ACL/payload facts, not guessed process facts. It must exclude that
process from the managed execution set and refuse recovery if there are zero,
multiple, or partial observer matches. A same-named or same-path process that
does not match the bound runtime fields is `UNATTRIBUTABLE`, not an observer.
The existing executor must treat every
observer validation failure as
`MT5_START_REQUIRES_INDEPENDENT_HELD_WITNESS`; a successful witness reaches
only the existing `MT5_START_FIXED_EFFECT_NOT_INSTALLED` fence.

## Progress

- [x] (2026-09-27) Selected the isolated investor-password observer as the
  full-scope M33-C7 design. The earlier independent review rejected the local
  JSON-only skeleton as non-provenanced.
- [x] (2026-09-27) Wrote this child ExecPlan and companion work record. No
  external operation, credential, task, release, process effect, hold release,
  entry authority, or order occurred.
- [x] (2026-09-27) Independent Astra plan review found the bootstrap-order
  contradiction and missing concrete provenance/credential/evidence detail.
  The plan now requires Release A candidate capture before Release B binding.
- [x] (2026-09-27) Astra re-review returned GO for local Release-A build only
  after the in-terminal snapshot topology, native read-only predicates, named
  suites, and a distinct Release-B review gate were added. It grants no
  external authority.
- [x] (2026-09-27) Implemented Release A: strict candidate/receipt contracts,
  a fixed no-secret/no-effect Windows metadata collector, fixed adapter
  fragments/capture operation, and focused tests. Targeted checks passed (3
  adapter transport/catalogue and 6 observer contract/collector tests), as did
  compilation, governance validation and diff check. M33 fingerprint refreshed
  to `sha256:70ff7801956f8a96658ec40591f2db16cce4cdf1265112cb8f4b7052f4eb2dda`
  while preserving M32. No T480 operation occurred.
- [x] (2026-09-27) Independent Release-A review initially found trust-chain
  defects; the required Astra-owned repair and separate final review are now
  complete. Final review returned GO for local Release A only after 25 selected
  observer/adapter tests, compilation and diff check. The next step is blocked
  solely on explicit observer-provisioning authority.
- [ ] Build and locally verify the release-bound collector, provenance chain,
  observer classification, and adversarial tests.
- [ ] Obtain an independent local implementation review.
- [ ] With separate authority, stage and capture read-only T480 binding facts.
- [ ] With separate credential/task authority, provision and prove one held
  no-order observer snapshot.
- [ ] With a later separate held-drill authority, integrate the accepted
  witness with the managed-terminal recovery drill.

## Current delivery board — authoritative next actions

This is the single operator-facing sequence for the remaining M33-C7 work.
The companion work record is the machine-readable source for its state; this
table must be kept in sync with it. A task marked **Codex** is executed only
through the fixed Forex adapter or local repository checks. A task marked
**Windows operator** deliberately keeps credentials and Windows administration
outside source code and agent-visible logs.

| Order | Task | Owner | Current state / required gate |
|---:|---|---|---|
| 1 | Read the M33 guardian status and prove maintenance hold is still enabled. | Codex | Done 2026-09-27: the fixed read-only call reached T480; guardian is running, `RISK_MAINTENANCE_OR_LEASE_HOLD` is active, and `entry_eligible` is false. The earlier socket error was a sandbox bridge restriction, not a host or T480 failure. |
| 2 | Create/rotate the Demo investor credential and provision the isolated non-admin `CS AI Lab MT5 Observer` S4U task, portable profile and exact ACLs. | Windows operator | Authorised by Chris on 2026-09-27, but no fixed Forex provisioner exists and the secret must never reach Codex. No MT5 recovery, hold release, entry enablement or order is permitted. |
| 3 | Commit the reviewed Release-A source. | Codex | Done 2026-09-27: committed after focused observer/recovery/adapter checks passed. |
| 4 | Fixed-stage/hash-verify Release A and capture candidate task, path, principal and ACL facts. | Codex | Authorised after Step 2 confirmation; blocked by Steps 1 and 3. Read-only: it cannot read credentials, start MT5 or trade. |
| 5 | Independently review the captured candidate evidence and accept or reject Release-B inputs. | Independent reviewer | Blocked by Step 4. Codex may prepare the evidence but cannot self-certify independence. |
| 6 | Build/test Release B from only accepted candidate digests, then obtain its separate independent implementation review. | Codex, then independent reviewer | Blocked by Step 5. |
| 7 | Fixed-stage/hash-verify Release B and collect one held, no-order observer snapshot. | Codex | Requires a new explicit held read-only authority after Step 6; snapshot must prove Demo/AUD/EURUSD, flat/no-pending/no-unresolved, hold enabled and entry disabled. |
| 8 | Implement and independently review the bounded managed-MT5 process effect. | Codex, then independent reviewer | Blocked by Step 7. The current executor deliberately refuses an MT5 start/stop effect. |
| 9 | Run and reconcile one explicitly approved held M33-C7 recovery drill. | Codex | Requires a separate drill authority; hold remains enabled, `entry_eligible: false`, no order authority and no orders. |
| 10 | Complete M33-C8 final proof: cold boots, T16-disconnected soak and an eligible natural Demo lifecycle/P&L capture. | Codex monitors/captures; Chris closes | Blocked by Step 9 and elapsed real-world conditions; it cannot be forced or substituted by local tests. |

<!-- forex-work-projection:start task=M33-INVESTOR-OBSERVER schema=forex.execution-work-projection.v1 -->
<!-- forex-work-item id=plan state=DONE -->
- [x] plan — Create governed investor-observer ExecPlan (DONE)
<!-- forex-work-item id=plan-review state=DONE -->
- [x] plan-review — Independently review the repaired observer design and authority boundary (DONE)
<!-- forex-work-item id=local-build state=DONE -->
- [x] local-build — Build and locally verify Release A bootstrap collector (DONE)
<!-- forex-work-item id=implementation-review state=DONE -->
- [x] implementation-review — Independently review local Release A implementation (DONE)
<!-- forex-work-item id=transport-hold-check state=DONE -->
- [x] transport-hold-check — Read M33 maintenance-hold status (DONE)
<!-- forex-work-item id=observer-provision state=BLOCKED -->
- [ ] observer-provision — Provision isolated Demo investor observer (BLOCKED)
<!-- forex-work-item id=release-a-commit state=DONE -->
- [x] release-a-commit — Commit reviewed Release-A source (DONE)
<!-- forex-work-item id=bootstrap-capture state=BLOCKED -->
- [ ] bootstrap-capture — Stage Release A and capture observer candidate facts (BLOCKED)
<!-- forex-work-item id=candidate-review state=BLOCKED -->
- [ ] candidate-review — Independently review candidate facts and approve Release-B inputs (BLOCKED)
<!-- forex-work-item id=binding-release state=BLOCKED -->
- [ ] binding-release — Build Release B with immutable observer binding (BLOCKED)
<!-- forex-work-item id=binding-review state=BLOCKED -->
- [ ] binding-review — Independently review Release B implementation (BLOCKED)
<!-- forex-work-item id=held-snapshot state=BLOCKED -->
- [ ] held-snapshot — Stage Release B and capture one held no-order observer snapshot (BLOCKED)
<!-- forex-work-item id=managed-effect state=BLOCKED -->
- [ ] managed-effect — Implement and independently review bounded managed-MT5 process effect (BLOCKED)
<!-- forex-work-item id=held-drill state=BLOCKED -->
- [ ] held-drill — Run and reconcile one separately authorised held M33-C7 recovery drill (BLOCKED)
<!-- forex-work-item id=m33-c8-final-proof state=BLOCKED -->
- [ ] m33-c8-final-proof — Capture final M33-C8 runtime proof and human closeout inputs (BLOCKED)
<!-- forex-work-projection:end -->

## Plan of Work

1. Review this plan independently before implementation. Confirm that it
   preserves M33-C7 rather than shrinking it, that the trust boundary is not a
   self-hashed JSON file, that the observer cannot reach an order path, and
   that each external mutation remains gated by explicit authority. Record the
   reviewer, revision/digests, findings, and any repair in this plan and the
   companion work record. A review is advisory and grants no deployment or
   broker authority.

2. Build **Release A**, the binding-free bootstrap collector. Replace the loose
   local observer contracts with strict candidate-report and receipt schemas in
   `config/schemas/`. They must include the Release-A payload digest; source
   task XML/action/principal, path, ACL and profile ACL digests; observer SID;
   canonical format/version; writer identity; and a refusal reason. Add a
   parser/validation module under `t480/` that rejects duplicate keys,
   non-finite JSON values, extra properties, and wrong types even when Python
   truthiness would otherwise accept them. Do not introduce a secret field.
   Release A must not create a trusted witness or immutable observer binding.

3. Add `t480/trading_health_mt5_observer_collector.py` and fixed Release-A
   payload/adapter/catalogue operations. It has only `--state-root`; it accepts
   no caller-selected task, path, account, process, credential, or command. It
   can inspect only `CS AI Lab MT5 Observer` after provision, and writes a
   candidate report plus receipt using write-then-replace semantics. It must
   generate a refusal receipt on failure and leave an earlier accepted artifact
   untouched. Add named unit tests in
   `tests/test_trading_health_mt5_observer_collector.py`. Its Windows source is
   the task XML/action/working directory and ACL, not process inference. Add
   fixed staged fragments and one hash-verifying read-only launch operation to
   the adapter/catalogue; keep every encoded command under the T480 limit.

4. Only after candidate review, build **Release B**. Add the fixed
   `t480/mt5_m33_investor_observer_snapshot.mq5` Expert Advisor and its
   source/binary digest to the binding. It uses only `OnInit`, `OnTimer`,
   account/terminal/program information functions, position/order enumeration,
   and atomic fixed-file output in the portable profile. It is loaded solely
   by the bound observer profile; the host collector never attaches to or
   controls a terminal. Extend the binding and witness schemas with Release-B
   payload digest, candidate-report digest, source-digest map, writer task SID,
   canonical witness digest, and collection times. Embed the expected binding
   in the Release-B payload rather than a `.local.json` file. Add a Release-B
   fixed snapshot operation that re-observes candidate facts, verifies exactly
   one pre-existing observer process and the EA snapshot source chain, and
   produces a trusted witness only when they match.
   Then extend `t480/trading_health_managed_mt5_inventory.py`,
   `t480/trading_health_guardian.py`, and
   `t480/trading_health_managed_mt5_recovery_executor.py` so observer identity
   is explicit. The inventory has four possible process outcomes: primary
   managed execution terminal, additional managed execution terminal,
   authorized observer, or unattributable. Only the first two can be considered
   by recovery. The guardian must fence entry and publish intervention when the
   observer is absent, ambiguous, stale, or mismatched. The executor must
   re-validate the receipt chain and all witness fields under the mutex before
   leaving the absent-terminal refusal; it must still refuse at the fixed start
   effect gate.

5. Add focused tests before each code path is accepted. Put strict parser
   cases in `tests/test_trading_health_mt5_observer_contract.py`, collector and
   atomic-write cases in `tests/test_trading_health_mt5_observer_collector.py`,
   process classification cases in
   `tests/test_trading_health_managed_mt5_inventory.py`, and consumer refusal
   cases in `tests/test_trading_health_managed_mt5_recovery_executor.py`. Cover valid bound
   observer input, extra field, duplicate JSON key, wrong boolean/number type,
   altered binding/self-hash/receipt/source digest, stale and future timestamps,
   mismatched boot/fingerprint/account/profile, Live server, wrong currency or
   symbol, position/pending/unresolved work, `entry_eligible: true`, any order
   submission value other than `STRUCTURALLY_UNAVAILABLE`, missing task,
   wrong principal/session/action/path/data directory/credential-target
   metadata/ACL owner, observer lookalike, two observers, observer included in
   duplicate cleanup, torn write, mutex conflict, and a witness that becomes
   stale between validation and use. Add observer/execution-terminal collision,
   unsupported task argument, secret-like field redaction, missing/duplicate
   observer process, stale-before-process-creation snapshot, EA/source digest
   mismatch, and every native trade-permission flag individually true, null or
   missing. Include tests proving the collector has no process-effect,
   task-mutation, credential-read, or order invocation.

6. Run the focused test suite, byte-compilation, transport catalogue checks,
   milestone validation, continuation check, and `git diff --check`. Record
   actual counts and output in this plan. Request a separate independent local
   implementation review, resolve any findings, and re-run affected checks.
   Local tests establish only implementation behavior, never T480 or broker
   truth.

7. Stop until Chris explicitly authorizes creation or rotation of the
   **Demo-only** investor credential and provisioning of the separate task/data
   directory in Windows protected storage. The provisioner must create the
   non-admin observer account/S4U task and portable profile under the exact ACL
   policy in Design, establish the investor login only in the MT5 UI, and leave
   no secret in a command or artifact. This is an external mutation and does
   not permit a snapshot or recovery.

8. Stop until Chris explicitly authorizes held read-only staging. Stage and
   hash-verify Release A with the fixed adapter, then capture the provisioned
   observer's candidate task/ACL/path/profile facts. Retain the raw adapter
   envelope, candidate report, collector receipt, SHA-256 manifest and a
   redaction declaration in `runs/evidence/M33/observer-bootstrap-<UTC>/`.
   Independently review those artifacts. They prove candidate identity only;
   they do not create a trusted witness, start MT5, or run recovery.

9. Build Release B using only the accepted candidate digests, then obtain a
   distinct independent Release-B implementation review. Under a further
   explicit held read-only staging authority, stage
   and hash-verify Release B then run exactly one no-order observer snapshot.
   Store before/after guardian/hold/inventory status, Release-B hash, immutable
   binding, collector receipt, witness, adapter envelopes, manifest and
   redaction declaration in `runs/evidence/M33/observer-held-<UTC>/`. Extend
   `scripts/capture_m33_evidence.sh` to collect these named files and
   `scripts/verify_m33_evidence.sh` to fail on missing hashes, stale witness,
   redaction failure, or an invalid receipt chain. The result must show
   Demo/AUD/EURUSD, flat/no-pending/no-unresolved state, no order capability,
   `broker_mutation: NONE`, maintenance hold enabled, and
   `entry_eligible: false`, and each four native permission fields false. Never
   demonstrate lack of trading rights by trying
   to place an order.

10. Record the two reviewed release hashes and two evidence-bundle manifest
    digests in this child work record and the parent
    `docs/plans/m33-managed-mt5-recovery-work.json`. The parent integration
    item may say only that the witness prerequisite is available; it must not
    claim M33-C7 completion.

11. A later parent-plan step may request a separate held recovery-drill
   approval. Only then may an accepted witness serve as the prerequisite for
   `START_ONE_MT5`; the fixed start effect, before/action/after reconciliation,
   independent review, and M33-C7 evidence remain separate work.

## Concrete Steps

All commands run from `/home/chris/projects/forex`.

For the local build and test wave, run:

    pytest -q tests/test_trading_health_managed_mt5_recovery.py \
      tests/test_trading_health_managed_mt5_recovery_executor.py \
      tests/test_trading_health_managed_mt5_inventory.py \
      tests/test_trading_health_mt5_observer_contract.py \
      tests/test_trading_health_mt5_observer_collector.py \
      tests/test_trading_health_guardian.py tests/test_t480_adapter.py
    python3 -m py_compile t480/trading_health_managed_mt5_inventory.py \
      t480/trading_health_mt5_observer_collector.py \
      t480/trading_health_managed_mt5_recovery_executor.py \
      t480/trading_health_guardian.py
    python3 scripts/forex_milestones.py validate
    python3 scripts/check_execution_continuation.py \
      --work-plan docs/plans/m33-investor-observer-work.json
    git diff --check

After the plan is first written, the continuation command is expected to say
`BLOCKED` and name `plan-review`; that is correct because implementation must
not start until independent review. After the review is recorded and
`local-build` becomes `IN_PROGRESS`, the same command should say `CONTINUE`.
During implementation, a passing focused test suite and no diff-check output
are required. Record actual output rather than copying these expectations.

Later T480 commands must be named fixed adapter catalogue operations created
by this plan. Do not run them until the appropriate explicit authority exists.
Their raw adapter envelope is the evidence; a heartbeat, synthetic JSON record,
or screenshot is not a substitute.

## Validation and Acceptance

The local implementation is accepted only when all new adversarial tests pass,
the inventory cannot count an observer as an execution terminal or cleanup
target, and the executor refuses every malformed/ambiguous/stale witness while
remaining incapable of a start or order. Adapter tests must prove every new
command remains under the encoded 7,500-character boundary and uses only a
hash-bound payload.

The operational observer surface is accepted only after an independent review
of raw T480 evidence verifies that exactly one separately provisioned observer
matches the immutable binding; that it is Demo-only and investor-authorized;
that its task/data directory/credential target and ACL are isolated from the
execution terminal; and that its fixed held snapshot has the required account
facts and no order capability. This is a prerequisite for a M33-C7 drill, not
formal M33 completion. Formal M33 evidence additionally requires the registry's
capture/verifier route, current evidence, human review, and later M33.4 proof.

## Idempotence and Recovery

All local commands are read-only or additive and can be repeated. The collector
must never overwrite a previous accepted witness with partial output: write to
a private temporary file, fsync where available, validate it, and atomically
replace only after a complete receipt chain exists. A collector failure leaves
the prior witness in place but causes the executor to reject it unless it is
still valid, fresh, and binding-matched.

If the observer cannot be provisioned or its identity cannot be independently
proven, retain the maintenance hold and leave `START_ONE_MT5` refused. Do not
fall back to the managed terminal, a cached listener fact, a manually edited
record, or a generic remote command. A failed stage must be repaired through a
new reviewed hash-bound release; do not bypass the fixed adapter.

## Review and stop conditions

The plan review is the immediate stop condition. The exact next action is an
independent read-only review of this new ExecPlan. It needs no external system
access and cannot approve, deploy, provision, alter a hold, or trade.

The external stop conditions are concrete: the read-only staging wave requires
Chris's staging authority; credential/task provisioning requires Chris's
separate Demo credential and Windows configuration authority; and using an
accepted witness in a managed-terminal start drill requires Chris's separate
held no-order drill authority. Each authority must keep maintenance hold on,
`entry_eligible: false`, no order authority, and no orders.

## Surprises & Discoveries

- Observation: a self-hash on a mutable local binding does not establish the
  identity, ACL, task, or credential source that generated it.
  Evidence: independent Astra observer review on 2026-09-27 returned NO-GO
  because the existing skeleton trusted mutable JSON and had no fixed producer
  or protected provenance chain.
- Observation: the fixed Forex T480 preflight now reaches the remote endpoint,
  but that proves only transport, not observer installation or account truth.
  Evidence: `runs/evidence/M33/20260927T043951Z-fixed-preflight-recovered.txt`
  records remote exit 0 and no staging/collector/drill operation.

## Decision Log

- Decision: use an isolated MT5 investor-password observer as the primary
  missing-terminal design.
  Rationale: it preserves the full M33-C7 requirement to start a missing
  component safely, unlike a duplicate-only scope amendment. No broker-native
  read-only GOMarkets adapter, credential, or runtime contract exists.
  Date/Author: 2026-09-27 / Chris, following independent Astra comparison.
- Decision: split local build, read-only staging, credential/task provisioning,
  and recovery drill into separate authority waves.
  Rationale: the first is repository work; the others mutate T480 or a Demo
  account and must not be implied by code implementation.
  Date/Author: 2026-09-27 / Codex.

## Outcomes & Retrospective

This plan is newly created. The local skeleton exists but is deliberately not
accepted: it lacks an immutable provenance chain, fixed producer, observer
classification, and adversarial coverage. The next outcome is a reviewed plan,
not a deployment claim.

## Artifacts and Notes

The upstream official MT5 documentation describes investor authorization as
account-status access without trading rights. That fact informs the design but
does not prove the broker account/task configuration; the later held snapshot
and raw T480 metadata must prove the actual selected implementation. Source:
https://www.metatrader5.com/en/terminal/help/startworking/authorization

Plan created 2026-09-27 because the selected observer solution needs a
self-contained build/proof path after independent review correctly rejected
the mutable local JSON skeleton.
