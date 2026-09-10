# W1.R work package: T480 reliability and recovery

Prepared 7 September; plan alignment updated 10 September 2026. **Current W1
recovery specification; execution status comes from the current handover and
bound evidence.** This update does not restart or deploy anything.

The original request packaged reviewed fixes; later work and approvals must be
read from the current handover rather than inferred from this original plan.
This package schedules remediation within [Wave 1](demo-income-wave-1.md) and
its W1.1–W1.4 acceptance criteria. Read the [shared guide](demo-income-waves.md)
and [Wave 1 report](../milestones/demo-income-wave-1-report.md) with it.
It neither starts a goal nor amends a milestone contract or runtime policy.

## Mission and ownership

Restore trustworthy Demo operation through connectivity and shared-service
interruptions, with explicit exposure, correct accounting and persistent risk
limits. This reduces avoidable losses, operator intervention and repeated AI
diagnosis. It does not establish a profitable strategy.

Forex owns listener behaviour, broker reconciliation, application status and
Wave 1 proof. `cs-ai-lab-infra` owns shared Windows/WSL startup, Docker,
PostgreSQL service availability and shared transport. Inspect the current
checkout and deployed state of both repositories before dependent work:

- Forex: `/home/chris/projects/forex`.
- Shared platform: `/home/chris/projects/cs-ai-lab-infra`.
- Forex transport dependency: the pinned checkout declared in `config/t480.json`.

Lab development is concurrent. A local commit does not prove deployment or
causation. Keep shared-platform changes in the owner repository; coordinate
one maintenance window and one writer per affected service. Do not roll back
another worker's changes or blindly update Forex's passing dependency pin.

The lab has its own recovery Wave 1 and M5 startup work. W1.R consumes the
specific capabilities needed by Forex; it does not execute or close those
entire milestones. In particular, R5's no-logon boot test is a proposed shared
dependency. Check both contracts and existing explicit approvals before its
implementation; prepare any exact missing amendment rather than silently
expanding M20. These documents alone grant no cross-repository deployment or
host-reboot authority.

## Review baseline to revalidate

These are findings from the preceding review, not a new captured proof bundle
or a statement of current host state:

- On 7 September, retained output from the lab runtime diagnostic showed a
  PostgreSQL shutdown at 15:47:10 NZST and readiness at 17:39:15 NZST. Windows
  uptime dated from 3 September. The initiating actor/cause was not established.
- SSH timed out intermittently. At 17:54 NZST, a later Forex status read
  succeeded with a fresh heartbeat and successful empty durable recovery.
  Neither a timeout nor an empty recovery list proves the broker account flat.
- A local fault-injection probe of `_monitor_update()` reproduced a per-position
  `RECOVERY_FAILED` result being classified as `IDLE` when process exit was zero.
- `_m20_demo_account_liquidity_command()` used `positions_get() or ()`, masking
  missing position data as zero positions. Missing protection in the status
  surface also must not be described as confirmed absence.
- The deployed shared startup task used interactive sign-in; the Forex installer
  also created a sign-in trigger. No-logon recovery was not demonstrated.
- Forex's pinned transport revision and hashes passed. The remote lab checkout
  was clean at `98e09c4`; local lab recovery work reached `0e4de43` during the
  review. No evidence attributed the earlier shutdown to that new commit.

Starting references: `t480/m20_demo_listener_service.py` (`_monitor_update`),
`t480/m20_demo_trading_session.py` (`recover_open_positions`),
`scripts/t480_adapter.py` (liquidity/status/install operations),
`tests/milestones/test_m20_listener_service.py`, and the lab's
`docs/wave-execution-status.md`, `scripts/t480_adapter.py` and startup contract.

## Fix schedule and dependencies

This is a dependency schedule, not a calendar forecast. No `target_date` or
completion timestamp is assigned. Preserve the actual status of each activity
from its handover/evidence; the table defines dependencies, not a status reset.

