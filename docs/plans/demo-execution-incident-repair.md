# Restore truthful Demo execution status and reconcile the September 23 incident

This living ExecPlan follows PLANS.md. Chris requested review, an ExecPlan and
implementation on 2026-09-23. The objective is an observable Demo workflow:
operators can distinguish a running process, blocked entries, genuine absent
signals and verified broker execution.

## Formal milestone dependency map

M30–M32 are reusable proven prerequisites. M33 remains the formal active
closed-trade commission-reporting milestone. Its reporting repairs can proceed;
it does not authorize broker actions or changing risk accounting. This explicit
incident-repair request authorizes local investigation and repair preparation.
Chris explicitly approved the proposed incident-specific risk-accounting
amendment, commit and fixed deployment in the next message, "approve".
The M33 contract records this narrow exception. It permits the exact loss
correction and reporting/reason repair, not general risk changes or forced trades.
Do not alter formal milestone state or describe this task as M33 closeout.

## Progress

- [x] Review current source and fixed database/broker observations.
- [x] Repair scoreboard source and verify the bounded diagnostic against PostgreSQL.
- [x] Display persistent risk blocks and position gates in both terminal views.
- [x] Correct runner refusal reasons and retain heartbeat risk fields locally.
- [x] Verify local repairs and specify the exact operational accounting correction.
- [ ] Deploy reviewed runtime/accounting changes under the operational amendment.
- [ ] Verify risk readiness, a fresh eligible decision and broker reconciliation.

## Evidence and discoveries

The fixed completeness query for 2026-09-22T17:00Z–2026-09-23T05:05Z returned
473 proposals, all NO_TRADE, zero attempts: 472 generic no-selection reasons
and one EXTERNAL_CASH_FLOW refusal. This does not prove 472 absent signals.
The retained later diagnostic returns 474 rows for the same bounds (not an
immutable snapshot): 469 generic unsafe-gate refusals, four no-clear-regime
refusals and one EXTERNAL_CASH_FLOW refusal. Of these, 34 pre-close decisions
had BUY/SELL signals but failed selection; another signal was risk-paused.
All 474 decisions are NO_TRADE with zero attempts. The earlier claim of no
signals is retracted. Historical generic reasons cannot prove the specific
failed gate for every row; current observations separately confirmed the
existing-position gate failed while the four positions were open.
_market_selection refuses any failed safety gate, but _strategy_trade_plan
then returns a generic no-selection reason. The heartbeat also discards
risk_policy and the compact operator report omits it.

Broker history shows opening deals for positions 43135808–43135811 at raw
1790124764. The export explicitly declares broker_timestamp_offset_seconds=10800;
subtract this before converting to UTC/NZ time. Earlier 12:52 opening claims
omitted that offset. All four entries are BUY 0.02 at 1.14518. Closing deal
profits are -7.12, -7.10, -7.21, -7.21 AUD, with zero reported commission,
swap and fee. Their -28.64 total exactly bridges 100989.45 to 100960.81.
Magic zero and blank comments do not identify who created these entries.
Chris confirms manually closing them and denies manually opening them.

The scoreboard references nonexistent demo_trade_ledger.trade_owner_strategy_id.
Ownership is available from demo_strategy_selection, joined by proposal_id.
The existing risk-resume flow treats a balance difference as a cash movement
and shifts equity anchors. Using it for these trading losses would erase their
effect from drawdown measures. Reconcile losses before considering resume.

## Plan of work

Fix sql/m20_strategy_trial_summary.sql ownership joins and count wins/losses
only for verified outcomes. Add a fixed, bounded read-only diagnostic operation
in scripts/postgres_pgvector_adapter.py using validated UTC bounds, showing
recorded signals, failed selection, proposals and attempts for the same period.
Fix scripts/listener_workflow_report.py to show blocked or unknown risk even
when the last decision has no signal. Preserve risk_policy in the listener
heartbeat and precise failed gate names in the runner's refusal reason.

For account reconciliation, retain broker raw bytes with
scripts/m20_all_history_capture.py. Prepare an additive immutable incident
record holding account scope, all eight deal IDs, opening/closing facts,
charges, source digest, unknown entry attribution and operator-confirmed close.
A transaction must lock the risk row, verify the exact starting balance and
source, add -28.64 once to expected balance, preserve daily/weekly/peak anchors,
and avoid changing any unrelated pause. Never invent a strategy proposal.
This accounting deployment is authorized by the operational amendment above.

## Validation and acceptance

