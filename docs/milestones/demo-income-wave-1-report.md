# Wave 1 progress and proposed risk policy

## 2026-09-10 autonomous continuity protocol: retained alert-path failures

The first T480-local autonomous continuity run (`e8d63f0c006bcebcf43a4efd`)
finished at 10:32:54 UTC under maintenance hold. It retained 362 fresh,
release-bound held heartbeats and completed one controlled listener-worker
handoff. The account began flat and available on `GOMarketsMU-Demo`; no order
was submitted. Both marked Discord drill deliveries returned `FAILED`.
Therefore the run is retained as an **inconclusive alert-path result**, not as
passing R5/R6 proof. Raw terminal observations are retained under
`runs/evidence/M20/w1-autonomous-continuity-20260910/raw/`.

Release `3c849d6ae161e792` was then prepared, hash-verified, configured and
installed under the same maintenance hold. It binds application revision
`80205609cce3f447682672bcaf09dd9545445e60` and governed configuration
fingerprint `sha256:cb3a904c2d19ae7a3084ed49e84e48fd42901ebb93ad2a64d3a8fa522e31ec76`.
The repeat run `96fe551548327893a189f8e2` was armed at 10:34:53 UTC after a
fresh flat Demo account observation. Its controlled handoff recovered at
10:35:24 UTC, but its incident delivery also returned `FAILED`; it remains
running only to retain its complete local continuity record. The fixed
secret-preserving T480 operation confirms an approved local Discord webhook
is configured. That is not evidence that Discord accepted a notification.

Commit `9b243cb` makes the next release retain only a safe external delivery
reason (`HTTP_<status>`, `TIMEOUT`, or `NETWORK_UNAVAILABLE`). Do not release
maintenance hold, treat either current run as passing alert proof, or replace
the existing webhook without an approved machine-local source. The remaining
blocker is genuine T480-to-Discord delivery, not listener continuity, broker
exposure, lease, Option B, or RDP/T16 availability.

## 2026-09-10 supervised protected-restart proof captured; closeout remains pending

A naturally accepted `GOMarketsMU-Demo` EURUSD BUY, ticket `42239799`, provides
the missing supervised protected-position handoff. The listener recorded the
durable attempt `278446f4-a0ac-5d46-8f66-5feb0a22272b`, submitted the 0.01-lot
BUY at 1.16405 with broker SL 1.16377 and TP 1.16447, then requested its
one-shot handoff only after protection was observed. The T480-local parent
(PID 9236) launched exactly one child worker (PID 23120); the child recovered
that exact attempt and ticket as `OPEN_MONITORING` at 09:15:17 UTC. This was
ordinary Demo operation: no order was created by the drill.

The same position subsequently closed by its owner exit at 09:19:02 UTC.
Broker history and PostgreSQL lineage record `CLOSED` / `MATCHED`, exit price
1.16386 and AUD -0.26 realised P&L. Broker-posted commission, fee and swap
were each AUD 0.00; recorded spread and slippage are estimates and must not be
presented as posted broker charges. At the evidence freeze, the account was
AVAILABLE and flat (balance/equity AUD 100991.90), the expected balance was
the same, Option B had no pause reasons, and unresolved attempts were empty.
Raw observations are retained unchanged under
`runs/evidence/M20/w1-supervised-restart-20260910/raw/`.

The current governed configuration fingerprint was refreshed to
`sha256:6087a6d3f489f02cb0678557bf2d482e49699471fdebcfd62b0b8e50d03ab008`
after the reviewed adapter-catalogue addition for narrowly retiring the failed
legacy marker. The deployed listener binding remains application revision
`7c2c1d1687ac9efc3b98be134f3c0ccb2992809f`, release
`6097225ef545ea46`, and the runtime risk/financing configuration fingerprint
`sha256:16abde21dc56729b2418f9c48d7091362a3c7622f976e3bb36e49f8492e0fb67`.
This distinction is retained because the catalogue control operation did not
alter the deployed listener payload.

Focused M20 and isolated persistent-risk tests pass (the isolated database
tests correctly skip when `FOREX_W1_TEST_DSN` is not supplied). Governance
validation passes after the fingerprint refresh. The listener is presently in
maintenance hold only to freeze this evidence; monitoring remains active.

**Wave 1 is not complete yet.** An independent read-only review must assess
this new raw bundle and the release/configuration binding. R5's detached-T16
and no-logon continuity criteria, R6's retained incident-and-alert delivery
evidence, and the broader M20 capture/review gates remain distinct. Partial
fills, nonzero posted charges, and overnight tariffs remain explicitly
unobserved qualifications for the temporary intraday scope. Do not infer
profitability or Live readiness from these Demo results.

## 2026-09-10 final held deployment and ordinary operation resumed

### Legacy restart marker retired and current proof path armed

The old pre-repair marker was the only condition preventing the new supervised
worker proof from running. Commit `4883b89777937b28159bcf136bc6eeacbd337e08`
adds a fixed T480 operation that requires maintenance hold and can archive only
attempt `47433bf8-565d-5f24-9550-ddeea4124cd3` / ticket `42235606`; it cannot
remove any other marker and retains the original as
`m20_demo_protected_restart_drill.legacy-42235606.json`.

At 09:13 UTC, broker account observation was AVAILABLE and flat at AUD
100992.55 with no unresolved execution. The operation archived the exact known
legacy marker under hold, then ordinary operation resumed. A fresh listener
heartbeat at 09:13:40 UTC records `protected_restart_drill` as `ARMED` on
release `6097225ef545ea46`. The next naturally accepted, full,
broker-protected Demo position is therefore able to trigger the supervised
worker handoff and retain its bound recovery evidence. Raw evidence is under
`runs/evidence/M20/w1-rearm-20260910/raw/`. No order was created by retirement
or re-arming.

Commit `7c2c1d1687ac9efc3b98be134f3c0ccb2992809f` was independently reviewed,
then deployed under maintenance hold as release `6097225ef545ea46`. The fixed
T480 diagnostic readback retained all four deployed payload hashes, the exact
application revision/configuration fingerprint, the original continuous Demo
lease, unlimited development trade count, one-position and notional caps,
Option B, and the temporary intraday financing mandate. The held listener was
fresh and broker account was AVAILABLE and flat at AUD 100992.55.

The corrected real-broker-input calculation-only refusal drill then used a
fresh EURUSD quote (8.024 seconds old), a valid minimum technical stop and the
same planned-stop-loss predicate used by ordinary strategy planning. It
calculated AUD 0.069326 at 0.01 lot, refused the authorised AUD 0.01 temporary
cap, submitted no order, and restored the exact original lease and AUD 100
Option B limit immediately. Post-drill account remained flat and risk summary
has no pause reason or unresolved execution. Raw evidence is under
`runs/evidence/M20/w1-final-20260910/raw/`.

Maintenance hold was released only after those checks. At 09:09:50 UTC the
new release was RUNNING with a fresh heartbeat and an ordinary `NO_TRADE`
assessment. The previous pre-repair restart marker remains explicitly
`LEGACY_UNVERIFIED`; it is not rearmed or presented as a successful automatic
handoff. The new supervised worker handoff therefore still needs one naturally
accepted protected Demo position and its exact recovery record before it can
be claimed on the Windows surface. No trade is forced to obtain it.

**Wave 1 remains incomplete** pending that real supervised-handoff evidence,
its independent evidence review, and the required final current bound
recommendation. Partial fills, nonzero posted charges and overnight/special-day
tariffs remain explicitly unobserved qualifications rather than reasons to
manufacture trades or extend exposure.

## 2026-09-10 closeout review and automatic-restart failure repair in progress

Astra independently accepted the captured protected listener recovery and later exact broker closure of BUY 42234057: AUD -0.47, broker stop-loss close at 08:43:50 UTC, PostgreSQL observation one second later, original proposal/attempt/lease retained. Six closed trades net AUD -1.98 and exactly bridge 100994.79 to 100992.81. Raw: `runs/evidence/M20/w1-closeout-20260910T084421Z/raw/`. Separate verification: `runs/verification/M20/w1-closeout-20260910/verify_retained.py` and `result.json`. Review: `docs/reviews/w1-closeout-astra-20260910.md`.

The next ordinary SELL 42235606 exposed a real failure in the newly added automatic drill: at 08:51:09 the scheduled task was Ready/result1 with no processes despite configured retries. The fixed listener recovery was performed under maintenance hold; by 08:52:43 monitoring was healthy. Broker account was AVAILABLE/flat at AUD 100992.55, post-recovery unresolved executions were empty, and expected balance matched. Original risk anchors and Option B pauses remain unchanged. The second close is broker/ledger evidence separately from the six-trade sample.

Terra is repairing drill bookkeeping so invalid/unwritable state cannot terminate protection, enforcing exact attempt+ticket recovery, and replacing exit-and-hope-for-task-retry with a supervised replacement worker. Astra also found that the old refusal probe called an obsolete sizing helper; the corrected probe shares the current loss calculation and validates quote UTC freshness. No trade is manufactured. Deployment and fresh refusal proof follow affected-area review under the existing hold.

Scope correction: unobserved partial fills, nonzero posted charges and overnight/special-day tariffs are explicit qualification gaps, not mandatory observations for the approved temporary intraday scope. Normal eligible-signal refusal is not an extra requirement invented by the handover. Actual production risk-calculation refusal and isolated reservation tests remain distinct.

**Wave 1 is not yet complete.** Required work includes reviewed repair/deployment, fresh applicable refusal proof with immediate original-lease restoration, exact final payload/configuration/limits binding and current recommendation. W1.R detached-T16/no-logon and incident-delivery proof still needs its explicit dependency disposition; backups alone are deferred to W4.0. Do not infer those capabilities from a listener-only restart or silently waive them. M20 retains its full independent capture/verification/Triad gates. No new wave, Live access or push is authorised.

## 2026-09-10 automated protected-restart trigger deployed

The operator authorised removal of the manual restart dependency. Commit `d897484` adds a T480-local one-shot trigger: after the first naturally accepted full Demo position has a durable `OPEN_MONITORING` record and broker SL/TP, it atomically records the bound attempt/ticket, exits the Scheduled Task once, and relies on the existing bounded task restart. Startup recovery records either `RECOVERED` for that exact open ticket or `CLOSED_BEFORE_RECOVERY`; terminal state prevents repetition. It never creates an order or changes broker protection. The focused listener and T480 adapter tests passed (95 tests total). The trigger is installed in release `fde38161fecebeae`.

During deployment a naturally open protected BUY `42234057` was present. A maintenance hold blocked new entries while preserving monitoring. The old listener was replaced through the hash-checked release path and the new release recovered the exact durable attempt `6170b7e5-bf55-5363-ab5f-160f6201fdf1` and ticket `42234057` as `OPEN_MONITORING`, with the original entry 1.16389, SL 1.16355 and TP 1.16445. A current broker account observation still reported one open position, and the new listener’s post-install monitor independently recovered the same ticket. This is genuine protected-position restart/recovery evidence with no duplicate entry. The maintenance hold was then removed; a fresh RUNNING heartbeat confirms ordinary Demo assessment resumed. Raw evidence is retained at `runs/evidence/M20/w1-automated-restart-20260910/raw/`.

The trigger was not exercised by this already-open position because it was installed after that entry. It is armed implicitly on the next newly accepted full protected Demo position and will execute exactly once without human action. Independent Astra evidence review remains required before treating W1.2/W1.4 restart proof as passed.


## 2026-09-10 natural position close and restart attempt

A naturally eligible Demo BUY (`42232651`, 0.01 lot) opened at 08:25:08 UTC with recorded broker protection: entry 1.16382, SL 1.16355 and TP 1.16422. The protected-restart drill began only after a current status observation, but broker history and matched PostgreSQL lineage show that the position had already closed at 08:28:05 UTC through its configured `COMPRESSION_BREAKOUT_M1_TWO_OPPOSITE_CLOSED_CANDLES` owner exit. The exact broker deals show a AUD -0.14 gross/net result with zero broker commission, fee and swap. The balance bridge moved from AUD 100993.78 to AUD 100993.64 and the current expected balance matches it.

The fixed `m20_listener_recover` action then restarted only the Session-0 `Forex-M20-Demo-Listener` Scheduled Task. A fresh RUNNING heartbeat and IDLE broker monitor followed, with no unresolved attempt or current account exposure. This is valid listener-restart and clean-lifecycle evidence, but **not** protected-open-position recovery evidence: the listener did not recover an open position because the broker close preceded the restart. Do not present it as satisfying W1.2/W1.4 restart proof. Retained raw evidence is under `runs/evidence/M20/w1-protected-restart-20260910/raw/`. No trade was forced, no Live surface was accessed, and no configuration or risk limits changed.


