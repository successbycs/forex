# M30 — final Demo lifecycle closeout

This ExecPlan is a living document. It must be maintained with `PLANS.md`.
It is the sole execution plan for the remaining M30 closeout work; its machine-
checked progress record is `docs/plans/m30-wave-4-final-proof-work.json`.

## Purpose / Big Picture

M30 is complete only when the deployed EUR/USD Demo listener independently
selects one eligible M1 setup, opens its single bounded `GOMarketsMU-Demo`
position, protects and closes it, and records the resulting broker facts in a
verifiable evidence bundle. The result is a demonstrable end-to-end operating
loop, not a claim of profitability or a test of Live trading.

The listener is already deployed and evaluates fresh completed M1 candles.
The remaining work is deliberately small: restore the terminal's automated
submission permission, retain the first *natural* listener-owned lifecycle,
then verify and review the captured proof. The bounded diagnostic has already
proved its fail-closed refusal behaviour and is supplementary only. A manual
MT5 order can demonstrate that an operator has broker access,
but it is not a listener decision and cannot satisfy M30-C1 or M30-C3.

## Formal milestone dependency map

M29 is `PROVEN` under its explicit retained-evidence exception and remains a
reusable prerequisite. M30 is the active `IN_PROGRESS` milestone. Its contract
requires a real system integration on the fixed `GOMarketsMU-Demo` EUR/USD
surface; it authorises the diagnostic and the normal listener only. M31 and
M32 are later contracts: no work in this plan starts, changes, or proves them.

Waves 1–3 and Package D are already implemented and verified. They provide
closed-candle identity, one terminal decision per candle, durable assessment
records, account identity, and reconciliation plumbing. This final wave fits
M30 because it produces exactly the contract's missing final-version order,
close, and reconciliation evidence. It does not add schemas, strategies,
risk settings, another timeframe, a scheduler, or a Live path.

## Progress

<!-- forex-work-projection:start task=M30-WAVE-4-FINAL-PROOF schema=forex.execution-work-projection.v1 -->
<!-- forex-work-item id=release-preflight state=DONE -->
- [x] release-preflight — Stage and verify every immutable final listener payload without interrupting the running Demo listener (DONE)
<!-- forex-work-item id=final-release state=DONE -->
- [x] final-release — Hold, install, and verify the final hash-bound Demo listener release, then release the hold only after a healthy heartbeat (DONE)
<!-- forex-work-item id=execution-drill state=DONE -->
- [x] execution-drill — Run the fixed one-shot Demo terminal-to-broker diagnostic and retain its distinct outcome without treating it as M30 proof (DONE)
<!-- forex-work-item id=natural-lifecycle state=BLOCKED -->
- [ ] natural-lifecycle — Retain one naturally eligible final-version Demo order, close, and broker reconciliation without forcing or retrying an order (BLOCKED)
<!-- forex-work-item id=proof-verification state=PENDING -->
- [ ] proof-verification — Verify the retained proof against M30 acceptance, exact revision, configuration fingerprint, and safety boundaries (PENDING)
<!-- forex-work-item id=independent-review state=PENDING -->
- [ ] independent-review — Obtain independent read-only review and record the M30 closeout recommendation or remaining defect (PENDING)
<!-- forex-work-projection:end -->

## Current observed state

At `2026-09-17T08:08Z`, the T480 listener was `RUNNING` on immutable release
`98d33531346f1c6a`. It had processed 56,039 assessments and its most recent
closed M1 candle was safely journalled as `NO_TRADE_RECONCILED`. The current
repository revision is `a09a2e321089f978227e21f54342811963aaf677`; the active
configuration fingerprint is
`sha256:2a233e61310e1187417bd4d234115d69b89d9aa9606511b6b5c54dc76760f9cb`.

The same read-only terminal check reported `terminal_connected=true`,
`account_trade_allowed=true`, and `account_trade_expert=true`, but
`terminal_trade_allowed=false` and therefore `submission_permitted=false`.
This is the current external blocker. It proves the listener will fail closed;
it does not authorise an automated UI change. T480 SSH was reachable at that
time. The operator's reported manual trade is supplementary context only; it
must not be named as a listener proposal or used in the M30 evidence bundle.
At `2026-09-17T08:43Z`, a later read-only recheck timed out at the T480 SSH
endpoint. At `08:45Z`, it timed out during the SSH banner exchange; ICMP and
TCP/22 probes then received no response. These checks changed no remote state;
terminal permission remains unconfirmed since the last observed fail-closed
value. The shared AI Lab transport independently repeated the preflight at
`08:48Z`: strict host-key and batch-mode checks passed locally, then its remote
SSH check timed out. The host/network surface, rather than the Forex adapter,
was temporarily unavailable. At `08:55Z`, shared transport and the listener
recovered, but terminal submission was still disabled. The listener also
observed an eligible trend-pullback SELL candidate and correctly vetoed it as
`NO_TRADE_RECONCILED` because its persistent Option B risk policy is paused
with `EXTERNAL_CASH_FLOW`.

