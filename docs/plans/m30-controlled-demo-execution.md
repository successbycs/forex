# Prove M30 with one bounded autonomous Demo order

This ExecPlan is a living document and follows `PLANS.md`. It implements only
M30's declared Demo proof surface. It does not enable Live trading, expand the
fixed T480 adapter, or change trading rules or risk limits. The continuous-Demo
operating-method amendment requires focused implementation verification and
release-readiness before maintenance hold may be released.

## Purpose / Big Picture

M30 will operate the protected EUR/USD GOMarketsMU-Demo listener across fresh
completed M1 candles and retain one naturally eligible trade from fixed
autonomous proposal through broker-confirmed closure and reconciliation. A
normal `NO_TRADE` is recorded and evaluation continues at the next fresh candle;
it never causes a broker retry or forced entry. The resulting lifecycle is an
integration proof, not evidence of a profitable strategy. The operator will be
able to run an offline verifier over the retained M30 evidence bundle.

## Progress

<!-- forex-work-projection:start task=M30-WAVE-1-CONTINUOUS-DEMO schema=forex.execution-work-projection.v1 -->
<!-- forex-work-item id=contract-alignment state=DONE -->
- [x] contract-alignment — Record M30 continuous-Demo authority and hybrid wave ordering (DONE)
<!-- forex-work-item id=listener-mode-design state=DONE -->
- [x] listener-mode-design — Define the smallest maintenance-hold versus ordinary-NO_TRADE listener contract (DONE)
<!-- forex-work-item id=listener-mode-implementation state=DONE -->
- [x] listener-mode-implementation — Implement continuous next-fresh-candle assessment without changing strategy, risk, or broker boundaries (DONE)
<!-- forex-work-item id=focused-verification state=DONE -->
- [x] focused-verification — Verify normal NO_TRADE continuation and all safety-stop, duplicate, persistence, and protection regressions (DONE)
<!-- forex-work-item id=independent-review state=DONE -->
- [x] independent-review — Obtain read-only review of the changed listener contract and focused verification evidence (DONE)
<!-- forex-work-item id=release-readiness state=DONE -->
- [x] release-readiness — Assess release readiness for the reviewed Wave 1 result without changing remote state (DONE)
<!-- forex-work-item id=deployment state=DONE -->
- [x] deployment — Deploy the reviewed release and remove maintenance hold only on explicit instruction (DONE)
<!-- forex-work-projection:end -->

- [x] (2026-09-16 02:42Z) Started M30 after M29 became proven.
- [x] (2026-09-16) Inspected the contract, fixed executor, M20 evidence
  tooling, and reconciliation baseline. Recorded the decision evidence in
  `docs/research/m30-demo-execution-evidence-brief.md`.
- [x] (2026-09-16 02:49Z) Performed read-only Demo readiness observations:
  the authoritative account was flat on GOMarketsMU-Demo/AUD, while the
  listener remained in `MAINTENANCE_HOLD` and its deployed application revision
  was `aa416361930e86d4346c33499491b20d14058d09`.
- [x] (2026-09-16) Add the M30 capture and offline verifier that bind the persisted proposal,
  raw operation output, source revision, configuration fingerprint, lifecycle, broker
  history, and reconciliation.
- [x] (2026-09-16) Independent Astra implementation review identified and
  repaired asynchronous entry handling, exact lifecycle selection, manifest
  surface mismatch, and suppressed pytest summaries. The 22 focused M30 tests
  pass, including a complete synthetic bundle and semantic negative controls.
- [x] (2026-09-16) Narrowed the capture preflight to M30's declared focused
  tests and governance validation. The former whole-repository run contained
  unrelated stale historical-state tests and did not test M30's Demo surface.
  The amended suite has 23 passing tests, including refusal of a missing
  targeted-verification receipt; registry validation passes.
- [x] (2026-09-16) Chris approved a narrow supporting-tooling amendment for a
  local retained-assessment envelope and offline completeness report. This is
  separate from the bounded Demo-order proof: it changes no runtime, schema,
  configuration, schedule, strategy, risk control, or broker authority.
- [x] (2026-09-16) Chris approved the bounded hybrid-delivery amendment:
  read-only persistence measurement, measured M1 capture repair, candle/refusal
  handling, final input checks, qualified context and reporting may be
  implemented before the M30 proof attempt. The final Demo lifecycle proves
  the resulting version; it does not authorise migration, scheduling, Live,
  strategy/risk, generic-interface or broker-retry changes.