## 2026-09-10 ordinary assessment checkpoint after reviewed resume

A single current-state observation at 08:24:45–08:24:49 UTC confirms the approved `97d2bf75679b5ee4` listener is RUNNING on `GOMarketsMU-Demo`, with a fresh heartbeat and an IDLE monitor recovery result. The Demo account is AVAILABLE and flat at AUD 100993.78. Option B has no pause reasons, retains the same anchors and expected balance, and the unresolved-attempt summary is empty.

The listener's most recent ordinary assessment was persisted and reconciled as `NO_TRADE` / `NOT_SUBMITTED` / `NO_TRADE_RECONCILED`: each of the five fixed M1 strategies returned no actionable signal. It neither submitted nor fabricated an order. The status retains ticket `42220632` as historical `LAST_KNOWN_UNVERIFIED` protection context; the separately retained broker/ledger reconciliation above establishes that it is a matched broker-side closure, while this flat account observation establishes no current exposure.

No eligible position exists for the protected-restart criterion. Continue ordinary listener operation without polling from Codex; resume evidence work when the listener naturally produces an attributable protected open position or a real eligible restrictive-risk refusal. Raw governed operation records are retained by the adapter execution log. No code, deployment, risk mutation, trade, Live access or push occurred in this checkpoint.


## 2026-09-10 broker lifecycle reconciliation and reviewed Option B resume

A fixed bounded read-only adapter, `forex-m20-current-lineage-summary`, was added because the existing all-history lifecycle report exceeded the Windows command-line limit. It returns only the fixed 10 September 2026 UTC window and binds the original lease, proposal, decision snapshot, attempt, position events, matched outcome and persistent balance state. It performs no broker, database, risk-policy or deployment mutation. The focused adapter suite passed (18 tests); the adapter and T480 suites passed together (94 tests); `git diff --check` passed.

The retained broker history at `runs/evidence/M20/w1-resume-20260910/raw/current-wave1-history.json` and database lineage at `runs/evidence/M20/w1-resume-20260910/raw/current-lineage-summary.json` independently identify three ordinary GOMarketsMU-Demo EURUSD 0.01-lot positions under original lease `9673811b-0e23-47f9-b8e6-e0a86d1adf06`: `42217856` BUY, AUD -0.33; `42220054` SELL, AUD -0.32; and `42220632` BUY, AUD -0.36. Each had a paired opening/closing broker deal, a broker stop-loss close, zero broker commission/fee/swap, and PostgreSQL `OPENED` then `CLOSED` / `MATCHED` evidence. Their AUD -1.01 net exactly explains the balance change from AUD 100994.79 to AUD 100993.78. The current expected balance and independently observed broker balance both equal AUD 100993.78. This is explained broker price P&L, not an inferred external cash flow.

Astra separately reviewed the raw evidence and source. It accepted the bounded report and supported the authorised fixed risk-resume flow, while explicitly retaining the distinction between exact broker close timestamps and PostgreSQL observations 2–3 seconds later. The fixed resume operation recorded `0549ee05-cb28-40b8-b965-bf44d4704398` at 08:12:41 UTC. The next account check was AVAILABLE/flat at AUD 100993.78; `pause_reasons` is now empty, `cash_flow_review_approved` is false, and the Option B baseline, peak, daily and weekly anchors and original lease are unchanged. Raw post-resume proof is retained in `runs/evidence/M20/w1-resume-20260910/raw/risk-resume-after-reconciliation.json`, `risk-policy-after-reviewed-resume.json` and `account-after-reviewed-resume.json`. No order was forced, no Live surface was accessed, and no release was deployed.

**Wave 1 remains incomplete.** The listener can make ordinary Demo assessments within the existing temporary intraday policy, which expires at 2026-09-17T00:00:00Z. Remaining real-world proof is a naturally occurring protected open-position interruption/restart with recovered ownership/protection; a genuine eligible-signal restrictive-risk refusal; observed nonzero charges and partial fills if the broker produces them; and tariff/overnight-calendar qualification. The final current configuration/effective-limit binding, complete evidence bundle, independent verification and bound Triad recommendation also remain required. Do not force a signal, cash-flow adjustment, trade, overnight hold, or broker condition to satisfy these criteria.


## 2026-09-10 M1 repair complete and ordinary Demo assessments resumed

The three remaining M1 requirements are implemented in
`01c7546369e48912f36fa4f72cc25e1b156b97af` and deployed as
`97d2bf75679b5ee4`. Migration 023 was applied through its fixed hash-bound
operation under maintenance hold, preserving existing ledger records. All four
payload hashes passed prepare; configure/install produced a fresh held heartbeat.

Terra implemented current-UTC checks after blocking reads and immediately after
reservation, with original decision-minute and candle-digest binding. Invalid
history records NO_TRADE without invented bars. A refused reserved order records
terminal NOT_SUBMITTED and reconciles without phantom exposure; it still counts
toward cumulative notional. Reversal exits require fresh synchronized inputs,
while broker SL/TP and owner wall-clock exits remain available.

Final targeted validation passed 102 tests, including actual capture with the
real recheck, minute crossings during reservation and history reads, changed
history, valid submission controls, stale post-entry reversal versus fresh
controls, owner time exits, and real isolated PostgreSQL event/reconciliation
tests. Full repository verification then passed with the isolated PostgreSQL
fixture enabled. The isolated test server was stopped afterward. Synthetic tests
remain engineering evidence, separate from the operating account.

Astra's separate read-only source/test review passed. Its final deployed-evidence
review returned **ENTRY_RELEASE_ALLOWED** for ordinary assessments and only
otherwise-eligible Demo trades. See
`docs/reviews/w1-m1-synchronization-review-20260910.md`. Raw capture is under
`runs/evidence/M20/w1-m1-final-20260910/raw/`; the separate offline deployment
verifier and test output are under
`runs/verification/M20/w1-m1-final-20260910/`.

Under the existing operator authority, maintenance hold was removed only after
that review. At 04:28:06 UTC, the listener was RUNNING on the new release, with
an ordinary completed assessment at 04:28:03. The observed M1 close was 04:28:00,
not stale cached history; outcome was NO_TRADE / NOT_SUBMITTED /
NO_TRADE_RECONCILED. Proposal `766f5469-228e-593c-a740-69ca83bff833` retained the
original lease `9673811b-0e23-47f9-b8e6-e0a86d1adf06`. The before/after deployment
risk state and anchors matched exactly; Demo was AVAILABLE/flat at AUD 100994.79
with no unresolved attempts. No risk resume, lease replacement or forced trade
occurred. The configuration fingerprint remains
`sha256:16abde21dc56729b2418f9c48d7091362a3c7622f976e3bb36e49f8492e0fb67`.

**Wave 1 remains incomplete.** The listener may now run continuously and assess
normally; before 06:00 UTC (18:00 NZST) financing refuses entries. Later trades
still require every data, strategy, cost, lease and Option B gate. The temporary
intraday policy expires at 2026-09-17T00:00:00Z and is not extended.
The next evidence opportunity is an ordinary eligible Demo lifecycle, actual
broker accounting and a protected-position restart; eligible-signal refusal and
other unobserved contract cases remain explicitly unproven. Collect evidence
when that external opportunity exists; do not force signals or wait in an AI
market-polling loop. Backups remain deferred to W4.0. This scoped Astra review
does not replace final bound Triad/M20 proof and grants no Live authority.

The existing goal record was inspected and still reported blocked with aggregate
usage but no numeric remaining-budget field. No replacement goal or budget
increase was created. This checkpoint records authorized resumed work, not
goal completion or a change to its controller state. No push occurred.

## 2026-09-10 deployment recovery — installed under hold; entry review still blocked

The transfer blocker is resolved. The existing fixed operation
`python3 scripts/postgres_pgvector_adapter.py forex-m20-stage-listener-release --approve`
successfully transferred all four payloads using SCP. It already documents the
Windows inline Base64/ssh launch failure encountered by the older fragment
path. No host permission, antivirus, SSH configuration or shared transport
change was needed. Use this operation for release transfer, with the release
directory established by the fixed first staging operation when necessary;
then require prepare/hash verification before stopping the held listener,
configuring and installing. Avoid repeating long inline fragment transfers.

Source `d44fee9` (application binding `cd91ed0`, a documentation-only descendant)
is now installed as release `e0fcf2590a81cd2e`. All four staged hashes passed
prepare. Configure and install succeeded; the 03:58:29 UTC heartbeat confirms
the new release running in `MAINTENANCE_HOLD`, successful empty monitor recovery,
and assessment total unchanged at 5853. The governed fingerprint remains
`sha256:16abde21dc56729b2418f9c48d7091362a3c7622f976e3bb36e49f8492e0fb67`.
No lease activation, risk resume, database migration or hold release occurred.

Raw before/after broker, risk, unresolved-attempt and deployment observations
are retained separately under
`runs/evidence/M20/w1-deploy-recovery-20260910/raw/`; offline verification is in
`runs/verification/M20/w1-deploy-recovery-20260910/`.

**Source review remains BLOCK_ENTRY.** This deployment resolves the requested
transport/install failure, but the previous repair did not satisfy the complete
Astra brief. `_entry_m1_history_is_synchronized` checks the captured window
against the original quote, without a new check before submission. The reversal
monitor remains capable of acting on old bars because its reader and predicate
were intentionally unchanged. Malformed/insufficient bar parsing still raises
before proposal persistence. The earlier claim that all such inputs become a
persisted non-actionable assessment is therefore too broad. These remaining
requirements must be repaired and tested before entry release. Neither this
operational recovery nor the earlier 69 tests establishes Wave 1 completion.

## 2026-09-10 M1 synchronization repair — deployment blocked, listener restored

Terra implemented the entry-only repair in commit `d44fee90bf25135b831fa2bd310a44d397d36751`.
It replaces the insufficient M1 count test with a fixed, fail-closed input
contract: exactly 64 chronological, contiguous one-minute candles must end at
the current observed quote's minute boundary. A stale, gapped, duplicate,
out-of-order, malformed, or future M1 entry window therefore records the
existing `completed_m1=false` safety gate and becomes a persisted non-actionable
assessment. No candle is filled or inferred.

The repair deliberately does **not** alter `_bar_rows()` or
`_closed_m1_bars_for_monitor()`. Existing broker SL/TP, owner wall-clock time
exits, and the monitor's protective exit path remain available even while entry
history is delayed. Option B and the W1.R maintenance hold are unchanged.

Focused tests passed: fresh current-boundary history, one-minute stale history,
a gap, a future window, and the separate monitor parser (`pytest -q
tests/test_t480_adapter.py`, 69 passed). `python3 -m py_compile
t480/m20_demo_trading_session.py` and `git diff --check` also passed before the
commit. This is engineering verification, not broker proof.

The hash-bound release deployment was attempted only after a current
`GOMarketsMU-Demo` account observation confirmed AUD 100,994.79 balance/equity,
zero available open positions, and no unresolved execution. The maintenance
hold was written again, the listener was stopped, and listener staging parts
1–3 succeeded. Part 4 then failed twice before reaching T480 execution:
`Program 'ssh.exe' failed to run: Access is denied`. The deployment was not
prepared, configured, or installed. The recovery operation restored the prior
release `2329eea2d53bba6d`, which then produced a fresh
`MAINTENANCE_HOLD` heartbeat and an empty monitor recovery result. No assessment
or Demo order occurred during this work.

Raw adapter results are retained in
`runs/evidence/M20/w1-m1-synchronization-20260910/raw/`, including the fresh
Demo candle query, flat-account query, restored-held-listener query, successful
staging fragments, and the retained failed fragment-4 response. The adapter's
append-only execution log retains both failed attempts. The candle query
returned 72 M1 rates with `last_bar_time=1789023060`; it is a fresh terminal
history observation, not evidence that `d44fee9` is deployed.

**Astra hand-back status: deployment blocked.** Review the source change in
`d44fee9` now if useful, but do not issue an effective-release or entry
recommendation until T480 can run the fixed staging operation, the new release
is hash-bound and installed under hold, and a current held status confirms its
release ID. The exact resumption condition is repair of the T480/remote-executor
ability to launch `ssh.exe` for the fixed staging command; do not remove the
hold or retry entry while this condition persists.

