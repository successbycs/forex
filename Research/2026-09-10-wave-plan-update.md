# Wave-plan revision: research-based net income

10 September 2026. Implements the operator's request to adjust the Waves after
the repository/literature/design review. **Documentation completed; wave
implementation, runtime changes and trading activation were not executed.**

Current planning entry point: [wave guide](../docs/prompts/demo-income-waves.md).
The numbered specifications govern the planned sequence; the active registry,
canonical configuration and explicit operator authority govern actual execution.

## Changes made

| Area | Adjustment and purpose |
| --- | --- |
| W1.4 | Independent persistent daily/weekly/drawdown reasons are the first repair. Recovery, rollover and restart cannot erase a required manual pause. Add remaining loss headroom and valid-stop sizing, with exact amendments before any changed execution semantics. |
| W1/W1.R | Preserve prior work and approvals; remove blanket statements that every activity is still unexecuted/planned. Separate synthetic equity-path checks from real Demo refusal, protected-position restart and lifecycle proof. |
| W2.1 | Complete broker-cost assumptions, signed price references and actual event/volatility gates. Revalidate quote, authority, risk and symbol constraints immediately before submission. |
| W2.2 | One shared executable policy, qualified clocks/data and honest simulated fills. Retained M6 and M16 artifacts are inputs to requalification, not sufficient edge evidence. |
| W3.1 | Absorb former research E1–E5 into one wave. Keep the M1 baseline and H_SESSION; replace H_H1 with one fully specified H_SLOW. Limit new confirmatory hypotheses to two and retain every development trial. |
| W3 inference | Freeze chronology, family, uncertainty, cost stress and decision criteria. Defer DSR/PBO/CPCV rather than adding a statistics platform. A correctly enforced pause is evaluated behaviour; an enforcement failure blocks progression. |
| W3 economics | Separate statistical support from viability after broker and recurring expenses, at feasible capital and operator effort. Unknown costs/capital cannot produce a supported business case. |
| W3.2/W3.3 | Reuse technical recovery proof, measure longer unattended operation, and qualify actual candidate Demo execution after exact authority. Shadow support alone cannot establish Live readiness. |
| W4 | Add a future, separately gated live pilot with explicit account/capital/loss/end conditions. Its saved prompt is planning-only and cannot enable Live. |
| Architecture | Reuse Python/PostgreSQL/T480, one account-level entry writer, explicit state transitions and bounded read-only LLM assistance. No graph database, new engine service or thirteen Edge milestones. |
| Prompts/history | Align W1 resume and research prompts; research prompt is an exact Wave 3 alias. Mark older research specifications/reviews as historical, retaining original findings. |

## Scope mapping and dependencies

The guide maps review actions A1–A12 and earlier R0/E1–E6 to the existing wave
owners. No registry IDs were renumbered, historical proof overwritten or
`project_state.json` statuses advanced. M20 remains the current active contract
at this revision; this document is not its closeout.

Execution must identify owning criteria and exact amendments where necessary:
additional quote retention versus M20's no-tick-stream rule; changed stop,
sizing, event or session semantics; H_SLOW's data and complete rules; research
evaluation scope; and any selected candidate's actual Demo execution. Future
Live work requires a new exact contract and explicit enablement authority.

Existing approved decisions remain: Option B, unlimited development trade
count with independent exposure caps, the specific AUD -0.29 cash-flow
confirmation, and the temporary AUD 0.01 refusal drill with immediate restoration.
The existing W1 resume prompt retains the operator's 25,000-token budget.
Other wave prompts assume no numerical goal budget. Research search/compute
limits are separate values to freeze before an experiment.

Missing operator-owned capital, minimum worthwhile income, cost allocation and
attention allowance remain explicit business-case inputs. Do not ask again for
already approved risk tolerances. Specify H_SLOW completely and freeze data,
windows and inferential criteria before evaluating it; it is not executable
merely because a name exists in the plan.

## Validation and limits

Validation passed: local links and balanced Markdown fences across 13 affected
documents; current-document whitespace; every W1–W4 activity ID; and exact
equality of the research alias and Wave 3 goal prompt. `git diff --check` and
`python3 scripts/forex_milestones.py validate` passed. The plan was also checked
for preservation of Option B, the Live boundary, prior execution approvals and
historical proof. No runtime tests were repeated for these documentation edits.

No broker observation or production-readiness proof is implied by a
documentation check. Current wave completion status must be read from evidence
and handovers at execution time. Unrelated run-history and local work were
preserved; no commits, deployments or goal changes were performed.

**Next implementation activity remains W1.4 risk-latch repair and remaining
W1 proof.** Updating this plan did not launch or resume that work.


## 10 September addition: swap-aware holding rules

At the operator's request, incorporated the
[swap-aware hold/close method](2026-09-10-swap-aware-hold-or-close.md) into the
shared wave guide, W1.1–W1.4, W2.1–W2.2 and W3.1/W3.3. Added activity ownership,
mission value, success criteria, real-world demonstrations and limitations.
Updated the numbered goal prompts, Wave 1 resume prompt and matching Wave 3
research alias.

W1 owns the calculator, financing-aware safeguards, policy configuration and
approved fallback, without depending on a W3 return forecast for otherwise
qualified intraday operation. W2 owns historical rate/conversion/calendar data
and replay. W3 owns holding-rule comparisons and horizon-specific evidence;
all variants count toward the recorded search and the two-challenger limit is
preserved. H_SESSION remains entry-only.

This instruction authorises documentation changes, not numerical holding limits,
forced liquidation, runtime deployment or additional Demo drills. An exit change
requires an exact amendment because current M20.13 is analysis-only. Option B,
Demo-only authority, existing approvals and W4.0 backup deferral remain intact.
No registry/state, runtime configuration or evidence claims were changed.
