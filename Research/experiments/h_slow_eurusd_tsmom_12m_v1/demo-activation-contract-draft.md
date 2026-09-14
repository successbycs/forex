# Draft: H_SLOW EUR/USD Demo activation contract

Status: **human-completion template; not approved or active**. Completing text
in this file does not activate H_SLOW, change a configuration, create a lease,
select an account, or establish broker proof. The current policy remains the
disabled research component described in [protocol.md](protocol.md).

`GOMarketsMU-Live` is forbidden. This draft must never be used to select a
Live account, terminal, server, credential, route, or saved login. It does not
increase the existing M1 cap, and an unfilled placeholder is not implicit
authority for an alternative cap.

## How to complete this contract

All `HUMAN DECISION REQUIRED` fields need an explicit human decision and an
immutable dated record before the associated deployment work begins. `EXISTING
FACT` fields describe the present repository situation and must be re-checked,
not copied as approval. A proposed value is not a decision. Secrets, account
numbers and credentials belong only in approved secret/local operator storage,
never in this document or evidence export.

## Scope and immutable safety boundary

| Field | Value / completion required |
| --- | --- |
| Instrument | **EXISTING FACT:** EUR/USD only. |
| Policy | **EXISTING FACT:** `forex.h-slow.eurusd-tsmom-12m.v1`; monthly 12-month completed-daily-close target. Any rule change needs a new policy version. |
| Server | **HUMAN DECISION REQUIRED:** exact Demo server identifier: `________________`. It must equal `GOMarketsMU-Demo`; otherwise activation is prohibited. |
| Live boundary | **EXISTING FACT:** `GOMarketsMU-Live` is structurally prohibited. No exception is available through this draft. |
| Trial authority and review | **HUMAN DECISION REQUIRED:** authority starts on activation and continues until Chris revokes it. Record the UTC review cadence and the fail-closed suspend/revoke procedure: `________________`. No automatic risk increase or policy change follows continued authority. |
| Human authority record | **HUMAN DECISION REQUIRED:** identity, date, decision reference and confirmation that account/risk/holding scope was reviewed: `________________`. |

## Account and terminal isolation

Preferred deployment is one separately configured Demo account and terminal
instance for H_SLOW. The current executor is single-owner and is not a
multi-stream deployment surface.

| Field | Completion required |
| --- | --- |
| H_SLOW Demo account identity | **HUMAN DECISION REQUIRED:** non-secret account label/approved identifier: `________________`. Do not select any saved login merely because it exists. |
| Terminal identity and host scope | **HUMAN DECISION REQUIRED:** approved terminal instance label, host/operation identity and deployment owner: `________________`. |
| M1 separation confirmation | **HUMAN DECISION REQUIRED:** record the distinct M1 account/terminal (non-secret label only) and confirm no shared state, lease, monitor path, magic/owner ID, audit/idempotency key space or local state directory: `________________`. |
| H_SLOW identifiers | **HUMAN DECISION REQUIRED:** unique stream ID, owner ID, magic ID, lease namespace, monitor-job identity, audit/idempotency namespace and state path: `________________`. |
| Shared-account alternative | **NOT APPROVED BY DEFAULT.** If proposed, it requires a separately recorded mandate change and verified atomic reservations, per-stream budgets, exact-ticket ownership, hedging/netting behavior, gross exposure/margin reporting and a two-position authority. Until then, activation is prohibited. |

This section implements the isolation requirements in
[`docs/parallel-demo-streams.md`](../../../docs/parallel-demo-streams.md); a
separate account alone does not prove isolation.

## Limits, sizing and feasibility

No current M1 allowance automatically applies to H_SLOW. All values below
must be explicit and must form one aggregate experiment budget across M1 and
H_SLOW; a second account must not double exposure by implication.

