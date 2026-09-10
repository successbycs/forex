# Goal prompt: Resume Wave 1 within 25,000 tokens

## Operator priority amendment — 2026-09-10

Get core Demo execution working first. Backup and isolated-restore proof is
explicitly deferred to [W4.0](demo-income-wave-4.md), before a funded pilot;
its absence is not a Wave 1 deployment, migration or recovery-drill blocker.
This supersedes earlier backup gates in the recovery package and handovers.
Keep Option B, Demo-only access, maintenance entry holds, fresh exposure/audit
checks, ledger/risk-state preservation and required execution evidence.
This amendment does not itself complete Wave 1 or authorise Live trading.


Prepared 7 September; revised 10 September 2026. **Saved continuation prompt;
this revision does not resume the existing goal.** Preserve prior work and
explicit approvals. The 25,000-token limit is the operator's existing request.

This tightens the operator's proposed Wave 1 prompt. It preserves W1.1–W1.4, reuses approved decisions, incorporates the proposed [W1.R recovery work package](demo-income-wave-1-recovery-work-package.md), and reserves time for a safe handover. The 7 September packaging update is documentation only; it does not resume execution or authorise the research wave.

Use the goal interface's native budget setting when available. The prose instruction is an execution constraint; it should not be represented as a verified account-wide billing cap. Current [official goal guidance](https://learn.chatgpt.com/use-cases/follow-goals) documents `/goal` and pause/resume controls but does not specify token-budget enforcement. On execution, confirm the budget recorded by the available goal mechanism rather than assuming the sentence alone sets it.

```text
/goal Resume and complete Wave 1: Trustworthy Demo execution in this repository. Use a 25,000-token goal budget. Read docs/prompts/demo-income-wave-1.md, docs/prompts/demo-income-waves.md and docs/prompts/demo-income-wave-1-recovery-work-package.md in full as the execution brief, and read the complete docs/milestones/demo-income-wave-1-report.md to identify remaining work. Verify findings against the current code, deployed release and evidence; preserve completed work instead of restarting it.

Include the swap/holding subactivities under W1.1-W1.4: qualify actual broker financing, version the holding mandate, include adverse financing in entry/risk checks, record deterministic reviews and implement only the approved protected-exit fallback. Do not invent overnight expectancy or wait for W3 to permit otherwise qualified intraday Demo operation. Obtain the exact holding/exit amendment before changing execution semantics.

Scope is W1.1-W1.4 only: align approved contract/configuration/deployment, correct order and position lifecycle handling, reconcile actual net broker P&L and costs, and enforce approved persistent capital-risk boundaries. Include listener and recovery defects that prevent trustworthy continuous Demo execution. Do not start the research wave.

First revalidate the 10 September risk-latch defect described in Research/2026-09-10-live-forex-readiness-review.md. Repair W1.4 so simultaneous daily/weekly/drawdown breaches record independent reasons and manual-review pauses survive recovery, day/week rollover, restart, maintenance release and lease renewal. Verify remaining headroom including applicable costs/reservations and valid-stop sizing. Cover synthetic equity paths with real-function/isolated-persistence checks; retain genuine broker refusal and protected-position restart proof separately. Never induce losses or put fabricated broker observations into operating risk state.

First inspect Git status, applicable AGENTS.md, project_state.json, the active contract in milestone_registry.json, and docs/evidence_and_milestones.md. Prepare a concrete plan showing what is already verified, what needs changes and what real-world proof remains. Reuse existing explicit approvals. Ask only for genuinely missing human-owned decisions or exact amendments beyond approved scope; continue independent authorised work.

Preserve approved Conservative Option B in config/runtime.yaml: planned loss per trade is the lesser of AUD 100 and 0.10% policy equity; daily loss pause 0.50%, weekly loss pause 1.00%, peak adjusted-equity drawdown pause 2.00%, with the existing Auckland boundaries and durable resume rules. Keep maximum_trades null and continuous duration, while retaining one position, USD 10,000 per-trade notional and USD 100,000 cumulative notional. Do not create replacement leases to bypass caps or reinterpret unknown account state as flat.

Follow W1.R's R1-R7 dependency schedule: diagnose the shared-runtime and intermittent connection failures; fix recovery-result classification and unknown exposure; establish coordinated maintenance; demonstrate T480 continuity and incident alerts; then finish the original Wave 1 evidence. Inspect current local and deployed cs-ai-lab-infra state as well as Forex's pinned transport dependency. Do not attribute an outage to concurrent development without evidence or update a passing dependency blindly. Shared-platform changes belong in their owner repository. Verify applicable contracts and prior approvals before the proposed no-logon reboot dependency; do not automatically execute the lab's own wave or milestone.

Check the T480 listener first without restarting a healthy service. Preserve diagnostics and distinguish unreachable transport, unavailable broker state, failed per-position recovery and confirmed empty positions. Revalidate the reviewed RECOVERY_FAILED-to-IDLE defect and the liquidity helper's missing-data-to-zero conversion before editing. A stale heartbeat, an empty durable recovery list or absent protection data cannot prove the account flat. Previously fixed negative-sleep and Windows/WSL resume defects must not be reimplemented without evidence of regression. Whole-host/WSL/database maintenance requires confirmed flat exposure and no unresolved executions; the separate protected-position drill restarts only the listener under the approved maintenance plan.

Follow the operator amendment: defer backup and isolated-restore proof to W4.0; do not block core Wave 1 Demo work on that evidence. Implement narrowly and test actual runtime behaviour. Deploy permitted changes to the fixed GOMarketsMU-Demo surface, capture required genuine lifecycle, fee, risk-pause and recovery evidence, and independently verify it against the exact contract, release and configuration. Never substitute mocks for broker proof or rewrite captured evidence. Preserve position protection through drills and checkpoints; use restrictive test settings rather than deliberately losing money. Unobserved partial-fill or nonzero-charge conditions remain explicitly pending where required.

Complete only when the approved Wave 1 criteria and required proof are satisfied. Otherwise save exact pending criteria, evidence references and a concrete resumption condition in docs/milestones/demo-income-wave-1-report.md. Avoid repeated market polling and unchanged-code reviews; verified ordinary Demo operation may continue collecting while AI work is paused.

Register and check the 25,000-token budget using the available goal-budget mechanism. If hard enforcement is unavailable, state that limitation; an absent recorded cap does not grant unlimited execution authority. Reserve budget for the handover and reach a safe checkpoint before exhaustion. Do not increase the budget, start a new goal to evade it, or claim completion because the budget ended. Stopping AI work must not stop necessary protective management.

No Live access or new strategy expansion. This prompt adds no commit, push, branch or PR authority; honour existing explicit authorisation within its scope. If exact deployment provenance requires a commit not covered by that authority, prepare the reviewable change and report the specific dependency; do not weaken provenance rules. Do not start another wave or milestone. M20 closeout still requires its entire active contract and current bound review gates; passing Wave 1 alone is insufficient.
```
