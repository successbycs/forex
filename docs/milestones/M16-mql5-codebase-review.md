# M16 — MQL5 CodeBase reference scan

Before the M16 Review Board, review a bounded shortlist of MQL5 CodeBase
examples only as learning material. This task is not a software dependency,
installation step, or trading-system evaluation.

For each candidate, retain its URL, category, apparent licence/author terms,
maintenance signals, relevant idea, safety surface, and one decision:

- `REFERENCE_ONLY` — useful learning material, but no project adoption;
- `REIMPLEMENT` — a small, independently specified and tested idea may be
  implemented in the Forex research code; or
- `REJECT` — unsuitable, unmaintained, unlicensable, unsafe, or redundant.

Prioritise read-only historical export, broker diagnostics, spread audit,
replay, drawdown, evaluation, statistics, and indicator-calculation examples.
Reject Expert Advisors, execution panels, order scripts, recovery/grid/
martingale systems, and unverified signal claims. No MQL5 CodeBase code may be
installed, invoked, copied into the Forex runtime, or granted access to the
Demo account through this task.

## Bounded scan — 2026-09-02

| Candidate | Category and useful idea | Decision | Reason |
| --- | --- | --- | --- |
| [SpreadAudit](https://www.mql5.com/en/code/75450) | Historical M1 spread percentiles and time-of-day cost diagnostics | `REIMPLEMENT` | A later Forex-owned, fixed read-only cost audit can use the idea once M1 spread history is retained. This M16 run uses a declared fixed cost sensitivity because the H1 snapshot has no observed spread field. No code is copied. |
| [RepaintTest](https://www.mql5.com/en/code/76632) | Closed-bar stability / future-data diagnostic | `REIMPLEMENT` | Its useful principle is the project’s existing point-in-time/no-lookahead test: an historical result must not change when later data is appended. Do not install the script or its chart/template machinery. |
| [Market Replay Tool](https://www.mql5.com/en/code/76669) | Visual historical replay | `REJECT` | It is an Expert Advisor with an interactive long/short drawing surface, outside the read-only research boundary. The project’s reproducible database replay is safer for the MVP. |
| [CTradeStatistics](https://www.mql5.com/en/code/1081) | Account-history statistics API | `REFERENCE_ONLY` | It is about trade/account history, which does not exist in this Demo-only, no-order phase. It may inform later reporting vocabulary only. |

The scan is reference-only. Candidate descriptions and maintenance signals are
as published by MQL5 CodeBase on the scan date; no licence is inferred and no
third-party source, binary, or dependency is introduced.