## 2026-09-10 continuation checkpoint — inspection only, budget stop

**Wave 1 remains incomplete. No implementation, deployment, restart, risk
resume, hold release or trade was performed in this continuation.**

Read the supplied goal objective and the required wave guide, W1 specification,
W1.R package, resume prompt and this full report. Inspected Git status,
AGENTS.md, current project state, the complete active M20 contract, evidence
rules and current risk implementation. Preserved the existing wave/research
documentation edits, run-history changes and other local work.

The fixed read-only `m20_listener_status` observation at
`2026-09-09T23:28:12Z` (10 September 11:28 NZST) reports:

- release `c523b1c904b8aa51`, `state=STALE`, `running=false` as derived by the
  status helper from heartbeat freshness;
- last heartbeat `2026-09-09T22:46:03.472998Z`, age 2,528 seconds;
- last recorded detail is the maintenance hold, with an IDLE/empty recovery
  result at that old heartbeat;
- historical ticket `41760154` remains `LAST_KNOWN_UNVERIFIED`.

The adapter retained its raw operation response in its configured append-only
execution log. This is a new status observation, not current broker exposure,
proof of process termination or a verified live job handle. The actual task,
process and broker state require diagnostics before any restart. Do not infer
flat exposure from the stale empty recovery result. No current backup or
no-logon recovery proof was checked in this continuation.

Current `enforce_risk_policy` still stores a single `pause_reason` and only
evaluates weekly/drawdown breaches when it is empty. Day rollover clears a
daily reason. This confirms that the reviewed latch defect remains in source;
no new behavioural reproduction or fix was performed during this checkpoint.
The active M20 state remains `NEEDS_FIX`.

### Concrete remaining plan

1. Inspect actual scheduled-task/process diagnostics and current shared-runtime
   state without restarting a healthy service. Confirm maintenance hold and
   broker/audit exposure through the permitted serialized surface.
2. Reproduce overlapping daily/weekly/drawdown breaches with the actual risk
   function, then implement independent persistent reasons and resume handling.
   Test recovery, rollover, restart, cash-flow overlap and remaining headroom
   against isolated persistence. Preserve Option B thresholds and anchors.
3. Verify technical-stop sizing and cost/reservation headroom; prepare any
   exact required execution-rule amendment before dependent deployment.
4. Review and commit the narrowly scoped authorised fixes; prepare a hash-bound
   release and rollback. Preserve unrelated documentation/local work. Confirm
   shared backup/restore prerequisites before disruptive host/database drills.
5. Complete W1.R recovery and W1.1 effective-limit proof, W1.2 genuine lifecycle
   and interruption proof, W1.3 broker accounting/charge observations, W1.4
   protected-position restart and actual restrictive-limit refusal. Restore
   Option B immediately after the approved AUD 0.01 drill. Keep unobserved
   partial fills/nonzero charges explicitly pending where required.
6. Independently verify retained raw evidence and obtain required bound review;
   do not claim Wave 1 or M20 complete from local tests or this handover.

### Budget and resumption condition

The objective explicitly limits execution to 25,000 tokens. The active goal
mechanism has no recorded cap and provides no tool to change an active budget.
The first usage recheck reported **30,948 tokens**, exceeding the requested
limit during required document/current-state loading. Execution stopped at
this inspection checkpoint; the excess is disclosed rather than represented
as compliance. No budget increase or replacement goal was created.

Resume implementation only with renewed operator budget authority. Use this
checkpoint and the inspected current specifications to avoid another full
historical-report reload unless the objective requires it; inspect changes and
fresh external state. The goal remains unfinished, not complete or formally
blocked merely because its budget was exceeded.

## Earlier checkpoints — historical observations follow

Status: **IN PROGRESS — Option B and the corrected listener are deployed on Demo. The Windows/Ubuntu risk-resume defect is resolved and independently checked. Fresh lifecycle/recovery evidence and final bound verification remain. See the latest checkpoint below.**

## 2026-09-07 W1.R execution checkpoint — maintenance hold and T480 continuity

W1.R is in progress. The listener remains in the fixed
`W1R_COORDINATED_MAINTENANCE` hold, so it continues bounded broker-side
reconciliation but cannot assess a quote or submit a Demo entry. Do not remove
that hold while the recovery drill remains incomplete.

The following corrections are deployed on the fixed `GOMarketsMU-Demo`
surface:

- Every per-position recovery failure now makes the supervisor fail closed;
  a successful process exit cannot report `IDLE` over a failed recovery.
- A failed MT5 `positions_get()` result is reported as unavailable, rather
  than as zero positions.
- The listener status separates durable protection from fresh observation.
  The retained historical SELL ticket `41760154` therefore reports
  `LAST_KNOWN_UNVERIFIED`; it is not represented as a current protected
  position. A direct successful broker read at the maintenance boundary
  reported `GOMarketsMU-Demo`, AUD, and zero open positions.
- Release `c523b1c904b8aa51` produced a fresh `MAINTENANCE_HOLD` heartbeat
  and successful empty recovery. Its hashes and configuration were prepared
  before install. The installed listener now uses a Windows boot trigger with
  passwordless S4U for the registered user, rather than a logon trigger.

The shared T480 startup dependency was also tested without extending or
closing its M5 milestone. Its temporary S4U probe completed successfully and
could see the Ubuntu distribution. The original boot action was found to name
an unavailable `health_dashboard` Compose service in the deployed checkout;
this terminated its WSL keepalive even though already-running endpoints still
returned health responses. The shared correction starts only `n8n` (which
starts PostgreSQL through Compose dependency resolution) and relies on the
dashboard's own restart policy. It passed the shared local suite and the
updated boot-triggered S4U task was registered with the former task XML kept
on T480 for rollback. A manually started task returned Ready with n8n and
dashboard health endpoints responding, but that is not no-logon reboot proof.

The host reboot drill was intentionally not run. The shared maintenance
preflight did not provide a usable current backup marker, and the shared M5
contract says to stop in that condition. No claim is made about reboot,
detached-T16, or post-reboot recovery. The exact resumption condition is:

1. produce and independently verify a current recovery-safe backup marker on
   the shared T480 surface;
2. retain a new flat-account and active-hold broker observation immediately
   before the drill; and
3. run the approved reboot, then capture fresh task, WSL/PostgreSQL, MT5 Demo
   identity, listener and risk-state evidence without Windows sign-in.

W1.R has not supplied W1.2/W1.4 protected-position restart proof, a nonzero
broker-charge outcome, incident/notification delivery proof, the full
detached-T16 window, or the contract-required final independent review.
Those remain pending and Wave 1 is not complete.

## W1.1 completed locally

The development-phase total trade-count ceiling is removed. The canonical
runtime configuration, M20 contract wording, schema, fixed lease validator,
and audit bridge now require `maximum_trades: null`. This preserves the
independent one-open-position, per-trade notional, cumulative-notional, and
per-trade maximum-loss controls.

The USD 100,000 *cumulative notional* limit still remains. It is not a
trade-count control, but at the maximum USD 10,000 notional it can practically
limit a lease to ten full-size entries. It needs a separate operator decision
if development trading must be unlimited by both count and cumulative
exposure.

## W1.2 and W1.3 progress

The local runner now distinguishes an MT5 API error from an empty position
result, and refuses new execution when either position or deal-history reads
fail. A broker-reported full or partial fill is not called rejected merely
because terminal position observation fails: it is recorded as `UNKNOWN` and
the reserved attempt remains entry-blocking. Migration `017_m20_unresolved_execution_state.sql` is applied on the fixed Demo PostgreSQL surface; the changed runner still must be deployed before it can govern executions.

Closed-outcome reconciliation now queries the broker position identifier,
requires matching opening and closing market deals with equal aggregate volume,
uses the volume-weighted closing price, and retains commission, fee, and swap as
actual broker amounts. Spread/slippage estimates remain separate from actual
net P&L. Missing or incomplete broker history remains unresolved rather than
being archived as a failed close.

## Recommended low-risk Demo drawdown policy

This is a conservative starting policy for an unproven M1 strategy. It makes
continued operation conditional on capital preservation, not on producing a
trade count or income target.

| Control | Recommended value | Action at breach |
| --- | ---: | --- |
| Planned loss per new trade | Lesser of AUD 100 and 0.10% of policy equity | Refuse the proposal if minimum broker volume cannot fit. |
| Daily net-loss budget | 0.50% of policy equity | Pause new entries until the next Auckland trading day. Existing broker SL/TP remains managed. |
| Weekly net-loss budget | 1.00% of policy equity | Pause new entries until an operator reviews and resumes. |
| Peak adjusted-equity drawdown | 2.00% | Hard pause new entries until an operator reviews and resumes. |
| Unknown equity, account currency, cash flow, position, protection, or reconciliation | Zero tolerance | Fail closed: no new entry; preserve and monitor any protected open position. |

### Definitions

- **Policy equity** is the reported AUD account equity after approved external
  cash-flow adjustments. It is never inferred from deposits, withdrawals, or
  balance adjustments.
- **Adjusted equity** = broker equity minus approved deposits plus approved
  withdrawals made after the policy baseline. A balance or cash-flow change
  without a matching, durable operator record blocks new entries.
- **Daily net loss** compares current adjusted equity with the fixed Auckland
  day-start adjusted-equity anchor. It includes unrealised P&L and therefore
  does not wait for a trade to close before stopping further risk.
- **Weekly net loss** uses the same method from the Monday Auckland anchor.
- **Peak adjusted-equity drawdown** is the loss from the highest durable
  adjusted-equity observation since the operator set the baseline. It includes
  unrealised P&L and never resets automatically.
- **Net** means the broker account result after actual fills, commission, fees,
  and swap. Execution estimates remain separate and are not subtracted again.

### Durable pause and reset rules

Persist the baseline, anchors, peak, expected broker balance, approved cash-flow adjustment, and pause reason in the PostgreSQL audit state. A listener restart or a new
Demo lease reads this state before it may reserve an order.

- A daily pause expires only at the next Auckland day boundary after an
  account/equity read succeeds. It does not clear a weekly or drawdown pause.
- Weekly-loss, peak-drawdown, and cash-flow pauses require the fixed
  `m20_listener_resume_risk_policy` operator action. It writes an append-only
  resume request; the next account check re-applies all limits. For an external
  cash flow only, that review shifts balance and equity anchors by the observed
  cash-flow amount so adjusted-equity drawdown remains continuous.
- An operator cannot reset the peak merely by creating a new lease. Resetting
  a baseline needs a separately recorded capital change and a new approved
  policy revision.

## Proof still required

Local tests do not prove W1. The changed release must be staged on the fixed
Demo surface, its effective limits read back, and then independently checked.
W1.2 and W1.3 remain in progress: MT5 API error handling, partial-fill state,
and broker deal-history reconciliation require further implementation and
Demo evidence. Option B values and pause authority are now approved. Migrations 016 through 021 have been staged and applied successfully to the fixed Demo PostgreSQL surface; the read-only audit verifier passes. The remaining decision is whether USD 100,000 cumulative notional should remain during the development phase.

## 2026-09-07 deployment correction

The previously deployed listener release `402ea373eafcc9f2` did not include the
Wave 1 risk guard and its risk-policy state was uninitialised. It was idle with
no protected position, and the fixed listener-stop operation returned `stopped: true`.
The legacy status operation is not a valid independent stop check because it
auto-restarts a stale listener; the pending release removes that side effect.
The pending release makes listener status read-only; recovery remains a separate
fixed operator operation so an inspection cannot restart execution.

The T480 endpoint rejects commands above roughly 2.5 KB. The deployment
protocol now uses fifteen service fragments, sixty-four runner fragments, and
thirty-two audit-bridge fragments. It verifies all four staged payload hashes
in a short fixed operation, records that release, and only then writes the
non-secret configuration containing the governed risk policy. This preserves
the configuration-to-release binding while fitting the endpoint limit.

The deployment source is committed because its configured application revision
is bound to `git HEAD`.

## 2026-09-07 Demo deployment evidence

Release `274556076400bc3c` was staged and installed after the remote SHA-256
checks for the listener, runner, PostgreSQL audit bridge, and Discord adapter.
The task produced a fresh heartbeat on `GOMarketsMU-Demo` for EURUSD and made a
valid `NO_TRADE` decision; it did not place an order.

The new continuous Demo lease is `3a44122e-4575-4e08-b632-8a506afc7293` and
has `maximum_trades: null`, one open position, USD 10,000 maximum notional per
trade, USD 100,000 cumulative notional, and AUD 100 maximum loss per trade.

