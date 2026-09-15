# Autonomous delivery status

## Active Harness status — 2026-09-14

**Active sequence:** Harness H1–H4 → Wave A → Wave B → Wave C. This is a
delivery-status change only; formal state remains M29 `BLOCKED` and no proof,
authority, Plane connectivity acceptance or trading execution is created.

The canonical active task metadata is
[`active-delivery-tasks.json`](active-delivery-tasks.json). The retained
[`autonomous-delivery-queue.json`](autonomous-delivery-queue.json) records the
historical/deferred W1–W3 plan only; it is not an active-task selector for the
Harness/A/B/C sequence.

Select and inspect the active task only with:

```text
python3 scripts/delivery_harness_status.py
```

| Task | Evidence/status | Next condition |
| --- | --- | --- |
| Harness H1: concise repository map | `COMPLETE_REVIEWED`; the repository map and canonical task metadata were independently accepted. | No further H1 action. |
| Harness H2: active sequence | `COMPLETE_REVIEWED`; the H1–H4 → A → B → C sequence and superseded wording were independently accepted. | No further H2 action. |
| Harness H3: visible task/evidence interface | `COMPLETE_REVIEWED`; the task/evidence interface and fail-closed dependency selection were independently accepted. | No further H3 action. |
| Harness H4: offline Plane mapping | `COMPLETE_REVIEWED`; the repository-only mapping was independently accepted. Plane remains display-only. | H5 is separately parked for T480 configuration, read-only connectivity, and board acceptance; it is not an H1–H4 → A gate. |
| Wave A | A1 n8n workflow, retention service and verified projection are implemented and independently reviewed; PostgreSQL still has `NO_STORED_BLS_FACTS`. | Clear shared T480 new-service capacity hold and obtain explicit deployment approval, then capture/project/report real BLS facts. FOMC/ECB remain A2. See the [A1 ExecPlan](../plans/wave-a1-n8n-calendar-lineage.md). |
| Wave B | Pending Wave A: bind PostgreSQL calendar context to final M1 eligibility and produce an explainable UTC/Pacific-Auckland joined report. | Keep disabled/default policy and all existing M1 safeguards unless separately approved. |
| Wave C | Pending Wave B: observe recurring protected Demo decision, execution and reconciliation. | Natural Demo operations only; no forced trade or fabricated proof. |

**Workflow:** Terra owns one bounded implementation task and task evidence;
Astra reviews it. After two failed Terra repairs of the same defect, Astra
repairs it and an independent read-only reviewer checks the material fix.
Formal reviewers remain read-only. H_SLOW and broad research are deferred,
not deleted.

**Triad flag:** `AGENTS.md` requires Triad-plus-domain recommendation for
closeout while `docs/triad_review.md` narrows Board execution to selected phase
gates. The active M29 registry separately requires its declared review. Pending
Chris's explicit reconciliation of `AGENTS.md` and `docs/triad_review.md`, the
stricter combined requirement applies. This flag does not amend M29 or weaken
any mandatory rule.

## Historical record — retained W1–W3/H_SLOW direction

The following status record is retained for provenance. It is not the active
work selector: H_SLOW and broad research are deferred by the active Harness
sequence above. Statements about its next package describe the historical
W1–W3 plan, not current delivery direction.

## Solo-operator critical-path reset — 2026-09-13

Chris directed delivery to prioritise reaching a real, bounded, reconciled
Demo decision-and-outcome loop over speculative edge optimisation and
collector hardening beyond the safety boundary. Initial Demo success means
frozen, explainable decisions made from fresh permitted inputs with protection,
cost attribution, retained evidence and reconciliation—not a claimed edge or
backtest result. H_SLOW forward/OOS tier sizing is therefore deferred until
after the initial fixed-risk Demo loop; it cannot enlarge the initial hard cap.
The existing M29 recovery proof and any active broker operation remain subject
to their formal contracts and fresh natural observation requirements.

**Mission clarification — 2026-09-13:** the project is a solo-operator Demo
trading platform, not a research-first assistant. The immediate definition of
success is process-correct trading decisions: a selected frozen strategy uses
fresh permitted inputs, correct Demo account scope, fixed risk/protection and
cost rules, and produces a retained reconciled outcome. This is deliberately
not a profitability claim. Work that does not directly enable or protect this
decision-and-outcome loop is deferred unless it addresses an observed safety
or reliability defect.

Chris has approved the FOMC/ECB first-party timing amendment and an ongoing,
revocable H_SLOW Demo trial. The active event contract is context-only with
unknown/partial coverage. The H1 fixed-risk readiness package is implemented,
tested and independently reviewed: one position; AUD 1,000 hard-loss ceiling;
USD 10,000 notional ceiling; USD 100,000 lease ceiling; Demo EUR/USD only;
and `DISABLED_NOT_ROUTED`. Its next remaining work is execution integration,
not a further human policy decision or forward/OOS tier proof.

The fixed H1 execution-request contract is also implemented and independently
reviewed. It consumes only an exact fixed-trial `PREPARED_DISABLED` record,
rejects tier evidence, cap expansion, malformed provenance, fabricated stop or
loss arithmetic, and synthetic numeric ranges, then emits a hash-bound
`DISABLED_NOT_ROUTED` request. It is a verified pre-adapter boundary, not
broker submission or proof. The next package is the fixed Demo adapter and
fresh broker-side preflight.

That preflight is now implemented and independently reviewed locally as the
parameter-free `h_slow_demo_preflight` T480 operation. It reads only the fixed
Windows-local H1 binding; requires the configured terminal's Demo/AUD identity,
EUR/USD specification, fresh quote and at most one visible position; and emits
only an opaque account-scope digest. It has no credential output, mutation,
generic broker surface or order route. It remains **not deployed**: installing
the non-secret terminal binding and observing a fresh read-only preflight are
the next external actions. This is not an execution adapter or trading proof.

The fixed preflight was invoked once on 2026-09-13 and failed closed because
the dedicated Windows-local H1 binding was absent. It was not retried. The
raw preflight result is now validated against the exact adapter schema,
recomputed tick age and configured broker-clock offset, H1 account scope,
fresh EUR/USD quote, position count and broker volume lattice. The
submission-disabled execution request independently binds that receipt hash,
requires a flat H1 scope, and verifies its side quote and volume against the
receipt. Both packages passed focused tests and independent read-only review.
They validate a supplied receipt, not its external authenticity; no execution
adapter, deployment, order or milestone proof has resulted.

The matching local receipt-verifier command is now implemented and
independently reviewed. It accepts exactly one regular, non-symlink local JSON
record; rejects malformed, duplicate-key, non-finite, oversized and
broker-clock-mismatched inputs; and emits only the canonical validated receipt
on success. Its offset comes only from governed configuration. It neither
contacts MT5 nor writes, routes, exposes credentials or changes execution
authority. This makes an eventually captured preflight replayable and
verifiable locally, not authentic by assertion and not an execution adapter.

The autonomous delivery queue's closed state model was repaired and
independently reviewed after it correctly exposed that already-recorded
`COMPLETE_REVIEWED_*` states were not parseable. Reviewed disabled/not-deployed
packages now satisfy delivery dependencies but can never be selected as
`READY`; parked and deferred work remain inert. The selector therefore
truthfully reports no software-only next package, retains M29 as `BLOCKED`,
and grants no execution authority.

## M20 calendar decision seam — 2026-09-13

