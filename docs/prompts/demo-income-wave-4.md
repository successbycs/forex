# Wave 4: Separately authorised live pilot

Prepared 2026-09-10. **Future gated plan. Current GOMarketsMU-Live prohibition
remains in force.** Updating this file does not amend that boundary, create a
milestone or grant Live credentials, connectivity or order authority.

Read the [shared guide](demo-income-waves.md) and [Wave 3](demo-income-wave-3.md).
M32's assessment is not a Live execution contract. This wave requires a new
exact contract and explicit operator mandate before dependent implementation.
A copied planning prompt below deliberately cannot activate Live.

## Activities, success and real-world tests

| ID | Change and mission value | Success criteria | Demonstration and authority boundary |
| --- | --- | --- | --- |
| W4.0 | Complete proportionate backup and recovery assurance, deferred from Wave 1 by the operator on 2026-09-10. Protect funded operation without delaying core Demo functionality. | A current verified retained backup covers the trading ledger, risk anchors and required configuration/secret recovery; an isolated restore demonstrates recovery within agreed recovery bounds. Shared infrastructure remains owned by `cs-ai-lab-infra`. | Restore to an isolated target, compare ledger/risk state and configuration, and retain independent verification before any funded pilot. Never restore over the operating ledger for this test. Missing proof blocks funded enablement, not Waves 1–3 Demo work. |
| W4.1 | Review one frozen candidate and the operator business case. Avoid funding a statistical or operational illusion. | Current W1/W2 proof, sufficient frozen research, actual candidate Demo qualification, feasible lot sizes/capital, complete expenses and measured operator effort. | Independently rebuild W3 findings and reconcile the candidate's genuine Demo fills/charges. If evidence or viability is rejected/inconclusive, return that decision without promoting it. |
| W4.2 | Prepare the exact account-bound Live operating contract, implementation and rollback, default-disabled. | Named account/server, strategy/release/configuration, capital, risk limits, loss/end conditions, mandate expiry/revocation, allowed orders and deterministic protection. Account-specific state and one entry writer; no generic trading interface or LLM authority. | After contract approval permits implementation, verify wrong account/server, mismatched version, revoked mandate, stale quote, uncertain exposure and duplicate attempt refusal on a non-Live surface. Review the concrete release/configuration and rollback before enablement. |
| W4.3 | Run one tiny, fixed funded pilot only after explicit enablement authority. Measure actual Live friction. | Predeclared maximum capital/loss, feasible minimum volume, cost tolerance, duration/end conditions and monitoring. No automatic scaling or strategy changes. | Under the separately approved Live surface, reconcile genuine orders, fills, fees, financing and cash flows; compare with Demo assumptions. Retain every loss, rejection, gap and intervention. Stop new entries at limits while applying the mandated protection/exit policy. |
| W4.4 | Decide whether continued operation earns its costs and attention. | Actual net income, uncertainty, drawdown, time under water, pause behaviour, expenses and human effort meet the frozen review criteria. | At the fixed review condition, reconcile Live statements and bills and issue continue/revise/retire/inconclusive. Any longer window, larger capital or risk change is a separate operator decision. |

Backup/restore assurance is deferred work, not waived completion: W4.0 must
pass before W4.3 funded enablement. It does not authorise Live access.

## Required mandate

Do not infer Live capital, worthwhile income, account terms or loss tolerance
from Demo operation. Obtain exact values before dependent implementation:
account/server identity; capital and maximum pilot loss; existing Option B or
an explicitly approved replacement; currency/exposure/lot constraints;
cost/financing schedule; frozen policy and data requirements; review/end date;
pause/resume and revoke authority; incident response; and acceptable operator
effort.

Distinguish blocking new entries from cancelling pending orders or flattening
positions. Define those actions for each failure class in advance; a generic
kill switch must not unexpectedly close protected positions. Risk limits are
controls, not guaranteed loss ceilings during gaps or slippage.

Prepare the complete reviewable configuration, checks and rollback before
requesting final enablement. Prior general development or Demo authority does
not waive the current explicit Live prohibition. No automatic promotion from
a green research status or a successful Demo trade.

## Scope and completion

Use the existing stack. No multi-currency portfolio, carry expansion, dynamic
risk increase, unattended model replacement, enterprise infrastructure or
always-on LLM in the order path. A minimum lot exceeding the approved risk
budget means the pilot is infeasible at that capital.

Keep Demo and Live evidence, credentials, state and claims distinct. Simulated
refusals can verify engineering, but cannot establish Live execution costs.
No full Wave 4 completion before its authorised funded proof and fixed-date
economic assessment; a pause or inconclusive finding is reported honestly.

On later execution, save `docs/milestones/demo-income-wave-4-report.md` with
mandate references, verified releases, raw evidence locations, operator
economics and the next explicit decision. Preserve all formal contract gates.

## Copy-and-paste planning goal prompt — no Live execution

```text
/goal Prepare Wave 4: Separately authorised live pilot, planning only. Read docs/prompts/demo-income-waves.md, docs/prompts/demo-income-wave-4.md and the actual Wave 1-3 handovers. Inspect Git status, applicable AGENTS.md, project_state.json, the active contract and evidence rules.

Review W4.1 prerequisites and prepare the concrete W4.2 contract/configuration design, criterion mapping, verification plan, loss/end conditions and rollback for one frozen candidate. Reuse exact existing approvals; identify missing Live account/capital/risk decisions without inventing them. Record unsupported or inconclusive economic prerequisites honestly.

Deliver a reviewable plan and exact proposed contract amendments in docs/milestones/demo-income-wave-4-report.md, clearly marked planning only. Preserve current milestone status and all historical evidence. Respect only an explicitly supplied goal budget.

Do not access Live, create/store Live credentials, change runtime configuration, deploy, submit orders, activate a mandate, start another milestone or execute W4.3-W4.4. A later explicit contract and enablement decision are required. This planning goal adds no commit/push/branch/PR authority.
```
