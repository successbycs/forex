# M31 — evaluate controlled Demo outcomes against a frozen baseline

This ExecPlan is a living document. Maintain it and its execution record,
`docs/plans/m31-demo-baseline-evaluation-work.json`, under `PLANS.md`.

## Purpose / Big Picture

M30 proved that the EURUSD Demo listener can make, protect, close, and reconcile
a natural trade. M31 answers a different question: what did the controlled Demo
workflow actually do during a pre-declared observation interval, compared with a
baseline that is defined before the result is viewed? The visible outcome is an
operator-readable scorecard showing decisions, refusals, selected trades,
broker-reconciled outcomes, cost coverage, and uncertainty. It is not an income
target, financial advice, proof of an edge, or authority to change the listener.

## Formal milestone dependency map

M30 is `PROVEN` in the imported clean evidence state: its bundle, verification,
four-role `RECOMMEND_COMPLETE` review, acceptance records, and Chris's approval
are local retained prerequisites. M31 is now `IN_PROGRESS`; its contract permits only
controlled `GOMarketsMU-Demo` workflow evaluation and provenance retention.
The active M31 work fits because it reads and evaluates existing records without
adding an order route, rule, account, or risk control. M32 depends on M31 being
formally `PROVEN`; its planning and implementation are blocked until then.

## Scope and safety boundary

The only broker identity is `GOMarketsMU-Demo`, the only instrument is EURUSD,
and the existing M1 listener remains unchanged. The scorecard consumes retained
data through existing fixed read-only operations or immutable local evidence.
It must never issue SQL, shell, MT5, or network commands outside an existing
allowlist. It does not reset a risk latch, release a hold, create a position,
retry an order, alter an entry rule, or estimate missing costs from a tariff.

The frozen baseline is `NO_CHANGE`: no exposure, zero trades, zero realised P&L,
and zero costs during the exact M31 interval. A historical reference is admitted
only if the same M1 rules, point-in-time inputs, interval, and cost assumptions
are demonstrably comparable. A non-comparable source is reported as context,
never made into a numerical performance comparison.

The already selected NO_CHANGE policy is a narrow exception to timeframe
comparability: taking no new exposure produces no new trade costs on either
timeframe. The retained M16 `overall.no_change` result may document that
historical null policy, but its active H1 strategy returns are not comparable
with this M1 interval. The exact M16 artifact was bound after observation; this
timing must remain visible. This is not a newly selected baseline, a currency
conversion of historical percentage returns, or evidence of trading ability.

## Progress

<!-- forex-work-projection:start task=M31-DEMO-BASELINE-EVALUATION schema=forex.execution-work-projection.v1 -->
<!-- forex-work-item id=m30-handoff state=DONE -->
- [x] m30-handoff — Preserve and validate the approved M30 evidence, review, and formal state in the normal worktree (DONE)
<!-- forex-work-item id=evaluation-protocol state=DONE -->
- [x] evaluation-protocol — Define the M31 interval-freezing method, no-exposure baseline, metrics, cost labels, and no-promotion rule (DONE)
<!-- forex-work-item id=source-inventory state=DONE -->
- [x] source-inventory — Inspect the existing fixed read-only evidence surface and classify interval completeness (DONE)
<!-- forex-work-item id=scorecard state=DONE -->
- [x] scorecard — Implement a deterministic M31 scorecard from retained interval evidence (DONE)
<!-- forex-work-item id=evaluation-capture state=DONE -->
- [x] evaluation-capture — Freeze the controlled M31 interval, capture raw evidence, and produce the scorecard (DONE)
<!-- forex-work-item id=verification-review state=IN_PROGRESS -->
- [ ] verification-review — Verify M31 evidence and obtain required independent recommendation (IN_PROGRESS)
<!-- forex-work-item id=human-closeout state=PENDING -->
- [ ] human-closeout — Obtain human approval and prove M31 when all contract gates pass (PENDING)
<!-- forex-work-item id=m32-boundary state=PENDING -->
- [ ] m32-boundary — Create M32 plan only after M31 is formally PROVEN (PENDING)
<!-- forex-work-projection:end -->

## Context and orientation

`t480/m20_demo_listener_service.py` runs the continuous M1 listener. It retains
one proposal per completed candle; a proposal may be `NO_TRADE`, `BUY`, or
`SELL`. `t480/m20_demo_trading_session.py` owns bounded Demo submission and
position management. The PostgreSQL audit bridge retains decisions, proposals,
attempts, position events, and reconciled outcomes. The listener's M5/H1 and
calendar outputs are context only; they cannot be reinterpreted as M31 entry
filters. `docs/milestones/M16-proof.md` is a methodological precedent for frozen
chronological evaluation but is not a same-timeframe M1 strategy benchmark.

