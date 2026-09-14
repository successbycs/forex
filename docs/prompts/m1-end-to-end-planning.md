# Prompt: define the M1 end-to-end delivery plan

**Planning only. Do not begin application implementation, deployment or trading.**

I have decided to prioritise one complete capability:

**An autonomous EUR/USD M1 Demo trading loop that uses real market data and economic-calendar information, makes explainable trade/no-trade decisions, executes eligible trades with existing protection, and stores decisions and broker-reconciled outcomes in PostgreSQL.**

This supersedes the previous equal-priority delivery sequencing for M1 and H_SLOW. Preserve H_SLOW, research, future capabilities and existing milestones as deferred work—not deleted work.

Read the AI delivery review, current Wave structure, capability definition, delivery status, active milestone contract and relevant implementation. Check previous claims against the code and available evidence. Reuse working components; do not restart the project.

**Define the smallest implementation plan that delivers this complete capability.**

1. State what already works, what is merely prepared, and which connections are missing. Distinguish verified findings from assumptions.
2. Propose a small number of outcome-based Waves. Each Wave must end in a useful demonstration, not merely completed modules.
3. Under each Wave, define bounded tasks with:
   - The observable result and why it is necessary.
   - Existing components to reuse and the change required.
   - Actual dependencies.
   - Acceptance checks and the environment/data needed to demonstrate success.
   - Whether it can proceed while the market is closed.
4. Map the proposed Waves and tasks to the existing plan. Identify what is retained, resequenced or deferred. Preserve IDs where practical.
5. Identify any conflicting instructions or contract requirements. Explain the precise amendment needed; do not silently waive requirements or request approvals already recorded.
6. Identify the first executable task and the final end-to-end demonstration.

**Scope boundaries**

- Keep the existing M1 strategy and approved risk limits unless an identified defect prevents the agreed outcome.
- Economic-calendar information initially controls entry eligibility, not trade direction.
- Include recurring collection, execution, reconciliation and essential operating visibility—not just a one-off demonstration.
- Preserve Demo-only account restrictions, protection, duplicate prevention, data freshness and reconciliation.
- Defer H_SLOW expansion, new strategies, adaptive sizing, broad news ingestion, dashboards, generic automation and unrelated hardening.
- A market-dependent observation may block that observation, not independent tasks within this M1 outcome.
- Historical replay, tests and prepared code must not be presented as fresh broker proof.

Plan for Terra to implement and Astra to review and resolve escalated defects. Do not start delegation during this planning request.

**Return the proposed plan in chat for review. Do not create another planning framework or change repository files yet. Make genuine human decisions explicit; choose ordinary technical details yourself.**