- [x] (2026-09-16) Implemented and focused-tested the local envelope/report
  readers. A retained listener spool record produced a digest-bound `NO_TRADE`
  envelope; a supplied empty summary remained an unmatched report result, not
  a claim about PostgreSQL. Unsupported retained input is preserved as an
  explicit operational refusal. M30 remains awaiting its separate Demo proof.
- [x] (2026-09-17) Amended the Demo policy: financing, rollover-calendar, and
  UTC entry-hour qualification are deferred to later Live readiness. The
  deployed `ba65739` configuration reports `DEFERRED_FOR_DEMO`; existing
  Demo risk, cost, position, protection, monitoring, and reconciliation gates
  remain mandatory.
- [x] (2026-09-17) Performed M30's one declared capture attempt on the
  deployed deferred-policy revision. It produced `NO_TRADE` (no fixed strategy
  selected); no broker order was submitted. The capture contract refused to
  manufacture evidence, the account remained flat, and maintenance hold was
  restored. Raw refusal artifacts: `runs/evidence/M30/20260917T001033Z/`.
- [x] (2026-09-17 00:22Z) Read the durable risk state and current Demo account.
  The account was flat (`open_positions: 0`) with no unresolved execution
  attempts; observed balance/equity and risk `expected_balance` each equalled
  AUD 100,989.59. The only entry pause remained `EXTERNAL_CASH_FLOW`.
  The fixed resume action is deliberately append-only and requires a current
  operator-reviewed attribution of the balance movement before it may be used;
  the earlier review applies only to its recorded historical movement.
- [x] (2026-09-17 00:45Z) Added and exercised a fixed read-only account-binding
  diagnostic. The deployed M20 listener, persistent M30 risk state, and
  complete bounded broker-history export all returned the same redacted
  `GOMarketsMU-Demo:<login>` SHA-256 binding
  (`4b12a2cebac68fadc4009c52f46e1cda20bd3c731ef94428ed2b47a2d29faabf`).
  Therefore the observed balance history belongs to M30's active Demo account;
  the paused H1 configuration is absent and must not be used to infer a
  different active account.
- [x] (2026-09-17 00:47Z) Attributed the M30 risk balance movement directly
  from fixed broker history: from the AUD 100,995.51 risk baseline at
  `2026-09-07T00:42:49Z`, 33 closed broker deals totalled AUD -5.92, with
  AUD 0.00 commission, swap, and fee. Current balance was AUD 100,989.59,
  leaving AUD 0.00 unexplained; no balance/credit entry occurred after the
  baseline. The fixed append-only resume action recorded
  `699b9538-3729-4584-9b24-f1d27a1ff3fe`, cleared the pause list, and left
  maintenance hold active. A future entry still requires its ordinary fresh
  risk check, market gates, and M30's no-retry capture rule.
- [x] (2026-09-17) Completed the targeted hybrid milestone alignment review.
  Chris approved the M30 operating-method amendment: continuous fresh-candle
  Demo evaluation will produce evidence; a normal `NO_TRADE` proceeds to the
  next candle, while safety stops still block new entries.
- [x] (2026-09-17) Wave 1 source review and focused verification established
  that the permanent listener already continues after a normal `NO_TRADE`; no
  production listener rewrite was required. A regression test now proves two
  successive fresh-quote assessments after `NO_TRADE`. The focused listener,
  fixed-session, adapter, persistence, and M30 suites passed (189 tests).
  Astra independently approved this local result. The old submitting M30
  collector is explicitly legacy-only; read-only proof extraction remains
  Wave 4.
- [x] (2026-09-17 01:32Z) Read-only Wave 1 release-readiness assessment was
  NO-GO. The deployed listener is running but held, binding revision
  `ba6573969b8be0d8b23276aa564aa5cb41b0a8d9` and fingerprint
  `sha256:f4cda442b8b0daee9d198d03fa027dc34dcee6356321a1c7e318cff06af46f3d`.
  The observed account was correctly GOMarketsMU-Demo/AUD, flat, and matched
  the redacted expected scope hash, but the local Wave 1 change is not a clean
  deployed revision and the status retains a `LAST_KNOWN_UNVERIFIED` historic
  protection record. No hold release or order occurred.
- [x] (2026-09-17 01:34Z) A further fixed read-only terminal diagnostic found
  two configured MT5 processes (one service-session and one interactive) and
  EURUSD history file-lock errors with synchronization failures. The terminal
  still reported zero positions and zero orders. This is a release blocker;
  closing the duplicate terminal is a separate fixed mutation requiring
  Chris's explicit instruction while maintenance hold remains active.
