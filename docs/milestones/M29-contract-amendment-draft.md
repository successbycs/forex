# Draft — M29 contract amendment and evidence design

Status: planning only. This document does not amend `milestone_registry.json`,
activate any operation, request a listener restart, make a broker call, or
assert that M29 (or any Wave/M20 criterion) is proven.

## Why an amendment is needed

The active M29 contract calls for proof of “interruption, outage, restart, and
idempotent collection recovery” on the real-time `GOMarketsMU-Demo` collection
surface. The current M29 capture instead kills a short-lived local adapter
client after a fixed `m27_demo_tick` read and issues another stateless read.
The hardened verifier correctly refuses its closeout: this format contains no
durable collector identity, outage observation, listener lifecycle record, or
persisted receipt/request identity through which deduplication could be shown.

There is an existing, materially closer held-only M20 listener surface:
`m20_listener_run_continuity_protocol` retains a local protocol record and
JSONL event log, establishes a flat held Demo baseline, samples a release-bound
heartbeat, makes one controlled listener-worker handoff, and retains a
postflight observation. There is also a separate held-only
`m20_listener_run_reboot_recovery_protocol` plus a read-only status operation.
The latter arms a post-boot verifier and records listener/watchdog state and a
fresh heartbeat. The historical Wave 1 reboot bundle demonstrates that kind of
surface, but is not current M29 evidence and must not be repurposed as such.

## Criterion mapping

| Active M29 criterion | Exact current capability | Can existing held-only protocol substantiate it? | Draft disposition |
| --- | --- | --- | --- |
| M29-C1 — real-time Demo collection and recovery workflow works | `m27_demo_tick` is a fixed read-only tick. The M20 continuity protocol samples the permanent listener’s local heartbeat under maintenance hold and performs one scheduled-task worker handoff. The reboot protocol performs a host reboot only after held/flat checks. | Partially. The continuity protocol can substantiate an intentional **listener-worker interruption and restart** with fresh local heartbeat. The reboot protocol can substantiate **host reboot recovery**. Neither establishes an upstream MT5/broker outage, and neither currently proves durable receipt deduplication. | Split the capability into separately measurable worker-handoff and host-reboot recovery. Do not retain “outage” or “durable deduplication” as passed terms unless a declared collector capability records them. |
| M29-C2 — milestone and repository verification | The repository has M29 tests and a verifier, but the current verifier deliberately rejects the stateless capture. `verify_w1_reboot_recovery.py` shows an offline pattern for validating retained operation envelopes and relationships. | Not by itself. Existing Wave 1 verification is not an M29 verifier and its historical bundle is not current. | Add an M29-only offline verifier with an exact required-artifact set, raw-envelope hashes, chronology checks, and negative controls. Keep test and governance commands; add a focused M29 contract test suite. |
| M29-C3 — current self-attested proof bound to revision/config/source versions | Continuity observations retain release ID, application revision, configuration fingerprint and payload hashes; the current M29 envelope verifier checks current Git/config and tick clock binding. | Only after a new run. Existing held/reboot records are historical, may be stale, and may not match the current revision/configuration. | Require a fresh, clean-worktree M29 bundle that binds the M20 release/payload hashes and listener configuration to the repository revision and current governed fingerprint. A material listener/config/contract change invalidates it. |
| M29-C4 — safety, provenance, point-in-time, no critical issue | Held-only protocols check Demo identity, flat exposure, monitor state, fresh heartbeat, S4U task identity, and retain `broker_mutation: NONE`; they leave maintenance hold in place. The raw M27 envelope provides Demo/symbol/tick checks. | Partially. These are strong no-order and provenance controls, but currently do not bind all M29 evidence into one contract-specific bundle and the reboot guard documents an unresolved-attempt limitation for historical evidence. | Require pre/post account and exposure observations, maintenance hold before/after, Option B/lease/risk anchors, listener/watchdog identity, payload/release hashes, fresh nonfuture tick/heartbeat times, and an explicit unresolved-attempt result. Any unavailable/ambiguous condition is `FAIL`/`INCONCLUSIVE`, not a pass. |

## Proposed contract language (draft)

Replace the M29 objective and C1 wording with the following bounded surface:

> Prove, while the M20 listener is under maintenance hold and the
> GOMarketsMU-Demo EURUSD account is confirmed flat, one controlled permanent
> listener-worker interruption and recovery. Retain a current, release-bound
> local heartbeat sequence and pre/post no-order safety observations. Host
> reboot recovery is a separately labelled optional sub-drill; an upstream
> broker/MT5 outage and durable collection deduplication are out of scope until
> a collector with durable receipt identity is declared and implemented.

Suggested replacement acceptance details:

- C1: one held-only controlled worker handoff; a fresh, release-bound listener
  heartbeat within the declared five-minute deadline; no duplicate worker;
  and preserved held/flat Demo condition. A host reboot, if included, has its
  own explicit `HOST_REBOOT` evidence subtype and must not be inferred from a
  worker handoff.
