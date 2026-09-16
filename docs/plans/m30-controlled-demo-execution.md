# Prove M30 with one bounded autonomous Demo order

This ExecPlan is a living document and follows `PLANS.md`. It implements only
M30's declared Demo proof surface. It does not enable Live trading, expand the
fixed T480 adapter, change trading rules or risk limits, or release the current
maintenance hold until existing fixed autonomous preconditions are met.

## Purpose / Big Picture

M30 will give the operator a reproducible record showing one deliberate
EUR/USD GOMarketsMU-Demo trade from a fixed autonomous proposal through broker-confirmed
closure and reconciliation. The outcome is an integration proof, not evidence
of a profitable strategy. The operator will be able to run an offline verifier
over a retained M30 evidence bundle.

## Progress

- [x] (2026-09-16 02:42Z) Started M30 after M29 became proven.
- [x] (2026-09-16) Inspected the contract, fixed executor, M20 evidence
  tooling, and reconciliation baseline. Recorded the decision evidence in
  `docs/research/m30-demo-execution-evidence-brief.md`.
- [x] (2026-09-16 02:49Z) Performed read-only Demo readiness observations:
  the authoritative account was flat on GOMarketsMU-Demo/AUD, while the
  listener remained in `MAINTENANCE_HOLD` and its deployed application revision
  was `aa416361930e86d4346c33499491b20d14058d09`.
- [ ] Add the M30 capture and offline verifier that bind the persisted proposal,
  raw operation output, source revision, configuration fingerprint, lifecycle, broker
  history, and reconciliation.
- [ ] Validate the implementation, record M30-C2/C4 as applicable, and obtain
  an independent read-only review.
- [ ] When the existing autonomous preflight is eligible, perform the bounded
  remote sequence once and retain its result.
- [ ] Verify the fresh bundle, record all M30 acceptance checks, obtain the
  required human sign-off and current review recommendation, and run formal
  `prove` if every contract gate passes.

## Surprises & Discoveries

- Observation: M20's executor already persists a proposal and has fixed
  one-position, Demo-only entry and close logic, but its capture contract has
  no M30 evidence bundle.
  Evidence: `t480/m20_demo_trading_session.py` and
  `scripts/capture_m20_demo_evidence.sh`.
- Observation: the currently observed listener status was `MAINTENANCE_HOLD`.
  Evidence: `m20_listener_status` observation at 2026-09-16T02:49:42Z; it
  explicitly says that no assessment or Demo order is permitted.
- Observation: the active release does not match the current local source
  revision, so the fixed adapter will fail closed before it can run new source.
  Evidence: `m20_listener_diagnostics` reported deployed revision
  `aa416361930e86d4346c33499491b20d14058d09`; the local M30 work is uncommitted.

## Decision Log

- Decision: retain the fixed autonomous entry gates and bind their persisted
  proposal to the M30 evidence bundle.
  Rationale: the repository is an autonomous Demo-trading platform; existing
  bounded gates prevent entry when inputs or risk state are unsafe.
  Date/Author: 2026-09-16 / Chris direction.
- Decision: retain the existing fixed execution path and build no generic MT5
  or shell interface.
  Rationale: the architecture assigns broker access only to the fixed Demo
  operation and M30 is not authorised to broaden it.
  Date/Author: 2026-09-16 / M30 contract and architecture.

## Outcomes & Retrospective

Not complete. No M30 order, hold release, or external mutation has occurred.

## Context and Orientation

`milestone_registry.json` declares M30 as a real-system integration proof:
one bounded autonomous `GOMarketsMU-Demo` EUR/USD entry, a mandatory close by the
configured cutoff or an earlier risk exit, and complete reconciliation. Its
freshness limit is 24 hours. `project_state.json` records mutable state and
`runs/run_history.json` records append-only transitions.

The only broker-capable route is `scripts/t480_adapter.py execute --operation
m20_demo_trading_session`, backed by `t480/m20_demo_trading_session.py`. That
operation already has fixed account, symbol, sizing, risk, idempotency,
protection, monitoring, and reconciliation constraints. Invoking it can place
an order. It must never be called merely to obtain a proposal.

`scripts/m20_demo_evidence_contract.py` verifies an M20 bundle without
contacting the broker. `src/forex/m20_reconciliation_baseline.py` establishes
that a retained assessment and broker history can only be joined by explicit
position identity; it must not infer a match from timestamps, prices, or
comments. M30 needs the same fail-closed standard plus a contract binding the
persisted autonomous proposal to the broker lifecycle.

