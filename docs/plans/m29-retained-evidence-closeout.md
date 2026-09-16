# Close M29 using the retained recovery drill

This ExecPlan is a living document and follows `PLANS.md`. It changes only the
M29 proof policy so the retained 15 September 2026 recovery drill can be
evaluated honestly. It never enables Live trading or creates an order surface.

## Purpose / Big Picture

M29 should establish one thing: the held Demo listener recovered from a
controlled worker handoff while the account was flat before and after. The
drill has already happened. This plan removes the requirement to repeat it
solely because documentation or evidence tooling changed, while keeping a
new proof requirement for any change to listener runtime payloads or governed
runtime configuration.

## Progress

- [x] (2026-09-16) Inspected retained M29 bundle, current contract, and changes after the drill.
- [x] (2026-09-16) Independent Astra review found no listener-payload or governed-runtime-config change after the drill.
- [x] (2026-09-16) Added a schema-supported, M29-only retained-evidence policy.
- [x] (2026-09-16) 32 focused/governance tests passed; exact retained bundle validated offline with `FOREX_M29_PROOF_OK`; parent agent completed independent read-only review without required repairs.
- [x] (2026-09-16 02:38Z) Recorded all four acceptance checks and passing current local verification; preserved Chris's 02:21:38Z approval unchanged.
- [x] (2026-09-16 02:39:52Z) Normal CLI emitted `M29 PROVEN at 2026-09-16T02:39:52Z` using Chris's unchanged approval; M30 became READY and was not started.

## Evidence Brief

Decision: whether the retained bundle can prove the bounded M29 function.

Evidence-supported findings:

- `runs/evidence/M29/20260915T111605Z/manifest.json` records
  `FOREX_M29_PROOF_OK`; all listed artifact hashes match.
- `m29-continuity.json` records a PASS handoff, requested at 10:14:24 UTC and
  recovered at 10:14:26 UTC; its baseline and postflight account are flat on
  `GOMarketsMU-Demo` under maintenance hold.
- Runtime payload files and governed runtime configuration have no changes
  from deployed drill revision `4dc94fe7895fd1a2eee605461a646c9618b29c1a`
  through current HEAD. Post-capture changes are governance, documentation,
  M29 capture/verifier scripts, and tests.

Reasonable inference: repeating the same worker-handoff drill would not add
meaningful function evidence unless the runtime payloads or configuration
change.

Rejected claim: the retained drill does not prove current uptime, broker
outage recovery, durable deduplication, profitability, host reboot recovery,
or any Live capability.

## Context and Orientation

`milestone_registry.json` declares M29. `project_state.json` stores the
recorded bundle and Chris’s sign-off. `src/forex/milestones.py` validates
evidence and performs the formal `prove` transition. The current generic
validator wrongly requires three different provenance identities to be equal:
the evidence-collector Git revision, the deployed runtime revision, and
current repository HEAD. They are distinct facts. The policy added by this
plan must preserve each one.

## Plan of Work

1. Extend the milestone registry schema and `src/forex/milestones.py` with a
   strictly shaped `retained_evidence_policy`. Permit it only for M29. It must
   pin manifest path and SHA-256, capture-time collector revision,
   configuration fingerprint, runtime payload-hash set, and a human-readable
   rationale. Reject extra fields, a different manifest, altered hash, or use
   by any other milestone.

2. Change evidence validation only when that exact M29 policy matches. Always
   validate manifest and artifact hashes, Demo surface, exit status, and result
   marker. For the pinned bundle, validate the recorded capture-time revision
   and configuration plus runtime payload hashes/configuration identity; do
   not require it to equal current HEAD or rerun the later verifier. For every
   other bundle retain current freshness, HEAD-binding, and verifier rules.

3. Amend M29’s objective and acceptance wording to say it accepts the retained
   worker-handoff result. Its invalidation rules must name listener payload,
   runtime configuration, declared recovery surface, or evidence tampering;
   they must not invalidate the accepted bundle merely for documentation or
   evidence-tooling changes.

4. Add focused tests: the pinned bundle passes; a changed artifact hash,
   payload hash, configuration fingerprint, manifest path, or use by M30
   fails. Retain existing tamper tests.

5. Run governance validation, focused M29 tests, and the offline retained
   bundle validation. Record C1/C3/C4 from the retained bundle and C2 from a
   current local verification. Preserve Chris’s existing sign-off only if it
   remains bound to the same manifest; otherwise request a new sign-off.