An evaluation interval is an inclusive UTC start and exclusive UTC end. It is
chosen and stored before querying the results. A cost-coverage label identifies
which of broker commission, fee, swap, observed spread, and slippage are present
for each selected trade. A row with missing cost facts remains usable for gross
outcome reporting but cannot support a net or Live-equivalent conclusion.

## Plan of work

First, use existing fixed read-only listener/audit evidence to inventory what
can be exported for a bounded interval. Record every source response's digest,
declared timestamps, row count, source/release identity, and gaps. If an existing
operation cannot provide a required bounded fact, add only a fixed read-only
adapter operation with a schema and tests; never introduce generic database or
remote access.

The M31 method is frozen now; the actual interval is intentionally not. A
separate `scripts/declare_m31_protocol.py` command creates an immutable protocol
and receipt in a clean committed checkout while its UTC start is still in the
future. After the interval ends, the capture command copies those unchanged
files into the evidence bundle before it reads results. This ordering prevents
a plan document from claiming a pre-declared interval that has not actually
been declared.

For this MVP, the interval is deliberately short: it must contain enough
completed M1 candles to prove the decision workflow, not a target number of
trades or a 24-hour sample. A normal all-`NO_TRADE` result is valid operational
evidence and is reported honestly; it is not a reason to force an entry. The
earlier 24-hour declaration is retained as superseded evidence and will not be
used for M31 capture.

Second, implement a pure scorecard module. It receives supplied immutable
records; it cannot contact MT5, PostgreSQL, or the network. It must group by
strategy/version and disposition, reconcile each selected proposal to one
attempt/outcome or state the exact missing relationship, calculate counts and
observed gross/net fields, and render both JSON and concise terminal text from
the same result. It must place `NO_CHANGE` alongside results but never call it a
trading strategy. It must reject duplicate decision keys, source-version drift,
future timestamps, malformed costs, and outcomes outside the frozen interval.

The implementation is `src/forex/m31_scorecard.py`; it has no subprocess,
database, MT5, adapter, or network dependency. `scripts/m31_scorecard.py`
reads exactly three regular local files: a frozen protocol, a bounded
completeness response, and the lifecycle response. It renders the same result
as concise terminal text or JSON. It rejects duplicate proposal identities,
identity drift, foreign interval rows, source-version drift, malformed cost
values, and outcomes that close outside the frozen interval.

Third, capture a new M31 bundle only after the protocol and scorecard are
committed and tests pass. The capture has no argument that can alter broker
state. It stores fixed-operation outputs unchanged, the protocol, scorecard,
test/governance receipts, revision/configuration identities, and a manifest.
The verifier checks hashes, M31 identity, freshness, interval binding, baseline
identity, no-Live declaration, and scorecard consistency. Independent review
and Chris's approval remain formal gates before M31 proof.

`scripts/capture_m31_evidence.sh` implements that capture contract. It accepts
only a new bundle path and a declared protocol directory, refuses a dirty
checkout, requires the declared protocol revision to match the evaluator, and
refuses to capture before the interval ends. It then calls only the named fixed
read-only operations, renders the scorecard from their retained bytes, records
the exact Git revision and artifact digests, and runs
`scripts/verify_m31_evidence.sh`. The verifier is local-only and re-computes the
scorecard, including the declaration-receipt timing/binding check.

For the completed original window, use its `--retained` route described in
`docs/milestones/M31-proof.md`. This invokes `scripts/m31_retained_evidence.py`
to retain unchanged original bytes, the additive fixed-query v2 response and
historical null source in a new bundle. It records the repaired evaluator
revision separately from the declaration/runtime revisions. Its verifier checks
current revision/configuration, original digests, deterministic recomputation,
Demo-only scope, verification receipts and observation freshness. It does not
start another window, deploy, or contact the broker. The technical proof marker
is not an independent completion recommendation or human signoff.

## Concrete steps

From `/home/chris/projects/forex`:

1. Inspect source completeness with named fixed read-only operations. Expect a
   redacted result that identifies Demo/EURUSD, an interval, joins, and any
   unavailable fields. Do not use a generic SQL or remote command.
2. Add pure parser, scorecard, JSON/text renderer, fixtures, and tests. Expect
   deterministic output for a complete fixture and explicit `UNKNOWN` or
   `NON_COMPARABLE_CONTEXT` for incomplete fixtures.