The M1 calendar gate is now connected to the final M20 Demo proposal path,
after the existing strategy, persistent-risk and existing-position vetoes and
before proposal persistence, reservation or order submission. The complete
calendar observation is hash-bound in the decision snapshot and retained in
the existing structured news-context field. A gate refusal converts an
otherwise actionable proposal to `NO_TRADE` and clears all order fields. The
PostgreSQL bridge and offline replay kernel independently recompute the overlay
and reject a re-hashed forged decision or a final-action mismatch. The policy
remains disabled, therefore this release records the disabled observation and
preserves the existing M20 behaviour. It is not activation, calendar coverage,
an order, a broker observation or M29 proof. Focused runner, bridge, gate and
replay verification passed with independent read-only acceptance.

## Fresh first-party policy-calendar observations — 2026-09-13

The reviewed fixed collector was run once per approved non-trading endpoint,
retaining FOMC capture `fomc-20260913-001` and ECB capture
`ecb-20260913-001` under the ignored local evidence store. Both returned a
complete fixed-endpoint HTML response. Independent local verification
recomputed each transport-observation hash and publisher-body hash, validated
the original captured envelope against the fixed family/URL contract, and
confirmed `execution_authority: false`. These are genuine retained source
observations, not a parser-derived event time, complete calendar coverage,
gate activation, MT5 operation, or M29 proof. The primary-context result
therefore remains `UNKNOWN` until exact timing and coverage requirements are
satisfied. A separate read-only review independently confirmed both receipt →
transport → strict envelope → publisher-body chains, including current
probe/program hashes and no symlinked capture paths.

A matching fixed, read-only H1 reconciliation snapshot is now implemented and
independently reviewed. It uses the same terminal identity boundary, returns
only a bounded 31-day EUR/USD position/deal snapshot, filters foreign symbols,
rejects incomplete broker rows and refuses more than one current position.
It has no order or mutation capability and is not deployed. Together, the
preflight, bound request and reconciliation snapshot prepare the full
pre-adapter Demo evidence path; the actual dedicated terminal binding and a
separate fixed execution adapter are still required.

The supporting fixed H1 financing-terms snapshot is also implemented and
independently reviewed. It retains broker EUR/USD swap/rollover, tick and
volume terms plus a fresh AUD/USD conversion quote, refusing absent, stale or
malformed data without an order route. These are observed inputs for labelled
cost/risk preparation, never assumed zero costs or activation authority.

The dedicated-terminal binding template and exact non-secret Windows setup are
now available in [H1 terminal setup](../h-slow-h1-terminal-setup.md). It
explicitly prevents reuse of the M1 terminal and does not store a password.

Canonical disabled H_SLOW stream-isolation and pre-activation mandate files
are now present and independently reviewed. They bind the separate opaque H1
scope, terminal label and namespaces to the initial fixed-risk cap file, but
remain `NOT_DEPLOYED`, `NOT_SELECTED` and `NOT_EXPOSED`. They are a
configuration boundary, not account selection, activation or broker proof.

The previously implicit H_SLOW operating-policy gap is now an independently
reviewed, inactive v1 semantics proposal. It fixes the proposed monthly
open-once/hold/close-first lifecycle, ATR20×3 broker-side initial stop, no
widening/trailing/target, ongoing no-end-date holding only with healthy
protection/reconciliation, observed overnight/weekend terms, non-invented
costs and annotation-only event context. The pure validator accepts only that
exact `DRAFT_NOT_ACTIVE`, Demo-only proposal and rejects type coercion,
activation, route, cap and rule mutations. It is ready for Chris to approve or
amend; it cannot itself submit, close or manage an order.

Initial checkpoint: 2026-09-12. Execution brief:
[Autonomous Delivery](../prompts/autonomous-delivery.md). This is a work queue,
not broker evidence, a milestone closeout or a claim that every stream is running.

## First-party policy-source verification checkpoint — 2026-09-13

Read-only FOMC and ECB publisher captures have been retained under the ignored
local evidence policy and independently verified from their immutable bytes,
receipts, manifest hashes, timing derivations and projected event records. The
verified calendar-source observations remain `UNKNOWN` coverage and
`PENDING_RETAINED_CAPTURE`; neither changes the primary-source contract,
event-risk gate, scheduler, MT5 surface, or order authority. The next safe W2
package is read-only integration of these verified observations into context
reporting. It must preserve unavailable/partial outcomes and cannot enable
trading.

That integration is now complete and independently reviewed. Its current
report verifies both locally retained policy bundles but correctly returns
`UNAVAILABLE` for every primary family under the unchanged source contract.
No safe implementation package remains in the autonomous queue: the next W2
step is a separate reviewed amendment to the source-qualification contract,
while W1/M29 and H_SLOW activation still require their declared external
observation or human mandate.

The fixed, read-only policy-calendar probe payload is now also implemented
and independently reviewed. It permits only the official Federal Reserve
FOMC calendar and ECB Governing Council calendar endpoints; it allows no
caller URL, redirect, retry, parser, retention write, MT5 or order surface.
It returns a capped, timestamped raw observation and requires an outer
transport deadline when it is later integrated. It is `NOT_DEPLOYED` and does
not itself create a retained capture, exact policy time, qualified coverage or
event-gate authority.

The companion fixed collector and immutable receipt-retention wrapper is now
also independently reviewed. It reserves a capture ID before a single
35-second-bounded transport attempt, refuses duplicate attempts, stores a
durable transport receipt for success or failure, and stores publisher bytes
only after the complete fixed-source success envelope validates. Symlinked
paths and unsafe partial replacement are refused. It remains `NOT_DEPLOYED`:
the next implementation is the canonical PostgreSQL calendar projection with
source/capture/digest lineage, as directed by Chris.

The retained BLS store has since been independently verified read-only: 19
immutable captures yielded 38 CPI/Employment candidate records, still with
`UNKNOWN` coverage. A machine-validated BLS monthly URL-template amendment
draft is prepared and its impact report finds all 38 candidates, but it is
explicitly `DRAFT_NOT_ACTIVE` / `NOT_APPLIED`. Chris's explicit approval is
the only action that may apply that source-contract policy; until then, the
unified context remains unavailable and no event gate can be enabled.

Chris subsequently approved and the repository applied the exact BLS
URL-template policy. The real retained BLS report remains non-authoritative:
the repeated captures are `AMBIGUOUS`, coverage is `UNKNOWN`, and the gate is
still disabled. The matching FOMC/ECB timing-source amendment is now prepared
and independently verified against both retained bundles, but is
`DRAFT_NOT_ACTIVE` / `NOT_APPLIED` pending Chris's separate explicit approval.

## Active goal implementation checkpoint — 2026-09-12

### Latest repair/review checkpoint