## Context and orientation

The listener is the Windows Scheduled Task `Forex-M20-Demo-Listener` on T480.
It calls `t480/m20_demo_listener_service.py`, which reads fresh quotes and
*closed candles* (a one-minute price bar whose end time has passed). It calls
the deterministic session in `t480/m20_demo_trading_session.py`; that session
either persists `NO_TRADE` or permits one selected strategy owner to use the
fixed Demo executor. The adapter `scripts/t480_adapter.py` provides only
catalogued commands; it is never a general shell or MT5 command channel.

`m20_listener_terminal_capability` only reads the terminal/account flags.
`m30_demo_execution_drill` is the separately authorised, fixed 0.01-lot Demo
BUY diagnostic. It uses a protective stop and immediate close under an
exclusive listener broker-path lock. It is intentionally not a strategy trade
and is not proof of M30. `capture_m30_natural_lifecycle_evidence.sh` captures a
final listener proposal by its proposal ID after its broker lifecycle is
complete. `verify_m30_evidence.sh` checks that captured bundle without talking
to MT5 or changing it.

All T480 staging and diagnostic calls must follow `docs/t480-deployment.md`.
The SSH transport has an encoded command-size limit. Reviewed payloads are
fixed, SHA-256 verified fragments; a `The command line is too long` response
is a no-go and must never be worked around with a generic remote shell.

## Plan of work

First, the operator enables **Algo Trading** in the exact bound
`GOMarketsMU-Demo` MT5 terminal. This is an external UI setting owned by the
operator, not a repository change. The executor then runs the read-only
capability operation. Only the exact observable value
`submission_permitted=true` advances the plan. A manual order does not change
this result because manual dealing and API/Algo Trading permission are distinct
MT5 capabilities.

Before a natural entry can proceed, inspect the persistent Option B risk pause.
`EXTERNAL_CASH_FLOW` means the runtime has detected a balance/equity change that
it cannot safely attribute to the listener. Its fixed resume path may record an
operator resume request but must not override a still-breached control. Resolve
the underlying account observation or use that fixed governed path; do not
remove a state file, amend an account balance, or weaken the risk policy.

The one-shot diagnostic is a narrow confidence check that
the final deployed terminal can submit, close, and recover Demo broker history.
It has no inputs and no retry loop. A refusal, account mismatch, terminal
failure, unresolved lock, or history failure is a durable blocker to repair;
it never triggers a forced or repeated order. Its captured output remains
separate from M30 proof. It was attempted on the final deployment and safely
refused because terminal submission was disabled; this completed the optional
diagnostic record and it does not need to be retried for M30 closeout.

Third, leave the listener running unchanged. It evaluates each newly closed M1
candle. When a named M1 strategy naturally selects a BUY or SELL and all
existing gates pass, the listener creates the only eligible position. Retain
that proposal ID only after MT5 reports the position closed and reconciliation
joins the decision, attempt, broker open/close, costs, and AUD outcome. Do not
alter strategy thresholds, session rules, risk caps, account mapping, or M1
cadence merely to obtain a trade.

Fourth, create a new timestamped, immutable M30 evidence directory using the
capture script. The bundle must contain raw fixed-operation output, timestamps,
redaction declaration, Git revision, config fingerprint, artifact digests, and
the final lifecycle. Verify it using the separate verifier. The verified
bundle must be less than 24 hours old when submitted for review.

Finally, run the M30 tests and governance validation, obtain an independent
read-only recommendation bound to the exact evidence/revision/configuration,
and follow the registry's closeout command. Review does not itself place,
approve, or alter a trade.

## Concrete steps

Run all repository commands from `/home/chris/projects/forex`.

1. The operator enables **Algo Trading** in the MT5 terminal used by the
   `Forex-M20-Demo-Listener` task. Then observe, without trading:

       python3 scripts/t480_adapter.py execute --operation m20_listener_terminal_capability

   Expected success gate: JSON contains `server":"GOMarketsMU-Demo"`,
   `terminal_connected":true`, and `submission_permitted":true`. If the last
   field is false, stop here: the terminal instance or its Algo Trading/API
   permission is still not the instance used by the scheduled listener.

2. Confirm the listener is healthy before normal observation:

       python3 scripts/t480_adapter.py execute --operation m20_listener_status
       python3 -m pytest -q tests/test_t480_adapter.py -k 'm30_execution_drill or transport_limit'

   Expect `running:true`, an advancing heartbeat, the Demo server, and passing
   transport tests. Do not proceed if status shows an account mismatch,
   unresolved exposure, maintenance hold, an active risk pause, or a
   command-length failure.