| Field | Completion required |
| --- | --- |
| Per-stream maximum open positions | **HUMAN DECISION REQUIRED:** `________________`. |
| Aggregate maximum open positions/exposure/risk across streams | **HUMAN DECISION REQUIRED:** `________________`. If it differs from existing approved caps, record the separate mandate/configuration change before activation. |
| Per-trade loss, daily/weekly loss and drawdown limits | **HUMAN DECISION REQUIRED:** exact values, currency, accounting basis and approved resume authority: `________________`. |
| H_SLOW notional/volume limit and cumulative lease budget | **HUMAN DECISION REQUIRED:** `________________`. |
| Sizing formula | **HUMAN DECISION REQUIRED:** deterministic formula, rounding direction, currency conversion, risk input and fail-closed condition: `________________`. |
| Minimum lot/step, contract size, tick value and margin | **HUMAN DECISION REQUIRED:** broker-observed values/source/time and feasibility rule. If minimum volume exceeds risk or margin headroom, return `NO_TRADE`: `________________`. |
| Pre-submit recheck | **HUMAN DECISION REQUIRED:** exact fresh quote, margin, exposure, account/server, cap and persisted-intent checks: `________________`. |

## Protection, entry, rebalance and exit

The pure policy output is not an order instruction. An activated adapter must
be separately implemented and verified after this contract is approved.

| Field | Completion required |
| --- | --- |
| Monthly decision input | **EXISTING FACT:** on UTC day 1 only; at least 240 completed daily bars, 13 required monthly closes, and closed/available-at validation. |
| Entry rule | **HUMAN DECISION REQUIRED:** whether an eligible target opens a new position, exact execution time/window, quote requirements, duplicate refusal and `NO_TRADE` handling: `________________`. |
| Rebalance rule | **HUMAN DECISION REQUIRED:** one persisted decision/rebalance attempt per signal month; define treatment of an unchanged target: `________________`. |
| Reversal rule | **HUMAN DECISION REQUIRED:** close-first/open-later ordering, confirmation/reconciliation, timeout and fail-closed behavior. Opposite signals must never offset or modify M1: `________________`. |
| Protective stop | **HUMAN DECISION REQUIRED:** deterministic placement, broker-side submission/verification, minimum distance, gap behavior and rejection handling: `________________`. |
| Take-profit/trailing/time exit | **HUMAN DECISION REQUIRED:** exact rule or explicit `none`; no discretionary or LLM override: `________________`. |
| Maximum holding and authority revocation | **HUMAN DECISION REQUIRED:** exact maximum holding rule and revocation management. A disable-new-entry action must preserve management/reconciliation of existing exposure: `________________`. |
| Failed close / unknown submission | **HUMAN DECISION REQUIRED:** preserve unresolved attempt/position, block duplicate submission, reconcile exact ticket, and specify escalation: `________________`. |

## Financing, rollover and weekend treatment

| Field | Completion required |
| --- | --- |
| Long/short swap and triple-rollover convention | **HUMAN DECISION REQUIRED:** broker-observed schedule, units, source/time and how it enters risk/reporting: `________________`. |
| Commissions, spread, slippage and conversion | **HUMAN DECISION REQUIRED:** observed values or explicitly labelled approved Demo estimates; unknown costs are not zero: `________________`. |
| Overnight permission | **HUMAN DECISION REQUIRED:** permitted/prohibited, stop/protection verification and action when data/terminal is unavailable: `________________`. |
| Weekend/holiday permission | **HUMAN DECISION REQUIRED:** permitted/prohibited, latest close deadline, gap assumption, holiday calendar source and failed-close escalation: `________________`. |
| Rollover protection | **HUMAN DECISION REQUIRED:** required pre/post-rollover reconciliation and handling of missing/changed charges: `________________`. |

## Monitoring, reconciliation and failure handling