Run focused PostgreSQL adapter, listener report, listener service and runner
tests with python3 -m pytest. Test position-gate refusal, no-signal plus risk
pause, absent risk, stale heartbeat, scoreboard ownership and verified-only
results. Run git diff --check and python3 scripts/forex_milestones.py validate.
Measure changed fixed SSH envelopes below 7500 characters before deployment.
Real-world acceptance requires the formerly failing scoreboard query to run,
an operator screen showing the actual block, broker/expected balance agreement
without moving loss anchors, and a subsequent eligible Demo lifecycle.
Local tests alone do not establish trading recovery.

## Idempotence and recovery

All observations are read-only. Preserve raw evidence and existing accounting.
Accounting replay must be idempotent by account and deal identity; conflicting
source or changed balances must refuse. Resume must not approve unknown future
cash movement. Do not force a trade or loosen strategy criteria for proof.

## Decisions and outcomes

2026-09-23: prioritize specific refusal evidence and existing report repairs.
The half-day investigation must separate pre-close position blocking from
post-close balance blocking. No additional waiting period is a repair.
Runtime deployment, incident accounting and execution recovery remain pending.

## Approved exact accounting amendment — application pending

Use policy `forex.m20.conservative-risk.v1`, currency AUD, Demo account scope
`4b12a2cebac68fadc4009c52f46e1cda20bd3c731ef94428ed2b47a2d29faabf`.
The source of truth for the proposed correction is the unchanged adapter
response under `runs/incidents/demo-entry-20260923/m20-all-history-068bb6d05046fbf0/`,
SHA-256 `068bb6d05046fbf018362c22fcd35cbdc6920f3b520948d0a57d8f5096dbcf18`.
All eight complete original deal objects must be retained, not merely this table.

| Position | Entry deal | Closing deal | Actual net AUD |
| --- | --- | --- | --- |
| 43135808 | 35649111 | 35667306 | -7.12 |
| 43135809 | 35649112 | 35667308 | -7.10 |
| 43135810 | 35649113 | 35667309 | -7.21 |
| 43135811 | 35649114 | 35667310 | -7.21 |

The additive incident record must key each deal uniquely by account scope and
deal ticket; classify the entries UNKNOWN_ORIGIN and the closures
OPERATOR_CONFIRMED, without synthesizing strategy ownership. Correct timestamps
by the exported 10800-second offset; opening fills occurred at approximately
09:52:44 NZST on September 23, not 12:52.

Before application, obtain a fresh flat-account observation, complete broker
history and risk summary; refuse any differing source identity, previously
accounted deal, pending order/attempt or unexpected balance. In one transaction,
take the same policy advisory lock as the bridge, then lock the risk row.
Verify scope, expected balance 100989.45 and broker balance 100960.81. Insert
the immutable incident/deal records and apply exactly -28.64 to expected balance.
Preserve baseline, peak 100995.17, daily anchor 100989.45 and weekly anchor
100988.91 (as observed; reject an unexpected concurrent state rather than
overwriting it). Preserve their dates, all unrelated pauses and resume history.
Remove only EXTERNAL_CASH_FLOW once the audited delta is fully reconciled;
leave cash_flow_review_approved false and invalidate the cached risk observation
so the next ordinary check must re-evaluate all limits. Replay of an identical
applied incident must be a no-op; conflicting replay must abort. Do not use the
generic resume operation, a cash-withdrawal adjustment or a manual UPDATE.

Implement and test this additive migration/fixed operation under Chris's
explicit risk-accounting amendment to M33's reporting-only restriction.
Acceptance tests must include exact application, duplicate replay, changed
balance/source/scope, already-accounted deal, rollback and preservation of
other pauses and drawdown anchors. The migration and fixed apply operation
are now implemented locally; actual application remains pending verification.

## Verification, review and remaining boundary

Owned paths are this plan/work record, the two report/adapter scripts,
`sql/m20_strategy_trial_summary.sql`, the listener/runner reason projections,
and their four focused test files. No risk policy, strategy, order, account or
formal milestone settings changed. Raw observations are retained separately
under `runs/incidents/demo-entry-20260923/`.

The focused suite passed all 220 tests on September 23. The diagnostic's actual
encoded SSH envelope passes the less-than-7500-character regression. Independent
read-only review (`incident_repair_review`) found its earlier blockers repaired:
both views show current database pauses, stale/missing sources cannot assert
readiness, and tests cover complete refusal propagation and heartbeat retention.
The review's remaining PostgreSQL scoreboard behavioral check is still pending.
The minor full-view position-label observation was also repaired and tested.
Final checks: all 23 terminal-report tests passed after that last label change;
`git diff --check` and milestone validation passed. The task-specific
continuation checker returned BLOCKED with only the commit/source-binding and
explicit risk-accounting amendment decisions outstanding; downstream deployment
and real-world proof remain represented in the work record.

