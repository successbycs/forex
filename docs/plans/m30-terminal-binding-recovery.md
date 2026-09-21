# Repair and deploy M30 listener terminal attribution

This living ExecPlan follows `PLANS.md`. Its execution record is
`docs/plans/m30-terminal-binding-recovery-work.json`. Chris repeatedly
authorised its review and execution; deployment of the reviewed diagnostic
is within that request, subject to real release prerequisites.

## Purpose / Big Picture

Restore trustworthy MT5 listener diagnostics so the operator can determine
which installation and data profile the M1 Demo worker uses and whether it
has trading permission. The reported executable mismatch was caused by
comparing an executable filename with an installation directory. The remedy
is to correct that comparison and observe the actual listener after release.
The expected visible result is fresh `MAPPED` telemetry or an accurate refusal.

## Formal milestone dependency map

M29 is PROVEN and reusable on its pinned historical surface. M30 is the active
milestone. This diagnostic repair supports M30's Demo execution/reconciliation
proof; it does not itself provide that proof. M31 remains dependent on M30
and is not started. No trading strategy, risk limits or account profile changes
are included. M30 still needs its natural protected order/close/reconciliation
bundle and its declared review and approval gates.

## Scope and owned paths

The MVP failure is false terminal attribution that blocks useful diagnosis.
The smallest implementation corrects `terminal_runtime_binding` in
`t480/m20_demo_trading_session.py`, retains validated failure hashes in
`t480/m20_demo_listener_service.py`, and correlates existing terminal process
paths through `scripts/t480_adapter.py`. The adapter returns hashes and
matching booleans; paths and credentials remain local to T480.

Owned tests are `tests/test_t480_adapter.py` and
`tests/milestones/test_m20_listener_service.py`. Owned documentation is this
plan, its work record, and
`docs/research/m30-terminal-binding-recovery-evidence-brief.md`.
New terminal installation, instance management, changing AutoTrading, risk
resume, forced orders, Live activity and formal milestone transitions remain
outside this repair. Preserve all captured evidence.

## Evidence and design

MetaQuotes documents `initialize` as taking an executable filename and shows
`terminal_info().path` as an installation directory. The old test fixture
incorrectly made the latter an executable too. The repaired worker validates
an absolute configured path ending in terminal.exe or terminal64.exe and an
absolute reported directory. It derives the connected executable identity by
joining that directory with the configured basename, then compares canonical
Windows-path hashes. Missing or different identities remain unavailable.

This identity is derived from the installation: it does not independently
prove a particular terminal PID or owner-approved data profile. `MAPPED`
binds the worker observation to a fresh, active listener PID/release. A data
profile hash is an observed identity, not approval to select a different one.

At 2026-09-20T09:02:47Z both existing terminal processes (Sessions 0 and 2)
had the same executable hash and matched the deployed configured path. At
09:02:50Z the fixed account reader observed GOMarketsMU-Demo/AUD, the account
identified by Chris's screenshot, and zero open positions. This reader runs
in SSH context and is not substitute evidence for a listener-owned binding.

`LAST_KNOWN_UNVERIFIED` is a display classification from a retained monitor-job
file while the current monitor is not RUNNING. It is not proof of an open
position. Preserve the record; use current account and listener evidence before
a release. Do not request terminal reselection based on the defective mismatch.

## Progress

<!-- forex-work-projection:start task=M30-TERMINAL-BINDING-RECOVERY schema=forex.execution-work-projection.v1 -->
<!-- forex-work-item id=repair-review state=DONE -->
- [x] repair-review — Correct the API comparison and independently review the diagnostic and tests (DONE)
<!-- forex-work-item id=remote-discovery state=DONE -->
- [x] remote-discovery — Observe configured process matching and the operator-identified Demo account (DONE)
<!-- forex-work-item id=commit-release state=DONE -->
- [x] commit-release — Commit the reviewed patch and deploy the bound diagnostic release (DONE)
<!-- forex-work-item id=verify-listener state=DONE -->
- [x] verify-listener — Observe fresh listener attribution and report actual permission and protection state (DONE)
<!-- forex-work-projection:end -->

## Plan of work and concrete steps

Work from `/home/chris/projects/forex`. The local repair and independent review
are completed. Tests cover directory-versus-file semantics, case/slash spelling,
wrong installations, invalid paths, unavailable MT5, output validation and
transport size. Five loop tests now stub the separate runtime-binding probe
so their monitoring/reconciliation assertions do not invoke an installed MT5
interpreter. Production order behavior is unchanged.

The final patch passed:

    python3 -m pytest -o addopts='' -q tests/test_t480_adapter.py tests/milestones/test_m20_listener_service.py tests/milestones/test_m30.py
    python3 scripts/forex_milestones.py validate
    git diff --check

Actual outcome: 188 passed in 53.42 seconds; governance and whitespace passed.
Independent reviewer `/root/binding_review` approved the code, then independently
ran all 34 listener-service tests after the test-isolation repair.