| Stage | Activities and owner | Dependency / exit condition | Wave mapping |
| --- | --- | --- | --- |
| A — Diagnose | R1, shared platform with Forex observations | Current incident baseline and actionable failure boundaries recorded; missing logs explicit. R2/R3 can proceed locally while remote diagnosis is unavailable. | W1.1, W1.2, W1.4 |
| B — Correct state | R2 and R3, Forex | Existing behaviour reproduced; focused behavioural checks pass for recovery failure, unknown exposure and successful recovery. | W1.2, W1.4 |
| C — Control deployment | R4, both owners; implement R6, Forex | One reviewed maintenance plan, entry hold, protection and rollback arrangements. R2/R3 and incident recording deployed only under applicable authority. | W1.1, W1.2, W1.4 |
| D — Prove recovery | R5, shared platform plus Forex; demonstrate R6 | Stages A–C ready; exact drill scope authorised. Detached-T16 test and separate flat-account reboot test meet the predeclared conditions. | W1.1, W1.2, W1.4; proposed platform dependency |
| E — Finish evidence | R7, Forex and required read-only review roles | Applicable R1–R6 acceptance and dependency gates satisfied; final implementation/configuration frozen; remaining genuine broker observations available. | W1.1–W1.4 |

Recommendation: complete R1–R4's diagnosis, code and maintenance prerequisites
before broader Wave 1 execution resumes. Their completion is not a substitute
for R5–R7. Missing platform authority blocks only dependent operations; finish
independent authorised work and hand over the precise dependency.

The 10 September W1.4 risk-latch repair joins Stage B and must be included
before final Stage C deployment and Stage E proof. Verify overlapping pause,
recovery and rollover cases as specified in [Wave 1](demo-income-wave-1.md).
Do not repeat successful R1–R4 work or infer current faults from old logs.

## R1 — Diagnose shared-service and connection interruptions

**Change / why:** Correlate bounded Windows power/session/network and OpenSSH
events, WSL/Docker starts/stops, PostgreSQL logs, MT5 authorisation errors and
Forex timestamps. Separate T16 control-path failure, shared database failure
and broker-terminal failure so a healthy component is not restarted blindly.
Use existing fixed read-only diagnostics; add a narrow fixed diagnostic only
if needed and within the owning contract.

**Success:** A timestamped incident timeline distinguishes observed facts from
inference, identifies affected layers and a supported corrective action. If
historic logs cannot establish the original cause, record it as unknown and
identify the exact diagnostic gap; do not invent attribution. R1 can finish
that diagnostic disposition, but required recovery proof remains pending.

**Real-world test / evidence:** Read the declared T480 surfaces and correlate
service/host lifetimes with failures. Retain raw responses, exit codes and
times; independently check the timeline. Where a historic cause is unprovable,
use the later approved recovery drill to demonstrate handling of the observed
failure class, not to claim the historic cause was proven.

**Failure / safety:** Unreachable host or missing logs means unavailable or
inconclusive evidence, not proof of shutdown or flat exposure. No speculative
restart, credential reset, firewall change or lease replacement.

## R2 — Propagate every recovery failure

**Change / why:** Validate the recovery response, marker and each position
result. Any failed, malformed or unresolved row must prevent healthy `IDLE`
reporting and keep new entries blocked. Successfully managed positions must
still receive protection when another row fails.

**Success:** `RECOVERY_FAILED`, malformed JSON, an unexpected response shape
and mixed successful/failed rows cannot become a healthy monitor merely
because process exit is zero. Genuine empty recovery and successfully monitored
positions retain distinct valid states. Retry does not duplicate an order or
discard durable exposure.

**Real-world test / evidence:** First retain local behavioural fault-injection
results for those cases. Then, on the approved Demo surface, capture a bounded
recovery failure and restoration with broker/application state comparison.
Use a protected position for the listener-only recovery drill under R4; verify
the same ticket and SL/TP remain accounted for. Local injection alone cannot
satisfy this broker proof.

**Failure / safety:** Any false healthy state, new entry during unresolved
recovery or lost position record fails. Preserve the durable row and the entry
hold; never manufacture a terminal close to clear the gate.

## R3 — Report unknown exposure truthfully

**Change / why:** Remove missing-data-to-zero conversions in the liquidity
helper and status displays. Separate observed broker exposure from durable
tracked exposure, and fresh protection from last-known protection. Include
observation time and failure status without leaking account credentials.

**Success:** A failed position query reports unknown, not zero; unavailable
protection is not described as no position. Unknown required equity/exposure
blocks entries while existing management continues. A true empty result is
accepted only after a successful appropriately scoped broker query, with any
discrepancy against durable attempts still unresolved.

**Real-world test / evidence:** Retain failed-read and restored-read outputs
during the approved connection drill. Compare the restored broker positions
and deals with the durable ledger and dashboard. Demonstrate that missing
observations neither clear exposure nor authorise another order; keep local
fault-injection coverage separate.

**Failure / safety:** A null result displayed as flat, or a stale protection
record presented as current, fails. Do not run competing MT5 API clients simply
to obtain diagnostics; use the deployed serialised path or a controlled hold.