- W1 latest-assessment listener bridge is now deployed to the existing
  GOMarketsMU-Demo M1 listener through its fixed staged release protocol. Before
  maintenance, a fixed read-only account observation confirmed AUD Demo,
  available position data and zero open positions. The listener was put into
  `W1R_COORDINATED_MAINTENANCE`, its 32-part service payload was hash-verified,
  and byte-identical already-deployed runner, audit-bridge and notification
  payloads were copied only after source/destination SHA-256 checks. This
  hash-checked copy replaces a runner base64 transfer that the constrained T480
  endpoint refused as too long; it does not widen a command surface. Prepared
  release `d855a7b01c0f7f3c` installed with a fresh held heartbeat, idle monitor
  and valid four-payload binding. A subsequent small release added a monotonic
  `assessment_sequence` to the replace-only record and a local exporter cursor:
  each retained receipt is now BASELINE_UNVERIFIED, CONTIGUOUS, DUPLICATE or
  GAP_OBSERVED with an exact missed sequence count. The final release
  `145fd9e88b5a6d8a` installed under the same checked hold and now correctly
  waits for a fresh quote. Its current governed configuration
  fingerprint is `sha256:ed6e7e73e2a41ede5392234c0580299e89eb0319563d5939417132fe97809f8f`.
  The read-only latest-export operation reports `LATEST_ASSESSMENT_ABSENT`, as
  expected until the next fresh market assessment. This is a released component,
  not M29 proof or continuous export coverage: fresh broker data, current
  listener/recovery revalidation and full per-assessment retention remain
  outstanding. It detects sampling loss but does not eliminate it. No Live
  surface or forced trade was used.
- W2 full-retention source work is implemented locally but is **not released**.
  The next listener release will write an immutable, sequence-named non-secret
  assessment record only after its bounded runner call returns; it never
  overwrites a prior record and leaves a staging artifact visible on a failed
  write. A companion reader and `scripts/m20_assessment_spool.py` reject
  unsafe/partial files, wrong release bindings and internal sequence gaps while
  returning only hashes plus retained source records. Forty focused source,
  reader, current-export and adapter tests passed along with governance and
  diff validation. This source component has no deletion, acknowledgement,
  broker call or order authority. It does not make the existing two-minute
  latest-record exporter lossless; a separately reviewed durable drain/ack
  path and controlled listener release remain required.
- The unreleased local drain/ack implementation now copies every record from
  one release-namespaced spool into an immutable local capture directory with
  the existing `demo-trading-operation.json` completeness gate. It binds both
  raw spool bytes and the extracted assessment in a receipt, then advances its
  local cursor only after all new captures have been durable. It never deletes,
  modifies or remotely acknowledges the Windows source spool. Existing capture
  conflicts and cursor/source disagreement fail closed. The source namespace is
  now release-specific, preventing a configuration-release transition from
  mixing sequences. Focused tests cover repeat drains, conflict refusal, cursor
  non-advance and the runnable local command. Deployment needs only a fixed
  trusted local mount path rendered into the already-authorised non-trading
  exporter service. A read-only check confirmed that this Linux environment
  does not expose `/mnt/c/ProgramData/ForexListener`, so no nonexistent mount
  was rendered or deployed. The next integration must use a separately
  reviewed fixed T480 page/read surface or another explicitly verified shared
  filesystem path. No listener release, path grant or broker operation has
  occurred.
- The transport blocker is now implemented as an unreleased fixed T480
  `m20_listener_spool_page` operation. Its only caller-controlled value is a
  non-negative integer local cursor; it reads no more than eight immutable
  files from the active release namespace, verifies release/configuration,
  filename/sequence, Demo server/symbol and bounded byte sizes, then returns
  base64 source bytes plus SHA-256 values. It has no delete, acknowledgement,
  assessment, task or order command. The local cursor is still advanced only
  after independent immutable retention. Adding this governed catalog surface
  changed the configuration fingerprint to
  `sha256:7524f2ca75d9c4b2852f457817ee04c11014687ddfd3d6b3fb12ec80a520770a`;
  state was refreshed, but no proof was recreated. Focused adapter/listener/
  drain tests and governance validation pass. The remaining integration is to
  decode and validate these bounded pages into the local drain, then deploy it
  under the usual controlled listener release procedure.
- The page decoder and local export command are now implemented but **not
  deployed**. They invoke only the fixed page operation with the local durable
  cursor, require an exact echoed cursor/release, strict contiguous sequences,
  valid base64 and matching raw SHA-256 before writing any mirror record. The
  mirror is trusted-path checked and immutable; its records flow through the
  same local drain, whose cursor moves only after every local capture has its
  final `demo-trading-operation.json` completeness file. Malformed bytes,
  hash/gap/release mismatches, unsafe paths and existing-byte conflicts refuse
  without advancing the cursor. Focused page, drain, listener and adapter
  checks pass. A controlled simultaneous listener/exporter release and an
  actual fresh assessment remain required; none was fabricated or inferred.
- The previously described local full-retention pieces are now deployed under
  the controlled listener/exporter procedure. Listener release
  `3e6d749eb27b8dba` has the immutable release-namespaced spool enabled, bound
  to governed configuration fingerprint
  `sha256:7524f2ca75d9c4b2852f457817ee04c11014687ddfd3d6b3fb12ec80a520770a`.
  The Linux `forex-m20-assessment-export.timer` now runs the fixed paged
  read-only exporter, rather than the replace-only latest-record bridge. Its
  first rendered-service run completed successfully at 2026-09-12T04:37:37Z
  with `SPOOL_ABSENT`, which is the expected fail-closed result before the
  newly released listener receives a fresh assessment. A subsequent fixed
  read-only page operation independently observed the same empty spool, while
  listener diagnostics showed `maintenance_hold_present: false`, valid payload
  binding and no failure. The prior “not released/not deployed” entries above
  describe the pre-release checkpoint and are superseded by this deployment
  result. This does not prove lossless coverage, continuous service operation,
  a broker outcome, or M29: the next natural fresh Demo assessment must be
  paged, hash-validated, retained locally and independently inspected before
  those narrower claims can be evaluated. No Live surface, forced trade or
  spool acknowledgement/deletion was used.
- A second-loop review of the deployed local spool exporter found and repaired
  two pre-observation retention defects: a symlinked intermediate mirror
  directory could otherwise escape the configured capture root, and a crash
  could leave a final-named partial mirror file. Each mirror ancestor is now
  checked as a real non-symlink directory; source bytes publish only from a
  fsynced staging file through an exclusive hard link, with unfinished staging
  refusing subsequent export. New regression tests cover both failures. The
  full suite and governance validation passed, the rendered user unit
  validated, and the enabled exporter completed a post-repair 16:43 NZST
  read-only pass with `SPOOL_ABSENT`. This hardens a local evidence path; it
  does not manufacture a record, improve broker availability, or satisfy M29.
- W2 latest-assessment export is implemented and deployed as a bounded bridge
  toward full M1/M20 retention. Each successful
  listener assessment atomically replaces one non-secret ProgramData record;
  it deliberately retains the complete snapshot/proposal pair but excludes the
  PostgreSQL-audit object and never blocks protection or the next assessment.
  A new fixed read-only adapter operation (`m20_listener_latest_assessment`)
  exports only that bounded record after checking active release, configuration,
  Demo-server and EURUSD bindings, with a raw-byte SHA-256. The retained replay
  adapter consumes that exact envelope and carries its transport provenance
  forward without inventing an outcome. Focused listener/adapter/replay tests
  and adapter-catalog validation pass. The separate read-only exporter is now
  deployed on Piwakawaka as the active two-minute
  `forex-m20-assessment-export.timer`; its first real run at 03:51:54Z
  succeeded with `LATEST_ASSESSMENT_ABSENT` from the preceding listener release
  `1c112dea6f545390`, retaining nothing. The listener bridge has subsequently
  been released as recorded above; no broker evidence or formal milestone state
  is inferred from this component deployment.
  Because the listener source is replace-only, it does **not** establish
  gap-free five-second assessment coverage: assessments overwritten before a
  later exporter poll remain absent. A sequence/acknowledged spool or an
  equivalent loss-accounting release is still required before calling that
  broader requirement complete. Absent/malformed records remain explicit
  fail-closed observations.
