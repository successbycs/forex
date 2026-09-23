# M32 — finish the Demo MVP quality review

This living ExecPlan follows `PLANS.md`. Its execution record is
`docs/plans/m32-demo-mvp-quality-work.json`. Chris's existing Demo MVP goal
authorises M32 after proven M31; no new trading authority is created.

## Purpose and formal milestone dependency map

Give the operator one clear Demo handoff: what was observed, how to see candle,
decision and trade state, what conditions must remain available, which gaps
remain, and why Live trading is not ready. M31 was explicitly approved and
proved at 2026-09-23T03:05:27Z; M30's natural lifecycle remains reusable evidence.
M32 is the final active registry milestone. Its scope is retained forward Demo
evaluation and the short final quality review, not strategy development.

## Scope, owned paths and non-goals

Own this plan/work record, `docs/research/m32-demo-quality-evidence.md`,
`docs/milestones/M32-proof.md`, M32 assessor/capture/verifier scripts,
`tests/milestones/test_m32.py`, and the M32-only review fingerprint dependency
list/tests if required. Reuse M30/M31 validators and the existing dashboard.

Observed-surface repair also owns `scripts/listener_workflow_report.py` and
`tests/test_listener_workflow_report.py`: the actual M32 read showed PostgreSQL
numeric-string fill prices rendered unavailable. Accept finite positive recorded
numeric strings in presentation only, and show the persisted NO_TRADE rationale
rather than infer “no qualifying setup.” Do not recompute a trade decision.

No deployment, broker mutation, manual-position closure, account switching,
risk reset/expansion, retry, Live access, new UI/service, policy publication,
commission model, or broader PostgreSQL design is included. Do not invalidate
unrelated proof merely because an M32 evaluator receives a new Git revision.

## Progress

<!-- forex-work-projection:start task=M32-DEMO-MVP-QUALITY schema=forex.execution-work-projection.v1 -->
<!-- forex-work-item id=prerequisites state=DONE -->
- [x] prerequisites — Confirm approved M31 and retained M30/M31 scope (DONE)
<!-- forex-work-item id=source-assessment state=DONE -->
- [x] source-assessment — Validate retained sources and capture the existing read-only operator view (DONE)
<!-- forex-work-item id=quality-report state=DONE -->
- [x] quality-report — Build and test the bounded quality assessment and operator handoff (DONE)
<!-- forex-work-item id=proof-review state=DONE -->
- [x] proof-review — Capture current-revision M32 proof and obtain independent review (DONE)
<!-- forex-work-item id=human-closeout state=DONE -->
- [x] human-closeout — Obtain result approval and prove M32 through the governed gates (DONE)
<!-- forex-work-projection:end -->

## Evidence basis and critical assumption

Read `docs/research/m32-demo-quality-evidence.md`. The critical assumption is
that already-retained parent raw facts can be re-evaluated without new trading,
and the current terminal report can distinguish stale/unavailable observations
from safe new-entry permission. First test parent hash inventories and the
existing pure validators, then run `python3 scripts/m20_listener_dashboard.py
--json` once through its existing fixed read-only operations. Retain output
unchanged in a new ignored M32 inventory directory. An unavailable view is a
specific failed visibility check; never infer account flatness from it.

## Plan of work

First validate the recorded parent manifests, closeout approvals and retained
raw artifacts. Recompute M30 natural-source audit and M31 supplemental evaluation
using existing validators, keeping parent collector/runtime and new assessor
versions distinct. Preserve the original files unchanged. Use the established
dashboard collector once, retain its timestamps and source status, and render
normal/narrow output from those same bytes.

Second implement a deterministic, offline M32 assessment. It must report the
demonstrated protected lifecycle, the refusal interval, cost/performance limits,
Demo-only authority, operator-managed terminal requirements and the actual
visibility result. Required operating components are the MT5 Demo terminal,
protected listener/monitor, durable audit bridge/PostgreSQL and read-only view.
Optional orchestration, extra account routing, new UI, strategy expansion and
Live components must not enter the required MVP path. Document existing retired
components and leave necessary protection alone. Remove something only if an
observed redundant component prevents the MVP and its removal is authorised.

Third capture the assessment, source copies, operator rendering, test/governance
receipts and exact configuration/evaluator bindings in a new M32 bundle. The
offline verifier must reject source tampering, missing parent approval, false
current-uptime claims, unsafe authority, fabricated cost/performance conclusions,
stale/future captures, and inconsistent derived reports. It must not recontact
MT5 or regenerate source bytes. Emit FOREX_M32_PROOF_OK only for that bounded
assessment; it is not a Live-readiness pass or formal milestone closure.

Fourth obtain an actual independent repair/implementation review and the
required bound four-role recommendation. Fix critical findings within scope.
Present real inputs, outputs and limitations to Chris; only explicit result
approval permits formal signoff/prove. Do not infer final approval from the
instruction to execute this goal.

## Acceptance and verification

M32-C1: retained real Demo data yields an inspectable final assessment and
operator handoff. M32-C2: focused M32 and affected regression tests plus registry
validation pass. M32-C3: current-revision, clean, hash-bound proof retains source,
configuration and runtime identity and passes the offline verifier. M32-C4:
safe, observable and explainable human-operated Demo use is evidenced within
stated conditions; no Live permission or performance claim is introduced.