## R4 — Coordinate maintenance and deployment

**Change / why:** Use one small maintenance record covering affected services,
owner, window, exact changes, deployed revisions/hashes, entry hold, existing
positions, persistent risk state, recovery checks and rollback. Ensure the
hold survives the planned interruption. Use existing mechanisms where adequate;
do not create a general orchestration platform.

**Success:** Maintenance blocks new entries independently of its protective
monitor. Host/WSL/database disruption begins only when successful broker and
audit checks confirm flat exposure and no unresolved execution. The separate
listener-only restart with an open position preserves broker protection.
Restoration retains the same lease, counters, baseline and risk anchors,
allowing only broker-reconciled P&L and legitimate policy-boundary transitions.
**Operator amendment, 2026-09-10:** Backup and isolated-restore evidence is
deferred to W4.0, before any funded pilot. Missing backup evidence does not
block Wave 1 Demo deployment, migration 022 or otherwise authorised recovery
drills. Prioritise core Demo functionality. Retain the existing entry hold,
fresh broker/audit checks, transaction-safe migrations, unchanged ledger/risk
anchors and the previous reviewed code/configuration. Do not reset state or
restore an old ledger to manufacture proof. Shared backup implementation
remains owned by `cs-ai-lab-infra`; it is not part of this Wave 1 execution.

**Real-world test / evidence:** Capture before/after hold, broker, ledger and
risk state for an approved maintenance window. Show zero new entries under
the hold, successful recovery and independent reconciliation before release.
Keep any independent Option B pause active; ending maintenance must not clear it.

**Failure / safety:** If current exposure is unknown, postpone disruptive
maintenance. Restore the last reviewed compatible configuration/task if needed;
do not erase logs, restore an old database over the audit ledger or reset risk
anchors. If rollback would restore the known false-healthy defect, retain the
entry hold and use a reviewed forward correction.

## R5 — Prove T480 continuity and unattended recovery

**Change / why:** Resolve the lab's SYSTEM-versus-S4U design discrepancy against
the current contract. Validate access to the existing WSL distribution, local
DSN, MT5 Demo terminal and protected settings under the intended account before
changing startup. Ensure Forex can recover when dependencies become ready;
do not assume a registered boot task proves this.

**Success:** Demonstrate two distinct capabilities: ordinary Demo operation
with T16 disconnected, and recovery after a host reboot without Windows sign-in.
Keep startup narrow; no new infrastructure platform or complete lab rebuild.

**Real-world test / evidence:** Proposed acceptance window for scheduling is
30 minutes with T16 disconnected during an active market, using T480-local
records. Separately, with exposure confirmed flat and the maintenance entry
hold active, perform the approved reboot. Confirm WSL/PostgreSQL, MT5 Demo
identity and Forex recovery without sign-in; then retain 30 minutes of local
operation. Proposed recovery target is five minutes from Windows boot to all
required dependencies and Forex recovery being healthy. Record/agree these
test bounds before the drill; they are not a production SLA or new risk limits.

After checks pass, any release of the maintenance hold follows R4 and existing
Demo authority. Neither test requires a trade quota. A later genuine protected
listener restart remains necessary for W1.4; a flat reboot cannot replace it.

**Failure / safety:** Needing T16, sign-in, manual service start, changed broker
identity or reset risk state fails the corresponding continuity claim. Keep
the unmet platform dependency explicit. Do not switch principals blindly or
weaken secret protection to make the test pass.

## R6 — Retain incidents and deliver bounded alerts

**Change / why:** Add small T480-local records for failure/recovery transitions
and notification delivery, using the existing status and SuccessByCS Discord
integration. Include last successful observation, component, error, release,
time and exposure certainty. Deduplicate and bound retry/storage behaviour;
keep configurable non-secret values canonical and secrets machine-local.

**Success:** One incident and its recovery can be reconstructed without
continuous AI polling. Notification success, failure and pending delivery are
distinct. Delivery cannot block protective management. A configured webhook is
not represented as delivered proof.

**Real-world test / evidence:** During the R2/R3 or R5 drill, retain the incident
record and an actual operator-channel alert plus recovery notification. During
loss of external connectivity, preserve pending/failed delivery and show a
bounded retry after recovery without flooding. Mark drill messages as drills;
they do not prove a real BUY/SELL event.