Before release, obtain the explicit local-commit instruction required by
`PLANS.md` ("Commit only with explicit human instruction."). Commit only the
eight owned code/test/documentation paths. Do not push. This is the remaining
authority boundary; generic execution approval is already present. The release
adapter records Git HEAD, so tagging uncommitted payloads as the existing
revision is not acceptable.

After commit, reread `docs/t480-deployment.md` and the release-readiness skill.
Rerun the fixed listener diagnostics, identity and account observations, verify
the expected Demo identity and current exposure, and inspect current hold and
monitor state. Reassess if these have changed. Do not resume risk or clear a
maintenance hold as a side effect. Recalculate command lengths against the
committed candidate. The current 207-operation stage/verify/prepare/configure/
install/identity surface has maximum encoded length 7,438, below 7,500.

Use `python3 scripts/t480_adapter.py execute --operation <fixed-operation>`
for all remote operations. Stage the service's 48 fragments, runner's 96,
bridge's 48, and notification payload's existing fixed fragments. The exact
numbered names and verification operations are in `OPERATIONS` and the catalog;
never substitute a generic copy or shell. Verify each assembled SHA-256, then
run `m20_listener_prepare`, `m20_listener_configure` and `m20_listener_install`
only when the readiness matrix below passes. Preserve current owner-managed
terminal/account selection and risk settings. Retain actual outputs in a new
evidence directory. The candidate payload release before commit is
`b1e732115e3a7937`; recalculate if payload bytes change.

After a healthy heartbeat, run `m20_listener_terminal_identity` and
`m20_listener_status`. Require fresh `MAPPED` with the active listener PID,
Demo/AUD and consistent installation hashes; record the observed profile hash
and permission booleans. Recheck configured account identity. If mismatched,
remain unavailable and report the specific discrepancy. If permission is false,
report that listener-owned fact; do not change the terminal GUI automatically.
Any actual risk pause remains subject to its existing governed process.

## Readiness, acceptance and rollback

| Check | Current result | Release requirement |
| --- | --- | --- |
| Repair and independent review | PASS | Exact reviewed payloads |
| Regression/governance/transport | PASS | Recheck after changed bytes |
| Account/exposure read | Expected Demo/AUD account, zero positions | Refresh before install |
| Committed source binding | PASS: f73a0c1 | Explicit local-commit instruction received |
| Fresh listener-owned attribution | PASS: MAPPED, advancing timestamps | Permission remains false |

Use the fixed installer's retained previous task and rollback behavior on an
unhealthy release. Never delete lease, monitor or risk files to make acceptance
pass. The diagnostic change requires targeted re-verification of listener
telemetry and source binding. M30 proof must be on the final deployed version;
M29's separate pinned historical bundle is not overwritten or reclassified.

## Surprises & Discoveries

The previous agents and tests assumed MT5 returned an executable path. Their
mismatch diagnosis and requests for terminal reselection were unsupported.
Current process evidence shows both existing instances share the configured
executable. The lingering monitor record also was overinterpreted as current
exposure. Correct data semantics before creating an operator blocker.

## Decision Log

2026-09-20: repair the directory/file comparison first; preserve current
configuration. Source: primary API reference and fresh fixed discovery.
Retain independent review as required by PLANS; obtain it directly instead of
asking Chris to organise it. Preserve explicit commit authority as the only
current release authority boundary. Do not infer M30 completion from this work.

## Outcomes & Retrospective

Local repair, independent review, regression checks and remote discovery are
complete. Raw observations are in `runs/local/m30-binding-review-4wjTv2mj/`.
Chris authorised the local commit (f73a0c1) and continuation of deployment.
Release b1e732115e3a7937 was staged, hash-verified, prepared, configured and
installed through fixed operations on 2026-09-20. No maintenance hold was
introduced or removed. Deployment diagnostics bind all four payload hashes to
f73a0c14cdd793d9e1c7a188ed5130a353de8306 and the unchanged configuration
fingerprint. Lease, risk policy and financing policy match the preflight.

Post-install identity is MAPPED with fresh heartbeat and binding timestamps;
a repeat capture advanced from 09:10:36Z to 09:11:08Z. The listener-owned
connection is Demo/AUD, but terminal_trade_allowed and submission_permitted
are false. API-disabled is false and account trading/expert permissions are
true. This now accurately attributes the terminal permission refusal. The
fixed account reader still reports the operator-identified account and zero
positions. The retained monitor record remains LAST_KNOWN_UNVERIFIED and was
not deleted or represented as a currently open position.

All 209 fixed deployment/discovery commands fit the transport envelope. The
218 raw JSON artifacts and their SHA256SUMS are retained under
`runs/local/m30-binding-deploy-A2HgHXrc/`. Offline checks verified payloads,
revision, preserved configuration/lease/risk and advancing MAPPED evidence.
The independent deployment review is recorded in the work JSON. This completes
diagnostic deployment, not M30 lifecycle proof or trading enablement. Terminal
Algo Trading permission and any persistent risk pause remain separate follow-up
work under the existing M30 controls.
