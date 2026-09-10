# Design review: research-based trading wave

> Historical review of the 7 September design. Future execution follows the
> [revised numbered waves](../docs/prompts/demo-income-waves.md) and
> [10 September design review](../docs/reviews/edge_discovery_design_review.md).
> H_H1 is no longer an active planned challenger. This review is not approval
> of the revised experiment or a current formal milestone recommendation.

Date: 7 September 2026. Reviewed artifact: [wave specification](2026-09-07-research-trading-wave.md).

**Verdict: suitable as a bounded implementation proposal, with explicit execution prerequisites.** The design offers a testable route to learning whether there is an edge. It does not establish an edge today. This is the author's self-review across research, engineering, risk and architecture concerns; it is not an independent Triad review or `RECOMMEND_COMPLETE` result.

## Findings and disposition

| Priority | Finding | Resolution in the specification |
| --- | --- | --- |
| Critical prerequisite | T480 status is stale despite an installed permanent task. Reliable collection cannot be assumed from deployment success. | R0 requires retained diagnostics, repair, genuine T16-disconnection and continuity proof. The negative-sleep path is a concrete defect candidate, not a claimed observed exception. |
| High | The current account-liquidity helper conflates a failed position query with an empty result. Its zero-position response cannot establish safe flatness. | Require strict position/history reconciliation in W1. Retained SL/TP metadata and current broker state are explicitly distinguished. |
| High | An H1 filter could become another ad hoc M1 modification dressed in academic evidence. | H_H1 is one frozen shadow hypothesis. Published monthly momentum is not its validation. E6 retains the stronger-horizon diversified comparison as separate research scope. |
| High | Much of the original research proposal duplicates existing Waves 1–3. | Explicit mapping reuses the ledger, eligibility work, replay and operator reporting. No parallel execution engine or second governance system. |
| High | Selecting profitable baseline trades mismeasures a filter's full policy effect. | Each candidate has independent simulated position/risk state and point-in-time opportunity reconstruction. Subset analysis stays descriptive. |
| High | Decision snapshots may miss costly periods where no assessment is produced. | Report missingness and conditional sampling. Additional bounded sampling requires explicit retention scope. No claim of an unbiased all-day cost map without suitable observations. |
| High | Twenty trades or six weeks can be mistaken for proof of sustainable income. | These are engineering/collection checkpoints. The protocol requires effective-sample and precision assessment, fixed evaluation dates and honest INCONCLUSIVE outcomes. |
| High | A family-level SPA rejection could be misrepresented as proof of the selected individual winner. | Require simultaneous candidate confidence bounds and two economic contrasts; validate method and assumptions before claiming support. If validation is unavailable, report descriptive results only. |
| High | Unknown charges, omitted failed trades or repeated spread deductions distort returns. | Signed broker ledger, full attempt denominator, separate estimates, explicit missing costs, recurring-cost evidence and correct incremental stress calculation. |
| High | Demo equity might be used to promise income at the human's unknown capital. | Actual intended capital, feasible lot sizing and minimum worthwhile income are required for a business-case pass. Pending inputs yield labelled scenarios. |
| High | A long goal may consume AI usage by watching markets. | Ordinary T480 code collects; checkpoints name exact resumption conditions. No repeated polling or new trials until one happens to pass. |
| Medium | AtLogOn and limited restart retries do not establish reboot/logoff resilience. | Actual task/power/dependency inspection plus a separate flat-account startup drill. No unapproved auto-login or secret storage. |
| Medium | Heartbeat freshness alone says little about protective monitoring and does not preserve history. | Record monitor freshness separately; add bounded local continuity evidence sufficient for interval verification. |
| Medium | Current news and volatility labels overstate what is measured. | Reuse W2.1 with qualified inputs, or explicitly record unavailable safeguards. Any required missing input blocks entries. |
| Medium | The earlier proposal allowed extending six weeks for coverage without a clear stopping rule. | The detailed protocol requires a new approved, versioned observation window. An inconclusive first result remains recorded. |
| Medium | Research completion could be confused with M20 proof or production authority. | Separate implementation checkpoints, completed evaluation, milestone closeout and later executed Demo promotion. Live remains prohibited. |

## Why this is worth building

It directs engineering toward five practical improvements: dependable unattended operation, a trustworthy net-income calculation, two falsifiable hypotheses, reproducible comparisons, and a clear decision to continue or retire. It limits model use to engineering and analysis; deterministic rules retain trading boundaries.

The biggest remaining commercial uncertainty is whether EUR/USD M1 has enough gross edge to cover costs under the small risk budget. The wave must be willing to reject that premise. If both candidates fail, adding more M1 indicators is not the default next step; the separate slower-horizon benchmark becomes a research option to assess.

## Decisions and evidence still needed at execution

- Current task/process failure diagnostics and strict Demo position/history reconciliation.
- Current W1 dependency proof; exact current release/configuration binding.
- Any exact M20 amendment needed for retained research data, eligibility changes or evaluation scope. The proposed goal does not silently amend the registry.
- Qualified historical bid/ask/cost data and genuinely untouched evaluation dates, or an explicitly prospective-only design.
- Intended capital, minimum worthwhile monthly net income, actual recurring costs/allocation and operator-time budget. Reuse prior approvals where already available.
- Actual login/power/dependency constraints and an approved flat-account reboot test procedure.

These dependencies do not prevent independent local implementation once the goal is authorised. They prevent the dependent execution or passing claim until resolved. No additional live or multi-currency authority is implied.

## Preparation validation

The specification was checked against the active M20 contract, Option B configuration, Waves 1–3, the latest Wave 1 handover, listener/scheduler source and fixed read-only T480 observations. Document links and scope/risk consistency are checked before handover. No deployment, strategy change, formal milestone review, goal launch or production proof is performed by this preparation.
