# Astra design review: T480-local trading health

Date: 2026-09-24. Independent reviewer: `/root/astra_health_design_review`,
model `gpt-6-astra`. Root authored the package; the reviewer inspected it
read-only and did not implement, deploy or approve execution.

## Recommendation

**Ready for human review and approval of the design package.** No remaining
design blocker identified in the final bounded review. This is a recommendation
about design completeness, not runtime proof, human approval or milestone
closeout. The user explicitly requested the design before execution.

## Review scope and evidence

The reviewer inspected the existing listener, runner, fixed adapter, prior
single-client agreement, then the evidence brief and full new ExecPlan.
Initial repo findings included Interactive/AtLogOn startup, disabled rollback,
a transient stop sentinel, historical S4U-only continuity assumptions, and local
WSL/PostgreSQL dependencies. These informed the draft's operating boundaries.

First reviewed plan SHA-256:
`852027bfab6248e6f1e367a548591fdfac83fa65da9506383f1aed8c19f97fb6`.

Final substantively reviewed plan SHA-256:
`0afe05a9d48609b4411198539930632224493b1beecb0f8bba8a2a9f8668bc08`.

Reviewed evidence brief SHA-256:
`d1e63f3fbfe6a9b1bcf314e4d2f3e246a8d54dd454ced630664e487cd9747466`.

Final saved plan SHA-256:
`657ae4d2f08e935fb5dbaeea444f1a579134637667e33901f1dd156d6d49fce5`.

The sole change after final review was the work projection's administrative
IN_REVIEW-to-DONE update. A comparison excluding that generated projection
confirmed no other change. Corresponding reviewed/final body SHA-256:
`3bab6cc11cfacc98032998efe80a520732c39b61c9a6faf80d88b84ed55efcd9`. Changing substantive design after this point requires affected
review; these hashes do not endorse future revisions.

## Required repairs and resolution

| Finding | Repair in final draft | Result |
|---|---|---|
| Late delegated tasks could mutate runtime after the guardian moved on. | Persist-before-dispatch requests bound to action/recovery/boot/generation/release and deadline; one outstanding action; stale-action refusal before effects; cancellation/join; timeout-after-effect reconciliation and corroborated receipts. | Resolved in design; implementation and race proof pending. |
| Monitor-only startup could never produce the assessments required before an entry permit. | Explicit isolated no-order readiness mode under the fence, no reservation/submission or consumption of production candle identity; normal loop progress checked after permit. | Resolved in design; runtime proof pending. |
| Laptop task defaults could suppress checks on battery or after missed starts. | Explicit effective battery/start/overlap/wake settings and AC/no-sleep operating assumptions, bounded cycle and power-event tests. | Resolved in design; measured verification pending. |

## Strengths accepted by the review

One local recovery owner; managed-process identity rather than name-based killing;
intent surviving reboot; separate entry fencing; persistent restart budgets;
unattended-session feasibility before dependent implementation; preservation
of exposure and in-flight execution; T16 independence; proof of work beyond
heartbeat/process count; explicit strengths, weaknesses and rollback behaviour.

## Remaining limitations and decisions

Runtime A remains an unproven feasibility hypothesis. Candidate B, if needed,
requires a concrete credential/security decision and separate approval. Flat
recovery does not prove safe recycling with exposure. A local process cannot
repair a powered-off host. Execution requires the user's design approval and
an explicit operational scope amendment; deployment, fault injection, the
24-hour soak, unattended reboot and natural lifecycle proof remain pending.

## Author verification

Plan/work projection validation, `git diff --check` and milestone governance
validation passed during design preparation. No implementation tests were
claimed for files that do not yet exist. Raw incident receipts remain in
`runs/local/m33-no-trades-diagnosis`; primary source links and applicability
are retained in `t480-local-health-evidence.md`. No runtime task, client,
credential, power policy, risk parameter or broker order was changed.