The local operator dashboard was checked against the running system: it showed
zero positions, balance 100960.81 AUD and ENTRIES BLOCKED: EXTERNAL_CASH_FLOW.
Retained `entry-diagnostic.json` SHA-256 is
`ca2260fb053ba4e9a1022d17d4da4aab75eb965d7b11c90fb5108266c8148d97`;
`risk-policy.json` SHA-256 is
`5e2e75616a5e7bf5d0a8fd5a719117ab6f905fd44766de09391e618b47f597f2`.

At the initial review, release readiness was NO-GO: source was uncommitted,
and the risk correction conflicts with M33's explicit exclusion of risk/account
changes. The current repair request permits local diagnostics/reporting fixes;
it does not silently amend that formal restriction. Reporting-query staging and
runtime reason deployment remain pending source binding; no remote mutation was
performed. The narrow operator decision is to authorize the incident-specific
risk-accounting amendment above and a commit/deployment of this repair package.
No strategy loosening, forced trade, general cash-flow approval or Live access
is requested. Do not describe current trading or whole-account P&L as repaired.

## Decision Log

2026-09-23, Chris: approved the precise requested exception to account for the
AUD 28.64 loss without resetting risk limits, then commit and deploy the package.
This removes the two prior authority blockers. Fixed adapters, fresh held/flat
checks, independent review and unchanged ordinary Demo gates still apply.
The deployment may release the temporary maintenance hold only after the new
release is verified healthy and the corrected account passes ordinary risk checks.

2026-09-23, implementation: extend the existing account identity observation
with pending-order count; an account with zero positions but pending orders is
not idle enough for the correction. Test migration behavior in a disposable
local PostgreSQL16 cluster, not on production fixtures. No runtime service or
dependency is added by this test environment.

## Implementation verification

The additive correction is `sql/operations/incident_20260923_reconciliation.sql`.
Fixed PostgreSQL operations are `forex-m20-stage-incident-20260923`,
`forex-m20-apply-incident-20260923` (both require `--approve`) and
`forex-m20-verify-incident-20260923` (read-only). No caller-controlled SQL,
account, amount or source path is accepted. Application hashes the retained
original response, compares all eight original deals to the reviewed SQL, then
requires fresh complete matching history, a flat account with no pending orders
and an acknowledged maintenance hold. SQL locks and verifies the risk row,
rejects unresolved execution or existing ownership, and records normalized
immutable incident/deal facts without creating strategy attribution.

All 24 incident tests passed, including actual SQL on disposable PostgreSQL16;
all 28 adapter tests passed. Independent review and final repaired-source hashes
are recorded in `docs/reviews/demo-execution-incident-20260923.md`.

First implementation commit: `0b0360c`. Subsequent pre-deployment sizing found
the existing runner fragment wrapper exceeded the transport limit. The unused
payload assignment and redundant root construction were removed; maximum
encoded fragment is now 7490 (<7500). Separate review cleared this repair and
all nine focused transport/install/account checks passed. No remote deployment
or maintenance hold occurred before this size check was repaired.

## Execution-work projection

<!-- forex-work-projection:start task=DEMO-EXECUTION-INCIDENT-REPAIR schema=forex.execution-work-projection.v1 -->
<!-- forex-work-item id=diagnose state=DONE -->
- [x] diagnose — Retain broker and PostgreSQL incident evidence (DONE)
<!-- forex-work-item id=local-repair state=DONE -->
- [x] local-repair — Implement truthful reporting and diagnostic fixes (DONE)
<!-- forex-work-item id=verify-review state=DONE -->
- [x] verify-review — Test and independently review local changes (DONE)
<!-- forex-work-item id=accounting-design state=DONE -->
- [x] accounting-design — Specify the exact loss-preserving incident correction (DONE)
<!-- forex-work-item id=commit-authority state=DONE -->
- [x] commit-authority — Authorize commit for source-bound deployment (DONE)
<!-- forex-work-item id=risk-amendment state=DONE -->
- [x] risk-amendment — Authorize the incident-specific risk-accounting amendment (DONE)
<!-- forex-work-item id=scoreboard-deploy state=PENDING -->
- [ ] scoreboard-deploy — Stage and verify the fixed PostgreSQL scoreboard (PENDING)
<!-- forex-work-item id=accounting-implementation state=DONE -->
- [x] accounting-implementation — Implement and test the additive fixed reconciliation operation (DONE)
<!-- forex-work-item id=runtime-deploy state=PENDING -->
- [ ] runtime-deploy — Deploy reviewed reason and accounting repairs through fixed adapters (PENDING)
<!-- forex-work-item id=real-world-proof state=PENDING -->
- [ ] real-world-proof — Verify balance agreement and a subsequent eligible Demo lifecycle (PENDING)
<!-- forex-work-projection:end -->