- Astra's second-loop review tightened the retained M20 replay reporter's
  provenance boundary: a forwarded source digest must now be exactly a
  lowercase 64-hex SHA-256 value, rather than merely beginning with
  `sha256:`. The focused replay/export/event-join suite (20 tests), governance
  validation and diff check passed after correcting a test-exposed expression
  typo in the initial repair. The reporter remains read-only; this does not
  authenticate the source bytes, fill missing outcomes, create a broker
  observation or change any M1/M29 proof state.
- W2 retained annotation automation is deployed locally. Terra supplied the
  one-pass report wrapper and pre-run immutable start markers; Astra implemented
  canonical per-decision UTC-day windows and repaired inclusive-midnight
  handling, ancestor paths, batch row/count validation and backwards-clock
  completion refusal. Independent pre-activation review and rendered-unit
  verification passed. First systemd run at 03:35:50.813Z succeeded with 20
  inputs, five attached, 15 refused; report digest
  `dbd7a37f4024a53b54277a2e5bad8bb7820b07cabea6361434f50de590a9224c` is retained
  in `runs/local/m1-event-reports` with its bound start marker. Timer is enabled
  and active (next observed trigger 16:10 NZST). Independent deployment-result
  review verified actual service/timer state, start/report/policy bindings,
  all 20 source hashes and exact rebuilds of all five attached sidecars.
  Full suite: 770 passed, 33 unconfigured database skips; governance
  and diff checks passed. This is local retained-data processing, not broker
  access or proof of continuous export coverage. No M1/M29 runtime or formal
  milestone state changed. The host must remain running; a watchdog interruption
  leaves a start record without a final report.
  The service now has a second, explicitly trusted root for the released
  current-assessment exporter. Its first dual-root pass at 04:11:00.642Z bound
  both roots in one immutable report, retained the existing 20 historical
  inputs (five attached, 15 refused), and found no current source while the
  listener waits for a fresh quote. This is a verified integration/deployment
  result, not an assertion that a current-market assessment exists or that all
  assessments are retained.
- Read-only deployment health was rechecked at 16:16 NZST: the BLS scheduler,
  M1 annotation timer and M20 latest-assessment-export timer were all active.
  The latest M1 annotation pass completed at 16:10:28 NZST with 20 inputs,
  five attached and 15 refused. The M20 export completed successfully at
  16:16:22 NZST with `LATEST_ASSESSMENT_ABSENT`. This is expected while the
  listener waits for a fresh market quote; it is neither a broker outage claim
  nor permission to synthesize an assessment. The remaining full-retention
  package requires a separately reviewed spool plus post-retention
  acknowledgement protocol, so an exporter cannot lose intervening records
  while the listener retains its execution/protection responsiveness.
- Independent event-service health was rechecked after the spool deployment.
  The enabled BLS timer completed its 16:00 NZST pass successfully, retaining
  two HTTP-200 monthly captures (September and October) with explicit
  `coverage_status: UNKNOWN`; this is publisher acquisition evidence, not a
  claim of complete calendar coverage. The enabled M1 annotation timer then
  completed at 16:11 NZST with 20 retained inputs: five sidecars attached and
  15 inputs explicitly refused. Both services report
  `execution_authority: false`. Their observed results do not depend on an M1
  order, do not change an order decision, and do not establish current-market
  or M29 proof.
- W2 retained M1 batch discovery and optional replay annotation joins are
  implemented and exercised locally. Terra supplied the bounded one-level
  batch; Astra repaired per-row timeout continuation, ancestor validation and
  diagnostic reason codes. Astra integrated a read-only replay join that
  rebuilds context from the verified current journal; missing/invalid/unavailable
  annotation never changes the existing replay or cost report. Independent
  read-only review confirmed report equality without the annotation and rebuilt
  all five actual attached sidecars. Actual batch: 20 direct assessment files,
  five attached, 15 refused (seven unsupported schemas, four non-JSON operation
  outputs, four invalid timestamp sequences). No original records were repaired
  or overwritten. All five contexts have no accepted events and four lookahead
  exclusions, with coverage UNKNOWN. Batch scheduling is not activated; the
  BLS publisher scheduler remains independent. See `docs/m1-event-annotations.md`.
  Final full suite: 758 passed, 33 unconfigured database checks skipped;
  governance and diff checks passed.
- W2 M1 event-annotation sidecar is now CLI-integrated with immutable,
  content-addressed local publication. Terra implemented the pure adapter and
  command; Astra repaired actual snapshot-body hash verification (matching hash
  labels alone were insufficient), strict digest syntax and ancestor-symlink
  rejection. Independent read-only review rebuilt an actual retained sidecar
  from assessment bytes and the verified BLS journal, confirming all bindings.
  Assessment `20260911T094157Z` produced sidecar digest
  `6cef49ab88149583110063fd515e66a8fdaf7d5dab2e81e975ec11b4bed35b5b`;
  repeat execution returned EXISTING without rewriting evidence. Its decision
  time is 09:42:42Z September 11: zero events qualify and four are excluded as
  lookahead, not a healthy-calendar assertion. Earlier `20260911T065015Z`
  correctly refuses because decision precedes snapshot capture by one second.
  Twelve focused module/CLI tests pass; the final full suite passed 753 tests
  with 33 unconfigured database checks skipped; governance/diff checks pass. See
  `docs/m1-event-annotations.md`. Automated discovery and report joins remain;
  M1 execution, broker records and milestone state are untouched.
- W2 scheduler deployment progressed on the actual authorised orchestrator,
  Piwakawaka. The earlier remote-T480 capacity restriction was incorrectly
  treated as a local global hold; local Windows C: has about 403 GB free and
  the user-service manager is running. Astra added/reviewed a safe renderer,
  repaired virtual-environment interpreter preservation, and verified rendered
  units and actual transport dependencies from a local service context.
  Local renderings/environment/store now live under ignored `runs/local/`.
  The initial service pass at 03:19:53Z returned two HTTP 200 captures for
  September/October with no parser quarantine; its hourly timer is enabled and
  active (next observed trigger 16:00 NZST). No new remote service, broker
  operation, M1 change or milestone closeout occurred. Independent read-only
  verification confirmed service/timer state and transport/program, acquisition,
  raw HTML, rebuilt journal and scheduler-result bindings. As-of accepted
  records rise from zero before capture to two after September and four after
  October. This is one verified service pass, not recurring reliability or
  complete coverage. This host must remain available. Fifty-eight focused
  renderer/service/scheduler/sidecar tests pass; diff checks pass.
  Terra also delivered a pure M1 annotation sidecar module and 16 focused
  compatibility checks; it remains pending Astra review and CLI/persistence
  integration, and has no operational trade-decision effect.
- Earlier W2 scheduling implementation checkpoint (activation superseded above): Terra
  supplied the durable scheduler ledger and separate cross-process lock;
  Astra added canonical hourly/current-plus-next-month policy, a bounded
  one-pass CLI and strict collector-result validation. The CLI independently
  rebuilds each child summary from retained observation bytes; separate
  read-only review verified matching and tampered actual retained summaries.
  Astra also repaired denial backoff to apply to HTTP 403/429 regardless of
  whether body processing reports HTTP_ERROR, truncation or oversize.
  Subsequent independent review exposed intrabucket clock rollback and interval
  policy-transition defects; Astra repaired both, plus ancestor-symlink
  rejection. A real local resume-subprocess integration test exposed and
  resolved a Boolean/list mismatch for parser quarantine. Capture bytes remain
  unchanged through crash recovery. Independent re-review passed 43 scheduler,
  CLI and service-template tests, including that integration. The final full
  suite passed: 732 tests, 33 explicitly unconfigured database checks skipped;
  governance and diff checks pass. Terra also prepared unactivated systemd user
  service/timer templates under `deploy/bls/`, separately reviewed. No publisher request, timer activation, broker operation,
  milestone closeout or raw-evidence modification occurred in this package.
  Remaining: render/validate deployment against the actual authorised host and
  resolve its applicable capacity requirement before activation; integrate
  operational annotations. Market-dependent proof remains paused.
