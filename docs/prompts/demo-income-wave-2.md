# Wave 2: Consistent, cost-aware decisions

Status: **PROPOSED — execute only on explicit operator instruction.**

Read the [shared wave guide](demo-income-waves.md). This wave covers original
activities 5–6. Verify the Wave 1 handover and current affected proof before
enabling any changed decision path. Unresolved critical exposure/accounting
defects block dependent Demo execution.

## Activities, success, and real-world tests

| ID | Change and mission value | Success criteria | Real-world demonstration |
| --- | --- | --- | --- |
| W2.1 | Validate executable-side price/volume/stops constraints, cost assumptions, scheduled-event exclusions, and genuine price-volatility checks. Replace hardcoded favourable safety labels with observations or explicit unavailability. | Every failed eligibility rule produces an auditable refusal; missing required context cannot pass; projections include applicable charges and explicit uncertainty. Target-after-cost feasibility is never called positive expectancy. | Capture genuine accepted/refused Demo decisions, actual broker constraints, a scheduled-event exclusion window, and broker fills. Compare projected costs with realised costs using a predeclared tolerance and inspect every material discrepancy. |
| W2.2 | Share deterministic strategy, sizing, protection, and exit calculations between replay and execution while keeping adapters thin. This makes research results relevant to what is traded. | Identical versioned inputs yield matching decisions/plans; decision-time availability is preserved; any intended strategy change is explicit and approved rather than hidden in a refactor. | Replay retained genuine Demo decision snapshots and observed lifecycle inputs through the shared implementation. Independently compare decisions, sizing, SL/TP, and exit instructions with deployed records under the documented numerical tolerance. |

## Design constraints

Ask for missing session/event policy and cost assumptions before implementing
them. Reuse already qualified sources when suitable. Do not invent a calendar
feed's availability, historical timestamps, fees, or licensing rights.

Use broker observations for execution conventions and symbol constraints.
Keep actual realised net P&L separate from projected spread/slippage allowances.
Record the reference prices and timestamps needed to explain the estimate.

If event data are required by the approved policy but missing/stale, block
entries with an explicit reason. A normal spread alone is not a volatility
test. Do not use an LLM to decide whether a hard risk gate applies.

Preserve strategy ownership and deterministic precedence unless an exact change
is separately approved. Describe precedence as selection policy; do not claim
it proves independent regime classification or strategy diversification.

For replay, use only data available at the recorded decision time. Decision
parity does not prove realistic historical execution. Any later SL/TP backtest
must handle bid/ask, costs, and ambiguous within-bar ordering explicitly.

## Completion and exclusions

Complete when approved eligibility rules and shared-logic parity pass their
behavioural checks and real-world comparisons, with affected evidence refreshed.
Report any unobserved event/cost condition as pending rather than generating it.

Exclude additional instruments, strategy optimisation, portfolio systems,
agentic macro/sentiment expansion, live access, and automatic Wave 3 start.
The current M20.13 document is analysis-only at preparation; check and approve
any necessary amendment before changing governed trading rules.

## Copy-and-paste goal prompt

```text
/goal Execute Wave 2: Consistent, cost-aware decisions in this repository. Read docs/prompts/demo-income-wave-2.md and docs/prompts/demo-income-waves.md in full. Their specifications, evidence rules, and usage controls define this goal. Read docs/milestones/demo-income-wave-1-report.md and verify the actual dependency status; do not assume Wave 1 completed merely because its report exists.

Scope is W2.1-W2.2 only: implement approved economic and market eligibility checks and unify deterministic research/deployed strategy logic. First inspect Git status, applicable AGENTS.md, project_state.json, the active contract, and docs/evidence_and_milestones.md. Revalidate scope and prepare a concrete activity plan.

Obtain missing human-owned policy decisions and approval for exact contract amendments before dependent changes. Preserve approved strategy semantics during refactoring. Unknown required inputs must not become passed gates. Keep actual broker costs separate from estimates and avoid double counting.

Test the actual runner and shared logic, then capture genuine Demo eligibility observations, event-window behaviour, fills, and replay/deployed parity. Independently verify retained evidence against the exact release and configuration. Tests or parity alone do not establish profitability.

Complete only when the approved Wave 2 criteria and real-world comparisons are satisfied. Otherwise record precise pending proof, blockers, and resumption conditions. Save docs/milestones/demo-income-wave-2-report.md with changed files, validation, evidence, and limitations. Respect any explicitly supplied budget and avoid repeated polling or reviews of unchanged code.

Do not start Wave 3 or another milestone. Do not enable live access, expand strategies, bypass risk controls, commit, push, create a branch, or open a PR. Preserve protective management of existing Demo positions. M20 closeout still requires every active contract gate.
```
