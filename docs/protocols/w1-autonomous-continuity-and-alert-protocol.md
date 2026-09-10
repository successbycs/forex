# Wave 1 autonomous continuity and alert protocol

## Purpose

Prove that the T480-hosted Demo listener operates and recovers without an
interactive T16/RDP session or a human timed a test. This protocol replaces
manual disconnect, manual observation, and manual service-start steps. It
does not place an order, alter a broker position, access Live, or weaken
Option B.

The test is owned by the listener's existing Session-0 Scheduled Task. T16 is
only an optional read-only viewer. A missing T16, closed RDP session, or no
interactive Windows logon must not affect test execution or result capture.

## Required implementation

Add one fixed T480-local operation, `m20_listener_run_continuity_protocol`.
It has no caller-controlled command, server, symbol, account, trade, or timing
parameters. Its committed bounds are:

| Setting | Fixed value |
| --- | --- |
| Surface | `GOMarketsMU-Demo`, EURUSD listener only |
| Entry state | Flat account, no unresolved execution, maintenance hold present |
| Observation window | 30 minutes |
| Heartbeat tolerance | No unexplained gap greater than 30 seconds |
| Recovery deadline | Five minutes after controlled listener-worker restart |
| Broker mutation | None |
| Alert scope | One marked `W1_CONTINUITY_DRILL` incident and one recovery notification |
| Alert retries | Bounded and deduplicated; failure never blocks protection |

Before starting, the operation must make fresh fixed read-only observations of
the broker account, unresolved attempts, risk policy, deployment binding and
task identity. It must refuse without side effects if the account is not
confirmed flat, a monitor/recovery is unresolved, deployment binding is
invalid, or the listener task is not `S4U` in Session 0.

The operation must create an immutable local run identifier and append every
state transition to a T480-local JSONL audit record. It must schedule its own
completion check through the T480 task infrastructure. Completion must not
depend on an open RDP connection, a running Codex process, a browser, or a T16
network connection.

## Automated procedure

1. **Preflight.** Refuse safely unless the exact Demo server, flat exposure,
   empty unresolved-attempt result, unpaused Option B state, valid payload
   hashes, and `S4U`/Session-0 task identity are observed.
2. **Baseline.** Persist baseline account/risk/deployment observations and a
   heartbeat sequence number/time. Enter or retain maintenance hold so no new
   entry can occur during the protocol.
3. **Continuity interval.** For 30 minutes, a separate T480-local verifier
   samples the listener heartbeat and task identity at a fixed cadence. It
   does not query MT5 repeatedly and does not use T16; local listener records
   are the primary continuity source. A stale heartbeat, changed principal,
   stopped task, or unexpected broker exposure is a failure.
4. **Controlled worker handoff.** While hold remains active and the account is
   still flat, request the existing fixed listener recovery path once. This is
   a listener-worker test, never a host reboot and never an MT5 order. Verify
   a new child worker and a fresh release-bound heartbeat within five minutes.
5. **Incident and recovery alert.** The operation records a bounded drill
   incident before the handoff and sends one marked drill notification. After
   recovery, it records and sends one recovery notification. It stores only
   message identifiers, delivery state and timestamps; webhook secrets and
   message content stay local/redacted. A notification failure is recorded as
   `PENDING` or `FAILED` and retried within the fixed bound without delaying
   monitoring or recovery.
6. **Postflight.** Make one fresh broker account, risk, unresolved-attempt,
   deployment and task observation. Require the original lease/risk anchors,
   Option B configuration and account scope to match the baseline. Preserve
   maintenance hold and write `PASS`, `FAIL`, or `INCONCLUSIVE` with exact
   reasons. Never automatically release the hold.

## Pass criteria

The protocol passes only when all are retained in raw T480-local evidence:

- at least 30 minutes of continuous, release-bound listener heartbeats within
  the declared gap tolerance;
- `S4U` task identity and Session 0 before and after the interval;
- no reliance on a T16/RDP session, shown by the absence of any T16-side input
  or control action in the protocol path;
- exactly one controlled worker handoff, fresh recovery heartbeat within five
  minutes, and no duplicate listener worker;
- unchanged `GOMarketsMU-Demo` account identity, flat exposure, empty
  unresolved-attempt summary, unchanged Option B/lease anchors and no order;
- one retained drill incident, one delivery result for the drill alert, and
  one delivery result for the recovery alert; and
- an offline verifier recomputes hashes, ordering, heartbeat gaps, binding and
  before/after equality without contacting T480, MT5 or Discord.

`INCONCLUSIVE` is the correct result for an unavailable alert channel or an
unavailable local observation. It does not become a pass from configuration
alone. `FAIL` leaves maintenance hold active and records an incident; it does
not retry the handoff indefinitely.

## Separate host-reboot proof

An unattended worker handoff does **not** prove host reboot recovery. Add a
separate fixed `m20_listener_run_reboot_recovery_protocol` only after the
current protocol passes and the T480 startup dependency is reviewed. It must
schedule its own post-boot verifier before rebooting, require a flat held Demo
account, wait five minutes for WSL/PostgreSQL/MT5/listener recovery without
interactive sign-in, then retain 30 minutes of local continuity. It must never
reboot when exposure is open or unresolved.

## Evidence and review

Store raw results under
`runs/evidence/M20/w1-autonomous-continuity-<UTC>/raw/` and independent output
under `runs/verification/M20/w1-autonomous-continuity-<UTC>/`. Bind the
contract revision, application revision, release ID, all payload hashes,
governed configuration fingerprint, lease, Option B state, and verifier hash.
An Astra read-only review may assess the retained bundle; it cannot run,
approve, or alter the protocol. This protocol supplies R5/R6 evidence. It
does not close Wave 1 or M20.