3. Declare a future fixed interval from a clean evaluator revision. After that
   interval ends, use the fixed capture and offline verifier. Expect
   `FOREX_M31_PROOF_OK` only when all required identities and evidence hashes
   match.
4. Run focused tests, governance validation, the evidence verifier, a separate
   read-only review, and then the registry closeout route.

## Validation and acceptance

M31-C1 is satisfied only when an operator can inspect a real bounded
`GOMarketsMU-Demo` interval scorecard showing all decisions, selected outcomes,
baseline, cost coverage, source identities, and uncertainty. M31-C2 requires
focused M31 tests and governance validation. M31-C3 requires a fresh hash-bound
real-world evaluation bundle matching the evaluator revision and configuration.
M31-C4 requires point-in-time interval enforcement, no look-ahead, Demo-only
binding, no unsafe fallback, and no unresolved critical review finding.

The mandatory checks are:

    python3 -m pytest -q tests/milestones/test_m31.py
    python3 scripts/forex_milestones.py validate
    bash scripts/verify_m31_evidence.sh runs/evidence/M31/<timestamp>
    python3 scripts/check_execution_continuation.py --work-plan docs/plans/m31-demo-baseline-evaluation-work.json

## Idempotence and recovery

Source inventory and scorecard rendering are read-only and repeatable. Capture
creates a new timestamped evidence directory and never modifies a prior one. A
missing source, bad join, stale observation, malformed cost, or unclear interval
is an explicit scorecard limitation and blocks only a conclusion that needs it;
it never triggers a broker retry or inferred replacement value. A failed
deployment is out of scope because this plan does not deploy the listener.

## Surprises & Discoveries

- Correction (2026-09-23): the ten-minute observation has completed. Original
  `runs/evidence/M31/mvp-20260923T012500Z-afce837` retains 01:15–01:25 UTC,
  ten NO_TRADE decisions and no selected outcomes. The original v1 verifier
  did not establish the registry's full proof contract. It remains unchanged.
  Do not repeat the window or wait 24 hours to repair local evidence checks.
- Repair: the bounded fixed PostgreSQL query now exports decision versions,
  rationale, timeframe and session Demo/EURUSD scope. Its v2 result is retained
  at `runs/evidence/M31/supplement-20260923T0208Z/completeness-v2.json`.
  Every original field and proposal matches; all ten records share revision
  `875b3280ad0e4552bcb143d707ca57ca0e4b6c62` and the current configuration.
- Additive evaluation: `scripts/m31_supplement.py` verifies original artifact
  hashes before enriching the report. It validates declaration timing,
  strategy/version/scope, rejects altered original fields, and cross-checks
  complete broker history with the declared server clock offset. There are
  zero EURUSD deals in this interval. Existing positions and account P&L are
  excluded, not assumed zero. Proposal/session schema does not retain an
  account hash for a direct decision-to-broker-account join; report that limit.
- Runtime diagnosis correction: four desktop-origin positions were observed
  separately, and the current existing-position gate was false. The interval
  proposals themselves record only `No selected actionable M1 strategy.`
  Do not rewrite that generic persisted rationale as a specific gate reason.
  No positions or trading controls were changed.

- Observation: the normal worktree initially lacked the M30 closeout bundle and
  formal state because capture occurred in a clean checkout. Evidence: the
  bundle and review directories were absent locally while the clean checkout
  verified them. The exact absent paths were copied without overwrite and local
  governance validation now passes.
- Observation: M16 provides historical methodology but not a like-for-like M1
  numerical comparator. Evidence: its retained proof is H1 and uses a distinct
  retrospective availability assumption. M31 must label it contextual.
- Observation: the existing bounded `forex-m1-postgres-completeness-summary`
  reader can provide candle-keyed proposals, attempts, statuses, and basic
  outcome linkage for an inclusive/exclusive UTC interval of no more than 24
  hours. The full hash-bound lifecycle extract can provide strategy ownership,
  reconciled outcomes, and observed cost fields; M31 must filter it locally to
  the frozen interval and reject rows outside those bounds. Evidence: source
  inventory read on 2026-09-23 used only named read-only operations.
- Observation: `m20_all_demo_history_export` returned a complete
  `GOMarketsMU-Demo`/AUD broker history at 2026-09-23T00:22:38Z (149 deals, 146
  orders) with a fixed account-scope hash. It is a broker cross-check, not a
  decision/refusal source.
- Limitation: the legacy `forex-m20-strategy-trial-summary` is not admissible
  for M31. Its 2026-09-23 source-inventory read failed because the deployed
  database does not contain `demo_trade_ledger.trade_owner_strategy_id`.
  M31 will derive strategy ownership only from the lifecycle source field that
  actually exists, and will retain the failed response as evidence of this
  excluded source. No schema migration or guessed replacement is in scope.