- [ ] Implement and focused-test Wave 1's listener-mode separation. This must
  preserve the fixed one-candle decision identity, all existing gates,
  journal-before-submission rule, one-position cap, protection, and no-retry
  rule. It does not itself release maintenance hold.
- [ ] Validate the implementation, record M30-C2/C4 as applicable, and obtain
  an independent read-only review.
- [ ] When the existing autonomous preflight is eligible, perform the bounded
  remote sequence once and retain its result.
- [ ] Verify the fresh bundle, record all M30 acceptance checks, obtain the
  required human sign-off and current review recommendation, and run formal
  `prove` if every contract gate passes.

## Surprises & Discoveries

- Observation: a successful fixed entry returns `OPEN_MONITORING`, not a
  terminal reconciliation. The original M30 capture/verifier therefore could
  not accept the real executor output. Also its manifest surface differed
  from the registry, and doubled pytest quiet flags suppressed the required
  passing-test summary.
  Evidence: `t480/m20_demo_trading_session.py` returns a scheduled monitor;
  `tests/milestones/test_m30.py` now exercises that response and exact final
  lifecycle through capture and the offline verifier.
- Observation: the owner monitor sends a time-stop close at the configured
  deadline. A broker fill after that deadline cannot prove the literal M30
  requirement to close by the cutoff. Earlier protected exits can prove it.
  Evidence: `_monitor_open_position` and `OWNER_MAX_HOLD_SECONDS` in
  `t480/m20_demo_trading_session.py`. No runtime timing or contract tolerance
  was changed by this tooling repair.
- Observation: M20's executor already persists a proposal and has fixed
  one-position, Demo-only entry and close logic, but its capture contract has
  no M30 evidence bundle.
  Evidence: `t480/m20_demo_trading_session.py` and
  `scripts/capture_m20_demo_evidence.sh`.
- Observation: the currently observed listener status was `MAINTENANCE_HOLD`.
  Evidence: `m20_listener_status` observation at 2026-09-16T02:49:42Z; it
  explicitly says that no assessment or Demo order is permitted.
- Observation: the active release does not match the current local source
  revision, so the fixed adapter will fail closed before it can run new source.
  Evidence: `m20_listener_diagnostics` reported deployed revision
  `aa416361930e86d4346c33499491b20d14058d09`; the local M30 work is uncommitted.

## Decision Log

- Decision: defer financing, rollover-calendar, and UTC entry-hour policy from
  the Demo M1 path to a later Live-readiness policy. Demo decisions retain an
  explicit `DEFERRED_FOR_DEMO` status and no assumed swap or commission.
  Rationale: Chris directed removal of the expired temporary Demo restriction;
  the final M30 proof must exercise the current Demo MVP rather than wait for a
  later Live-policy input. Existing Demo-only, risk, cost-coverage, position,
  protection, monitoring, and reconciliation gates remain unchanged.
  Date/Author: 2026-09-17 / Chris.

- Decision: amend the active M1 MVP goal to reflect the deployed Demo policy.
  Package D is complete. Package F/M30 remains a real-world proof requirement,
  but can only succeed on an authentic eligible M1 setup and a permitted risk
  state; it must not force or retry an order after a valid `NO_TRADE` result.
  Rationale: the policy restriction was removed, while the decision engine's
  no-trade outcome and safety gates remain part of the MVP's intended function.
  Date/Author: 2026-09-17 / Chris.

- Decision: do not automatically clear the current `EXTERNAL_CASH_FLOW` pause.
  Rationale: matching current expected and observed balance proves there is no
  ongoing mismatch, but does not attribute the historical movement that first
  latched the pause. The fixed resume operation records an operator review and
  must not be substituted with an inference or a prior review for a different
  balance difference. Date/Author: 2026-09-17 / Codex from durable risk,
  account, and unresolved-attempt observations.

- Decision: use the redacted `server:login` binding, not an account-label or
  repository workstream name, to attribute M30 operational evidence.
  Rationale: the H1 configuration is paused/absent, while the direct binding
  comparison proves the active M20 terminal, risk state, and broker history
  are the same account. Date/Author: 2026-09-17 / Codex observation.

- Decision: resolve the `EXTERNAL_CASH_FLOW` pause through the existing
  append-only fixed resume operation after exact broker-history attribution.
  Rationale: the AUD -5.92 balance movement exactly equals the 33 recorded
  closed-deal outcomes, so no unaccounted cash movement remains. The action
  did not submit, modify, or close a broker order and maintenance hold remains
  in place. Date/Author: 2026-09-17 / Chris's active M30 MVP goal.

