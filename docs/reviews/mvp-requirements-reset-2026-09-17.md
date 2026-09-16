# MVP requirements reset — 2026-09-17

## Decision requested

Reset the repository around one observable outcome: a protected, explainable
EUR/USD **Demo** M1 decision loop that records one terminal decision per closed
candle and, when an existing signal is actionable, records the resulting Demo
order through broker reconciliation. This is an MVP reliability and evidence
goal, not a profitability claim or a Live-trading programme.

This review is a requirements recommendation. It does not change runtime,
milestone state, deployment, schedules, or broker authority.

## Evidence reviewed

- `AGENTS.md`, `project_state.json`, `milestone_registry.json`, and
  `docs/evidence_and_milestones.md` for project authority and proof gates.
- `docs/workflows/m1-demo-decision-workflow.md` and
  `t480/m20_demo_trading_session.py` for the existing M1 path.
- `docs/plans/m30-controlled-demo-execution.md` and
  `docs/plans/m1-hybrid-prefect-postgres.md` for active and proposed scope.
- Package B/C retained outputs: the exact 104-second M1 sample contains 16
  persisted `NO_TRADE` proposals, showing that current identity is poll/snapshot
  bound rather than closed-candle bound.

## Reset MVP requirements

1. **Demo-only M1 operation.** Only `GOMarketsMU-Demo` and `EURUSD` may be
   used. Live trading remains structurally prohibited.
2. **One terminal decision per closed M1 candle.** Every usable closed candle
   has exactly one persisted `BUY`, `SELL`, or `NO_TRADE`; invalid or unavailable
   input records a safe refusal. Repeated polls and restart cannot create a
   second decision or submission for that candle.
3. **Existing safety remains intact.** Keep the current fixed account, quote,
   spread, exposure, risk, cost, reservation, and broker-result protections.
   Existing position monitoring and protective exits must not depend on capture
   or reporting availability.
4. **Durable, inspectable evidence.** Retain the decision snapshot, reason,
   selected owner, proposal identity, and attempt/outcome where one exists in
   PostgreSQL and the existing retained evidence paths.
5. **One real Demo lifecycle proof.** M30 closes only after one eligible,
   bounded Demo order is opened, closed, and broker-reconciled on the resulting
   version. A `NO_TRADE` proves decision recording, not execution completion.
6. **Small operator view.** The existing read-only listener/dashboard and
   PostgreSQL summaries must show current status, the latest decision/refusal,
   and any order lifecycle. No new dashboard platform is required.

## Immediate implementation scope

Package D is the only remaining MVP build package:

- deterministic closed-candle decision key;
- one additive PostgreSQL uniqueness constraint;
- matching listener/bridge persistence contract; and
- focused duplicate, refusal, restart, and existing-safety tests.

After it is applied with its matching Demo release, retain one short M1
observation showing exactly one terminal decision per candle. Then run the
existing bounded M30 Demo order/close/reconciliation proof when a genuine
eligible signal occurs. Never force an order.

## Explicitly deferred

- Prefect installation, deployment, or flow work;
- n8n changes beyond already-running bounded integrations;
- new data stores, schedulers, workflow engines, dashboards, or migration
  frameworks;
- required economic-event gate or source-coverage project;
- M5/H1 as an M1 entry veto or execution owner;
- M15 or any new execution timeframe;
- new strategies, risk limits, dynamic sizing, and performance optimisation;
- broad data completeness, backfill, endurance, or availability claims; and
- Live trading.

Current B/C persistence observations remain useful evidence but do not justify
building a broader data platform. Unknown coverage outside their bounded sample
is acceptable for this MVP.

## Required contract/plan simplification

The current hybrid plan includes Package E (qualified context and broad
reporting) and an optional Prefect/n8n branch. Neither is required for the
reset MVP outcome. Before treating this reset as binding, amend M30-C2 and the
hybrid plan so they require only the retained envelope/completeness work,
candle-keyed decision integrity, targeted verification, and the existing M30
final proof. Keep Package E and the optional pipeline branch deferred rather
than incomplete.

## Acceptance evidence

| Requirement | Smallest evidence |
| --- | --- |
| One decision per candle | Focused local duplicate/restart tests plus one short retained Demo observation after deployment |
| Safe refusal | Focused malformed/stale-input test and persisted refusal/`NO_TRADE` output |
| Persistence | Exact PostgreSQL summary joined to retained assessment identities |
| Existing protection | Existing focused listener/monitor regression checks |
| M30 completion | One bounded Demo `OPENED` → `CLOSED` broker-reconciled lifecycle on the final version |

## Review conclusion

The repository already has most MVP infrastructure: a fixed Demo listener,
existing PostgreSQL audit path, retained assessment evidence, read-only status,
and reconciliation. The material MVP defect is duplicate decision identity
within one M1 candle. Fix that defect, observe it, then prove the existing
Demo lifecycle. Everything else is deferred until the retained Demo evidence
creates a concrete reason to expand scope.