The remote PostgreSQL policy state was initialized in AUD at policy equity
AUD 100,995.51, with no pause. It recorded the Conservative Option B policy
and its daily 0.50%, weekly 1.00%, and peak drawdown 2.00% controls. The
read-only audit verifier returned `FOREX_M20_DEMO_AUDIT_VERIFY_OK` after
deployment.

This is deployment proof, not milestone closeout. A post-release accepted
broker lifecycle with fee-complete reconciliation, independent verification,
and the contract's review recommendation remain required.

## 2026-09-07 unresolved-exposure gate

The deployed listener was restarted through its fixed recovery action after a
stale heartbeat. It produced a fresh heartbeat, then correctly failed closed
at the database one-position gate. The listener reported no protected current
broker position, but that observation cannot close a historical attempt.

The fixed read-only `forex-m20-unresolved-attempt-summary` identifies four
legacy attempts with `OPENED` then `FAILED` events. Each lacks a broker order
reference, position ticket, and position identifier. They are:

- `feffc714-c88f-5d34-bdca-705040a28565`
- `e0dac54c-6b56-5a84-9022-126c3c21e00b`
- `15dffa0b-0446-500c-af09-ddce686e11f9`
- `c66d1af4-3d00-56a8-83e2-881f1eec416b`

The gate must remain closed: a flat current terminal result cannot establish
how any of these historical broker executions ended. W1.2 and W1.3 are
**PENDING**, not failed, while retained broker history is insufficient to map
each attempt to exact opening and closing deals and their fees. W1.4's
open-position restart drill is also **PENDING** because no safely attributable
protected position is available.

Resumption requires retained broker deal/order history that identifies each
attempt's exact broker position, or a separately approved, hash-bound
reconciliation procedure that can prove the mapping without overwriting the
append-only audit record. Until then the listener may run only as a
fail-closed observer; it cannot submit a new order.

## 2026-09-07 retained broker-history attribution

The fixed `m20_unresolved_history_probe` read the Demo EURUSD deal history
for the four unresolved timestamps. It applies the governed +10,800-second
broker timestamp offset before comparison. Each mapping is unique by adjusted
open time, action, and 0.01-lot volume:

| Attempt | Broker position | Open UTC | Close UTC | Net AUD | Broker charges |
| --- | ---: | --- | --- | ---: | --- |
| `feffc714-c88f-5d34-bdca-705040a28565` | 41488649 | 09:18:05 | 09:28:07 | 0.18 | commission 0, fee 0, swap 0 |
| `e0dac54c-6b56-5a84-9022-126c3c21e00b` | 41495536 | 11:18:08 | 11:21:00 | 0.01 | commission 0, fee 0, swap 0 |
| `15dffa0b-0446-500c-af09-ddce686e11f9` | 41499398 | 12:04:03 | 12:13:02 | -0.56 | commission 0, fee 0, swap 0 |
| `c66d1af4-3d00-56a8-83e2-881f1eec416b` | 41499981 | 12:13:07 | 12:15:01 | -0.21 | commission 0, fee 0, swap 0 |

This closes the retained-broker-history gap, but does not alter the immutable
audit. The current bridge correctly refuses `record-closed-outcome` without a
durable open-position state row, which these legacy attempts predate. The
remaining W1.2/W1.3 implementation is a fixed append-only historical
reconciliation action that validates these deal sets, appends provenance and a
reconciliation revision, and never modifies the existing `OPENED` or `FAILED`
events. Until it is independently verified, the global one-position gate must
remain closed.

## 2026-09-07 fixed retained-history reconciliation prepared

A local, hash-bound reconciliation path is prepared for the four attributed
legacy attempts. It has no caller-supplied account, symbol, position, deal, or
SQL input. It re-reads each exact Demo broker position identifier, requires two
EURUSD market deals with the recorded UTC timestamps, directions, 0.01-lot
volumes, and AUD net P&L, then asks the audit bridge to append the following
new records:

- one immutable `CLOSED` event carrying the complete broker deal set and its
  SHA-256 digest;
- one fee-complete `MATCHED` AUD outcome, with unavailable historical
  spread/slippage estimates kept `NULL`; and
- one immutable `REPAIRED` reconciliation revision whose source records the
  absence of a legacy outcome.

The existing `OPENED` and `FAILED` events are not modified. The action cannot
submit or modify an order, and it does not change the persistent risk-policy
state: the policy baseline was initialized after these historical closes, so
adding their P&L to `expected_balance` would create a false cash-flow signal.

The reconciliation is not yet deployed or executed. It changes the governed
T480 command catalog, so it needs a new revision, configuration-fingerprint
refresh, hash-checked release deployment, and an explicit operator decision
before the append-only remote database write. Local validation covers all four
broker deal mappings and the broader Wave 1 focused test suite; the current
milestone validator correctly reports configuration-fingerprint drift until
that governed configuration is formally adopted.

## 2026-09-07 retained-history reconciliation executed and verified

Release `073853dd0cce8d57` was hash-verified, prepared, configured, and
installed on the fixed `GOMarketsMU-Demo` EURUSD listener surface. The first
reconciliation execution failed closed before writing because the bridge lacked
a UUID function import. The defect and deployment guard were corrected in
commits `5b1a0d8` and `4c3a845`; installation now refuses a release that lacks
a successful hash-bound preparation.

The corrected fixed reconciliation then completed with
`FOREX_M20_HISTORICAL_RECONCILIATION_OPERATION_OK`. It appended all four
broker-attributed legacy lifecycles. The independent read-only unresolved
summary is now `[]`. The lifecycle ledger records, for every recovered attempt,
`OPENED`, `FAILED`, and appended `CLOSED` events, a `REPAIRED` outcome, actual
commission, fee, and swap of AUD 0.00, and the retained broker-history reason.
The recovered net total is AUD -0.58.

The persistent conservative-risk policy remains unpaused, with the original
AUD 100,995.51 baseline, expected balance, peak, daily anchor, and weekly
anchor. The reconciliation did not treat historic P&L as a current cash flow.
The independent audit verifier returned
`FOREX_M20_DEMO_AUDIT_VERIFY_OK`, including Demo-only, cap, idempotency,
immutable-trigger, and fee-completeness checks. The listener then produced a
fresh `RUNNING` heartbeat and a normal `NO_TRADE` assessment without a
protected broker position.

This clears the four legacy unresolved-attempt blockers for W1.2/W1.3. Wave 1
is still not complete: it needs a clean, post-release accepted Demo
`OPENED`-to-`CLOSED` lifecycle with broker fees, the W1.4 restrictive-risk and
recovery drills, retained raw proof, independent verification, and the
contract-required review recommendation.

## 2026-09-07 Wave 1 resumed: current lifecycle, liveness, and safe checkpoint

At 02:40 UTC, the fixed read-only listener status was stale on deployed release
`073853dd0cce8d57`. Its last durable monitor record named the unresolved Demo
SELL attempt `a78aec5c-6dd3-5f91-aaa4-464571e2cc93`, broker position
`41751387`, with its recorded SL and TP. The weaker account-liquidity helper
reported zero positions, but it intentionally treats an unavailable MT5
position result as an empty collection and therefore could not close that
attempt.

The fixed `m20_listener_recover` operation restarted only the existing
`Forex-M20-Demo-Listener` Scheduled Task. It did not expose an arbitrary order
operation. The restarted monitor reconciled that durable attempt to a
broker-side close at 14:40:43 NZST. The independent lifecycle summary reports
an exact `OPENED` then `CLOSED` lifecycle, entry 1.16085, exit 1.16106, AUD
realised P&L -0.29, and broker commission, fee, and swap each AUD 0.00. Its
reconciliation status is `MATCHED`; the unresolved-attempt summary is `[]` and
the independent audit verifier returned `FOREX_M20_DEMO_AUDIT_VERIFY_OK`.

At 02:44 UTC the existing deployed listener was again `RUNNING` with a fresh
heartbeat, an IDLE successful monitor result, and no current protected
position. This is a current operational observation, not a final evidence
bundle or a claim of continuous uptime. The zero broker charges make this a
fee-complete zero-charge lifecycle; it does not demonstrate nonzero-fee
handling, which remains pending actual observation.

The risk state is fail-closed with `EXTERNAL_CASH_FLOW`, even though its
expected balance and observed account balance both now equal AUD 100,995.22.
The likely sequence is that the restarted runner assessed balance before the
supervisor reconciled the already broker-closed tracked position; it briefly
saw the -0.29 realised trade movement as unexplained cash flow. This is an
inference from the persisted timestamps and state, not a claimed direct remote
exception trace. No resume action was issued. The pause prevents new entries
until a recorded review, so it is safe but not correct evidence of an actual
deposit or withdrawal.

Local changes now make startup reconcile durable open-position state before
the first assessment/risk gate, and fail closed with
`MONITORING_UNAVAILABLE` if that reconciliation cannot run. They also prevent
a bounded monitor pass from causing a negative `sleep()` interval and a stale
supervisor. Focused listener, M20 trading, T480 adapter, and runtime-config
tests pass, as do milestone governance validation and `git diff --check`.
These changes are **not deployed**: the T480 release protocol binds
`application_revision` to `git HEAD`, and this goal does not authorise a
commit. Do not stage, prepare, configure, or install this uncommitted source as
proof for the existing revision.

### Exact resumption conditions

1. Obtain explicit commit authority for the reviewed listener and test changes.
   Commit the exact source, then refresh any affected fingerprint and stage,
   prepare, configure, and install its hash-bound release. Capture a fresh
   listener status and strict lifecycle/risk summaries after deployment.
2. Verify the false `EXTERNAL_CASH_FLOW` pause was not caused by a real account
   cash flow. If it was not, use the fixed resume action only after that
   operator review, then verify the next account check remains unpaused and
   matches expected balance. If it was real, record the approved cash-flow
   adjustment instead; do not resume on inference alone.
3. Obtain an explicit temporary restrictive-limit value and restoration
   procedure for the W1.4 refusal drill. Run it only against the deployed
   hash-bound release, with no intentional loss, and retain before/after risk
   state plus restart/protected-position proof.
4. Capture a clean-worktree, post-deployment M20 evidence bundle and run the
   independent verifier. Current documentation and uncommitted source make the
   fixed capture command correctly refuse a bundle today. A fresh zero-charge
   lifecycle exists, but a nonzero broker charge remains an explicit pending
   W1.3 condition when the broker supplies one.

Wave 1 remains **IN PROGRESS**. No M20 closeout, production access, strategy
expansion, new lease, risk-policy resume, commit, or deployment was performed
by this checkpoint.

## 2026-09-07 authorised deployment and W1.4 refusal drill

The operator authorised the reviewed changes, confirmed that no external cash
flow occurred around the AUD -0.29 close, and approved an AUD 0.01 temporary
planned-loss limit solely for the refusal drill. Commits `71eb182` and
`83f302f` deployed release `29072a8900d6831b` with configuration fingerprint
`sha256:8a4f7d278e3b536b31f7f6c272ce032719877af7075c62cdd60ab0c1ae3a55e6`.
The release hash gate initially rejected a duplicated staged service segment;
no deployment occurred until a clean restage passed prepare, configure, and
install. The new listener then reported a fresh `RUNNING` heartbeat, an IDLE
empty durable-position recovery, and no protected position.

For the drill, the listener was stopped before the temporary five-minute
Demo-only lease was installed. The fixed no-order calculation used live
GOMarketsMU-Demo EURUSD metadata: minimum volume 0.01 and a minimum-increment
loss of AUD 0.013893. That exceeds the approved AUD 0.01 cap, so it returned
`FOREX_M20_DEMO_RISK_REFUSAL_DRILL_OK` with
`M20 minimum EURUSD price increment exceeds the AUD loss cap` and
`order_submitted=false`. The standard continuous Demo lease was restored
immediately with the approved AUD 100 maximum loss, then the listener was
restarted and verified healthy.

The authorised `resume-risk-policy` request could not be recorded because its
local PostgreSQL connection at `127.0.0.1:5432` closed unexpectedly. The
persistent risk state therefore remains fail-closed; no entry is authorised
until that database path is healthy, the fixed resume request succeeds, and a
subsequent account check verifies the expected balance remains aligned. This
deployment and drill do not close Wave 1: fresh retained evidence, independent
verification, the required protected-position restart/recovery proof, and the
contract-required review recommendation remain outstanding.