- W2 fixed one-pass BLS acquisition now works through the existing shared T480
  transport and immutable local response/capture storage. Terra supplied the
  bounded no-redirect probe; Astra integrated transport/failure receipts and
  offline resume, repaired truncated-body detection and staging-only recovery,
  aligned parser year bounds, and resolved Windows command-length failures
  with a compact streamed payload. No remote files/service were installed.
  Actual HTTP 200 at 2026-09-12T02:59:44.873Z yielded two BLS records with no
  parser quarantine. Independent read-only review verified the entire retained
  byte/hash chain and confirmed zero records before capture availability.
  `--resume` reproduced the journal without a new request. Evidence and the
  two preceding transport failures remain under ignored
  `runs/evidence/W2/bls-collector-20260912`; see the publisher integration note
  for hashes and provenance limitations. Twenty-nine focused tests pass;
  the full suite passed with 689 tests and 33 configured skips. Subsequent
  exact-main-guard/program-hash hardening passed focused review/tests as well.
  This is a functioning one-pass collector, not a deployed scheduler, complete
  event coverage, operational order attachment or formal proof closeout.
  Scheduling/service integration remains independent implementation work;
  persistent host deployment remains subject to the recorded capacity limit.
  No M1 strategy, broker settings or milestone state changed.
- W2 explicit late-capture isolation is implemented and CLI-integrated. The
  store appends a hash-bound quarantine marker for an eligible unpublished
  late capture; raw bytes, metadata and published journals remain unchanged.
  Later captures can proceed, while unmarked lateness/corruption still fails.
  Current isolation health is reported separately from decision-time context.
  Astra repaired optional-directory discovery after lock waits and parent
  directory synchronization. All 37 focused tests passed; separate read-only
  review checked multiple late captures, idempotency across later generations
  and original-byte preservation. The full suite passed with 660 tests and 33
  configured skips; governance and diff checks passed. This changes a future W2 store/CLI release
  binding, not M1 runtime or formal milestone proof.
  A fresh fixed read-only host storage check observed C: 16.8/235.6 GiB free
  at 2026-09-12T02:43:58Z. Shared infrastructure's current capacity rule prevents
  a new persistent service there; collector/service implementation and local
  verification remain independent work. See the publisher integration note
  for the exact missing acquisition/scheduler path. No host cleanup, service
  deployment or broker operation occurred.
- W3 monthly OPEN-intent expiry is implemented in persistence, SQL migration
  and the disabled worker. Only dated, never-claimed OPEN intents in the exact
  original scope expire; their non-submission audit is separate and immutable.
  CLOSE, CLAIMED, UNKNOWN and legacy undated work remain unresolved. Astra
  repaired database session-timezone handling, deadline enforcement after
  row-lock and account-index waits, SQL NULL-state checks and migration
  preservation of additional owner constraints.
  Twenty-eight targeted checks passed, including seven on fresh disposable
  PostgreSQL; the normal suite passed with 650 tests and 33 configured skips.
  Governance and diff checks passed. Separate read-only review independently
  reproduced the final account-index rollback correction and accepted the
  package. This changes future H_SLOW schema/worker release bindings and
  requires migration before that deployment; no trading database, M1 runtime,
  risk settings or formal milestone state changed. Independent router,
  protection, reservations and deployment integration continue; M29's broker
  recovery observation remains paused under its existing resumption conditions.
- W3 initial protective-stop derivation is implemented and connected to disabled
  sizing: `h_slow_protection.py` and the optional `protection_snapshot` path in
  `h_slow_prepare.py` use the proposed canonical ATR20 × 3 rule. The snapshot
  must reproduce the plan's research decision; verified event attachments remain
  supported. Astra repaired precision/context handling, exact raw-stop retention,
  OHLC validation and complete calculation-input binding. Twenty-six focused
  protection/CLI tests passed; the full repository suite, governance validation
  and diff checks also passed. Separate read-only review verified the repairs,
  including gap-aware ATR, zero-range/OHLC refusal and conservative rounding.
  No order, broker setting, deployed component or
  milestone status changed. This W3.1 preparation change affects a future
  H_SLOW release/configuration binding, not existing M1 runtime proof. It does
  not satisfy M29's live recovery surface. Actual account observations, aggregate
  reservations, ongoing protection/router integration and deployment remain.
- W3 disabled order preparation now connects a lifecycle OPEN plan to explicit
  quote/stop, cost, tick/volume, notional, lease and margin inputs, runnable with
  `scripts/h_slow_prepare.py`. Astra corrected loss sizing to include actual
  entry-to-stop spread loss, added Demo source and lifecycle-ID checks, and
  repaired decimal overflow/underflow and cap-rounding cases with bounded
  precision, final cap verification and refusal of lossy JSON numeric output.
  Sixty affected tests, governance
  validation and diff checks passed. Separate read-only reviews verified the
  repairs, including the final JSON-output precision correction. No broker call, risk-limit change or
  activation occurred. A protective-stop rule, actual account observations,
  combined exposure reservation and router/protection integration remain.
- The retained M6 D1 payload was inventoried and its decoded-byte hash checked:
  365 daily bars from 2025-04-03 through 2026-08-28. This corrects the assumption
  that only the shorter H1 sample is available; see the Wave 2 report. Missing
  final August session and availability/month-end checks remain, so the
  inventory does not qualify a September H_SLOW target yet.

- W2 monthly BLS integration is implemented: `bls_monthly_events.py` selects
  CPI/Employment Situation from the official monthly-list shape; the existing
  capture store and resume path accept it via `bls_capture.py --monthly-url`.
  `config/event_sources.json` and `docs/reviews/bls-event-source-scope.md`
  record the separate W2 usage scope; the historical M7 registry is unchanged.
  Astra repaired stale exact-schedule fallback when a newer identified release
  has missing/TBD time, inconsistent date or a date outside the source month.
  Such observations now retain uncertain semantic revisions and the original
  invalid-date reason. The full suite passed before the final date correction;
  all 46 affected tests passed afterward. Separate read-only review verified
  the final correction, including recovery to a later valid revision without
  changing earlier decision-time results. Authentic raw publisher collection
  and component deployment remain pending, not satisfied by fixture tests.

- W2 interrupted-publication recovery now has `resume_bls_capture` and
  `scripts/bls_capture.py --resume`. Exact retained-input retries complete only
  missing metadata/journal artifacts; existing metadata conflicts fail and
  missing raw refuses without creating a store. Astra replaced direct final-
  file writes with flushed staging plus exclusive atomic hard-link publication,
  and made directory-sync failures visible. Independent read-only reviews
  passed both publication and recovery changes. Forty-two related tests and
  governance validation passed. Failure injection is engineering evidence,
  not a physical power-loss or deployed-service demonstration. Late capture
  isolation, source qualification and scheduled collection remain outstanding;
  no market or trading settings changed.

