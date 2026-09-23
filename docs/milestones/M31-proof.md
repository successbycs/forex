# M31 Demo evaluation proof

M31 evaluates the protected Demo workflow; it does not change trading rules or
prove profitability. Formal state remains in `project_state.json`. A technical
`FOREX_M31_PROOF_OK` result alone cannot close the milestone: the required
completion recommendation and Chris's review/signoff remain separate gates.

## MVP observation and scope

The retained declaration selected 2026-09-23 01:15:00–01:25:00 UTC
(inclusive/exclusive) before observation, at revision
`afce837c1b51d252761542ee05cab43ac1a89166`. Its NO_CHANGE reference means no
new exposure, no trades and no new trade costs. Ten persisted NO_TRADE decisions
and zero EURUSD broker deals were observed. Existing positions and their P&L
are not included. M30's protected natural lifecycle remains separate proof.

The unchanged raw bundle is
`runs/evidence/M31/mvp-20260923T012500Z-afce837`. The supplemental fixed bounded
query v2 in `runs/evidence/M31/supplement-20260923T0208Z/completeness-v2.json`
adds versions, rationale, timeframe and session scope. The evaluator requires
every original decision field to match, including proposal identity, time,
action, attempt and reconciliation fields. Missing or drifting strategy,
application/configuration identity and non-M1/non-Demo records are refused.

The retained M16 source is
`runs/evidence/M16/20260902T023427Z/walk-forward-probe.json`. Only its NO_CHANGE
zero-exposure behavior is used. Its 12 H1 sessions and retrospective availability
assumption cannot support an active M1 strategy comparison. This policy and M16
reference were selected in the prewindow plan; the exact artifact was bound
after observation, which remains disclosed in the report.

## Reproduce without another observation or broker action

From a clean committed repository, run:

    bash scripts/capture_m31_evidence.sh --retained \
      --bundle runs/evidence/M31/<new-formal-directory> \
      --original-bundle runs/evidence/M31/mvp-20260923T012500Z-afce837 \
      --enriched-completeness runs/evidence/M31/supplement-20260923T0208Z/completeness-v2.json \
      --historical-reference runs/evidence/M16/20260902T023427Z/walk-forward-probe.json
    bash scripts/verify_m31_evidence.sh runs/evidence/M31/<new-formal-directory>

This route performs no remote operation. It copies retained bytes without
overwriting the original, runs focused tests and governance validation, and
retains separate derived evaluation, summary and generic evidence manifest.
The verifier checks digests and recomputes the evaluation from raw inputs,
binds current evaluator revision/configuration to the manifest, and checks that
both capture and the observation itself are less than 24 hours old. Rewrapping
an old observation cannot refresh its freshness. This 24-hour expiry is an
evidence freshness rule, not a minimum trading observation duration.

The original legacy capture/verifier is retained for compatibility. Its
`FOREX_M31_EVIDENCE_VERIFIED` marker alone does not meet this formal contract.

## Required limitations

- This is an evaluated refusal interval, not a traded-outcome or profitability
  sample. No trade is forced to produce a preferred result.
- Broker history belongs to the retained account-scope hash. Proposal/session
  records have no account hash for a direct join. No executed-trade attribution
  or account-wide P&L claim is made from this observation.
- Generic persisted refusal text is retained verbatim; separate diagnostics of
  the existing-position gate must not replace it.
- The original collector, runtime decision revision and repaired evaluator are
  different identities and are recorded separately, not relabelled as one.
- Raw evidence is self-attested, not independently attested by the broker.
- A passed technical wrapper still needs independent review, the registry's
  recommendation and human signoff. M32 remains gated until formal M31 proof.
