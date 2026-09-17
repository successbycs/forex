# M30 Wave 4 — final-version Demo lifecycle proof

## Purpose

Complete M30 on its declared proof surface without widening the MVP: observe
one naturally eligible EUR/USD `GOMarketsMU-Demo` order from the final reviewed
listener version through mandatory close and broker reconciliation. The
operator must be able to inspect the closed M1 decision, strategy owner,
proposal, broker attempt, position lifecycle, costs, close, and reconciliation
using retained raw observations and the existing read-only evidence view.

This plan does not create a trade. `NO_TRADE`, a terminal refusal, an unsafe
account, a disabled terminal, or unavailable broker state remain correct
outcomes. The listener continues normal protected Demo operation while waiting
for a naturally eligible setup.

## Scope and boundary

The only external target is the existing fixed `M1_EURUSD_DEMO` profile on
`GOMarketsMU-Demo` for EURUSD. The fixed T480 adapter remains the only broker
path. Do not use generic shell, SQL, MT5, n8n, dashboard, or AI actions as an
alternate execution route. Live trading, strategy/risk changes, M15 authority,
new database schema, and forced/retried orders are out of scope.

One exception is the separately labelled, one-shot M30 Demo execution drill.
It is a fixed terminal-to-broker diagnostic, not an M1 strategy decision. With
the listener's broker path exclusively locked (while monitoring remains
running), it may submit exactly one 0.01-lot EURUSD BUY to the bound
Demo account, attach a capped protective stop, immediately close it, and retain
the broker result. It has no caller parameters and cannot be used as M30 proof,
strategy performance, or a replacement for the normal decision path.

The final release contains the terminal-capability preflight: disabled or
unavailable MT5 terminal/API capability records a `NOT_SUBMITTED` refusal and
does not call `order_send`. It must be deployed through the hash-bound T480
release procedure before any M30 proof observation can count as final-version
evidence.

## Formal dependency map

M29 is already proven under its retained-evidence policy and is reusable. M30
is the active contract. Waves 1–3 and Package D are implemented and verified;
they supply candle identity, continuous protected Demo operation, fixed account
binding, and the evidence view. Wave 4 is the remaining M30 activity. M31 and
M32 are planned later milestones and are not authorised by this work record.

## Progress

<!-- forex-work-projection:start task=M30-WAVE-4-FINAL-PROOF schema=forex.execution-work-projection.v1 -->
<!-- forex-work-item id=release-preflight state=DONE -->
- [x] release-preflight — Stage and verify every immutable final listener payload without interrupting the running Demo listener (DONE)
<!-- forex-work-item id=final-release state=DONE -->
- [x] final-release — Hold, install, and verify the final hash-bound Demo listener release, then release the hold only after a healthy heartbeat (DONE)
<!-- forex-work-item id=execution-drill state=IN_PROGRESS -->
- [ ] execution-drill — Deploy and run the fixed one-shot Demo terminal-to-broker diagnostic; retain its distinct result without treating it as M30 proof (IN_PROGRESS)
<!-- forex-work-item id=natural-lifecycle state=BLOCKED -->
- [ ] natural-lifecycle — Retain one naturally eligible final-version Demo order, close, and broker reconciliation without forcing or retrying an order (BLOCKED)
<!-- forex-work-item id=proof-verification state=PENDING -->
- [ ] proof-verification — Verify the retained proof against M30 acceptance, exact revision, configuration fingerprint, and safety boundaries (PENDING)
<!-- forex-work-item id=independent-review state=PENDING -->
- [ ] independent-review — Obtain independent read-only review and record the M30 closeout recommendation or remaining defect (PENDING)
<!-- forex-work-projection:end -->

## Owned paths and evidence

- This plan and `m30-wave-4-final-proof-work.json` record actual progress.
- Existing fixed T480 release operations stage, prepare, configure, install,
  and verify payloads. They do not receive arbitrary commands.
- New raw release and proof observations must be retained under a new
  `runs/evidence/M30/` timestamped directory. Never overwrite prior evidence.
- The current listener and evidence view are inspected through their fixed
  adapter operations and read-only scripts.

## Acceptance and verification

Before deployment, inspect the active M30 contract, Git revision, configuration
fingerprint, account/server/symbol binding, flat/exposure state, monitor,
broker-path lock, staged payload hashes, and rollback path. Use
`release-readiness` before changing T480 state.

**Deployment requirement — T480 command envelope:** before staging or invoking
any T480 release operation, read `docs/t480-deployment.md` and run the encoded
command-length regression check in `tests/test_t480_adapter.py`. Every fixed
non-fragment operation must remain below the stated envelope. Larger reviewed
payloads must be numbered, hash-verified fragments; a runtime launcher must
start a hash-bound payload rather than embed a large command. A
`The command line is too long` result is a deployment `NO-GO`, not a retry or
an excuse to bypass the adapter.

After deployment, capture a new release-bound heartbeat and an ordinary
read-only decision observation. During normal operation, retain the first
naturally eligible final-version lifecycle through broker close and complete
reconciliation. Verify that its decision/proposal/attempt/position/outcome
identities join exactly, its revision/configuration match the deployed release,
and no Live target or unreviewed broker action occurred. Run applicable focused
tests, milestone validation, and the work-projection/continuation checks.

Formal M30 closeout is separate: it needs the review and recommendation gates
declared by the registry. A successful deployment, a `NO_TRADE`, or a test pass
alone is not M30 proof.

## Risks and rollback

An incomplete or hash-mismatched payload is a deployment stop, not a reason to
copy files manually. A failed install must retain or restore the previous
scheduled task through the fixed release procedure. The broker-path lock is
created only for the execution drill and keeps listener monitoring active. A
disabled terminal produces a durable refusal, not an automated UI change or
retry.