- Decision: retain the fixed autonomous entry gates and bind their persisted
  proposal to the M30 evidence bundle.
  Rationale: the repository is an autonomous Demo-trading platform; existing
  bounded gates prevent entry when inputs or risk state are unsafe.
  Date/Author: 2026-09-16 / Chris direction.
- Decision: retain the existing fixed execution path and build no generic MT5
  or shell interface.
  Rationale: the architecture assigns broker access only to the fixed Demo
  operation and M30 is not authorised to broaden it.
  Date/Author: 2026-09-16 / M30 contract and architecture.
- Decision: use M30's focused test suite and governance validation instead of
  `scripts/verify_project.sh` before the one bounded capture attempt.
  Rationale: this MVP proof must verify its own source, contract, and safety
  boundary; unrelated legacy expectations do not provide additional assurance
  for the M30 operation and previously prevented the attempt before broker
  contact.
  Date/Author: 2026-09-16 / Chris direction.

## Outcomes & Retrospective

Local tooling is repaired and 23 focused M30 synthetic tests pass. The capture
preflight is now limited to that suite and registry validation. No M30 order,
hold release, or external mutation was performed by this change. A clean,
committed revision remains necessary before the fixed Demo action can run;
real-system proof, deployment readiness, and formal closeout remain pending.

## Context and Orientation

`milestone_registry.json` declares M30 as a real-system integration proof:
one bounded autonomous `GOMarketsMU-Demo` EUR/USD entry, a mandatory close by the
configured cutoff or an earlier risk exit, and complete reconciliation. Its
freshness limit is 24 hours. `project_state.json` records mutable state and
`runs/run_history.json` records append-only transitions.

The only broker-capable route is `scripts/t480_adapter.py execute --operation
m20_demo_trading_session`, backed by `t480/m20_demo_trading_session.py`. That
operation already has fixed account, symbol, sizing, risk, idempotency,
protection, monitoring, and reconciliation constraints. Invoking it can place
an order. It must never be called merely to obtain a proposal.

`scripts/m20_demo_evidence_contract.py` verifies an M20 bundle without
contacting the broker. `src/forex/m20_reconciliation_baseline.py` establishes
that a retained assessment and broker history can only be joined by explicit
position identity; it must not infer a match from timestamps, prices, or
comments. M30 needs the same fail-closed standard plus a contract binding the
persisted autonomous proposal to the broker lifecycle.

## Plan of Work

### Continuous-Demo operating method

Wave 1 changes the M30 collection method, not the strategy or proof outcome.
The running listener must distinguish a deliberate deployment maintenance hold
from an ordinary terminal decision. When the active Demo lease and every
existing safety gate pass, it assesses each new completed M1 candle. A
persisted `NO_TRADE`, unsuitable spread, or occupied position is an ordinary
outcome: record it and wait for the next fresh candle. Unknown broker state,
account-binding failure, active risk pause, failed durable persistence, or
unresolved exposure blocks new entries and leaves position monitoring active.

No implementation or deployment is authorised by this wording alone. Wave 1
must pass focused tests, independent review, and release-readiness. The
release gate is separate from normal per-candle autonomous execution. Once
released, the first naturally eligible complete lifecycle is collected
read-only for M30; the collector does not submit a second order merely to make
a proof bundle.

The legacy `scripts/capture_m30_evidence.sh` remains retained only as the
historical one-shot collector. It invokes `m20_demo_trading_session` and can
submit an order, so it is **not** permitted for continuous-mode proof capture.
Wave 4 must add `scripts/capture_m30_natural_lifecycle_evidence.sh`, accepting
one already-persisted proposal ID. That collector must first ensure a clean
material revision and pass M30 tests/governance, then read only the exact
listener, attempt, lifecycle, history, and reconciliation records for that
proposal. It records `m30-verification.txt` as the focused local verification
receipt and does not run unrelated full-repository tests or submit, retry,
modify, or close an order. Once the matching terminal closed lifecycle is
observed, retain raw listener/attempt observations, lifecycle/history/
reconciliation reports, listener diagnostics, configuration, source revision,
test outputs, redaction declaration, hashes, manifest, and
`FOREX_M30_PROOF_OK` summary. The verifier must be offline and fail closed for
any changed artifact, stale evidence, wrong server/symbol,
persisted-proposal/revision/config mismatch, open or unresolved position,
missing mandatory close evidence, or incomplete broker reconciliation.