6. Run `python3 scripts/forex_milestones.py prove --id M29`. Report its exact
   output. A successful command is the only condition that writes `proven_at`.

## Validation and Acceptance

From the repository root run:

    python3 scripts/forex_milestones.py validate
    python3 -m pytest -q tests/milestones/test_m29.py
    python3 -m pytest -q tests/test_milestone_governance.py
    python3 scripts/forex_milestones.py prove --id M29

Acceptance requires the retained bundle to pass only through its exact pinned
policy, all negative controls to fail closed, and `prove` to emit the normal
success result. No T480 command, broker action, order, or maintenance-hold
change is part of this plan.

## Idempotence and Recovery

The policy is additive and exact-manifest-bound. Re-running validation and
tests is safe. If any check fails, do not edit the raw bundle; revert the
policy change and retain the existing evidence unchanged.

## Decision Log

- Decision: accept the retained drill rather than repeat it.
  Rationale: unchanged runtime payloads/configuration and an existing PASS
  record make another drill redundant for this bounded function.
  Date/Author: 2026-09-16 / Chris direction, Astra independent review.

- Decision: also preserve the diagnostics runtime revision
  `4fc956d5184d4f0c3a47c7d3c469fac9ff2843e8`, distinct from the drill and collector
  revisions. Its four payload hashes match the drill and current files.
  Date/Author: 2026-09-16 / implementation inspection.
- Decision: preserve existing manifest-bound approval across current local
  verification. This records Chris's already supplied decision without
  manufacturing a new sign-off or changing its original timestamp.
  Date/Author: 2026-09-16 / approved plan execution.
- Decision: commit the reviewed owned paths before formal prove. Chris supplied
  explicit commit authority during execution; clean-worktree closeout remains
  enforced.
  Date/Author: 2026-09-16 / Chris direction.

## Surprises & Discoveries

The retained diagnostics report a later application revision than the drill,
but all four runtime payload hashes and governed configuration agree. The old
verifier incorrectly equated these with the collector revision. The M29 policy
now keeps all identities and checks executable bytes.

The default continuation checker fails with `IsADirectoryError` on the repo
root because the old A1 work record lacks `markdown_plan`; the old H5 execution
record has the same issue. This work does not change that unrelated metadata.
The current explicit H5 production-orchestration record can be checked.

## Owned Paths and Verification Matrix

Owned paths: `src/forex/milestones.py`,
`config/schemas/milestone-registry.schema.json`, `milestone_registry.json`,
`tests/milestones/test_m29_retained.py`, `docs/milestones/M29-proof.md`,
`docs/evidence_and_milestones.md`, this plan, and M29 state/history updates.
Existing M29 evidence and human approval entries are preserved.

Expected path: a pinned aged bundle passes with distinct collector/runtime
revisions. Negative controls reject modified artifacts, manifest, current
payload/configuration, policy payload/configuration, collector/runtime revisions,
manifest path and unknown fields. M30 cannot use the policy. Unpinned M29 still
requires fresh proof. Approval still requires the exact bundle and configuration;
current local verification remains mandatory. Existing clean-worktree, normal
verifier tamper and governance tests also pass.

Actual command: `python3 -m pytest -q tests/milestones/test_m29.py tests/milestones/test_m29_retained.py tests/test_milestone_governance.py`
returned success for 32 tests. `forex_milestones.py validate` returned
`milestone governance valid`. Direct `validate_evidence_bundle` on the original
bundle returned `FOREX_M29_PROOF_OK`. No raw evidence bytes were changed.

## Outcomes & Retrospective

Implemented and formally closed through the normal `prove` transition at
2026-09-16T02:39:52Z. Implementation commit: `874e66d`. Current verification
passed on that committed implementation before closeout; all four acceptance
checks are recorded. The parent agent independently reviewed the policy,
schema, validator and tests without required repairs.

The policy digest (SHA-256 of sorted, compact JSON) is
`53f3351c2018c2b70c19934d9362538b361cea57eb76af9791a48fea1b0a00e7`.
The manifest digest remains
`bd19c0179122cbef432871380837572dddc056067456aea231fd02099dc26785`.
Chris's original approval timestamp remains 2026-09-16T02:21:38Z.

No T480 or broker command, repeat drill, raw-evidence mutation or Live action
occurred. The result is historical proof of the bounded held worker-handoff
function; it makes no uptime, broker-outage or profitability claim. M30 is
READY, not started. Final state/history and this progress record are committed
separately after proof; that administrative commit does not change runtime
payloads, proof implementation, or the observed evidence.