A subsequent T480 PostgreSQL health probe reported the container healthy and
accepting local connections, but one immediate retry of the fixed resume
request produced the same connection-closed error. Treat the database path as
unavailable to the listener until its application connection succeeds; do not
retry it in a tight loop.

### Connection-path correction

The follow-up investigation identified an application adapter defect, not a
PostgreSQL outage. The trading runner's `_bridge()` invokes the verified bridge
inside T480 Ubuntu, where PostgreSQL is loopback-bound. The fixed resume action
instead invoked that bridge with Windows Python. The same `127.0.0.1` DSN then
addressed Windows rather than Ubuntu. At 03:01 UTC the listener's recovery and
independent PostgreSQL summaries were successful; the durable entry block was
still `EXTERNAL_CASH_FLOW`, with expected balance AUD 100,995.22 and no resume
record. The earlier statement that the listener's database path was unavailable
was therefore incorrect.

The resume adapter now invokes the same fixed Ubuntu bridge, retaining its
source hash check. It forwards the existing local DSN through `WSLENV` by name
and restores the previous environment afterward. No database endpoint, SQL,
account, or order parameter is exposed. Adapter regression tests and governance
validation pass. The existing operator confirmation of no external cash flow
authorises the recorded resume; its real-world result and subsequent balance
check must still be captured before claiming the blockage resolved.

### Resume verified on Demo; remaining Wave 1 proof

Commit `7d50038` fixes the resume adapter. The unchanged runtime payload release
`29072a8900d6831b` was hash-checked, rebound to that committed application
revision and the unchanged `sha256:8a4f7d278e3b536b31f7f6c272ce032719877af7075c62cdd60ab0c1ae3a55e6`
configuration, and restarted without replacing the current session lease.
The corrected resume succeeded at 03:03:31 UTC and created audit record
`b8694a8c-e227-4857-ae71-41e333d88d1c` for the reviewed `EXTERNAL_CASH_FLOW`
pause.

At 03:04 UTC, the subsequent risk check showed `pause_reason: null` and
`cash_flow_review_approved: false`. Expected balance, broker balance, and broker
equity all equalled AUD 100,995.22. Baseline, peak, daily anchor and weekly
anchor stayed unchanged at AUD 100,995.51. The strict durable-position recovery
succeeded with an empty result; the listener heartbeat was fresh. The
read-only audit verifier passed its Demo-only, exposure, proposal-first,
idempotency, append-only and fee-completeness checks. The temporary AUD 0.01
drill was not repeated and the approved Option B limits remain in effect.

Raw operation responses are retained unchanged under
`runs/evidence/M20/w1-resume-20260907T030324Z/`. Independent offline assertions
compared before/after state, the resume ID and timestamps, observed account
values, unchanged anchors, recovery, and audit output; the result and SHA-256
input hashes are separate at
`runs/verification/M20/w1-resume-20260907T030324Z/resume-verification.json`
(`FOREX_W1_RISK_RESUME_VERIFIED`). These are operational evidence, not a final
M20 bundle. The focused M20, adapter, accounting-dashboard and configuration
test suites passed, as did governance validation and `git diff --check`.

| Item | Current result and remaining condition |
| --- | --- |
| Reported PostgreSQL/resume blockage | **PASS — resolved.** Resume writes and subsequent risk checks work through T480 Ubuntu. |
| W1.1 release/configuration alignment | Rebound to `7d50038`; final effective-limit comparison in the bound Wave 1 bundle remains **PENDING**. |
| W1.2 lifecycle/recovery | The last retained matched lifecycle is the earlier AUD -0.29 close. The current lease `9673811b-0e23-47f9-b8e6-e0a86d1adf06` has no execution yet in the captured summary. Its genuine opened-to-closed lifecycle and controlled interruption/recovery proof remain **PENDING**. |
| W1.3 accounting proof | New sample must retain attributable raw broker deals and independently recompute fills, fees and net totals. Nonzero charges and partial fills remain unobserved; no synthetic observation is counted as broker proof. |
| W1.4 risk recovery | Resume and unchanged anchors across the flat restart/session history are verified. Restart with an actually open, broker-protected position remains **PENDING**. The prior AUD 0.01 calculation-only probe does not by itself demonstrate a listener assessment refusal or open-position recovery. |
| Final verification/review | **PENDING** until the required observations exist. No wave/milestone completion is claimed and no next wave is started. |

A clean detached worktree at `/tmp/forex-wave1-7d50038` is prepared for the
existing capture script; its governance and T480 preflight pass. This preserves
the main checkout's unrelated research/prompt work without weakening the
clean-revision rule. Do not invoke or recapture repeatedly while the required
lifecycle is absent. Resume proof work when the ordinary approved Demo listener
has an eligible protected position for the recovery drill and a current-lease
broker close. Preserve the lease and caps; do not force a trade or renew a lease
to manufacture evidence. No further operator decision is needed for the
resolved connection defect.

### Protected-open Wave 1 alert

The listener now issues one best-effort Discord message after all three real
conditions hold: the broker position is observed with positive entry, stop and
take-profit values; PostgreSQL has accepted the durable `OPENED` record; and
the local monitor job has been written. The message identifies the Demo EURUSD
side, volume, ticket, entry, SL and TP, then asks the operator to resume Wave
1. It cannot submit, modify, close, delay, or invalidate an order or lifecycle.

The listener status returns only `discord_open_alert_configured`, never a
webhook URL. Deployment preserves an already configured T480-local Discord
setting. The status must be `true` before the first eligible open; a synthetic
message is not proof and was not sent. The alert complements the dashboard; it
cannot automatically resume a Codex goal.

### SuccessByCS alert configuration and current availability checkpoint

At 05:39 UTC, the operator authorised use of the locally configured
SuccessByCS bot. The T480-local listener configuration was updated from the
existing local CSP configuration without printing, copying into the repository,
or committing the webhook secret. Release `8237331c7fa79d5a`, bound to source
revision `63b9a30d654186eb129aed6581a02a73d233e1c9` and configuration fingerprint
`sha256:da580b9e9131ff01987835cada4a7ada82465fdd3900fc38b8809d572a219eb5`, was
installed successfully. The status surface reported
`discord_open_alert_configured: true`. It does not expose the webhook URL.

The latest read-only status at 05:44 UTC then reported a fresh supervisor
heartbeat but `MONITORING_UNAVAILABLE`: its bounded durable-position monitor
received the MT5 error `Terminal: Authorization failed`. The listener correctly
failed closed and did not submit an assessment or an order. There was no open
position to protect. The fixed recovery operation at 05:45 UTC could not reach
T480 because SSH to `192.168.0.210:22` timed out during banner exchange; it did
not run and made no change to the scheduled task, broker, lease, or risk state.

Wave 1 remains **IN PROGRESS**. Resume when T480 is reachable, the MT5
GOMarketsMU-Demo terminal authorises again, and a read-only listener status
confirms a successful durable-position monitor before normal eligible Demo
operation continues. The next genuine protected `OPENED` event will send the
configured Discord alert, which is the cue to perform the authorised
open-position restart/recovery evidence drill. Do not force a trade, send a
synthetic Discord message, or treat the alert configuration itself as broker
proof.

### 2026-09-07 W1.R planning handover — not executed

The operator requested packaging of the reviewed fixes without execution.
[W1.R: T480 reliability and recovery](../prompts/demo-income-wave-1-recovery-work-package.md)
now supplies R1–R7, mapped to W1.1–W1.4, with owners, dependencies, acceptance,
real-world tests and rollback boundaries. The wave guide and both Wave 1 goal
entry points reference that package. This update changes planning documentation
only; no repair, deployment, restart, trade, goal resume or milestone transition
was performed, and no acceptance criterion is newly marked PASS.

The preceding review found intermittent SSH recovery and a shared PostgreSQL
shutdown/readiness gap from 15:47:10 to 17:39:15 NZST. Its cause was not proven.
The listener was reachable again at the review's 17:54 NZST snapshot. These
observations supersede the interpretation of a permanently offline T480, not
the need for current checks. They are not a final raw evidence bundle.

The earlier statement that there was no position to protect during failed
observation was too strong. Unknown broker exposure must remain unknown; an
empty durable recovery list or missing protection field is insufficient proof
of flatness. The review also locally reproduced per-position `RECOVERY_FAILED`
being presented as `IDLE`. R2/R3 schedule those corrections; they are not yet
implemented by this planning update.

Next execution, when explicitly instructed, begins with W1.R's diagnosis and
state-handling prerequisites, then coordinated maintenance, proposed platform
continuity proof and original Wave 1 evidence. Reuse prior risk decisions and
completed implementation. Resolve only missing authority/contract scope for
dependent shared-platform drills. Preserve the original proof gaps and do not
automatically start another wave or the lab's own milestone.

## 2026-09-10 continuation — independent risk pauses implemented, deployment pending

**Wave 1 remains incomplete.** The operator supplied an additional 50,000-token
allowance. Implementation commit: `3472885` (`fix(wave1): preserve independent
risk pauses and gate reservations`). No push, branch, next wave, Live access,
new Demo lease or maintenance release occurred. The final goal-tool check
returned no registered goal; no native budget enforcement or completion is
claimed for this continuation.

### Implemented and reviewed locally

- Migration 022 retains each risk pause independently, backfills an existing
  scalar reason, preserves anchors/resume history, and prevents a legacy
  scalar-only writer from silently clearing the new latches.
- Daily rollover clears only the daily latch. Weekly/peak/manual reasons
  survive recovery, week rollover and process restart. An operator resume
  acknowledges one manual reason and requires another account observation.
- The risk state binds to the verified Demo account identity using a hash;
  another account cannot inherit or reset it. Legacy state binds on its first
  accepted observation after migration; this does not prove historical identity.
- Remaining daily, weekly, peak and per-trade cash headroom limits new planned
  risk. Reservations and risk changes share a transaction lock across leases;
  the reservation rejects paused, stale, unbound or insufficient risk state.
  The runner refreshes account state before reservation. Existing global
  unresolved-attempt protection remains in place.
- At minimum volume, the executor retains the intended technical stop and
  refuses an unaffordable trade. The strategy documents now expressly remove
  stop tightening solely to fit the budget. This is the scoped W1.4 correction,
  not a new strategy or a change to Option B amounts.
- Fixed read-only task diagnostics expose task state, process identities,
  power settings and recent Python application events. The supervisor now
  retains bounded, redacted crash frames and retries a transient Windows
  status-file replacement failure at most three times. These changes are
  not deployed and do not establish the cause of the observed crashes.

### Validation and retained evidence

`scripts/verify_project.sh` passed, including **294 tests**, configuration,
registry, Triad-policy, secret and adapter checks. **23 tests use an actual
isolated PostgreSQL 16 instance** on localhost port 55481 and the dedicated
`forex_w1_test` database. Reservation refusal tests isolate proposal parsing;
they do not claim a complete broker execution or a concurrent end-to-end
order-race demonstration.

The original committed risk function reproduced the defect against PostgreSQL:
following a simultaneous breach, recovery and next-day rollover permitted entry.
The corrected function retains weekly and peak pauses. A separate actual restart
of the isolated database preserved its state exactly; a subsequent recovered
next-day observation still refused entry. All equity paths here are synthetic.

Evidence index: `runs/evidence/w1-continuation-20260910/index.json`.
Remote raw observations and local engineering outputs occupy separate
subdirectories. The index binds source hashes and implementation revision.
`runs/verification/w1-continuation-20260910/artifact-check.json` separately checks
artifact hashes, restart equality, retained manual latches, broker flatness and
operating pause preservation. This is a separate verifier process, not a Triad
recommendation, external witness or M20 proof bundle.

### Current T480 observations

- The listener was found stopped, task result **1**, and was recovered once
  under the existing maintenance hold. It subsequently exited again. The
  final status is **STALE**, old release `c523b1c904b8aa51`, last heartbeat
  `2026-09-09T23:44:21.611405Z`. Do not describe it as continuously running.
- Task diagnostics show S4U, no Forex Python process, and both battery-start
  prohibition and stop-on-battery enabled. No matching Python Application
  Error/WER event was returned. These settings are observations, not proof
  that battery state caused either exit. Historical Python exception frames
  were not retained; the new crash recorder addresses that diagnostic gap.
- A fresh read-only broker probe observed `GOMarketsMU-Demo`, AUD balance and
  equity **100,994.79**, and **zero open positions**. This is flatness at that
  capture, not a continuing guarantee or a reinterpretation of the old
  monitor-job ticket.
