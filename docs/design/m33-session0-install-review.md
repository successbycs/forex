# M33.1 interim Session 0 listener installer review

Independent read-only reviewer (Explore subagent, static review, 25 September 2026).
Scope: `t480/m33_listener_session0_install.ps1`, `scripts/apply_m33_session0_listener_install.py`,
`tests/test_m33_session0_listener_install.py`. The reviewer cannot approve; it found
no blockers and returned "safe to apply after fixes". Nothing was run on the T480.

| # | Finding | Severity | Disposition |
|---|---|---|---|
| 1 | Heartbeat proof could pass on a stale status file; fixed 10 s wait | should-fix | Fixed: pre-start heartbeat captured, poll up to 60 s, require Running task, live worker, heartbeat newer than the pre-start value, release id, age < 30 s and MAINTENANCE_HOLD |
| 2 | Rollback did not stop or verify workers | should-fix | Fixed: `Restore-Previous` stops surviving workers and asserts none remain |
| 3 | Restore could mask the original failure and leave state unasserted | should-fix | Fixed: restore wrapped separately, both messages reported, final state asserted Disabled (`RESTORE_NOT_CLEAN`) |
| 4 | "Order path blocked" overstated: the held monitor runs `--recover-open-positions-once` | should-fix | Fixed: output now says entry assessment blocked and open-position monitoring active under the existing exit policy. Release-hold approval must state a boot-start task exists |
| 5 | Hold checked once | should-fix | Fixed: re-read before registration, before start and after the proof, with schema check |
| 6 | Apply script idempotency weak | should-fix | Fixed: adapter and catalog checked independently, missing ids only |
| 7 | Probe task not guarded; tests textual | should-fix | Partly: Running/Queued probe task now refuses; tests strengthened for ordering, restore sequence and hold rechecks; PowerShell is still not executed in tests (no Pester) |
| 8 | Run op hid the installer's reason | nit | Fixed: child output is captured into the thrown message |
| 9 | Principal only checked for S4U | nit | Fixed: non-empty, not a service account |
| 10 | `approval_required` on the run op | nit | Not adopted: `validate_contract` forbids approval-based Forex operations |

Residual limits: PowerShell behaviour is unproven until the fixed operations run on
the T480; the boot trigger and `RestartCount 3` must be handed to the guardian
before activation (ExecPlan amendment condition 2); fingerprint refresh needs
Chris's named preserved milestones.
