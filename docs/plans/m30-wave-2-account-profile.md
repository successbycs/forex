# M30 Wave 2 — Fixed Demo account profile

This ExecPlan implements exactly one local execution profile:
`M1_EURUSD_DEMO`. It binds the active M1 listener to a locally held SHA-256
account scope for the existing `GOMarketsMU-Demo` AUD `EURUSD` account. It is
not account routing and it does not create a profile scheduler, portfolio
layer, new strategy, risk change, M15 path, or Live capability.

The active listener remains on its currently deployed release while this work
is implemented and verified. A later deployment needs separate explicit
authority and a short fixed maintenance hold only if the fixed installer needs
one. No order is ever forced to prove this profile.

## Deployment record

On 2026-09-17, after explicit operator authority, the fixed T480 procedure
provisioned and validated the ignored local profile, installed release
`a9ff090f0a566849` at application revision `005f0ca`, and removed the short
maintenance hold only after a fresh release-bound heartbeat. The listener then
completed a fresh closed-M1 `NO_TRADE` assessment on `GOMarketsMU-Demo`/AUD.
This is deployment evidence, not an assertion of profitability or a forced
trade proof.

## Acceptance

- The runner accepts only a locally held profile whose exact fields are the
  fixed profile name, Demo server, AUD currency, EURUSD symbol, and a valid
  SHA-256 account scope.
- It verifies the profile before it can create an executable M1 assessment and
  again before it crosses the execution-reservation boundary.
- A missing, malformed, or mismatching profile fails closed: it creates no
  reservation and cannot call the broker order API.
- The local profile value is never committed; the fixed deploy configuration
  hand-off rejects an absent or invalid local file.
- The fixed provisioning operation accepts only a separately supplied valid
  hash, creates only this ignored profile file, and refuses to replace a
  different existing binding. It does not contact MT5 or derive the expected
  value from the account it protects.

## Progress

<!-- forex-work-projection:start task=M30-WAVE-2-ACCOUNT-PROFILE schema=forex.execution-work-projection.v1 -->
<!-- forex-work-item id=profile-contract state=DONE -->
- [x] profile-contract — Define the one fixed local M1_EURUSD_DEMO profile contract and its configuration hand-off (DONE)
<!-- forex-work-item id=runtime-binding state=DONE -->
- [x] runtime-binding — Enforce the profile before executable assessment and before execution reservation (DONE)
<!-- forex-work-item id=verification state=DONE -->
- [x] verification — Prove matching and mismatching profile behaviour, including no reservation and no broker order on mismatch (DONE)
<!-- forex-work-item id=independent-review state=DONE -->
- [x] independent-review — Obtain an independent read-only review of the profile boundary and focused checks (DONE)
<!-- forex-work-item id=release-readiness state=DONE -->
- [x] release-readiness — Record local release readiness and any external deployment prerequisite (DONE)
<!-- forex-work-projection:end -->

## Owned paths

- `t480/m20_demo_trading_session.py`
- `scripts/t480_adapter.py`
- `t480/command-catalog.json`
- `tests/test_t480_adapter.py`
- `docs/workflows/m1-demo-decision-workflow.md`
- this plan and its execution-work record

## Validation

Run focused runner and adapter tests, configuration validation, and
execution-work projection validation. Inspect that the mismatch test reaches
neither `reserve-execution` nor `order_send`. An independent read-only review
is required before readiness is recorded.