The close-by-cutoff check uses the latest broker closing-deal timestamp and
the current source-bound owner's maximum holding period, measured from entry
submission. No grace interval is added. The separate observation timeout
allows collection latency and does not change a trading rule or prove a late
close. The raw asynchronous reconciliation remains `OPEN_MONITORING` in the
entry artifact; the final independently observed lifecycle supplies closure.

Second, run focused tests and the contract verification over synthetic fixture
bundles. Record exact outputs in this document. Use the QA verification skill
before treating the implementation as complete; it validates the code and
fixtures but cannot prove M30's real-world surface.

Third, after an independent read-only implementation review and
release-readiness, release maintenance only when the deployed revision matches
the reviewed source, the account is still GOMarketsMU-Demo, and the existing
fixed preflight passes. The listener then evaluates fresh completed M1 candles
under its existing autonomous gates. Preserve monitoring and broker protection
until any accepted position closes by cutoff or earlier risk exit. A normal
refusal is journalled and the next fresh candle may be assessed; changed market
input, missing close, unknown broker outcome, or reconciliation failure never
retries an order or manufactures evidence.

Finally, run the offline verifier and the registry verification, record each
criterion with the evidence path, finish implementation, collect the current
required recommendation and Chris's closeout sign-off, and run the normal
milestone CLI prove transition. The CLI-generated `proven_at` is the only
formal completion record.

## Concrete Steps

Run every local command from `/home/chris/projects/forex`.

    python3 scripts/forex_milestones.py validate
    python3 -m pytest -q tests/milestones/test_m30.py
    bash scripts/verify_m30_evidence.sh runs/evidence/M30/<bundle>

After implementation, run the relevant QA verification commands named by the
new tests and inspect the parsed manifest and reconciliation output. Before an
external continuous-Demo release, do not run the legacy
`capture_m30_evidence.sh`. Wave 4's future read-only natural-lifecycle
collector may run only after release-readiness and all fixed Demo safety gates
pass; it must not initiate an attempt.

Expected successful eventual verifier output is:

    FOREX_M30_PROOF_OK

This output alone is not closeout; it must remain fresh, match the current
revision/configuration, and pass all formal review and CLI gates.

## Validation and Acceptance

Implementation acceptance requires tests that demonstrate `NO_TRADE` cannot
be captured as M30, a Live server reference is rejected, and an authentic synthetic
closed/reconciled Demo bundle verifies while negative controls fail.

M30-C1 requires fresh raw evidence of one persisted-proposal-bound Demo EUR/USD entry and
broker-confirmed terminal close. M30-C2 requires the registry and M30 tests to
pass. M30-C3 requires a current manifest tied to the exact revision,
configuration, and retained source versions. M30-C4 requires no Live reference,
no unresolved exposure or reconciliation, correct provenance, and a
mandatory-close-or-earlier-risk-exit record. Tests and synthetic fixtures do
not substitute for C1 or C3.

## Idempotence and Recovery

Synthetic fixture verification and read-only status observations are repeatable.
Raw external capture directories are created once;
never overwrite, repair, or delete an incomplete bundle. If a preflight or
revalidation fails, keep maintenance in its safer state and create a new
proposal rather than extending stale evidence. If a broker operation reports a
fill but exposure is unclear, do not retry: preserve the raw result and follow
the existing monitoring/reconciliation path.

## Artifacts and Notes

Owned paths are M30 proof documentation, the future read-only natural-lifecycle
capture/verifier scripts, focused
tests, this evidence brief and plan, and M30 state/history changes. Existing
raw evidence and unrelated H5 continuation metadata are not owned by this
plan.

## Interfaces and Dependencies

The M30 evidence verifier accepts only an explicit bundle directory and does no
network or adapter calls. The
only execution interface remains the pre-existing no-argument fixed T480
operation. `GOMarketsMU-Live`, generic MT5, generic shell, arbitrary SQL, and
automatic approval are prohibited.

Review amendment (2026-09-16): updated the collector to observe the existing
asynchronous monitor instead of requiring a synchronous close, and bound the
manifest, proposal, attempt, snapshot, owner, position, cutoff and reconciled
broker facts. This repairs proof tooling without changing trading authority,
runtime payloads, strategy limits, or retained external evidence.

MVP amendment (2026-09-16): replaced the unrelated whole-repository capture
preflight with M30's focused tests and registry validation. This preserves the
clean committed revision, Demo-only, fixed-operation, close, reconciliation,
and offline-evidence gates while removing stale historical-test coupling.