- C2: an offline M29 verifier must check raw artifacts, hashes, envelope
  success, event ordering, heartbeat gap/deadline, pre/post equality, and
  no-order state. It must reject a missing/extra artifact, altered raw envelope,
  bad release/configuration binding, future or stale timestamps, wrong server,
  non-flat exposure, released hold, failed/inconclusive protocol, and duplicate
  worker evidence.
- C3: the capture must occur inside the contract’s 10-hour window with
  nonfuture timestamps, clean tracked revision, current governed configuration
  fingerprint, exact listener release ID, application revision, payload hashes,
  protocol schema version, and verifier hash. The manifest must bind every raw
  file by SHA-256 and the raw operation envelopes must themselves carry the
  same configuration/release binding where available.
- C4: require `GOMarketsMU-Demo`, `EURUSD`, account available and flat before
  and after, `MAINTENANCE_HOLD` retained before and after, no unresolved attempt
  in the authoritative declared source, unchanged Option B/risk/lease anchors,
  S4U/Session-0 listener identity, and `broker_mutation: NONE`. No order,
  close, modification, hold release, generic command surface, or Live access
  is permitted.

The amendment must also delete the unsupported terms “outage” and “idempotent
collection recovery” from a closeable M29 claim unless their definitions and
evidence are added. If durable deduplication is retained, the contract must
define a durable collector-owned receipt/request key, the persistence location,
the exactly-once/no-mutation invariant, and a safe replay observation across a
worker restart; the current fixed tick read is insufficient.

## Proposed capture bundle (not implemented)

Use a new M29-specific capture command only after the registry amendment and
operator authority. It should create a fresh immutable directory such as
`runs/evidence/M29/<UTC-run-id>/`, never overwrite raw evidence, and retain:

| Artifact | Source and purpose |
| --- | --- |
| `preflight-account.json` | Raw fixed account/exposure envelope: available, AUD Demo identity, zero positions. |
| `preflight-listener.json`, `preflight-watchdog.json`, `preflight-diagnostics.json` | Raw fixed local identity/heartbeat/hold/release/payload observations. |
| `continuity-arm.json` | Raw envelope for the fixed held-only protocol arm, including its immutable run ID. |
| `continuity-record.json` and `continuity-events.jsonl` | Raw retained protocol state and append-only event log, copied without repair or normalization. |
| `postflight-account.json`, `postflight-listener.json`, `postflight-watchdog.json`, `postflight-diagnostics.json` | Raw postflight proof of flat Demo account, continued hold, fresh heartbeat, task identity and no duplicate worker. |
| `reboot-*.json` (only for declared optional sub-drill) | The raw pre/post boot, record and diagnostic envelopes needed by a reboot-specific verifier. Do not mix this with worker-handoff success. |
| `revision.txt`, `configuration.json`, `manifest.json`, `summary.txt` | Revision, fingerprint/release/payload binding, complete artifact hash list, redaction declaration, and result marker. The summary cannot be the proof. |
| `verification.json` | Offline M29 verifier result, verifier file hash/version, every check and its input hashes. Keep this separate from raw evidence. |

The verifier must use only the retained bundle and local repository/configuration
needed for current-binding validation. It must not contact T480, MT5, Discord,
or a broker. Raw envelope paths must be relative, contained in the bundle,
unique, regular files and exactly match the manifest’s required list. Secrets,
account values beyond what the contract explicitly needs, endpoints, and alert
content remain redacted; redaction must not remove server, symbol, timing,
release/configuration, or no-order fields needed for verification.

## Operator and external prerequisites

This proposed drill requires explicit operator authorization after the contract
is amended. It is not authorized merely by this draft. Before any capture:

- the healthy listener must **not** be restarted merely for inspection;
- the operator must select a safe maintenance window, confirm the Demo account
  is flat and no protected position needs monitoring, and authorize entering
  the existing maintenance hold;
- the held-only protocol must confirm current S4U/Session-0 task identities,
  fresh heartbeat, valid deployment binding, Demo account availability, and the
  authoritative unresolved-attempt condition declared by the amendment;
- T480/Windows Task Scheduler, the M20 release files, MT5 Demo connectivity,
  and the local persistence paths must be available; any unavailable condition
  makes the run refused or inconclusive;
- a host reboot, if selected, needs separate explicit approval because it is a
  materially disruptive operational action even though it has no order surface;
- no operation may remove maintenance hold automatically after success or
  failure. Return-to-service remains a separately authorized action.

## Non-claims and decision needed

The existing held-only continuity and reboot facilities are evidence candidates,
not proof that M29 is complete. Historical Wave 1 evidence cannot satisfy the
M29 freshness/current-binding requirement. The next decision is whether M29
should be amended to the bounded held listener-recovery claim above, or whether
to first implement a distinct durable collector/outage/deduplication surface
that can honestly support the current broader wording.
