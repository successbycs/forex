# Wave 1: Trustworthy Demo execution

Status: **PROPOSED — execute only on explicit operator instruction.**

Read the [shared wave guide](demo-income-waves.md). This wave covers original
activities 1–4. Its purpose is reliable exposure and accounting under durable
risk limits; it does not establish a profitable strategy.

## Activities, success, and real-world tests

| ID | Change and mission value | Success criteria | Real-world demonstration |
| --- | --- | --- | --- |
| W1.1 | Align M20, runtime limits, deployment, and operator documentation. The operator approved no total trade-count ceiling during development; retain the independent exposure and loss limits. | The approved unlimited development count policy matches contract, canonical config, effective release, and displayed limits; no unresolved contradictory execution rule. | Read back effective Demo limits and deployed release/configuration identity through the fixed surface; independently compare with approved artefacts. |
| W1.2 | Correct API-error, empty-position, open, partial-fill, rejected, and unknown states. Reconcile exact broker identifiers and opening/closing volume. This prevents false closures and unmanaged exposure. | API error never means flat/closed; partial or uncertain execution remains exposure-aware; entry-only history cannot close a position; retry/restart cannot duplicate an order. | Capture a genuine Demo OPENED-to-CLOSED lifecycle and controlled connection interruption/recovery. Compare application state with broker positions/deals. Retain actual partial-fill proof if observed; otherwise label that real-world condition pending and retain fault-injection coverage separately. |
| W1.3 | Reconcile fills, close volume, commission, fees, swap, and currency P&L; separate actual amounts from estimates. Trustworthy net results are necessary for strategy selection. | Every reported closed outcome matches attributable broker transactions within predeclared currency-rounding tolerance; no entry-as-exit, balance-as-profit, or duplicated execution cost. Incomplete history stays unresolved. | Independently recompute a predeclared sample of genuine closed Demo outcomes and aggregate totals from retained broker records. Include nonzero charge examples where actually available; zero-cost rows cannot prove nonzero-fee handling. |
| W1.4 | Add approved persistent equity-relative risk, loss/drawdown budgets, caps, and pause/resume rules. Size from a valid stop or refuse when minimum volume cannot fit. | Budgets survive process restart/session renewal; account cash flows do not masquerade as returns; breaches and unknown equity/exposure block entries while protection remains active. | Restart the deployed listener with an open protected Demo position and retained risk state. Use a temporary approved restrictive limit to demonstrate refusal, without deliberately creating losses. Read back state before/after restart and restore approved configuration with recorded provenance. |

## Starting points to revalidate

- `t480/m20_demo_trading_session.py`: position queries, order result mapping,
  history selection, monitoring, sizing, and cost capture.
- `t480/m20_postgres_audit_bridge.py` and `sql/migrations/`: reservations,
  durable state, outcome integrity, and cap enforcement.
- `t480/m20_demo_listener_service.py`: restart and stop behaviour.
- `config/runtime.yaml`, schemas, and `milestone_registry.json`: effective
  operator policy and contract consistency.
- Actual runner behavioural tests and active milestone verification commands;
  source-string assertions alone do not prove runtime behaviour.

These references are investigation starting points, not authorisation to
rewrite every component. Keep changes narrow and preserve historical records.

## Completion and exclusions

Prepare the activity plan and missing operator decisions first. Do not choose
capital risk tolerances or amend the contract without the required approval.
Complete independent authorised fixes while dependent work awaits decisions.

Wave completion requires its approved acceptance criteria and declared proof,
with no unresolved critical exposure or accounting defect. If a rare condition
cannot be observed, report the precise proof gap; do not silently weaken the
criterion. A progress handover does not claim completion.

Exclude new strategies, new AI trading influence, parameter optimisation,
additional instruments/positions, live access, and new infrastructure platforms.
Do not start Wave 2 or close M20 merely because Wave 1 tests pass.

## Copy-and-paste goal prompt

```text
/goal Execute Wave 1: Trustworthy Demo execution in this repository. Read docs/prompts/demo-income-wave-1.md and docs/prompts/demo-income-waves.md in full and treat their activity specifications, shared boundaries, evidence rules, and usage controls as this goal's execution brief.

Scope is W1.1-W1.4 only: align approved contract/configuration/deployment; correct order and position lifecycle handling; reconcile net broker P&L and costs; enforce approved persistent capital-risk boundaries. Verify previous findings against current code before editing.

First inspect Git status, applicable AGENTS.md, project_state.json, the active milestone contract, and docs/evidence_and_milestones.md. Prepare a concrete activity plan and identify missing operator risk decisions or exact contract amendments. Obtain required decisions before dependent changes; continue independent authorised work.

Implement narrowly, test actual runtime behaviour, and demonstrate success on the declared GOMarketsMU-Demo surface with retained raw evidence and separate independent verification. Never substitute mocks for broker proof. Preserve existing position protection throughout drills and budget checkpoints.

Complete only when the approved Wave 1 criteria and proof are satisfied. If evidence, approval, or an external condition is missing, report the exact pending criteria and resumption condition without claiming completion. Save a concise handover in docs/milestones/demo-income-wave-1-report.md. Respect any explicitly supplied goal budget; do not invent or increase one. Avoid repeated market polling and unchanged-code review.

Do not start another wave or milestone. No live access, new strategy expansion, commits, pushes, branches, or PRs are authorised. M20 closeout remains subject to its complete contract and bound review gates; passing this wave alone is insufficient.
```
