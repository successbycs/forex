# Autonomous Delivery

## Status

Proposed human-approved Goal Mode execution brief. It authorises Demo-only
repository work; it does not authorise live trading, a risk-latch override,
or a claim of profitability.

## Goal

Complete the Forex roadmap sequentially from the active milestone through
M32, using only GOMarketsMU-Demo where a contract permits broker interaction.
Deliver every milestone only after its declared real-world proof, independent
verification, and current Triad-plus-domain `RECOMMEND_COMPLETE` result are
bound to the exact contract, revision, configuration, verifier, and evidence.

## Operating rules

1. Astra owns the plan, integration, safety decisions, evidence gate, and
   final defect repair. Terra may implement bounded work packages. Use two
   loops: implementation plus independent verification/repair; neither loop
   may self-approve completion.
2. Read `AGENTS.md`, `project_state.json`, the active contract in
   `milestone_registry.json`, and `docs/evidence_and_milestones.md` before
   milestone work. Implement only the active milestone unless this Goal moves
   it forward after formal closeout.
3. Never access, enable, or trade `GOMarketsMU-Live`. Do not expose a generic
   MT5/order interface. Do not force trades, close positions to manufacture
   evidence, reset caps, or fabricate, alter, or overwrite raw evidence.
4. Treat every risk pause, external-cash-flow discrepancy, unresolved
   execution, broker ambiguity, or material safety finding as fail-closed.
   Continue safe read-only diagnosis, but require Chris’s explicit review for
   a human-owned approval, release, or risk-resume decision.
5. Keep mutable evidence/state separate from committed implementation. Do not
   commit, push, branch, or open a pull request unless separately authorised.
6. Do not claim profitability from operational proof. Economic readiness
   requires its own contract, costs, loss-streak controls, forward evidence,
   and domain review.

## Completion standard

The Goal is complete only when the active roadmap milestone is formally
closed under its contract and every subsequently started milestone through
M32 has independently met its own proof gate. A blocked human-owned decision
is reported with the exact read-only evidence, the safety effect, and the
smallest required operator action.
