# Evidence Brief: M30 listener terminal-binding recovery

## Superseding source review — 2026-09-20

The previous conclusions that the listener uses a different executable and
requires owner reselection are withdrawn. The API inputs were misinterpreted.
MetaQuotes' [initialize reference](https://www.mql5.com/en/docs/python_metatrader5/mt5initialize_py)
specifies an executable filename; its [terminal_info reference](https://www.mql5.com/en/docs/python_metatrader5/mt5terminalinfo_py)
demonstrates an installation directory in `path`. Both undated primary
references were consulted 2026-09-20. This directly applies to the diagnostic;
it does not establish actual T480 account/profile identity. The code and prior
tests compared file to directory. A corrected comparison must precede any
conclusion that remote configuration is wrong.

`LAST_KNOWN_UNVERIFIED` is a display classification derived from a retained
monitor file and the current monitor not being RUNNING. It is not affirmative
proof of an open position or unresolved broker exposure. Fresh exposure remains
to be observed before a restart. No additional terminal is justified by the
available evidence. The remaining sections retain the earlier interpretation
for provenance; these corrections govern execution.

## Decision

Decide whether the M30 listener may be reconfigured to use a specific MT5
terminal, and what must be established first.

## Proposed claim or hypothesis

If the listener is configured with the executable and data profile of the
intended GOMarketsMU-Demo/AUD M1 terminal, its listener-owned binding will
return `MAPPED`; that result is necessary, but not sufficient, for an
autonomous Demo entry.

## Context

- Instrument / market: EUR/USD, GOMarketsMU-Demo only.
- Timeframe: closed M1 candles.
- Data source: T480 listener-owned heartbeat and the fixed T480 adapter.
- Period examined: 2026-09-19T23:24:37Z to 2026-09-19T23:24:46Z.
- Intended use: restore trustworthy terminal attribution before M30 natural
  lifecycle observation.
- Known constraints: no Live server, generic remote shell, desktop automation,
  forced/retried orders, or risk-policy change.

## Evidence reviewed

| Source | Type | Relevant finding | Applicability | Limitations |
| --- | --- | --- | --- | --- |
| `docs/plans/m30-mt5-terminal-identity-diagnostic-work.json` | listener-owned deployed evidence | Final listener release reported `TERMINAL_EXECUTABLE_PATH_MISMATCH`. | Directly applies to the active M30 listener. | Does not name either local path. |
| Fixed `m20_listener_terminal_identity` observation, 2026-09-19T23:24:44Z | current read-only T480 observation | Listener task is running; binding is `UNAVAILABLE`; two terminal processes are in Sessions 0 and 2. | Directly applies to current process topology. | Session number does not identify account or profile. |
| Fixed `m20_listener_status` observation, 2026-09-19T23:24:46Z | current read-only T480 observation | Server is GOMarketsMU-Demo/EURUSD, but protection is `LAST_KNOWN_UNVERIFIED`. | Directly applies to entry safety. | It does not reconcile current broker state. |
| Operator-supplied MT5 login dialog | human observation | Visible desktop terminal names GOMarketsMU-Demo. | Supports candidate-terminal identification. | Does not bind it to the scheduled listener. |

## Findings

### Evidence-supported

- Claim: the current scheduled listener cannot be attributed to the visible
  MT5 terminal.
  - Evidence: listener-owned binding reports an executable mismatch and the
    read-only topology contains separate Session 0 and Session 2 processes.
  - Confidence: high.
- Claim: new entries are not currently safe to enable.
  - Evidence: listener status reports `LAST_KNOWN_UNVERIFIED` protection.
  - Confidence: high.

### Reasonable inferences

- Inference: the visible terminal is a candidate for the intended Demo account,
  not proof of the listener's configured executable/data profile.
  - Why it is reasonable: its login dialog names the permitted Demo server.
  - What remains unproven: its executable path, data profile, currency, and
    compatibility with the Scheduled Task context.

### Assumptions to test

- Assumption: one identified executable/profile can be selected without
  creating another MT5 instance.
  - Test required: owner identifies the dedicated M1 Demo terminal; a fixed
    configuration update followed by listener-owned binding returns `MAPPED`.
  - Pass/fail measure: fresh `MAPPED`, Demo/AUD binding, and exact active
    listener PID. Any mismatch, ambiguous result, or stale heartbeat fails.

### Rejected or unsupported claims

- Claim: enable AutoTrading in the visible window to solve M30.
  - Reason: terminal permission is not attributable until the listener binding
    is `MAPPED`.
- Claim: start another MT5 terminal instance to solve M30.
  - Reason: it creates another candidate without selecting the configured
    executable/profile and increases ambiguity.

## Risks to validity

- Data quality: the status has not reconciled its retained position to current
  broker state.
- Execution realism: no order is authorised by this diagnostic.
- Other risks: a wrong terminal/profile can bind a different account or leave
  protection uncertain; full local paths and credentials must not be recorded.

## Recommendation

Create and execute the bounded M30 terminal-binding recovery ExecPlan below.
Its first executable steps are read-only. Configuration selection and release
remain conditional on an explicit owner identification of the intended terminal.

## Proposed ExecPlan inputs

- Goal: establish a trustworthy M1 Demo listener-to-terminal binding.
- Scope: redacted discovery, fixed configuration application after owner
  selection, release readiness, reconfiguration, and read-only observation.
- Non-goals: create or close MT5 instances, broker actions, Live access,
  strategy/risk changes, or state-file removal.
- Acceptance criteria: fresh `MAPPED` Demo/AUD binding and no unknown
  protection state before permission assessment.
- Decision gate: owner identifies the intended executable/profile and approves
  its selection.
- Evidence links: the sources named above.