| Field | Completion required |
| --- | --- |
| Daily operational summary | **HUMAN DECISION REQUIRED:** UTC schedule/owner and required per-stream plus aggregate fields: decisions, rejects, attempts, positions, exposure, marked-to-market, costs/financing, drawdown, incidents and coverage: `________________`. |
| Weekly review | **HUMAN DECISION REQUIRED:** schedule/owner and separate operational, strategy-economics and operator-viability conclusions: `________________`. |
| Reconciliation | **HUMAN DECISION REQUIRED:** cadence and exact broker identifiers/fields for orders, positions, deals, P&L, commission, swaps, balance and ownership. M1 and H_SLOW must remain separately attributable: `________________`. |
| Health and recovery | **HUMAN DECISION REQUIRED:** monitor health, restart procedure, state/lease recovery, stale data/terminal outage behavior and escalation contact: `________________`. |
| Safety failure / limit breach | **HUMAN DECISION REQUIRED:** fail-closed disable-new-entry action, position-protection checks, manual-resume authority, evidence retention and incident review: `________________`. The pre-activation mandate must retain this as a separate non-secret `risk_resume_authority_reference`; it is a reference to an approval record, not a capability grant. |
| No forced evidence | **EXISTING FACT:** no order, close, risk-pause bypass or restart is permitted merely to create a lifecycle, rollover or recovery record. |

## Events, release, evidence and review gates

| Field | Completion required |
| --- | --- |
| Economic events | **EXISTING FACT:** annotation only for v1; missing annotations do not manufacture `CLEAR` or silently veto H_SLOW. Any event eligibility rule requires a new versioned policy and fail-closed coverage/timing contract. |
| Release/configuration binding | **HUMAN DECISION REQUIRED:** exact reviewed release/revision, governed configuration fingerprint, H_SLOW policy version and any approved adapter/state schema version: `________________`. |
| Pre-activation verification | **HUMAN DECISION REQUIRED:** commands/results covering policy direction/clock/data, sizing, protection, account binding, persistence, duplicate refusal, ownership, recovery and reconciliation: `________________`. |
| Evidence plan | **HUMAN DECISION REQUIRED:** retained raw observations, redaction declaration, decision snapshots, timestamps, hashes, broker responses and independent verification location: `________________`. |
| Review gates | **HUMAN DECISION REQUIRED:** named human/operator review, required independent technical/domain review, and applicable formal milestone/contract amendment gates: `________________`. |
| Activation declaration | Leave blank until every prior field and applicable verification/review gate is complete: `________________`. |

## Explicit non-claims

This draft does not state that H_SLOW is deployed, isolated, safe to trade,
profitable, funded-ready, or proven. It does not alter `project_state.json`,
`milestone_registry.json`, runtime configuration, account selection, terminal
selection, lease, risk cap, routing, or order behavior. Actual activation and
formal completion require their separately applicable authority, evidence and
review gates.

## Recorded operator decisions — 2026-09-13

The following decisions were explicitly supplied by Chris for the initial
H_SLOW **Demo** trial. They supersede a conflicting blank field in this draft,
but do not turn the pre-activation mandate into execution authority or select
the machine-local login. They are represented by the reviewed canonical
pre-activation files in `config/`, which remain
`PRE_ACTIVATION_REVIEWED` / `DISABLED_NOT_ROUTED`.

| Decision | Recorded value |
| --- | --- |
| Server and instrument | `GOMarketsMU-Demo`, EUR/USD only. |
| Stream and terminal labels | `H_SLOW`, `H1_demo`, `h1_demo_scope`, `h1_demo_terminal`; dedicated terminal, distinct from M1. |
| Trial and resume references | `h1_trial`; `resume_h1`. |
| Authority duration | Begins only after the exact activation checks pass; ongoing until Chris revokes it. No fixed end date is required or implied. |
| Position and fixed initial caps | One position; 0.01 lots maximum; AUD 1,000 maximum loss; USD 10,000 maximum notional; USD 100,000 lease ceiling. These are ceilings, not targets. |
| Risk change | No confidence, recent-result, reload-capacity or inferred-edge based increase is permitted in the initial trial. |

The remaining blank fields below are not administrative delays. They are the
exact execution semantics still needed before an order-capable adapter can be
created: deterministic entry/exit/protection and hold management, observed
financing/cost treatment, operational monitoring/reconciliation and the
machine-local terminal binding. Until those are bound and independently
verified, H_SLOW remains submission-disabled.