- W2 local capture/storage integration is implemented in
  `event_capture_store.py`, `scripts/bls_capture.py` and `event_context.py
  `--store`. Original UTF-8 bytes, metadata and journal generations are
  published without replacement; annotation reads verify retained data.
  Astra repaired raw/parser binding, missing published capture detection,
  generation-prefix consistency, symlink ancestors, ambiguous JSON and
  fractional-second ordering. Focused filesystem/process/CLI tests and the
  full repository suite passed; governance and diff checks passed. Separate
  read-only review verified the repairs, including unpublished-generation
  recovery with fractional timestamps (21 combined store/CLI tests). The storage
  boundary is POSIX/trusted-local-owner, not a deployed collection service.
  Incomplete writes and late captures stay explicit recovery conditions;
  source input bytes are not repaired or overwritten. Recovery policy and
  source-qualified scheduled collection remain necessary before unattended
  publisher operation. No M1 listener, broker or remote database was changed.

- W3 preparation worker now joins timed lifecycle evaluation and durable intent
  persistence without claiming or routing orders. Astra repaired a store/runtime
  registry mismatch and ensured earlier account intents remain visible after
  terminal/configuration changes. Thirteen focused tests passed; separate
  read-only verification confirmed both repairs. These latest worker checks
  use a database double, not a new remote or PostgreSQL demonstration.
- W2 event revision journal now retains normalized capture content and parser
  quarantines. Astra repaired dropped daylight-saving fold information,
  cross-source disappearance tracking and insufficient revision/capture lineage
  validation. Independent review passed, including adversarial rehashed-but-
  inconsistent records and decision-cutoff checks. This is internally checked
  retained data, not authenticated publisher history or durable storage.
- The retained BLS context CLI's raw-byte hash and explicit caller-supplied
  capture provenance passed independent review. No remote job was installed.
- Deployment inspection identified fixed M20 listener and GDELT workflow paths,
  neither already hosts these new components. Next: implement the separate
  read-only capture/retention/job integration under the owner-directed goal,
  accounting for its actual source and release requirements. Absence of an
  existing job is an implementation gap, not a global market dependency.

Pending work includes publisher collection and durable retention, H_SLOW
pending-plan expiry/supersession, actual routing/protection/monitoring and
deployment integration. Submission remains disabled. Formal milestones and
their evidence requirements are unchanged.

The attached owner-directed goal has initiated parallel W2/W3 implementation.
All market-dependent milestones and their content remain preserved for Monday
resumption after checking the actual required broker surface.

- W2 retained replay: Terra implemented `src/forex/m20_replay_report.py` and
  `scripts/m20_replay_report.py`. Local retained snapshot/proposal/outcome pairs
  now produce classifications, cost coverage, per-record errors and explicit
  duplicate exclusions. Astra added strict duplicate-key/nonfinite JSON
  rejection. Input bytes are hashed and preserved; declared provenance remains
  unverified. This does not yet compare every historical execution field or
  establish policy performance.
- W2 now has `scripts/m20_replay_batch_report.py`, a read-only inventory for
  direct retained operation records. It preserves per-source SHA-256 and
  refusal reasons, rejects unsafe symlinked run paths, and deliberately does
  not aggregate money across unreconciled sources. Its first complete local
  inventory found 20 source records: 16 reportable/replayable pairs, nine
  valid classifications, seven older-schema classification errors, and four
  non-JSON T480 stdout refusals. No linked broker outcome is retained, so no
  cost or profitability conclusion is available. This makes the imported
  data's limits visible; it neither repairs raw captures nor changes broker,
  listener, M29 or execution state.
- M1's local spool exporter now recovers a completed matching cursor staging
  record left by an interrupted local atomic publication, and fsyncs the
  cursor directory after replacement. A partial, conflicting or symlinked
  staging file still refuses the pass for investigation. This changes only
  local post-retention cursor recovery; source records remain immutable and
  unacknowledged on Windows, and no listener/broker/order surface changed.
- The paged spool exporter now also accepts a later first source sequence when
  no local cursor exists, matching the immutable-spool reader's explicit
  baseline rule. It still requires every subsequent source record to be
  contiguous from the local cursor. This prevents a valid release-namespaced
  spool that begins after its earliest assessments from being rejected, without
  permitting a gap after retention has started.
- W2 also has a strict read-only MT5 history reporter,
  `scripts/m20_history_report.py`. Its retained 2026-09-10 Demo history source
  has an earlier 08:44Z capture with 15 paired closes and AUD -3.19 net, and a
  later 09:29Z capture with 19 paired closes, AUD -4.10 net, 15 losses, two
  wins, two flats and eight stop-loss-like exits. Reported commission, fee and
  swap fields are each AUD 0.00 in both captures. This is an imported
  historical observation, not a decision linkage, full cost/tariff proof,
  current account state or a profitability conclusion. No automatic
  strategy/risk change follows it.
- A fresh fixed read-only all-Demo-history operation at 16:55 NZST observed
  123 account rows; after excluding three Demo deposit rows, the M20 EURUSD
  scope had 120 deals / 60 paired closed positions, AUD -10.41 net, 45 losses,
  11 wins, four flats and 16 stop-loss-like exits. The all-history reader now
  accepts only its separate named schema and excludes non-M20 rows before
  applying tradable-position checks. Its exact raw response, report and
  receipt are immutably retained under ignored local operator storage at
  `runs/local/m20-history-captures/m20-all-history-d66933f404af3574/`; this is
  not an M29 proof bundle, a retained-source replacement, a complete cost
  finding or an automatic strategy/risk-change trigger.
- W2 operational monitoring's daily all-history retention units were rendered,
  passed `systemd-analyze --user verify`, and were linked into Piwakawaka's
  authorised user manager on September 12. The enabled timer runs at 17:05
  host-local with no catch-up; its reviewed one-shot is confined to the
  existing fixed read-only all-Demo-history capture command, with no order,
  listener-control or configuration surface. Its first natural run at 17:05:02
  NZST succeeded in seven seconds and immutably retained response/report/
  receipt `m20-all-history-3e90ed5cdaf6b430`. Rebuilding the report and
  independently checking receipt hashes both passed. This improves future
  Demo outcome retention only; it does not provide M29 proof or cause
  automatic strategy/risk changes.
- W2 event integration: `scripts/event_context.py` connects retained JSON
  metadata through qualification and annotation into one report. Astra repaired
  revision coercion, missing identity/provenance, order-dependent duplicate
  versions and fallback to stale schedules after unusable newer revisions.
  Separate read-only review verified temporal behaviour and the fixes.
  [Usage](../event-context-command.md). Publisher collection, complete coverage
  and attachment to operating records remain to implement.
- W3 lifecycle: Terra implemented `src/forex/h_slow_lifecycle.py`, with
  unknown/pending attempts preventing further intent, foreign-ticket refusal,
  same-direction holding and close-before-reopen planning. Astra bound intent
  IDs to isolation configuration; separate read-only review passed. This is a
  pure planner over supplied observations. Durable state, observation clocks,
  actual reconciliation, sizing/protection, routing and deployment remain
  required before operational use.

Next independent packages: integrate durable H_SLOW intent/state and observation
timing; connect retained-data reports to real retained export shapes; implement
the source-qualified event publisher path. Keep account/holding activation and
market proof pending separately. No remote deployment or new orders occurred
in this checkpoint; these runnable local components are implementation progress.

### Subsequent runtime and retained-data integration

- H_SLOW observation timing is implemented in `src/forex/h_slow_runtime.py`
  and runnable through `scripts/h_slow_runtime.py`. It validates an explicit
  maximum age, acquisition/receipt/evaluation ordering and monthly target
  expiry. Unknown reconciliation stays WAIT. Separate review passed; tests
  cover boundary age, expiry and actual command execution.
- H_SLOW persistence now has SQL and a Python connection-factory adapter.
  Astra corrected the planner/store intent-hash mismatch, added account-wide
  unresolved-claim serialization, and fixed SQL's null-direction loophole.
  Terra independently verified these fixes on a disposable PostgreSQL 17.6
  database, including the real planner-to-Python-adapter path. The reproducible
  opt-in integration test is `tests/integration/test_h_slow_postgres.py`;
  [results and limits](../reviews/h-slow-postgres-integration.md).
  Test containers were removed; no deployed database was migrated.
- H_SLOW now also has a fail-closed durable-worker command wrapper at
  `scripts/h_slow_worker.py`. It reads one retained runtime input and only an
  explicitly named local `FOREX_H_SLOW_*` DSN environment variable, refusing
  invalid input/name before importing a database driver. It exposes no DSN
  argument, database discovery, MT5, claim or order route; a successful
  result must remain `DISABLED_NOT_ROUTED`. This makes the reviewed durable
  preparation path deployable once a human selects the isolated store, but it
  does not migrate a database, select an account or activate H_SLOW.
- `scripts/m20_replay_report.py --retained-export` now consumes actual retained
  operation/lifecycle/lineage exports. Independent review passed. The retained
  `runs/evidence/M20/20260911T094157Z/demo-trading-operation.json` yielded one
  valid replay pair; its lifecycle summary retained 70 coverage-only rows.
  Missing snapshot bodies remain missing. Nested JSON ambiguity is rejected.

Next integration: official publisher parsing and capture; a configured H_SLOW
worker joining timed observations and durable state; sizing/protection and
approved routing. Database verification establishes local persistence behaviour,
not deployed trading or M29 proof. Market-dependent milestone work remains
paused for Monday, with original requirements preserved.

- BLS CPI/Employment Situation parsing is implemented in
  `src/forex/bls_events.py` against the inspected three-column schedule shape.
  Astra corrected timezone detection so script text, negated wording and
  fixed Eastern Standard Time wording cannot silently select seasonal New York
  time. Missing supported timezone declarations remain DATE_ONLY. The parser
  hashes UTF-8 text; raw-response-byte retention is still a separate requirement.
  BLS raw downloads returned 403 during inspection, so authentic raw HTML
  verification, first-seen/revision persistence and scheduled collection remain
  pending. The parser fixture is not a live-source evidence claim.

### Subsequent BLS operational evidence

- The preceding pre-deployment statements are superseded by the current
  Piwakawaka user-service observation. The enabled hourly BLS timer completed
  its 17:00 NZST pass on 2026-09-12 with two fixed shared-T480 HTTP 200
  captures (September and October 2026), immutable transport/acquisition/raw
  HTML/metadata/journal artifacts, and empty parser-quarantine lists. The
  rendered units remain limited to annotation-only, read-only public-calendar
  collection; M1's enabled annotation service consumes that same retained
  store and retains context-only sidecars. `config/event_sources.json` now
  accurately records `DEPLOYED_RAW_CAPTURE_ACTIVE` while retaining
  `coverage_status: UNKNOWN`. These narrow current captures neither establish
  historic publisher availability nor complete calendar coverage, M29 proof,
  trading eligibility, a calendar veto, or any order authority.

## Historical W1–W3 scheduling rule — superseded

The following describes the retained W1–W3 scheduling model. It is historical
context only and must not select current work. Formal milestone status and that
former autonomous-delivery sequencing were deliberately
separate. `M29` remains formally **BLOCKED** until its declared external proof
and contract decision are resolved; it is not skipped, waived or represented
as proven. That condition parks only work that depends on M29 evidence. It
does **not** park market-independent Wave 2/3 research, data qualification,
policy, isolation, reporting or deployment-preparation packages. Its retained
queue and selector do not select the active Harness/A/B/C sequence. Use only
the active task source and `delivery_harness_status.py` command above.

## Delivery queue

| Package | Wave / ownership | State | Next action / acceptance |
| --- | --- | --- | --- |
| M29 recovery-verifier hardening | W1 reliability / active M29-C2–C4; Terra implements, Astra reviews | PARKED_EXTERNAL_PROOF; closeout intentionally refused | Capture preserves only an `UNSUPPORTED` read-only observation and exits nonzero. Verifier binds, validates and then refuses it because collector lifecycle/outage/restart/durable-dedup proof does not exist. Focused negative-bundle tests passed; the separate read-only check accepted Astra's canonical-marker correction. A declared durable collector surface remains required. No broker mutations. |
| Governed tick-offset repair | W1 reliability / affected M27–M29 prerequisites; existing uncommitted work | IMPLEMENTED; independent review passed 2026-09-12 (focused M20 adapter/evidence tests and compilation) | Verify broker clock convention independently, then capture fresh proof only when a current quote is available. The offset is never inferred by making a stale tick appear fresh. |
| M1 receipt-time binding | W1 reliability / current M20 evidence path and offline replay | REVIEWED; deployment/proof pending | The offline adapter accepts only the two exact deployed snapshot schemas (base, or base plus paired financing/holding records), recomputes a canonical body SHA-256, and requires matching non-empty proposal ID, snapshot ID and proposal digest before it supplies the later receipt time to the classifier. Modified retained data, partial/unknown schema and unbound proposals fail closed. This prevents replay from treating receipt-time M1 availability as invalid merely because it follows the earlier broker tick. Focused adapter/M20 evidence/kernel tests, full test suite, compilation, governance validation and two independent read-only review loops passed. It is pure/read-only and does not alter the listener or prove M20. |
| Triad review runner containment | W1 evidence/review reliability; Astra Loop-2 repair | IMPLEMENTED and tested, fresh M20 review pending | The runner now creates a clean archive snapshot at the bound revision, copies only manifest-listed hash-verified evidence and current governed state, constrains reviewer inputs and preserves raw attempt output as hashed artifacts. Focused tests cover snapshot isolation, unlisted-artifact exclusion, tamper refusal and failure retention. A new bound M20 review requires a clean matching release and fresh evidence. |
| Remaining M1 reliability and recovery | W1 / map exact outstanding criteria from current handover | PARKED_EXTERNAL_OBSERVATION after delivery audit 2026-09-12 | The immutable spool/page exporter and its local recovery paths are deployed and tested. Resume only when a natural fresh listener assessment and broker-surface revalidation are available; do not restart a healthy listener to manufacture either. |
| M29 durable-recovery contract mapping | W1 / active M29 planning | REVIEWED draft; human contract decision pending | The exact [contract/capture amendment draft](M29-contract-amendment-draft.md) maps the current held-only worker-handoff and reboot surfaces to every criterion. It shows that neither proves broker outage nor durable deduplication, so those terms need a new collector or removal from a bounded amended claim. This produces no proof and does not touch the listener. |
| Reusable economic-event annotations and required costs/data | W2 / annotation kernel | REVIEWED; no trading authority | A pure decision-time annotation layer now binds an unchanged qualified-event result, retains source/revision/availability and quarantines, and reports coverage as `UNKNOWN`. It returns context only—never allow/block/direction. The Wave 2 report now records this and the H_SLOW point-in-time input boundary. Publisher ingestion and a qualified coverage snapshot remain separate work. |
| One H_SLOW policy and stream isolation | W3.1 / policy kernel implemented; account isolation pending | REVIEWED; disabled durable preparation available | Disabled pure EUR/USD 12-month monthly trend policy now rejects look-ahead, unavailable, nonchronological, incomplete and missing month-end-session input. Focused tests and separate read-only review passed. Its durable worker command is submission-disabled and requires an explicitly selected local store. Explicit Demo account/terminal, limits, protection, holding and state isolation remain pending authority. |
| H_SLOW point-in-time D1 adapter | W2.2/W3.1 / historical-replay input boundary | REVIEWED; research-only | A pure adapter now converts only a validated EUR/USD D1 snapshot at its exact decision cutoff into explicit closed/available daily policy inputs, bound to the snapshot hash. Focused tests—including malformed D1 timing—and separate read-only review passed. This adds no feed, retained quote surface or execution authority. |
| H_SLOW research decision record | W3.1 / point-in-time policy evaluation | REVIEWED; research-only | One deterministic record now binds the snapshot hash, adapter-input hash and frozen policy target. A matching digest-verified annotation-only event context may be attached without changing the target; a separate review also confirmed no caller mutation can alter an attached target. `BUY`/`SELL` remain research targets and the record exposes no execution authority. |
| Declarative two-stream isolation | W3.1 / account-scope and ownership kernel | REVIEWED; disabled | A pure closed-schema registry now validates separate opaque Demo scope, terminal and state/monitor/lease/reservation/outcome namespaces; it also rejects collisions inside either stream. Focused tests and a separate read-only review of Astra's correction passed. It will not select an account or add execution authority. |
| H_SLOW activation contract | W3.2 / human-owned activation decisions | REVIEWED pre-activation validator; explicitly inactive | The [human-completion template](../../Research/experiments/h_slow_eurusd_tsmom_12m_v1/demo-activation-contract-draft.md) enumerates account/terminal, aggregate limits, protection, holding, costs, monitoring, evidence and review decisions. A pure validator can check a completed opaque mandate and separate risk-resume approval reference against stream isolation while refusing `ACTIVE`, Live, scope drift, injected authority and a second position. Focused tests and separate read-only reviews passed. No placeholder or validation result is authority. |
| Two-stream Demo activation and observation | W3.2–W3.3 / exact Demo mandate required | PARKED_HUMAN_MANDATE | Account/terminal selection, approved limits/holds, operational checks, actual fills/reconciliation and stream-isolation evidence. No profitability prerequisite. Other Wave 2/3 preparation remains eligible while this is parked. |

## External proof and authority dependencies

- M27/M28 remain NEEDS_REVALIDATION; M29 remains BLOCKED in formal state.
  A market pause blocks fresh-market proof, not the independent queue above.
- M20 remains HUMAN_REVALIDATION_EXCEPTION, not PROVEN. Existing lifecycle,
  continuity and charge proof gaps must not disappear from final reporting.
- Longer-hold account/terminal and exact risk/holding mandate are not selected
  by this goal. Do not pick a saved account or increase the current position
  cap. Prepare deployment-ready code without enabling unspecified authority.
- No commit/push/branch/PR permission is added. Where proof needs a clean bound
  release, preserve changes and identify the required human action.

## Review and resumption

Terra owns bounded Loop-1 implementation. Astra reviews and personally fixes
unresolved defects. A separate read-only review checks Astra's material fixes.
Formal reviews/sign-off remain distinct from development acceptance.

After each package, record changed paths, behavioral test commands/results,
review disposition and the next independent task. Resume market-dependent
capture only when fresh required data and the exact safe surface are available.
No forced orders, risk resets, invented proof or repeated AI market polling.
Keep IMPLEMENTED / TESTED / REVIEWED / DEPLOYED / PROVEN states separate.

### Delivery audit — 2026-09-12 17:16 NZST

The independent delivery audit found all authorised non-trading components
implemented, tested and deployed where their own local operational
requirements were satisfied: BLS collection, M1 event annotation, M20 paged
assessment retention and daily all-history retention. The final local M1 spool
recovery fixes were verified by the full suite. The queue now exposes no
artificial ready package: remaining M1 work needs a natural fresh assessment
and broker-surface revalidation; M29 needs its separate recovery observation;
H_SLOW activation needs the exact human account/limits/holding mandate. Those
are distinct external dependencies, not waived milestones or reasons to alter
the M1 listener, account routing, risk limits or order authority.

### Exporter observability repair — 2026-09-13

Two transient read-only spool-export passes on September 12 exited nonzero and
later scheduled passes recovered to `SPOOL_ABSENT`; no source cursor/staging
artifact remained. The export wrapper now emits a structured non-secret error
classification to the user-service journal (`FIXED_OPERATION_TIMEOUT`,
`FIXED_OPERATION_NONZERO`, `LOCAL_CURSOR_REFUSED`, or
`PAGE_OR_LOCAL_RETENTION_REFUSED`) instead of an undifferentiated refusal.
It never logs the broker response bytes. This repair changes diagnostic output
only, not the fixed operation, listener, source-spool retention, trading or
formal M29 evidence state.

### Critical-wave implementation handover — 2026-09-13

- **W1:** the durable recovery collector, exact MT5/M1 reconciliation baseline
  and declarative operating schedule/service register are implemented, tested
  and Astra-reviewed.  They are non-trading and do not substitute for M29's
  fresh recovery drill.
- **W2:** primary BLS/FOMC/ECB source coverage, point-in-time context and the
  disabled M1 risk-gate preparation are implemented and reviewed.  The official
  FOMC and ECB calendar patterns presently expose dates but not declared
  intraday decision times, so retained observations are quarantined with
  `UNKNOWN` coverage.  Source qualification and an enabled gate therefore
  remain unavailable by design.
- **W3:** the H_SLOW strategy/lifecycle, event-context refusal boundary,
  combined-exposure report and local readiness command are implemented and
  reviewed.  A directional preparation remains submission-disabled and refuses
  the current unavailable primary context.  Activation remains human-mandate
  dependent.

The read-only queue selector now returns
`FOREX_AUTONOMOUS_DELIVERY_QUEUE_NO_SAFE_PACKAGE`: every uncompleted critical
package requires either a real fresh Demo/external observation or Chris's
exact H_SLOW activation mandate.  This is a delivery-state record, not a
milestone closeout, deployment assertion, profitability claim or authority
change.

### W2 canonical calendar PostgreSQL projection — 2026-09-13

The prepared calendar projection stores every validated structured calendar
fact in PostgreSQL with its publisher family/URL, capture timestamp, raw and
receipt digests, event identity/time/title, optional country/currency/impact,
qualification state/reason and source revision.  Immutable publisher bytes and
receipts remain the hash-bound evidence source; the database is the canonical
queryable record, not a replacement for that evidence.  The narrow adapter
uses one parameterized idempotent insert keyed by a digest of the complete
fact.  Consequently a later qualification or quarantine conclusion can be
recorded even where the publisher bytes did not change.

The package is implementation-tested and independently read-only reviewed,
but is **not deployed**: the SQL file is intentionally manual and no collector
has been given database credentials, a migration action, event-gate authority,
MT5 access, or order authority.  The next safe W2 package is to bind retained
calendar records to this projection after the approved schema migration path
is available.
