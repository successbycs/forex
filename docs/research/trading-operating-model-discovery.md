# Trading operating model discovery — 2026-09-23

## Recommendation

Prioritise finishing the existing M30 Demo workflow: a natural protected EURUSD
trade, mandatory close, reconciliation, verification and required review. The full
operating-model architecture is a future target, not an MVP prerequisite.

MVP completion means the existing milestone's protected Demo lifecycle is
reconciled, its evidence passes verification, and the required review and human
approval gates are satisfied. Reuse valid existing proof; do not demand another
trade or a runtime deployment solely for this operating-model proposal.

The only optional near-term improvement recommended here is a small change to the existing
operator view: explain “no qualifying trade”, “waiting for fresh prices”, and
“confirmed scheduled closure” distinctly. Show market hours only when verified;
otherwise show “schedule unknown”. Reuse existing observations, rules and reporting
components. Do not make this presentation improvement a gate to M30 execution or
proof, and do not build a calendar service to supply a missing display value.

Defer full PostgreSQL policy publication/activation records, a generated playbook,
new calendar enforcement, and wider rule consolidation until after the M30 MVP.
Option A remains the preferred future architecture: compose existing authoritative
rules into a complete versioned publication retained in PostgreSQL. Chris's
requirement that all trading information belongs in PostgreSQL remains in force;
the outstanding schema work is explicitly deferred, not claimed complete.

An observed defect in account identity, risk, protection, exit capability or audit
integrity still requires repair before the operation that depends on it proceeds.
Optional architecture improvements must not become invented safety prerequisites.

This is a design recommendation, not an implemented publication service. No live
database inspection, migration, runtime deployment, or broker action was performed.
The offline prototype demonstrates representation and shared rendering only.

## D1: current ownership and rule inventory

Inspected revision: `b4e1bdec6de07f60127e4ba52f3441a3665d386f`, with existing
unrelated worktree changes preserved. Sources below are repository evidence.
“Enforced” means implemented in inspected code; deployment of each rule was not
revalidated in this discovery. Existing operational observations cannot establish
every rule's current deployed value.

| Rule / status | Current meaning and authority | Loader / consumer | Persistence and human description | Relevant verification source |
|---|---|---|---|---|
| DEMO_SCOPE / enforced | Demo EURUSD only, runtime.yaml plus fixed SERVER/SYMBOL constants | config.load_configuration; adapter release; runner.capture | demo_trade_session/proposal; m1-demo-decision-workflow.md | tests/test_config.py; tests/milestones/test_m20.py |
| SESSION_CALENDAR / unknown | No complete qualified broker weekly/daily/holiday calendar found | No session-calendar consumer in inspected fixed catalogue | No complete calendar/version entity found in inspected migrations; capability-architecture.md acknowledges gap | No dedicated deployed session-calendar proof found |
| QUOTE_FRESHNESS / enforced | Runner MAX_TICK_AGE_SECONDS=30; separate financing conversion quote limit is 10 seconds and currently deferred | runner._market_selection/capture; listener waits for fresh quote | demo_decision_snapshot.freshness_seconds; operator report | tests/milestones/test_m20.py; tests/milestones/test_m20_listener_service.py |
| SPREAD / enforced | General selection requires <=12 points | runner._market_selection/capture; m20_policy_kernel.market_selection | snapshot spread and strategy selection; operator view | tests/test_m20_policy_kernel.py |
| STRATEGY_SELECTION / enforced | Five strategies; fixed selection order and one owner; session breakout alone uses 07:00 <= UTC hour <20 | runner._strategy_assessments and kernel counterpart; fixed Python constants | demo_strategy_selection / assessments; m1_multi_strategy_execution.md | tests/test_m20_policy_kernel.py |
| RISK / enforced | runtime.yaml: 0.10% and AUD100 per trade, daily 0.50%, weekly 1%, drawdown 2%; account-wide one-position and notional caps remain | adapter embeds policy; listener loads environment; runner requests bridge.enforce_risk_policy and reserve_execution | demo_risk_policy_state, independent pause fields from migration 022; runtime.yaml/workflow | tests/milestones/test_m20_risk_policy_persistence.py |
| SUBMISSION / enforced | Persist proposal, reserve once, revalidate, then sole entry order_send; duplicate proposal never resubmits | runner.capture; bridge.persist_proposal/reserve_execution | migrations 006 and 024 candle identity, demo_execution_attempt; workflow | tests/milestones/test_m20.py |
| PROTECTION_EXIT / enforced | Broker SL/TP; owner holds 10/8/10/6/10 minutes for momentum/compression/pullback/range/session; opposite-candle invalidation | runner._owner_exit_contract/_monitor_open_position/recover_open_positions | demo_open_position_state, position events/outcomes; strategy trial docs | tests/milestones/test_m20.py; listener service tests |
| RECONCILIATION / enforced | Broker history and costs determine outcome; unresolved state differs from closed | runner._closed_position_costs/_record_closed_monitor_outcome; bridge.reconcile | trade outcome and ledger, migrations 007–010, 018/021; operator report | tests/test_postgres_pgvector_adapter.py; M30 verifier |
| FINANCING / deferred | DEFERRED_FOR_DEMO, empty rollovers; no qualified charge/calendar | runtime.yaml -> environment -> runner.project_financing | policy/state in retained assessments; workflow explicitly labels deferral | tests/test_m20_financing.py |
| MANUAL_ATTRIBUTION / deferred gap | Existing listener magic identifies its execution; full account-wide manual/external provenance entity remains deferred | listener execution/history readers; no complete manual classification writer established | risk resumes exist, but do not replace a manual-trade ledger; controlled-demo plan deferral | No complete manual-attribution acceptance proof found |
| OPERATOR / enforced controls, partial playbook | Operator-managed client; fixed hold/recovery/resume functions; independent manual-review risk reasons | listener and fixed catalogue, bridge.resume_risk_policy | demo_risk_policy_resume append-only; unblocking plan and operator view | risk persistence and listener service tests |