- The operating database still has `EXTERNAL_CASH_FLOW` paused, baseline
  **100,995.51**, expected balance **100,995.32**, unchanged anchors and its
  existing resume record. The AUD 0.53 difference from the new balance needs
  broker-ledger attribution. The operator's historical AUD -0.29 confirmation
  cannot be extended to this difference. No pause was cleared.
- The shared backup check returned a valid **PostgreSQL-logical** manifest
  captured on **2026-09-07 19:45 NZST**. It is older than the shared 24-hour RPO.
  The available shared handover reports isolated synthetic restore success
  but does not establish a verified retained full-lab T16 bundle. A current
  backup/restore evidence pointer was requested from the operator.

### Remaining criteria and resumption sequence

| Area | Status and exact remaining work |
| --- | --- |
| W1.1 / R4 | Local configuration fingerprint and migration artifacts updated. Obtain current affected-data backup and isolated-restore evidence; retain fresh broker/ledger/risk baseline, then stage migration 022 and the compatible reviewed release under the entry hold. Verify source hashes, task configuration and unchanged anchors before considering release. |
| W1.2 | Prior lifecycle repairs retained. Capture a genuine eligible Demo open-to-close lifecycle on the final release and independently reconcile protection, ownership and terminal/broker results. No manufactured signal or forced loss. |
| W1.3 | Broker charge and reconciliation proof remains incomplete. Qualify actual commission/financing/fee behavior and reconcile the current balance difference; preserve the cash-flow pause until its exact attribution and approved review are satisfied. |
| W1.4 | Independent latches and reservation headroom pass local integration checks. Planned-loss allowance currently includes stop distance and the existing spread-based slippage estimate; it still does **not** establish applicable commission, financing or other charges. Complete this qualification/integration, reservation concurrency proof and review of unknown-account manual-pause persistence before enabling entries. Then prove a real protected listener restart and the approved AUD 0.01 refusal drill, restoring Option B immediately. |
| R1 / R5 | Recurring task exit remains unresolved. Deploy the redacted crash recorder when deployment prerequisites permit, capture the actual failing frames, fix the supported cause, and demonstrate recovery. Do not infer battery causation or change startup principals blindly. Detached-T16 and separate flat/no-logon reboot windows remain unproven. |
| R6 / R7 | Local crash retention is implemented; bounded incident delivery/recovery proof and current independent review gates remain pending. Rebuild affected proof against the final contract, revision, configuration and broker evidence before claiming completion. |

The maintenance hold and independent risk pause must remain. Database migration,
reboot and other disruptive work remain blocked on current recovery evidence.
Do not close Wave 1 or M20 from this code commit or the passing local checks.


## 2026-09-10 operator amendment — core Demo function first

The operator explicitly directed: “push it out, we WANT THE CORE FUNCTION
WORKING FIRST.” Backup and isolated-restore evidence is therefore deferred
to **W4.0, before funded operation**. This supersedes the backup-based blocking
conditions in earlier checkpoints, including the preceding continuation.
No backup or restore success is claimed.

Wave 1 may proceed with reviewed Demo code deployment, migration 022 and
otherwise authorised recovery drills without awaiting backup evidence.
Existing Demo-only, Option B, maintenance-hold, fresh broker/audit flatness,
state-preservation and execution-proof requirements remain. No destructive
ledger reset or Live access is authorised by this amendment.

Next execution priority: verify current exposure and hold; deploy the reviewed
risk/diagnostic fixes with migration 022; diagnose and repair the listener exit;
finish fee/accounting and risk-gate checks; then collect the required genuine
Demo lifecycle/refusal/restart evidence. Do not resume the deferred backup
programme as a prerequisite or automatically start Wave 4.

## 2026-09-10 execution continuation — ledger repaired and candle feed recovered

This checkpoint supersedes the operational blockers above where explicitly
resolved below. **Wave 1 and M20 remain incomplete.** Backup/isolated restore
remains deferred to W4.0; it was not used to block this deployment.

### Changes and retained operating evidence

Evidence root: `runs/evidence/M20/w1-resume-20260910/`. Original tool responses
are retained under `raw/`; local tests and separate verification results are
not substitutes for broker evidence.

- Verified starting revisions `3472885` and `8076413` against current source.
  Preserved the existing Wave/Research edits. Scoped commits this continuation:
  `787a058` (fixed SCP release staging and retained-close reconciliation),
  `dd4a5be` (unknown-account latch and exact refusal-lease restoration), and
  `e16729b` (terminal history diagnostics and duplicate-terminal recovery).
  No push, branch or next-wave execution occurred.
- Initial fresh Demo observation: AUD balance/equity **100,994.79**, zero open
  positions. The unresolved execution was attempt
  `65915347-d4a1-53e2-94a2-dccfc41a164f`. Actual broker history identified order /
  position **41782938**, entry deal **34524700**, stop-loss close **34525414**,
  net **AUD -0.53**. Symbol, side, magic, protective prices and corrected broker
  timestamps matched its unique retained proposal. See `raw/demo-history.json`
  and `raw/reconciliation-context.json`.
- Applied `sql/operations/w1_reconcile_attempt_65915347.sql` once under the risk
  lock, appending the missing lifecycle events/outcome and adjusting expected
  balance once. Original attempts, leases and capital anchors were preserved.
  The operation rejects duplicate application. Reconstructed spread/slippage
  estimates remain unknown rather than invented. Actual commission, fee and
  swap on this close were zero. Post-baseline broker net **-0.72** reconciles
  baseline **100,995.51** to **100,994.79** with no external-cash-flow rows in
  the retained account window. Separate arithmetic/history verification:
  `runs/verification/M20/w1-resume-20260910/cashflow-attribution.json`.
- The operating unresolved-attempt query then returned an empty array. Applied
  migration **022** with the legacy cash-flow pause backfilled into the
  independent reason array. There was no ledger reset. Captured pre/post state
  demonstrates unchanged baseline, weekly and peak anchors during migration.
- The fully explained cash-flow pause was resumed through the audited fixed
  operation, resume ID `22179ea4-b2b9-4d78-8a5f-0e5f0d056f5c`. This uses actual
  attribution, not an extension of the operator's historical AUD -0.29 statement.
  Fresh subsequent account enforcement consumed the review flag and reported
  no active reasons. The daily anchor rolled normally to **100,994.79** for
  Auckland **2026-09-10**; baseline, weekly and peak remain **100,995.51**.
- Inline release transfer hit a Windows access-denied error before SSH on the
  second segment. The fixed SCP path transferred all four complete payloads;
  the existing prepare step verified their source hashes. Current deployed
  code release is **c1985bc7637d8712**. After the adapter-only recovery commit,
  prepare/configure rebound it to `e16729b` without replacing the lease or code.
  One stale-binding configure attempt was correctly refused before this
  successful prepare/configure sequence (`raw/bound-*.json`).
- Added persistent `UNKNOWN_ACCOUNT_STATE` latching on invalid entry-account
  observations. A later healthy observation does not clear this manual latch.
  The real isolated PostgreSQL tests verify latch/anchor persistence and two
  simultaneous reservation attempts across different leases: exactly one
  reserves and the other is refused by global position serialization.
  **25** real isolated-PostgreSQL tests passed; the final repository check
  passed **297** tests (`final-repository-tests.txt`). These are engineering
  checks, not proof of actual broker concurrency or funded suitability.

### Terminal incident: supported diagnosis, recovery and limits

The initial recurring listener exits had task result 1 and no retained Python
exception frames. The deployed crash recorder retains safe exception type and
bounded frames; no fresh equivalent crash has yet been captured. Do not claim
the historical process-exit cause is proven.