**Failure / safety:** Lost incident records, duplicated alert storms or stalled
protection fail. A powered-off/disconnected T480 cannot notify immediately;
state that limit. Do not introduce an always-online external watcher as an
implicit requirement for this package.

## R7 — Stabilise the release and finish original Wave 1 proof

**Change / why:** Freeze one reviewed implementation/configuration after the
fixes, then assemble the final W1.1–W1.4 evidence and independent verification.
Use a clean checkout of the declared revision without discarding unrelated
work. Documentation updates must not cause automatic deployments/restarts;
respect the verifier's exact revision requirements and plan provenance once.

**Success / real-world test:**

- **W1.1:** Read back effective approved limits, application revision, payload
  hashes and governed configuration; independently compare them with the
  canonical artefacts, including `maximum_trades: null`.
- **W1.2:** Retain a genuine Demo OPENED-to-CLOSED lifecycle, exact broker
  identifiers/volumes and controlled interruption/recovery without duplicate
  execution. Record partial-fill proof if observed; otherwise retain that
  explicit observation gap and separate behavioural coverage.
- **W1.3:** Before selecting outcomes, declare the sample window, inclusion
  rule and rounding tolerance (proposed AUD 0.01 per outcome and aggregate,
  with the rounding method recorded). Recompute every included outcome and
  the aggregate from raw attributable broker deals, including commission,
  fees and swap; keep execution estimates separate. Include nonzero charges
  when available; zero-charge rows do not establish nonzero-fee proof.
- **W1.4:** Retain risk state before/after a listener restart with an actually
  open protected Demo position. Demonstrate an actual deployed entry refusal
  under the previously approved temporary AUD 0.01 planned-loss cap, then
  restore Option B immediately. The earlier calculation-only refusal probe
  is supporting evidence, not proof of the complete listener refusal path.
  Independently test all overlapping pause reasons against the real function
  and isolated persistent integration state, including recovery/rollover.
  Preserve manual latches through maintenance and restart. Synthetic equity
  inputs are engineering fixtures, never fabricated broker evidence.

Preserve Option B: lesser of AUD 100 and 0.10% policy equity per trade; daily
0.50%, weekly 1.00%, peak adjusted-equity drawdown 2.00%; existing Auckland
boundaries and durable resume rules; one position, USD 10,000 per trade and
USD 100,000 cumulative notional. Keep the continuous lease and unlimited
development trade count. Do not renew a lease to bypass its cumulative cap.
Reuse the operator's no-external-cash-flow confirmation for the specific
AUD -0.29 close; it is not approval for unrelated later balance differences.

**Failure / safety:** Missing raw observations, failed comparisons, material
revision/configuration drift or unresolved critical defects remain FAIL or
PENDING. No forced trades, intentional losses, strategy tuning or live access.
Revalidate the fixed capture command before use: it can execute a Demo session,
so it is not a read-only exporter and must not compete with the listener.

## Evidence, review and handover

At execution, use separate immutable raw and verification locations, for example
`runs/evidence/M20/w1-recovery-<UTC>/` and
`runs/verification/M20/w1-recovery-<UTC>/`. Bind contract, relevant repository
revisions, deployed hashes, effective configuration, verifier identity and
timestamps. Retain independent verification of both engineering drills and
the required broker observations; neither substitutes for the other.

Update the existing Wave 1 report with R1–R7 status, W1.1–W1.4 status, observed
failure, exact change, source references, test/evidence references, unresolved
dependency and resumption condition. Preserve earlier entries as history;
correct unsupported claims explicitly rather than rewriting raw evidence.

The package is complete only when its approved activities and dependencies
are demonstrated. W1.1–W1.4 remain the original Wave 1 acceptance criteria;
this package cannot waive them. Any unapproved scope addition remains a
proposal, not an inferred requirement or permission. Milestone closeout still
requires the whole current M20 contract and bound Triad-plus-domain
`RECOMMEND_COMPLETE`; this package does not close M20 or start another wave.

## Execution entry point — saved, not invoked

After explicit execution instruction, use the updated
[Wave 1 resume prompt](demo-income-wave-1-resume-goal.md), which incorporates
this package. Reuse existing approvals and request only missing decisions for
dependent operations. Respect the supplied budget, reserve the handover, and
do not treat an absent recorded cap as unlimited execution authority. Do not
keep AI polling while ordinary authorised Demo collection waits for evidence.

Wave 3 retains extended operator-effort and economic evaluation. Reuse current
W1.R evidence there where applicable; do not duplicate drills merely to fill
another report. The research wave and any production/live access remain outside
this package.