The loader is not a hot-reload guarantee: `src/forex/config/__init__.py`
validates YAML and constructs effective configuration; `scripts/t480_adapter.py`
packages runtime values into the fixed release; listener configuration loads
`FOREX_M20_*` environment values; the runner consumes those values. Editing local
YAML alone does not change the deployed listener. Fingerprints in current session
and proposal records provide identity, but are not the complete policy contents.

Migration 006 is historical: subsequent migrations 011 and 016 change the old
finite lease and trade-count restrictions. Reading only 006 would misstate current
policy. Migration 019 stores mutable risk state, not an approved rulebook; 020
stores resume records and 022 extends independent pause handling. Database schema
deployment is unverified here. The report intentionally makes no claim that a
universal operating-policy table currently exists.

Current path:

    YAML + code constants -> adapter release -> listener/runner
                                    -> bridge -> PostgreSQL decisions/outcomes
    retained listener/account observations -> operator report

Proposed path:

    Reviewed Git inputs + qualified source receipts
        -> one immutable publication (full content + digest)
        -> PostgreSQL publication and activation records
        -> deployed verified copy -> decisions referencing that publication
        -> human playbook and terminal explanation using the same identity

“Authoritative” is scoped: Git owns proposed rule edits; an append-only activation
record owns which published version became effective; PostgreSQL owns retained
trading facts; deployed bytes are a verified copy. Neither a local file nor a UI
may independently activate policy. For existing positions preserve the rule version
captured on entry and its owner; a new publication must not silently change exits.

Precedence: Chris's current M30 authority and explicit deferrals take precedence
over broad architectural aspirations. The capability-architecture document places
session work before unattended operation; the narrower current contract permits
the bounded Demo loop with freshness/spread checks and deferred calendar policy.
Record that scope distinction; do not manufacture a new M30 completion requirement.

## D2: primary-source evidence

All sources below were opened on 2026-09-23. Publication/effective dates are
unspecified unless stated. These are source-reading notes; web tool observations
are not an immutable broker-qualified production calendar receipt.