A separate concrete failure prevented assessments: both M1 and M5 bar requests
returned `Terminal: Call failed` although quotes/account queries worked. The
terminal log reported EURUSD history file-opening error **32**. Windows defines
32 as a [file-sharing violation](https://learn.microsoft.com/en-us/windows/win32/debug/system-error-codes--0-499-).
There were two processes for the same configured terminal executable, in
Session **0** and interactive Session **2**. With Demo freshly flat, no pending
orders, listener stopped and maintenance hold present, the fixed recovery
closed only the duplicate interactive process **17572**, preserving service
process **16340**. M1 immediately returned **72** bars and M5 **5** bars, both
successful, on the original Python API **5.0.6147**. See
`raw/terminal-session-diagnostics.json`, `raw/close-duplicate-terminal.json`, and
`raw/candles-after-duplicate-close.json`.

An isolated, hash-pinned API **5.0.6180** test had reproduced the same failure
before closing the duplicate. It was not promoted into the existing virtual
environment. Its candidate requirements and raw result remain in this evidence
root. No terminal history was deleted and no host reboot was performed.

**Operational prevention:** do not open the same configured MT5 installation
in an interactive RDP session while its autonomous Session 0 instance runs.
Use the Forex status surface; any separate chart terminal needs an independently
configured data directory. Recovery does not automatically kill terminals.
Detached-T16 duration and a separate flat/no-logon reboot test remain unproven.

### Entry boundary and remaining work

The observed historical intraday deals have zero commission, fee and swap;
that does not establish future financing terms. The forward cost model still
hard-codes zero commission/financing allowance and does not impose a holding
boundary before rollover. **Normal entry release remains held pending this
qualification.** An operator holding-policy decision has been requested:
intraday liquidation before broker rollover, or overnight holding with explicit
swap allowances. Do not silently invent a new forced-close policy. Obtain the
applicable account commission terms, then enforce the chosen financing boundary
in both projected net returns and planned loss; recapture affected proof.

Other outstanding Wave 1 criteria: genuine lifecycle on the final compatible
release; genuine risk refusal on an eligible signal; protected-position restart;
retained failure/recovery proof for the original recurring exit; detached/no-logon
operation and applicable incident delivery; independent final bound review.
No signals, fills, losses, fees or completion evidence may be manufactured.

### Final checkpoint, 2026-09-10 12:43 NZST

The second bounded refusal window, after history recovery, captured eight
observations: normal broker-data `NO_TRADE` assessments plus one temporary
fresh-quote wait that recovered. No eligible signal reached the planned-loss
refusal path. This is **not refusal proof**. The collector restored the hold
and the exact original lease in its finalization path; session ID remains
`9673811b-0e23-47f9-b8e6-e0a86d1adf06`, maximum planned loss **AUD 100**.
No order was manufactured to obtain evidence.

Final retained observations show a fresh **MAINTENANCE_HOLD** heartbeat at
`2026-09-10T00:43:21.741879Z`, task **Running**, listener processes in Session 0,
and no new recorded crash. Fresh broker observation is Demo/AUD,
balance=equity **100,994.79**, positions **AVAILABLE / 0**. Normal entries are
**not enabled**. This is a point-in-time observation, not a 30-minute detached
or reboot qualification.

`raw/post-recovery-audit.json` reports the operating Demo ledger audit passed:
Demo-only, caps, proposal-first, idempotency, immutable triggers, cost schema
and fee-incomplete exclusion. This does not certify prospective fee estimates.
Separate reproducible read-only checks and raw hashes are saved in
`runs/verification/M20/w1-resume-20260910/verify-recovery.py` and
`recovery-verification.json`; they explicitly leave lifecycle, genuine refusal
and historical exit-cause proof false. The isolated local PostgreSQL test
instance was stopped after testing; the operating database was not stopped.

**Resume:** obtain the pending holding-policy decision and applicable broker
commission/rollover terms; implement and verify fee-aware net/risk gates; then
release normal Demo entry only when those prerequisites pass. Capture a natural
eligible refusal in a bounded window with immediate Option B restoration,
a genuine lifecycle and protected restart. Keep recording any real recurrence
of the listener exit for a supported fix. Complete the remaining R5/R6 and bound
review evidence within Wave 1. No backup evidence is a prerequisite.

## 2026-09-10 swap-safeguard implementation checkpoint

Operator instruction: “execute this change”, following incorporation of the
swap-aware method into the waves. Executed the independent W1 calculator,
entry/risk and audit changes. W2/W3 were not started. **This is partial Wave 1
implementation and deployed engineering verification, not completion or proof
of an overnight edge.**

### Correction to the preceding holding-policy analysis

Current code already enforces owner-specific time exits: Range 6 minutes,
Compression 8 minutes, other M1 owners 10 minutes, plus existing protective
SL/TP and invalidation rules. The earlier implication that normal holding was
indefinite was incorrect. Rollover exposure can occur near the cutoff or when
an exit fails. These existing exits remain unchanged; continuous lease duration
is not unlimited position duration.

### Implemented and deployed

- `config/runtime.yaml` now holds a schema-validated financing mandate using
  existing owner exits, a 10-second observation-age ceiling, explicit calendar
  coverage/events and all-in round-trip commission/fee allowance per lot.
  Unverified calendar and charge terms are **null**, not zero. No numerical
  overnight holding rule or forced liquidation was invented.
- Added one pure signed points-mode EURUSD calculator in the fixed runner.
  It supports the observed USD-profit-currency mode, converts debits using
  AUDUSD bid and credits using ask, applies explicit rollover multipliers,
  retains source/capture/conversion timestamps and refuses unsupported,
  missing, stale, non-finite or inconsistent inputs. Other modes remain
  unqualified. Calendar completeness/holiday correctness requires broker
  qualification; a source label alone is not proof.
- Entry assessment uses the current maximum owner window (10 minutes,
  conservative for shorter owners). Unknown financing makes the proposal
  NO_TRADE. Known commission/fees and adverse swap enter planned loss at full
  precision before reservation. Positive swap cannot enlarge Option B capacity.
  Costs are refreshed before reservation; changed costs require reassessment.
- The v2 projected cost convention includes financing debits and charges;
  potential credits remain separately displayed and are not counted toward
  entry feasibility pending qualification. This is conservative TP feasibility,
  not calibrated expectancy. Actual broker net accounting remains unchanged.
- Decision snapshots retain financing inputs/mandate and a deterministic
  holding recommendation; the bridge accepts and checks the paired records.
  The evaluator returns HOLD/CLOSE/REVIEW_REQUIRED but grants **no execution
  authority**. With no W3 forecast it reports EVIDENCE_UNQUALIFIED. It does not
  yet schedule position-specific rollover reviews or route a new close rule;
  those dependent parts remain pending below, rather than being called complete.
- Added fixed read-only swap-term capture and a deployed financing preview.
  No order surface, lease replacement, risk-anchor reset or database migration
  was added. Source commits: `c192cf9`, then `dba0a16` to shorten the preview
  command after an actual Windows command-length failure. No push occurred.
- Deployed release **9f4601f3fd269894** under the existing maintenance hold,
  bound to `dba0a16`. All four payloads transferred by fixed SCP and passed the
  existing prepare/hash checks. Existing approvals and unrelated work preserved.

### Evidence and verification

Raw directory: `runs/evidence/M20/w1-swap-20260910/raw/`.
The broker capture reports points mode 1, long **-5.91**, short **+2.30**,
Wednesday triple-rollover flag, EURUSD contract size 100,000, minimum .01 lots.
These are observed terms, not proof of a posted charge or future rate stability.

The deployed read-only preview at `2026-09-10T01:30:54Z` observed those rates and
returned **UNKNOWN** for both sides because calendar/charge qualification is
absent; no order was submitted. Its original Windows command failure is retained
separately from the successful rebound result. Never replace this gap with an
assumed zero-cost calendar.

Repository verification passed **311 tests**, including **25** isolated real
PostgreSQL tests. Fourteen new financing tests cover debit/credit conversion,
triple treatment, boundary inclusion, missing/stale/future/invalid data,
financing-inclusive planned loss, conservative holding recommendations and an
actual assessment function refusing absent financing. The shortened adapter
also passed its focused checks. These tests use labelled synthetic fixtures;
they do not demonstrate broker swap settlement.

Separate read-only verification and raw hashes:
`runs/verification/M20/w1-swap-20260910/verify_preview.py` and `result.json`.
Final captured state: listener **running / MAINTENANCE_HOLD**; fresh Demo balance
and equity **100,994.79**, positions **AVAILABLE / 0**. No normal entry release,
new overnight authority or swap-posting reconciliation is claimed.

### Exact remaining dependencies and next action

1. Identify the actual Demo pricing arrangement and verify applicable commission/
   fee terms. Asked the operator whether it is Standard, GO Plus+ or another
   arrangement. Prior zero-charge closes alone do not establish future terms.
2. Qualify a timestamped broker rollover/calendar window, including applicable
   DST/holiday and daily multipliers; populate canonical fields from that source.
   The window must cover the intended position horizon; expiry refuses entries.
3. Prepare the exact approved cutoff/fallback and contract amendment before
   adding execution-influencing rollover exits (M20.13 currently analysis-only).
   Wire position-level scheduled/material-change reviews and their durable
   decisions through existing protection/recovery, without widening owner exits.
4. Capture genuine authorised Demo rollover postings and reconcile predictions
   within a predeclared rounding tolerance. Do not open or extend a position
   merely to produce proof. Scope intraday versus overnight qualification in the
   amendment; missing overnight cases are not a claim of intraday failure.
5. Finish the previously pending lifecycle/refusal/protected-restart and W1.R
   proof. W3, not this calculator, will establish a calibrated holding advantage.

Backup/isolated restore remains deferred to W4.0. No completion timestamps,
review recommendations or historical broker evidence were fabricated.

## 2026-09-10 continuation checkpoint — current release and pricing qualification

**Wave 1 and M20 remain incomplete.** This checkpoint records a fresh,
read-only operating observation after the execution brief was resumed. It does
not release normal entry authority, alter a lease, restart the service, or
claim a broker lifecycle.

Raw observations are retained in
`runs/evidence/M20/w1-continuation-20260910/raw/`. Their separate offline
verifier is `runs/verification/M20/w1-continuation-20260910/verify_current_state.py`.
It passed with marker `FOREX_M20_W1_CONTINUATION_VERIFIED` and checks the
captured hashes without contacting T480 or the broker.

- At 2026-09-10 03:12 UTC, the T480 Scheduled Task and its Session 0 listener
  were running on release `9f4601f3fd269894` under the existing maintenance
  hold. The retained account observation is `GOMarketsMU-Demo`, AUD,
  balance/equity AUD 100,994.79, with `AVAILABLE` positions and zero open
  positions. The historical ticket 41760154 remains explicitly labelled
  `LAST_KNOWN_UNVERIFIED`; it is not presented as live protection.
- The fresh fixed symbol observation remains EURUSD points swap mode 1: long
  -5.91, short +2.30, contract size 100,000 and Wednesday triple-rollover flag.
  This is a broker observation, not a qualified calendar, future quote, or
  posted-swap proof.
- The hash-bound deployed financing preview made no order and granted no
  holding authority. It returned `UNKNOWN` for both sides because the canonical
  policy has no verified calendar window or fee schedule. This is the intended
  fail-closed result, not a fault to bypass.
- Revalidated commits `c192cf9` and `dba0a16` against current source and ran
  the financing, T480 adapter and persistent-risk suites successfully (81
  passed; 25 PostgreSQL-dependent cases skipped because no isolated test
  database was started for this read-only checkpoint). The tests are labelled
  engineering evidence, not broker proof.

### Broker-source qualification result

GO Markets' Mauritius disclosure statement says Standard accounts have no
monetary commission and Plus+ accounts charge AUD 3 per side per 100,000 FX
units (AUD 6 round turn); it also says swap is charged or credited for a
position held at the close of the trading day, 23:59 platform time. The public
terms do **not** identify this specific Demo account's pricing arrangement,
account-specific concessions, server timezone/DST calendar, or future fee
schedule. Historical zero-charge intraday rows cannot prove those facts.

Before populating `financing_policy`, obtain the account's actual arrangement
(Standard, Plus+, or another documented arrangement) from its account record or
GO Markets, plus a timestamped rollover schedule that covers the intended
intraday horizon and identifies holiday/triple-day treatment. Then an exact
approved intraday cutoff/fallback and the M20.13 contract amendment are needed
before any execution-influencing exit change. Keep the existing 6–10 minute
owner exits unchanged until then.

### Proposed M20.13 amendment for operator review — not enacted

For this system's current intraday-only owner contracts, the conservative
proposal is: reject a new EURUSD entry when the next **broker-qualified**
rollover is less than 15 minutes away. Fifteen minutes comprises the longest
existing owner exit (10 minutes) and a five-minute execution/recovery buffer;
it is an operational margin, not an expectancy claim. Do not open a new
position over a weekend or public-holiday rollover window until a later,
separately qualified holding policy authorises it.

No existing position's stop, target, strategy-owned exit, or maximum duration
is widened by this amendment. If an existing position reaches rollover because
of a failed or uncertain exit, retain broker-side protection, record the
incident, and block dependent entries; never assume it closed or force a blind
flattening from stale data. The cutoff becomes effective only after the
operator approves this exact text, the M20 contract is amended, and the
calendar/fee inputs are qualified and deployed under maintenance hold.

The required Astra pre-entry review has **not** been performed in this
continuation: this execution used the available implementation model and no
model switch is implicit. Its narrow future input is the exact diff/configuration
for `c192cf9`/`dba0a16`, the broker-source qualification above, the deployment
rollback plan, and the retained raw/verification paths. It cannot substitute
for the repository's final Triad-plus-domain review or operator decisions.

## 2026-09-10 current-release W1.4 refusal drill

The operator's earlier approval of a temporary AUD 0.01 maximum planned-loss
limit was exercised on the current release `9f4601f3fd269894`, while the
listener was already in maintenance hold and the Demo account was flat. This
is a calculation-only drill; it did not manufacture a signal, submit an order,
or create a loss.

Raw operations are retained at
`runs/evidence/M20/w1-refusal-final-20260910/raw/`; the separate no-network
verifier is `runs/verification/M20/w1-refusal-final-20260910/verify_refusal.py`.
It verifies the captured configuration fingerprint, before/after flat account,
release, hold, exact lease identity, temporary cap and restoration.

- Temporary lease activation retained session
  `9673811b-0e23-47f9-b8e6-e0a86d1adf06` and preserved its original copy.
- Live GOMarketsMU-Demo EURUSD metadata reported minimum volume 0.01 and a
  minimum price-increment loss of **AUD 0.013851**, greater than the temporary
  AUD 0.01 cap. The fixed risk function returned
  `FOREX_M20_DEMO_RISK_REFUSAL_DRILL_OK`, with no order submitted.
- Restoration immediately returned the exact same session to the approved
  AUD 100 maximum planned-loss limit. Fresh observations after restoration
  show listener `MAINTENANCE_HOLD`, release `9f4601f3fd269894`, and a flat,
  available GOMarketsMU-Demo AUD account.

This replaces prior-release calculation-only refusal evidence for the current
release. It is still not evidence of a normal eligible-signal refusal, a
protected-position restart, broker lifecycle, fee qualification, or Wave 1/M20
completion.

## 2026-09-10 isolated PostgreSQL W1.4 refresh

Refreshed the durable risk and reservation checks without accessing the
operating database. The dedicated local PostgreSQL 16 instance used only
`127.0.0.1:55481/forex_w1_test`; it was stopped immediately after the run.
The current bridge passed **25** real PostgreSQL tests in
`tests/milestones/test_m20_risk_policy_persistence.py`, including independent
daily/weekly/drawdown/cash-flow/unknown-account latches, permitted resume
behaviour, minimum remaining headroom and two concurrent reservations across
different leases yielding exactly one reservation.

Raw test output is retained at
`runs/evidence/M20/w1-postgres-refresh-20260910/raw/risk-persistence-tests-rerun.txt`.
The initial connection attempt used a non-existent local `postgres` role and
failed before any test setup; it remains retained as diagnostic context. The
rerun used the instance's existing `chris` role and passed. These are isolated
engineering checks, not broker concurrency, fee, lifecycle or profitability
proof.

## 2026-09-10 03:25 UTC continuation checkpoint

**Status: Wave 1 remains in progress; normal Demo entry remains disabled.**
This is a new bounded read-only observation of the existing deployment, not a
restart, lease change, migration, entry release or broker-order drill.

Raw evidence is retained in
`runs/evidence/M20/w1-continuation-20260910/raw/` under the `20260910T0324_*`
and `20260910T0325_*` names. The offline verifier
`runs/verification/M20/w1-continuation-20260910/verify_0325_checkpoint.py`
checks captured hashes and declared state without contacting T480 or the
broker; its result is `0325-result.json` with marker
`FOREX_M20_W1_CONTINUATION_0325_VERIFIED`.

- The fixed Demo listener was running in `MAINTENANCE_HOLD`, release
  `9f4601f3fd269894`, with a fresh heartbeat. Its Windows task was `Running`
  as the S4U principal in Session 0, with no recorded current Python failure.
  Its preserved ticket `41760154` is still `LAST_KNOWN_UNVERIFIED`; this
  historical durable record is not asserted to be a current position.
- The independent MT5 account query returned `GOMarketsMU-Demo`, AUD,
  balance/equity AUD 100,994.79, zero open positions and an `AVAILABLE`
  position observation. The bounded unresolved-history query returned only
  historical September deals; it does not replace current broker lifecycle
  proof bound to this release.
- The deployed calculator observed EURUSD points-mode swap terms (long -5.91,
  short +2.30), minimum volume 0.01, Wednesday triple flag and fresh AUDUSD
  conversion quotes. Both BUY and SELL projections were `UNKNOWN`, with no
  submitted order or holding authority, because `financing_policy` still has
  null fee and calendar qualifications. This fail-closed outcome is correct.
- Current focused engineering verification passed: the financing and T480
  adapter suites (81 tests) and milestone governance validation. These checks
  do not establish actual commission, rollover schedule, posted financing,
  normal eligible-signal refusal, protected-position restart, or M20 proof.

**Activity plan and resumption conditions:** W1.1/W1.3 configuration remains
pending the exact account fee arrangement and a broker-qualified rollover
calendar; W1.2 needs a genuine lifecycle/protected restart during ordinary
authorised Demo activity; W1.4 has current refusal and isolated-persistence
engineering evidence but remains short of all broker proof. Once the operator
supplies documented account pricing and rollover/DST/holiday rules, prepare the
exact M20.13 cutoff amendment for approval, obtain the required read-only
pre-entry review, deploy under the hold and then reassess release eligibility.
Until then, maintenance hold is retained and no fallback assumes zero costs.

## 2026-09-10 review and amendment handover

Prepared two bounded, review-only artefacts without changing M20, runtime
configuration or the deployed release:

- [W1 pre-entry review packet](../reviews/w1-pre-entry-review-packet.md),
  committed as `63d8c17`, binds the required Astra review to deployed release
  `9f4601f3fd269894`, its code revisions, configuration fingerprint, raw
  captures and exact safety questions.
- [Proposed M20.13 rollover amendment](../reviews/w1-m20.13-rollover-amendment-proposal.md),
  committed as `ac81f02`, supplies the exact 15-minute pre-rollover intraday
  entry cutoff and failed-exit fallback for operator review. It is explicitly
  not applied to the contract and grants no new exit or overnight authority.

The next dependent action requires the account-specific commission arrangement,
a dated broker-qualified rollover/DST/holiday calendar, and operator approval
of the amendment text (or a recorded variant). The requested Astra review then
assesses the concrete changes. Maintenance hold remains in force pending those
inputs and the existing entry gates.

The exact minimum source fields and safe redaction guidance are in
[W1 operator inputs for entry release](../reviews/w1-operator-inputs-for-entry-release.md).

## 2026-09-10 operator-authorised broker-blocker resolution

The latest instruction explicitly authorises resolution using other sources
and inference. The prior demand for operator-supplied account pricing and a
full holiday calendar is superseded **for temporary intraday Demo operation**.
See [source analysis and limitations](../../Research/2026-09-10-w1-broker-blocker-resolution.md).
Actual account fees and overnight/holiday settlement remain unqualified.

Implemented `DEMO_ESTIMATE`: reserve the public Plus+ AUD 6/lot round-turn
allowance (AUD .06 at .01 lots); allow weekday entries from 06:00 UTC only if
the existing maximum ten-minute horizon ends strictly before 18:00 UTC.
This wider exclusion replaces the proposed 15-minute rollover cutoff.
The policy expires at 2026-09-17 00:00 UTC. Stale quotes, expired coverage,
weekends, longer holds and unsupported inputs still refuse. Estimated fees
are separate from actual broker accounting; the holding evaluator does not
accept `DEMO_ESTIMATE` as overnight evidence. No Option B thresholds change.

Implementation commit `352ee84`; Windows command-length correction `d681d05`.
Release **2329eea2d53bba6d** was transferred, hash-checked, configured and installed
under maintenance hold. Configuration fingerprint:
`sha256:16abde21dc56729b2418f9c48d7091362a3c7622f976e3bb36e49f8492e0fb67`.
The first configure command was too long; retained failure output shows it
failed before applying configuration. The previous listener was recovered
under hold, source descriptions were shortened to Research references, and
the successful retry is retained separately.

Raw: `runs/evidence/M20/w1-broker-resolution-20260910/raw/`.
Offline semantic verifier and hash inventory:
`runs/verification/M20/w1-broker-resolution-20260910/verify.py` and `result.json`.
Marker: `FOREX_W1_BROKER_RESOLUTION_DEPLOYMENT_VERIFIED`.
Observed 03:40 UTC: current release running in `MAINTENANCE_HOLD`; Demo AUD
account AVAILABLE/flat, balance/equity 100994.79. Unresolved attempts were empty
before deployment; retained risk-state/anchor/resume snapshots match exactly
before and after. No lease activation/reset or schema migration was performed.
Deployed preview reads the new policy and refuses both sides because it is
outside the intraday window. In-window broker acceptance is not yet observed.

Validation: targeted financing/adapter/M20/config tests passed (128 cases).
Full `scripts/verify_project.sh` passed; its 25 isolated PostgreSQL cases were
skipped without their fixture. Earlier persistence results remain separate.
Final shortened configuration and milestone governance validation passed.

Remaining action: review the exact new code/configuration before removing
maintenance hold, then collect ordinary eligible Demo lifecycle and protected
restart evidence. This change is implementation/source analysis, not an
independent final review. The old review packet's revision binding is stale.
No further operator broker questionnaire or numerical-cutoff approval is needed
for this dated temporary policy. Real broker fee proof, independent review,
applicable Wave 1 proof and formal M20 closeout remain outstanding. No completion
or normal-entry release is claimed. No push occurred.

## 2026-09-10 Astra pre-entry review and ordinary assessment

Read-only source review of `352ee84`/`d681d05` and release
`2329eea2d53bba6d` found no critical issue in the approved temporary financing
delta. Current Demo exposure and unresolved-attempt checks were empty, Option B
had no active pauses, and M19 remained PROVEN. Focused tests passed. The
maintenance hold was removed under the explicit continuation authority.

**Final review disposition: BLOCK_ENTRY.** The first ordinary assessment
exposed a missing M1 freshness check: at 03:44:48 UTC its newest M1 close was
01:12 UTC (9,168 seconds old). No order was submitted. Maintenance hold was
restored immediately. Later history caught up (03:45 close in the 03:45:18
assessment), but the entry check still accepts stale histories by count alone.
An isolated actual-parser reproduction accepted 64 bars with newest close
6,960 seconds old. This is labelled engineering evidence.

Final 03:47 observation: release unchanged, running/MAINTENANCE_HOLD, Demo
AUD account AVAILABLE/flat, balance/equity 100994.79. No lease/risk reset,
forced trade, host restart or implementation edit was made. The original
assessment and its later recovery are retained separately.

Review and Terra handover:
`docs/reviews/w1-pre-entry-astra-20260910.md`.
Raw: `runs/evidence/M20/w1-pre-entry-20260910/raw/`.
Implement the explicit entry freshness gate and review its interaction with
reversal monitoring while preserving broker protection/time exits. Test the
fresh-quote/stale-history case, then deploy under hold and request affected-area
review. The operator's model assignment requires Terra for this implementation;
the current Astra turn stops at the concrete review finding and safe handover.
Genuine lifecycle/accounting/protected-restart evidence and final M20 gates
remain pending; NO_TRADE_RECONCILED is operational evidence only.

## 2026-09-10 T480 autonomous listener watchdog installed

The non-trading continuity interval was cancelled under maintenance hold and
retained as `INCONCLUSIVE` with reason
`OPERATOR_CANCELLED_BEFORE_INTERVAL`; it is not continuity proof.

To remove reliance on a T16 connection or interactive sign-in, the fixed T480
operation `m20_listener_install_watchdog` installed
`Forex-M20-Listener-Watchdog`. It runs as `S4U` in Session 0, starts at Windows
boot, and repeats every two minutes for up to 3,650 days. Its only action is
Windows Task Scheduler's fixed request to run `Forex-M20-Demo-Listener`.
It has no broker, order, lease, risk-policy, hold-release, credential, or
caller-supplied command surface. The installation response records
`broker_mutation: NONE`.

A separate fixed read-only check confirms the watchdog is installed, `Ready`,
uses `schtasks.exe /run /tn "Forex-M20-Demo-Listener"`, ran successfully, and
uses the `S4U` logon type. The listener remained `Running` in
`MAINTENANCE_HOLD` with a fresh heartbeat, no failure record, and a flat
GOMarketsMU-Demo account. Raw T480 operation responses remain in the governed
adapter execution log; no webhook, credential, or account secret is retained
here.

This confirms installed unattended scheduling, not an unattended reboot proof.
A controlled reboot/no-sign-in test remains the real-world continuity criterion
and must retain the task and listener recovery observations before it can be
claimed. No Live access, forced order, hold release, or push occurred.

## 2026-09-11 autonomous T480 reboot and no-sign-in recovery proof

A held, flat-account reboot protocol was committed in `1bbcc9c` and executed
on T480 without using T16, RDP, a browser, or Codex to start the post-boot
recovery worker.
The first two request mechanisms did not change the Windows boot time and are
retained as failed protocol attempts. The final fixed Session-0 reboot task
requested a forced restart after the then-current GOMarketsMU-Demo observation
reported zero open positions and the listener/watchdog were S4U with a fresh
held heartbeat. That earlier operation did not independently query the global
unresolved-attempt ledger; the historical reboot record must not be read as
proving that separate condition.

T480 reported a new uptime start of `2026-09-11T02:55:49.5000000Z`. Its
post-boot S4U verifier waited 75 seconds and wrote the retained record for run
`b29fb651ee1d4916b11522c7d1a18801`: listener task `Running`, watchdog task
`Ready`, original release `8e6ee43f0b396b91` preserved, fresh post-boot
heartbeat, and `broker_mutation: NONE`. Independent fixed reads then confirmed
GOMarketsMU-Demo remained available and flat, the maintenance hold remained
active, and the watchdog had completed successfully. The offline verifier
returned `FOREX_W1_REBOOT_RECOVERY_PROOF_OK`.

Raw evidence: `runs/evidence/M20/w1-reboot-recovery-20260911-attempt3/raw/`.
Offline result: `runs/evidence/M20/w1-reboot-recovery-20260911-attempt3/verification/result.json`.
The failed earlier attempts remain retained separately and are not represented as
successful continuity proof.

This establishes the requested unattended host reboot recovery criterion. It
does not replace the separate 30-minute worker/alert continuity protocol,
broker lifecycle/accounting qualifications, or final independent Wave 1/M20
review gates. Maintenance hold remains active; no Demo order, Live access, or
hold release occurred.


## 2026-09-11 reboot-evidence verifier correction

A read-only Astra review found that the first offline reboot verifier did not
validate the operation envelopes, AVAILABLE broker observations, preflight hold,
actual boot chronology, watchdog S4U execution, or Session-0 listener identity.
It is superseded by `scripts/verify_w1_reboot_recovery.py` and retained only as
an historical artifact. The strengthened verifier succeeds against the unchanged
raw broker, host, listener, watchdog, record, and diagnostics captures in
`runs/evidence/M20/w1-reboot-recovery-20260911-attempt3/`; it rejects a negative
control with a falsified boot timestamp.

The new reusable reboot request guard also requires an available flat
GOMarketsMU-Demo account, `MAINTENANCE_HOLD`, an IDLE monitor with no recovered
position, fresh heartbeat, and S4U listener/watchdog identities before it can
request a restart. This guard was implemented after attempt3 and was therefore
not exercised by that historical run. The global PostgreSQL unresolved-attempt
summary is a separate authoritative gate. Attempt3 does not prove its state at
the exact reboot instant, and the Session-0 diagnostic proves scheduled-task
identity rather than proving that no person signed in anywhere on Windows during
the interval. The reboot operation is now one-shot and refuses reuse while its
retained record exists; a future reboot requires a reviewed version that embeds
the authoritative PostgreSQL unresolved-attempt check. These are explicit
limitations, not passed criteria.

The observed reboot still demonstrates that the T480 listener and watchdog
recovered under maintenance hold without an order, T16, RDP, browser, or Codex
being used to start the post-boot worker. Wave 1 remains open for its separate
completion gates.
