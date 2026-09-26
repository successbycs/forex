# Evidence brief: T480-local trading health and recovery

Decision date: 2026-09-24. Design only. This brief supports
[the ExecPlan](../plans/t480-local-trading-health.md); it does not authorise deployment.

## Decision and hypothesis

Determine whether one T480-local recovery owner can restore exactly one approved
MT5 Demo client and one listener, independently of T16, without bypassing the
existing order, risk, account or reconciliation controls. The hypothesis fails
if recovery needs a T16 command/manual sign-in under the claimed unattended
mode, starts a second client, loses track of an in-flight order, or declares
readiness without fresh work and local audit availability.

## Context

Instrument EURUSD; broker GOMarketsMU-Demo; account currency AUD; existing M1
strategies and risk limits unchanged. Runtime receipts use UTC with Auckland
operator display. The incident was examined on 24 September 2026. This is
availability engineering, not evidence of profitability or a new trading rule.
No backtest can establish Windows session compatibility or recovery correctness.

## Evidence reviewed

| Source | Finding and applicability | Limitation |
|---|---|---|
| `runs/local/m33-no-trades-diagnosis/listener-diagnostics.json` | At 07:07:58 UTC the listener task was Disabled, Interactive, with no listener process. | Point-in-time evidence; not the entire preceding outage timeline. |
| `runs/local/m33-no-trades-diagnosis/windows-sessions.json` | The governed session check stopped at quser reporting no user. Corroborates missing interactive session. | Diagnostic exits with error rather than returning a structured empty session list. |
| `runs/local/m33-no-trades-diagnosis/mt5-status.json` | MT5 process existed; its shared startup task was boot-triggered, last result 0. | Existence does not establish account, worker attachment or order permission. |
| `runs/local/m33-no-trades-diagnosis/risk-policy.json` | No recorded active risk pause. | Stale account observation cannot permit a new entry. |
| `scripts/t480_adapter.py`, listener and runner sources | Interactive listener, disabled rollback, retired legacy watchdog, existing child-launch restriction, local WSL bridge. | Source is not proof of every installed property. |
| `docs/plans/m30-single-client-recovery.md` | Existing agreement makes Chris responsible for client availability and defers logoff/reboot recovery. | Historical milestone references are not current state. This new design proposes superseding only those availability boundaries. |
| [Microsoft TASK_LOGON_TYPE](https://learn.microsoft.com/en-us/windows/win32/api/taskschd/ne-taskschd-task_logon_type), updated 2024-02-22, accessed 2026-09-24 | Interactive-token tasks need an existing user session. S4U has noninteractive and network/encrypted-file restrictions. Password-backed tasks require credentials at registration. | None of these modes establishes MT5 compatibility. |
| [Microsoft multiple-instance policy](https://learn.microsoft.com/en-us/windows/win32/taskschd/tasksettings-multipleinstances), updated 2020-12-11, accessed 2026-09-24 | IgnoreNew prevents overlapping instances of the same task. | It does not prevent a different task or manual launcher creating duplicates. |
| [MetaQuotes initialize](https://www.mql5.com/en/docs/python_metatrader5/mt5initialize_py), publication date unspecified, accessed 2026-09-24 | Initialization can launch a terminal; the default connection timeout is 60 seconds. | No documented PID-only attachment guarantee. Keep the existing worker child-launch restriction and explicit deadlines. |
| [MetaQuotes terminal_info](https://www.mql5.com/en/docs/python_metatrader5/mt5terminalinfo_py), publication date unspecified, accessed 2026-09-24 | Connection, permission and data-profile fields support readiness checks. | Installation path is not proof of process identity; permission flags alone do not prove execution. |
| [MetaQuotes order_check](https://www.mql5.com/en/docs/python_metatrader5/mt5ordercheck_py), publication date unspecified, accessed 2026-09-24 | Request validation is separate from execution. | A health check must not send a trade to manufacture proof. |
| [Microsoft Sysinternals Autologon](https://learn.microsoft.com/en-us/sysinternals/downloads/autologon), page updated 2021-07-27, accessed 2026-09-24 | Can establish a session automatically; administrators can recover its stored secret. | Credential/security decision; not enabled by this design request and not an unconditional recovery guarantee. |

## Findings

Evidence-supported, high confidence: current MT5 boot and listener logon
requirements are mismatched. The existing runner already has a useful
single-client safety boundary. Reuse it; give explicit launch authority only
to the managed recovery path. Local WSL/PostgreSQL remain prerequisites even
when T16 is disconnected.

Reasonable inference: a common, verified boot runtime for the terminal and its
workers could remove the manual sign-in dependency. It is unproven. A prior
SSH-launched history export cannot establish task-context trading readiness.

Assumptions to test first: boot task profile/credentials and WSL access;
attachment to one intended terminal/data directory; account permissions;
child-launch restriction during missing-client and race tests; no T16 runtime
files, sockets, tunnels or services; scheduling after a genuine cold boot.

Rejected claims: a running executable guarantees trading; a heartbeat proves
assessment progress; restarting repeatedly repairs broker/network outages;
closing a terminal closes broker positions; an earlier M29/M30 result proves
this new unattended topology; a local guardian can recover a powered-off host.

## Risks to validity

Synthetic tests do not establish Windows session behaviour. Market closure can
look like stale data. Cached timestamps can mask failed workers. Process paths
can be shared across profiles and sessions. Fault injection while flat does not
prove recovery with open exposure. Broker-side stops do not prove application
monitoring or a mandatory timed exit. Study each explicitly in the proof matrix.

## Recommendation and ExecPlan inputs

Create the bounded ExecPlan and run a held, flat, no-order session feasibility
spike only after design execution is approved. Proceed with the full guardian
only after that spike passes. Preserve Demo scope and current risk parameters.
Completion requires fault recovery, sustained progress, T16 isolation, reboot
proof and the separately authorised natural Demo lifecycle, with immutable
receipts and independent review. Alternatives and their limitations are in the
ExecPlan; no session mechanism is labelled proven by this evidence brief.