| Source | Finding / applicability | Limitation |
|---|---|---|
| [GO Markets MU FAQ](https://www.gomarkets.com/en/faqs) | MU entity identified in footer; describes platform UTC+2/+3 and financing at platform midnight | No exact seasonal transition calendar, EURUSD weekly opening/closing, daily trading break, or Demo-specific guarantee |
| [MU Forex page](https://www.gomarkets.com/en/markets/forex-cfds) | Describes Forex offering | Not a dated instrument session specification |
| [MU maintenance page](https://www.gomarkets.com/en/maintenance-schedule) | Table lists MT5 maintenance on 26 September, 10:00–15:00 UTC | Rendered row lacks year and named Demo server; does not establish 23 September closure or recurring trading hours |
| [MetaQuotes SymbolInfoSessionTrade](https://www.mql5.com/en/docs/marketinformation/symbolinfosessiontrade) | MQL5 API reports weekday/session-index start/end as seconds after midnight; date part ignored | Capability documentation, not actual broker hours; cannot assume the API exists in Python |
| [MetaQuotes Python API](https://www.mql5.com/en/docs/python_metatrader5) | Published Python function list provides symbols, ticks, account and orders; no session-trade getter listed | Negative documentation finding, not runtime probing; MQL5 and Python must not be conflated |
| [MU disclosure PDF](https://lp.gomarkets.com/docs/mu/MU-Disclosure-Statement.pdf) | Fetch attempted | Browser returned internal error; no PDF finding adopted |

No qualified weekly opening, daily break, or current holiday exception was
established. Financing midnight must not be reinterpreted as a closed session.
The fixed Forex catalogue inspection found no operation returning an enumerated
weekly quote/trading schedule. Calling existing status repeatedly cannot obtain it.

Smallest next qualification: retain EURUSD's trading and quote session
specification from the intended Demo terminal with server/symbol identity and
capture time, plus broker evidence for clock transitions and dated exceptions.
If automation is necessary, separately propose a fixed read-only terminal-local
MQL5 export of session rows and identity; do not invent a Python call or add a
generic shell. An operator-visible specification capture can qualify initial
values without first building a service. A weekly schedule alone cannot prove
holiday coverage or actual broker execution availability.

## D3: options and decision

All options below are designs, not current capabilities. Approval and activation
must be distinct from editing. Each must retain full policy content, input/source
digests, known/effective times, and per-decision references in PostgreSQL.

| Criterion | A: compose existing config/code | B: dedicated policy file | C: PostgreSQL policy authoring |
|---|---|---|---|
| Sole rule writer | Existing Git source owners; publication compiler extracts values | Git policy file; move values out of old owners before adoption | Controlled database writer with approval workflow; Git exports read-only |
| Activation / loading | Reviewed release + immutable DB activation; verified runtime copy | Same, with new loader/schema/fingerprint integration | DB-approved version exported to signed/verified deployment artifact |
| PostgreSQL traceability | PASS by design with full publication + activation + decision links; missing today | PASS with same required additions | PASS with immutable version rows and decision links |
| Single authority | PASS if extracted values are not separately editable | FAIL if existing values remain editable duplicates; PASS after migration | PASS if Git/runtime copies cannot independently activate edits |
| Truthful unknown state | PASS with explicit schedule/observation separation | Same | Same; database does not supply missing broker facts |
| Rollback / conflict | Append activation of prior reviewed compatible version; compare full digest | Same plus migration compatibility | Same plus authoring and export recovery |
| Database outage | No new entries when existing audit unavailable; protect positions through existing owner path | Same | Same; authoring/activation also unavailable |
| Human view | Generated effective values + maintained explanations | Natural grouping, but risks copied constants | Requires database-backed editor/export for convenient human review |
| M30 impact / effort | Lowest initial effort; report can inventory existing rules without runtime adoption | Medium; loader changes and rule migration broaden proof impact | Highest; new authoring, access-control, publication and recovery workflow |

Prefer A for a later operating-model implementation, not the next MVP delivery.
The next proposal is limited to P1's existing operator view. A dedicated file (B) can become useful
when qualified session facts need their own authoring lifecycle, but is not
necessary to establish one human entry point. C becomes preferable if operational
policy editing must occur through a multi-user application and existing publication
controls make Git authoring the bottleneck. Neither condition was demonstrated.

This future design would satisfy PostgreSQL retention without treating repository
files and database records as identical authorities. Deferred data contract:
publication(content, digest, rule/source/code identities, known_at, effective_from,
valid_until), activation(publication_digest, deployed_release, observed_at, authority),
and decision reference(publication_digest, exact observed facts, reason). These
are design concepts, not approved table names or a schema migration. Retain raw
source evidence under the existing raw-evidence policy and its reference/hash in
PostgreSQL; record full source receipts/content there as required by the future
trading-information schema, rather than keeping only an unrecoverable URL.

## D4: local demonstration and limits

`research/operating_model_discovery/demo.py` consumes one synthetic publication
and timestamped examples, emits JSON or a human view, and includes no production
imports or external calls. Seventeen examples cover boundaries, breaks, weekends,
dated holidays, explicit seasonal offsets, Auckland daylight saving, calendar gaps,
unknown/expired facts, stale feed, unsafe spread, mismatched policy and existing
position handling. Dated intervals are deliberately used to avoid pretending an
unqualified timezone name or weekly recurrence engine is proven. Holiday precedence
is represented by already-resolved intervals, not an implemented notice compiler.

Nine local tests now pass. They check boundaries, stale-versus-closed,
unknown transitions, identity conflicts, output parity, future knowledge and
protection handling. They do not test publication to PostgreSQL, deployment,
live calendar acquisition, or production trading. Synthetic quote/spread inputs
are examples; source-referenced runtime thresholds must be extracted in production,
not maintained as a second handwritten rule set.

Observed example results:

    stale_feed: scheduled OPEN; observed STALE_OR_UNKNOWN; entry BLOCKED
    unknown_calendar: scheduled UNKNOWN; next transition null; entry BLOCKED
    at_open: session CANDIDATE_ONLY; execution NOT_EVALUATED_NO_ORDER_CAPABILITY
    exit_unavailable: EXIT_UNRESOLVED_CONTINUE_PROTECTION

Both prescribed CLI commands completed successfully for all 17 examples, and
the policy hashes matched across formats. Text defaults to a concise explanation;
`--details` adds all audit fields from the same object. A separate review found
that a future conflicting interval could falsely predict an opening. The repaired
evaluator checks the earliest intervening boundary and all rows active there;
unknown/conflicting targets suppress the prediction. Its regression test passed.

The QA-verification matrix is covered by nine tests: regular/break/holiday/weekend
boundaries, expired/missing policy, stale-versus-closed, spread and absence of
execution authority, seasonal offsets, existing protection/unresolved exit,
JSON/text parity, future knowledge/bad numeric input, and future interval conflict.
No production test or M30 proof is claimed by these local checks.

## D5: delivery proposal and acceptance

Delivery order: complete M30's existing proof, required repairs, review and
approval gates first. P1 is optional supporting work, not an intervening wave or
completion gate; defer it too if it would delay M30. P2 and P3 are deferred
until after M30 unless a separately evidenced safety defect requires an earlier
targeted repair. Neither missing market-hour display data nor an absent publication
system is, by itself, a reason to stop the authorised Demo workflow.

P1 — optional, small operator-visibility improvement: use
`docs/workflows/m1-demo-decision-workflow.md` and extend the existing operator
report with scheduled state (initially UNKNOWN), observed feed state, current
decision reason, and effective-version availability. Reuse report inputs; do not
infer broker closure or claim an effective policy digest absent from observations.
This supports M30 operator visibility; map the exact report changes to its
existing supporting-reader scope. Test `tests/test_listener_workflow_report.py`
and inspect the terminal against retained current observations. Reader-only work
should not invalidate runtime proof. Roll back only owned report edits. P1 is the
smallest useful follow-up; it does not complete the full target model.
Acceptance is that the operator can distinguish no setup, unavailable fresh
prices, and a source-confirmed closure without reading raw JSON. Unknown schedule
information must remain unknown. No new policy store, migration, publication
service, rule extraction framework, strategy change or trading-hour veto belongs
in P1. If P1 requires those additions, reduce it to explaining existing facts.

P2 — deferred after M30: qualify the actual schedule, define session-policy fields/schema under
`config/runtime.yaml` and `config/schemas/runtime.schema.json`, add publication
construction through `src/forex/config/` and fixed deployment binding in
`scripts/t480_adapter.py`, then evaluate through an explicitly shared session
function at runner entry. Keep feed/schedule/entry/exit semantics separate.
Add a narrowly scoped PostgreSQL publication/activation/decision-reference
migration and bridge integration in the same delivery so rules used for trades
remain reconstructible. This requires an explicit M30 scope amendment or a
separate later contract before runtime/schema adoption: the current contract
defers calendar gates. It is not a prerequisite silently added to current proof.
Verify missing/stale schedule, DST boundaries, holidays, mismatches and DB failure;
check transport and release-readiness before deploying. Retain real session-boundary
observations and a lifecycle on the adopted version if required by affected M30
proof. Revert through a reviewed previous publication/release, preserving all
audit history and current-position owner contracts; never update raw evidence.

P3 — deferred after M30: consolidate broader strategy/risk/operator lifecycle documentation and full
account ledger including manual attribution. This remains the deferred later phase,
requiring a suitable new/amended contract and a dedicated schema plan; no assumption
that M31 authorises it. Reuse unaffected M30 evidence, run targeted migration and
attribution tests, retain genuine account history for reconciliation, and require
a tested compatible rollback/forward repair before deployment.

Discovery requires no trade, no schema migration, and no new scheduling service.
No runtime rule or market hours were changed. Production acceptance and formal
milestone closeout remain separate from this design review.

## Assumption audit

| Earlier assumption | Finding / change |
|---|---|
| New policy file is best | Not supported now; prefer composition of current owners |
| Weekly timetable sufficient | Rejected: dated exceptions, clock basis and observations required |
| Quiet feed proves closed | Rejected: maintain UNKNOWN and independent feed state |
| Generated playbook sufficient | Values can be generated; explanations and responsibilities need maintained prose |
| DB only needs hashes | Rejected: complete policy and decision-time facts needed, hashes alone insufficient |
| Calendar enforcement belongs immediately in MVP | Not established; P1 visibility is smaller, P2 changes policy and proof |
| Hours define operating model | Rejected: inventory includes risk, strategy, execution, protection and reconciliation |

## Source identity and review record

Key inspected SHA-256 values (current working bytes, not a deployed attestation):

    config/runtime.yaml d7c41d0ac39b63361ec9f82aaae8d391d2bca2534c5c48fd7a5749404b0997b2
    t480/m20_demo_trading_session.py 7ae1eacd792120f51367e5e0ccb88c60316945534f214228bedbbc73421aa623
    t480/m20_demo_listener_service.py 2c02581178e47a259bd8aa15541a6dbec09441a9abd5dc9e679b321e9c538c15
    t480/m20_postgres_audit_bridge.py 3101deebfaaff0f6630a92bea8f98fadcdd7bbcc6da24aef7cabf7f166946e6e
    src/forex/m20_policy_kernel.py 41c06cfb700319de2070514aadd8793cd4970f3523a8d83d597dd27431b887ef
    scripts/listener_workflow_report.py c6820bb82a49edf618921543fe3a03f37eae466c673d1b1efcc792cbff0b9481

Independent reviewer `/root/operating_model_review` completed read-only D5 review
on 2026-09-23, reran all nine tests and confirmed no remaining discovery blockers
after the future-transition repair. Follow-ups: translate reason codes into plain
language for P1, qualify actual Demo sessions for P2, and specify database/publication
interfaces in the separate implementation contract. None grants deployment approval.

Reviewed artifact digests (report digest precedes final verification/review notes;
prototype bytes below were reviewed after repair):

    report 7e1145cca26f2d27b6c73e2480f8e4320a795e6a7c6a97d1888e48b68234aa30
    demo.py c8cd51d28b0ee9530a73147065e9c5a50c58674f4dc16261a6a29f0d38cabf87
    examples.json b8a0479af14792a2737688fc3c4808ad50532cd133c3268905397fdb9bfda35b
    test_demo.py 8310d7100830899e437cdb54dcf4c7595ecff83d8ee4c44e204d30c4e9c6fcb1

Final local verification: nine tests pass; both CLI formats run for 17 examples;
formatting and milestone governance validation pass. Owned files are this report,
the discovery plan/work record, and the three isolated prototype files. Existing
unrelated changes were preserved. No commit, migration or deployment performed.