- Limitation: `forex-m20-current-lineage-summary` is permanently bound to
  2026-09-10 and therefore is contextual diagnostic evidence only, not an M31
  interval source.
- Observation: the local scorecard implementation passed its deterministic,
  duplicate, drift, interval-boundary, missing-join, Demo-identity and CLI
  tests on 2026-09-23. It has not captured or evaluated a real M31 interval.
- Observation: the M31 capture/verifier package passed 12 focused tests on
  2026-09-23. The capture test confirms the current dirty checkout is refused
  before a bundle path is created; the verifier test confirms altered scorecard
  bytes are rejected by their manifest digest. This is implementation proof,
  not an M31 evaluation capture.
- Correction: earlier plan wording said the evaluation-protocol task “froze the
  M31 interval.” That was not true: it defined the freezing method and baseline
  only. The task label now states that fact, and a real interval remains a
  capture-time artifact written before source reads.
- Correction: the initial capture implementation created its protocol at
  capture time. That could not demonstrate the window was chosen before its
  results existed. It now requires a separately retained future-window protocol
  receipt whose timestamp and evaluator revision are verified offline.

## Decision Log

- Decision (2026-09-23): retain the original declaration and raw bundle and
  evaluate supplemental provenance separately. Independent read-only reviewer
  `/root/m31_gap_review` supports the preselected historical null comparison
  with explicit post-observation binding disclosure. This does not waive the
  required formal verification, review or human signoff. Reviewer-required
  repairs added timeframe/session scope, strategy version drift checks, original
  manifest verification and data-derived historical session counts.

- Decision: use `NO_CHANGE` as the only initial numerical baseline. Rationale:
  it is fully specified, does not invent a strategy or execution cost, and
  makes no profitability claim. Date/Author: 2026-09-23 / M31 evidence brief.
- Decision: require a frozen protocol before data evaluation. Rationale:
  choosing an interval after results are seen creates selection bias. Date/Author:
  2026-09-23 / M31 evidence brief.
- Decision: defer commission estimates, manual attribution, session-policy
  publication, and strategy promotion. Rationale: none is required to measure
  retained outcomes honestly, and each needs separate evidence or authority.
  Date/Author: 2026-09-23 / Chris's Demo MVP goal.
- Decision: use the existing bounded completeness reader as the canonical
  decision denominator and the lifecycle extract for enriched outcome fields.
  Rationale: the first is parameter-bound to the frozen 24-hour interval; the
  second supplies fields absent from that summary and is locally re-bounded by
  the pure evaluator. Date/Author: 2026-09-23 / source inventory.
- Decision: defer actual interval declaration until a clean committed evaluator
  checkout is available. Rationale: this preserves the required ordering
  (protocol before results) while allowing the capture to bind its scorecard to
  an immutable revision. Date/Author: 2026-09-23 / M31 capture design.
- Decision: make pre-declaration a separate artifact, rather than an argument
  passed to capture. Rationale: the receipt establishes both the declared time
  and exact evaluator revision before the interval begins. Date/Author:
  2026-09-23 / M31 evidence repair.
- Decision: use a short, pre-declared M1 observation interval for the MVP,
  rather than wait 24 hours. Rationale: M31 requires controlled, reproducible
  Demo workflow evaluation, not a trade-count target; the existing scorecard
  records natural `NO_TRADE` decisions and any natural selected outcome without
  changing execution behaviour. The original 24-hour declaration is retained
  but superseded. Date/Author: 2026-09-23 / Chris's MVP feedback.

## Outcomes & Retrospective

The original ten-minute capture is complete; an additive evaluation is retained
at `runs/evidence/M31/derived-20260923-mvp-repair-02`. It reports ten NO_TRADE
decisions, consistent decision provenance and zero broker deals in that window.
Sixty focused M31/adapter/completeness/history tests, governance validation
and whitespace checks pass. Dirty-checkout tests now use an isolated simulated
Git state and do not depend on this worktree accidentally being dirty.

The first clean retained-evidence capture
`runs/evidence/M31/formal-20260923-f0ac41d` passed with `FOREX_M31_PROOF_OK`.
Independent repair review passed. Commit this progress update and regenerate
the final technical bundle from the same retained sources so HEAD bindings
remain exact. This is local evaluation, not another observation window.
Remaining work is the bound completion recommendation and human
signoff. The original failing formal checks must pass before closeout. M32
remains gated. No broker mutation or new observation period is required for
these evaluation repairs.