## Plan of Work

First, add `scripts/capture_m30_evidence.sh`,
`scripts/m30_evidence_contract.py`, `scripts/verify_m30_evidence.sh`,
`docs/milestones/M30-proof.md`, and `tests/milestones/test_m30.py`. Capture
must first ensure a clean material revision and pass M30 tests/governance.
After the fixed action reports a terminal closed lifecycle, it must retain the raw
operation result, lifecycle/history/reconciliation reports, listener
diagnostics, configuration, source revision, test outputs, redaction
declaration, hashes, manifest, and `FOREX_M30_PROOF_OK` summary. The verifier
must be offline and fail closed for any changed artifact, stale evidence,
wrong server/symbol, persisted-proposal/revision/config mismatch, open or
unresolved position, missing mandatory close evidence, or incomplete broker
reconciliation.

Second, run focused tests and the contract verification over synthetic fixture
bundles. Record exact outputs in this document. Use the QA verification skill
before treating the implementation as complete; it validates the code and
fixtures but cannot prove M30's real-world surface.

Third, after an independent read-only implementation review, perform the
smallest remote sequence only when existing autonomous entry gates are
eligible: verify
the account is still GOMarketsMU-Demo and flat; release maintenance only when
the fixed autonomous sequence's preconditions are satisfied and a deployed
release matches the committed M30 source; invoke the one fixed operation once;
leave monitoring and broker
protection active until the position closes by cutoff or earlier risk exit;
then retain the resulting immutable evidence. A refusal, changed market input,
missing close, or reconciliation failure ends the attempt without retrying or
manufacturing evidence.

Finally, run the offline verifier and the registry verification, record each
criterion with the evidence path, finish implementation, collect the current
required recommendation and Chris's closeout sign-off, and run the normal
milestone CLI prove transition. The CLI-generated `proven_at` is the only
formal completion record.

## Concrete Steps

Run every local command from `/home/chris/projects/forex`.

    python3 scripts/forex_milestones.py validate
    python3 -m pytest -q tests/milestones/test_m30.py
    bash scripts/verify_m30_evidence.sh runs/evidence/M30/<bundle>

After implementation, run the relevant QA verification commands named by the
new tests and inspect the parsed manifest and reconciliation output. Before an
external attempt, do not run `capture_m30_evidence.sh` until the existing
autonomous preflight and all fixed Demo safety gates pass.

Expected successful eventual verifier output is:

    FOREX_M30_PROOF_OK

This output alone is not closeout; it must remain fresh, match the current
revision/configuration, and pass all formal review and CLI gates.

## Validation and Acceptance

Implementation acceptance requires tests that demonstrate `NO_TRADE` cannot
be captured as M30, a Live server reference is rejected, and an authentic synthetic
closed/reconciled Demo bundle verifies while negative controls fail.

M30-C1 requires fresh raw evidence of one persisted-proposal-bound Demo EUR/USD entry and
broker-confirmed terminal close. M30-C2 requires the registry and M30 tests to
pass. M30-C3 requires a current manifest tied to the exact revision,
configuration, and retained source versions. M30-C4 requires no Live reference,
no unresolved exposure or reconciliation, correct provenance, and a
mandatory-close-or-earlier-risk-exit record. Tests and synthetic fixtures do
not substitute for C1 or C3.

## Idempotence and Recovery

Synthetic fixture verification and read-only status observations are repeatable.
Raw external capture directories are created once;
never overwrite, repair, or delete an incomplete bundle. If a preflight or
revalidation fails, keep maintenance in its safer state and create a new
proposal rather than extending stale evidence. If a broker operation reports a
fill but exposure is unclear, do not retry: preserve the raw result and follow
the existing monitoring/reconciliation path.

## Artifacts and Notes

Owned paths are M30 proof documentation, M30 capture/verifier scripts, focused
tests, this evidence brief and plan, and M30 state/history changes. Existing
raw evidence and unrelated H5 continuation metadata are not owned by this
plan.

## Interfaces and Dependencies

The M30 evidence verifier accepts only an explicit bundle directory and does no
network or adapter calls. The
only execution interface remains the pre-existing no-argument fixed T480
operation. `GOMarketsMU-Live`, generic MT5, generic shell, arbitrary SQL, and
automatic approval are prohibited.
