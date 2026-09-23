# M32 — Demo MVP operator handoff and quality proof

This is a bounded assessment of the human-operated Demo workflow, not approval
for Live trading, unattended availability or a profitability claim. Formal
status and the latest evidence path are in `project_state.json`.

## What the operator can use

From `/home/chris/projects/forex` with the project environment active:

    python3 scripts/m20_listener_dashboard.py

The existing read-only view shows the candle, recorded assessment/decision,
broker position count and recorded trades, including fill/exit prices and P&L
when available. Add `--full` for detailed source evidence and missing fields.
NO_TRADE means a decision not to enter; RUNNING alone is not permission to trade.
The persisted rationale is shown without inventing a more precise explanation.
PostgreSQL numeric-string prices are now displayed instead of marked missing.

Keep the approved GOMarketsMU-Demo terminal open in the signed-in operator
session. Leave the protected listener/monitor, account/risk/exposure gates,
durable journal, no-retry rule and PostgreSQL audit bridge unchanged. Do not
restart, close, adopt or duplicate positions merely to make the view look clear.
Live access and parameter/risk changes are outside this handoff.

## Retained observations and limits

Approved M30 demonstrates a naturally selected protected entry-to-close lifecycle
with reconciled broker evidence. Approved M31 records ten NO_TRADE decisions in
2026-09-23 01:15–01:25 UTC and zero EURUSD broker deals in that interval. Its
historical reference is a zero-exposure NO_CHANGE baseline, not evidence of
active-strategy performance. Both original source evaluations reproduce exactly.

The actual read-only report retained at
`runs/evidence/M32/inventory-20260923/operator-report-v2.json` was generated at
2026-09-23T03:17:38.652030+00:00. It showed RUNNING, a matched assessment,
NO_TRADE with recorded rationale, 113 ledger rows and four broker positions.
Risk permission was unavailable; account flatness and current protection of
unrelated/manual positions were not established. This snapshot is not a claim
about continuous or present uptime. Historical unresolved rows remain visible.

The required MVP consists of the approved Demo terminal, protected listener and
monitor, durable audit storage and this existing read-only view. No new dashboard,
orchestration framework, multi-account routing or strategy optimisation is
required. The legacy watchdog was already retired under M30; M32 removes no
runtime service or safety control.

## Reproduce the final assessment

From a clean committed revision, use a new output directory:

    bash scripts/capture_m32_evidence.sh \
      --bundle runs/evidence/M32/<new-directory> \
      --operator-report runs/evidence/M32/inventory-20260923/operator-report-v2.json
    bash scripts/verify_m32_evidence.sh runs/evidence/M32/<new-directory>

Capture copies approved parent artifacts without rewriting them, records their
approval bindings, recomputes the raw assessments, renders the actual operator
report at normal/narrow/full widths, and retains test/governance receipts.
Verification checks hashes, scope, timestamps, original-source consistency,
current evaluator/configuration identity and unchanged approved parent evidence.
The 24-hour evidence expiry is not a required waiting period. Expired observations
cannot be refreshed by rewrapping them. No remote or broker operation occurs.

`FOREX_M32_PROOF_OK` means the bounded retained-evidence check passed. Independent
four-role recommendation and Chris's explicit M32 result approval are still
required for formal closeout. The implementation repair review by
`/root/m32_quality_review` passed after source-availability, runtime-binding,
decision-age and derived-warning checks were tightened; 59 focused tests passed.

## Live-readiness assessment

NOT_READY_FOR_LIVE. There is no qualified statistical/out-of-sample performance
result; Demo costs do not establish Live-equivalent commission/slippage/financing.
Direct account/manual attribution and historical ledger gaps need later design
work. Interactive-session dependency and unrelated-position protection remain
explicit limits. Further non-executing research needs separate authorisation;
none of these gaps authorises a Live trade or expands this Demo MVP.