3. Only if a separate terminal-to-broker diagnostic is needed after permission
   is restored, run the one-shot diagnostic exactly once:

       python3 scripts/t480_adapter.py execute --operation m30_demo_execution_drill

   A valid diagnostic ends with its explicit success marker and recorded close
   history. It is supporting evidence only. If it reports a refusal, preserve the exact result in the work
   record and fix the stated condition; do not retry by changing its size,
   symbol, server, or order parameters.

4. Observe normal operation, with no parameter or strategy change:

       python3 scripts/t480_adapter.py execute --operation m20_listener_latest_assessment
       python3 scripts/t480_adapter.py execute --operation m20_listener_status

   Continue only when a new final-release listener-owned proposal is a BUY or
   SELL, then wait for its required close and reconciliation. A `NO_TRADE` is
   valid operational evidence and means continue observing later fresh candles;
   it is not an M30 closeout result.

5. Capture and verify that one lifecycle using its listener proposal ID:

       bash scripts/capture_m30_natural_lifecycle_evidence.sh <proposal-id>
       bash scripts/verify_m30_evidence.sh runs/evidence/M30/<timestamp>
       python3 -m pytest -q tests/milestones/test_m30.py
       python3 scripts/forex_milestones.py validate

   Expect `FOREX_M30_PROOF_OK` from the verifier, M30 tests passing, and
   governance validation passing. Record actual output paths and hashes in the
   work record rather than copying raw broker data into Git.

6. Run the independent review route required by the registry, then use the
   milestone CLI to record checks/evidence and attempt formal proof. Do not
   claim completion unless the CLI writes `proven_at`.

## Validation and acceptance

M30-C1 is met only by one autonomous, bounded Demo entry from the final listener
through mandatory close and full reconciliation. M30-C2 requires the focused
M30 tests, governance validation, and inspectable retained decision evidence.
M30-C3 requires the fresh self-attested bundle to bind the deployed release,
Git revision, and configuration fingerprint. M30-C4 requires Demo-only server
binding, no unsafe fallback, no Live contact, and no unresolved critical issue.

The bounded diagnostic, manual order, dashboard, tests, and a `NO_TRADE`
record each offer useful supporting evidence, but none meets C1 or C3 alone.

## Idempotence and recovery

The capability and status operations are read-only and can be repeated. The
execution drill cannot be repeated while its lock exists; its fixed cleanup
operation may clear only an unsubmitted `REQUESTED` lock. Never delete a lock
or state file manually. A failed staging/install uses the existing hash-bound
release rollback path. If SSH is unavailable, retain the timeout result and
continue only local checks; do not use another account, a manual order, or a
generic remote command as a substitute.

## Surprises & Discoveries

- Observation: Manual dealing can work while the listener refuses automation.
  Evidence: at `2026-09-17T08:08Z`, the reachable bound terminal reported
  `terminal_trade_allowed=false` and `submission_permitted=false` while all
  Demo account permission fields were true.
- Observation: T480 SSH availability was intermittent.
  Evidence: timeouts after `2026-09-17T06:42Z` were followed by successful
  fixed read-only adapter calls at `2026-09-17T08:08Z`, then another timeout
  at `2026-09-17T08:43Z` and no host or TCP/22 response at `08:45Z`.
- Observation: T480 has a strict encoded command-length limit.
  Evidence: the release procedure uses 48 fixed, hash-verified fragments;
  command-length failure is now an explicit deployment no-go.

## Decision Log

- Decision: Treat the manual MT5 trade as supplementary broker-access context,
  never as M30 proof. Rationale: it has no listener decision/proposal identity
  and bypasses the autonomous decision path. Date/Author: 2026-09-17 / Chris
  and Astra.
- Decision: Keep the terminal UI permission human-owned. Rationale: Chris
  explicitly deferred repository-controlled AutoTrading configuration; the
  listener remains fail-closed until the read-only capability check proves it.
  Date/Author: 2026-09-17 / Chris.
- Decision: Do not force a natural strategy trade to finish M30. Rationale:
  the contract makes the first naturally eligible lifecycle the only M30 proof
  surface; the fixed diagnostic separately establishes broker wiring.
  Date/Author: 2026-09-17 / M30 contract.

## Outcomes & Retrospective

The release and continuous closed-candle assessment loop are operating. M30 is
not yet complete because the scheduled terminal refuses automated submissions
and no final-version natural listener lifecycle has been retained. When those
two facts change, this plan provides the exact capture, verification, review,
and formal-closeout route without expanding the MVP.

## Artifacts and notes

The current work record is
`docs/plans/m30-wave-4-final-proof-work.json`. Raw M30 evidence belongs under
`runs/evidence/M30/<timestamp>/` and is intentionally not committed. The only
tracked record of a blocker is a concise, redacted statement in the work plan.

Plan revision, 2026-09-17: expanded the prior Wave 4 note into a self-contained
M30 closeout ExecPlan after the operator reported a manual Demo trade. The
revision records that manual trade correctly as supporting context, adds the
observed terminal-permission gate, and preserves the contract's natural-order
proof requirement.
