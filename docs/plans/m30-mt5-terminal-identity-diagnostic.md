# M30 listener MT5 runtime-binding diagnostic

This ExecPlan is a living document governed by `PLANS.md`. It repairs a failed
diagnosis without widening the M30 Demo-only execution boundary.

## Purpose / Big Picture

The M30 listener reported that automated submission was unavailable while an
operator had enabled Algo Trading in a visible MT5 client. The earlier
diagnostic queried MT5 from a new SSH-launched Python process and listed two
terminal processes. That did not establish which MT5 context the Scheduled
Task listener uses. Its conclusion about Session 0 was therefore invalid and
is withdrawn.

After this package is deployed, an operator can run the fixed
`m20_listener_terminal_identity` operation and see one of three results:

- `MAPPED`: the listener's own child worker supplied the redacted MT5 runtime
  binding and its parent listener process is currently present;
- `AMBIGUOUS`: a valid binding exists but cannot be matched to a running
  listener process; or
- `UNAVAILABLE`: the listener did not produce a valid binding.

Only `MAPPED` permits interpretation of `terminal_trade_allowed` for the
listener. This diagnostic never sends an order, changes MT5 settings, stops
the listener, or accesses a Live account.

## Formal milestone dependency map

M29 is proven and reusable. M30 is active and this package fits M30 because it
repairs the terminal-permission evidence needed before an autonomous Demo
entry can occur. It does not satisfy M30's real-world proof surface: M30 still
requires one naturally eligible, protected and reconciled Demo lifecycle.
M31, M15, UI automation, generic remote control, strategy changes, and account
or risk-policy changes remain out of scope.

## Context and design

`t480/m20_demo_listener_service.py` is the permanent Scheduled Task payload.
It starts fixed child calls to `t480/m20_demo_trading_session.py`. The new
`--terminal-runtime-binding` child call uses the same local Python interpreter,
configured terminal path, and task context as normal listener work. It returns
only the Demo/AUD binding, submission flags, and SHA-256 hashes of the terminal
executable and MT5 data profile. The listener records that result plus its own
process ID and capture time in the heartbeat, then refreshes it at most once
every 30 seconds. A changed GUI setting is therefore never interpreted from a
startup-only snapshot.

`scripts/t480_adapter.py` reads that already-published heartbeat and compares
the recorded listener PID with fixed Windows process enumeration. It does not
call `MetaTrader5.initialize`, so the diagnostic itself cannot attach to or
start a terminal. It returns terminal process IDs only as supporting topology,
not a claimed profile mapping.

## Plan of work

1. Replace the invalid SSH-side MT5 identity probe with listener-owned runtime
   binding telemetry and a read-only correlation operation.
2. Test a successful Demo binding, unavailable MT5, malformed runner output,
   explicit `MAPPED`/`AMBIGUOUS`/`UNAVAILABLE` classification, no order path,
   and the T480 command-size envelope.
3. Run local verification and governance validation.
4. Keep the release-critical installer and runner-fragment commands below the
   T480 encoded-command limit. The runner uses 96 fragments; this is transport
   packaging only and does not alter its trading logic.
5. Before any release, use release-readiness and retain a material-change
   impact decision. Deployment is not performed by this package because the
   existing listener must not be put on a maintenance hold merely for this
   diagnostic.
6. After a separately authorised no-hold release method is available, observe
   the released listener binding. If `MAPPED`, inspect the reported permission
   state. The separate `EXTERNAL_CASH_FLOW` risk pause remains an independent
   M30 blocker and is not altered here.

## Validation and acceptance

From the repository root, run:

    python3 -m pytest -q tests/test_t480_adapter.py -k 'terminal_identity or terminal_runtime_binding or catalog_and_adapter_operations_match'
    python3 -m pytest -q tests/milestones/test_m20_listener_service.py -k 'runtime_binding or loads_without_mt5'
    python3 scripts/forex_milestones.py validate

The operation is accepted locally when these checks pass and its fixed command
is below 7,500 characters. A deployed observation is accepted only if it
returns `MAPPED` with fresh heartbeat and binding timestamps, one matching
listener process for the exact active release, Demo server and AUD currency.
Any other result is evidence of uncertainty, not an
instruction to change a GUI setting.

## Progress

<!-- forex-work-projection:start task=M30-MT5-TERMINAL-IDENTITY schema=forex.execution-work-projection.v1 -->
<!-- forex-work-item id=runtime-binding state=DONE -->
- [x] runtime-binding — Implement listener-owned MT5 runtime binding and fixed read-only correlation (DONE)
<!-- forex-work-item id=behavioural-tests state=DONE -->
- [x] behavioural-tests — Test binding results, failure paths, no-order boundary and transport size (DONE)
<!-- forex-work-item id=deployed-observation state=BLOCKED -->
- [ ] deployed-observation — Release and observe the actual listener runtime binding (BLOCKED)
<!-- forex-work-projection:end -->

## Surprises & discoveries

- At 2026-09-17T09:06Z, the old probe found two terminal processes and a false
  `trade_allowed` value. That is evidence of a terminal problem, but not proof
  of which process or data profile the listener used.
- The old probe could initialise MT5 from its own SSH context. It is retained
  only as superseded implementation history and must not be used as proof.
- Release readiness initially found the runner's former 80 fragments and the
  installer exceeded T480's encoded command boundary. The release-critical
  commands now fit; paused H1 commands remain outside this M30 release path.

## Decision log

- 2026-09-17, Astra: replace the prior conclusion with `UNKNOWN` and make the
  diagnostic listener-owned. This is the smallest design that tests the needed
  causal link without unsupported desktop automation.
- 2026-09-17, independent review: require fresh runtime evidence, exact active
  release/PID correlation, and bounded refresh before `MAPPED` is allowed.
- 2026-09-17, Astra: use 96 hash-verified runner fragments and compact the
  fixed installer rather than retrying an overlong command or widening SSH.

## Outcomes & retrospective

The previous statement that Session 0 was the listener terminal and required
an Algo Trading setting change is withdrawn. Local implementation and tests
are complete. No claim about the deployed listener, terminal profile, Auto
Trading state, M30 proof, or risk-pause resolution is made until the new
release is observed on T480.