From `/home/chris/projects/forex`, run targeted tests, then:

    python3 -m pytest -q tests/milestones/test_m32.py
    python3 scripts/forex_milestones.py validate
    bash scripts/verify_m32_evidence.sh <new-M32-bundle>
    python3 scripts/check_execution_continuation.py --work-plan docs/plans/m32-demo-mvp-quality-work.json

Actual terminal rendering and retained-source recomputation are required;
mocks alone do not demonstrate the operator workflow. Capture/review from a
committed revision under the existing commit authority; never push implicitly.

## Recovery and stop conditions

All sources and outputs are additive and read-only with respect to trading.
Never overwrite a prior bundle. Missing external data blocks only the dependent
claim; continue independent assessment work. Keep the existing protected M1
loop unchanged. A current safety defect requires diagnosis under the repository
workflow, not a risk bypass. M32 cannot close without a passing recommendation
and explicit human result approval.

## Surprises and discoveries

M31's actual approval and proof are now present. Its result is deliberately a
ten-minute refusal evaluation. A generic NO_TRADE rationale is not a precise
gate diagnosis, and it is not evidence of an empty account. The operator view
already has one supported command, normal/full layouts and a reusable JSON
report; another dashboard is unnecessary.

The first M32 read-only view captured at 2026-09-23T03:09 UTC shows four broker
positions and a current NO_TRADE. Its ledger has recorded entry prices as
strings; the short renderer incorrectly omitted them. Parent M30 and M31 raw
audit recomputations both match the retained results. The small presentation
repair is required for an honest, explainable final handoff; no data or trading
rule changes are needed.

## Decision log

2026-09-23: reuse retained M30/M31 evidence and the existing read-only view.
This satisfies the declared retained-evidence surface without making the user
wait for another trade. NOT_READY_FOR_LIVE is a valid assessment outcome, not
a reason to build optional features into the Demo MVP.

## Outcomes and retrospective

M31 is formally proven and M32 started. Parent raw recomputation and the actual
03:17 UTC operator snapshot pass. The implementation's 59 focused tests pass.
Independent read-only reviewer `/root/m32_quality_review` reproduced the parent
results and actual report, found acceptance gaps, and verified their repairs:
missing assessment/ledger, Live runtime binding, stale decision and forged
age/warnings are now rejected. Deterministic generation time binds presentation
to acquisition without changing raw sources. The reviewer reports no remaining
critical issue preventing capture; this is not formal closeout approval.
Clean-revision capture `runs/evidence/M32/formal-20260923-v1` passed at e611152
with 59 tests. Bound cycle `M32-20260923T032356Z-e6111526` has four valid
PASS_WITH_FINDINGS reviews, no HIGH/CRITICAL finding and RECOMMEND_COMPLETE;
recommendation assessment is HEALTHY and the result is recorded in project
state. The retained summary shows SELL 1.14623 to 1.14616, reconciled, and ten
NO_TRADE decisions in the separate M31 interval. No new trade was forced.

Medium/low findings remain explicitly bounded: operator-managed availability,
unverified unrelated-position/account attribution, no qualified performance or
Live-equivalent cost basis, self-attestation, optional-component exclusion rather
than new removal, generic test-receipt parsing and an existing duplicate review
summary write. These do not justify expanding the MVP or its trading authority.
Later Live or unattended promotion requires separate design and evidence.

At that preparation point only Chris's M32 result approval remained; M31
approval did not approve M32. The completed approval is recorded below.
Before presenting the approval handoff, commit this factual progress record and
refresh the offline bundle and bound recommendation against that committed
revision. Use the unchanged retained sources, a new evidence directory, and all
four independent roles; do not edit prior reviews or claim a stale binding is
current. The latest manifest/recommendation in `project_state.json` is canonical.
If refreshed verification/review fails, reopen proof-review and repair in scope.
This plan creates no authority to trade Live or alter positions.

2026-09-23 update: recorded actual source validation, presentation repair and
independent repair review so the next step is proof capture, not another trade
observation. `docs/milestones/M32-proof.md` provides the bounded operator handoff.

2026-09-23 closeout preparation: recorded actual passing proof and independent
four-role recommendation, retained limitations, and the registry-required human
approval blocker. Revision-only rebinding uses retained evidence, not a fresh
market-observation period. After explicit M32 approval, assess the latest
recommendation and evidence again, record signoff with both reviewed flags,
and prove M32 using `scripts/forex_milestones.py`; do not sign off in advance.

2026-09-23 final closeout: Chris explicitly replied “approved” to the M32
closeout request. Before recording that decision, the final retained bundle
`runs/evidence/M32/formal-20260923-final` passed its offline verifier at 887facc,
the four-role recommendation `M32-20260923T032732Z-887facc0` assessed HEALTHY,
and governance validated. Human signoff was recorded at 03:32:09Z; the governed
prove command wrote M32 PROVEN at 03:32:10Z. M30 and M31 remain PROVEN. All
goal steps are complete at their declared bounded Demo surfaces. The existing
operator-managed terminal, manual-position and performance limits remain;
Live is NOT_READY and no trading authority or runtime setting changed.
This post-proof administrative update records the completed result without
rewriting source evidence or changing the reviewed implementation revision.
