# Forex repository map

This concise map is the active Harness H1 artifact. It is implementation
guidance, not a milestone-proof, deployment or trading-authority claim.

| Area | Active components | Authoritative source | Safe status/check | Evidence surface |
| --- | --- | --- | --- | --- |
| Formal governance | Milestone registry, mutable state and run history | `milestone_registry.json`, `project_state.json`, `runs/run_history.json`, `AGENTS.md` | `python3 scripts/forex_milestones.py validate` | Contract checks, retained evidence and only `proven_at` establish formal completion. |
| Active delivery | Harness H1–H4 then A1–C3; H5 is the separately blocked Plane-acceptance record | `docs/milestones/active-delivery-tasks.json` | `python3 scripts/delivery_harness_status.py` | Task paths, commands/results, review disposition and evidence class in the task record. |
| Calendar information | BLS / FOMC / ECB retention, projection and context | `config/primary_event_context.json`, retained raw receipts, `sql/economic_calendar_facts.sql` | Source-verifier and context-report commands; no fetch is implied | Raw bytes and receipts remain authoritative; PostgreSQL is the queryable projection. |
| M1 decision/execution | Fixed EUR/USD Demo listener, policy kernel, final calendar overlay and PostgreSQL audit bridge | `t480/m20_demo_listener_service.py`, `t480/m20_demo_trading_session.py`, `t480/m20_postgres_audit_bridge.py` | Declared M29 capture/verifier commands only | Fresh Demo decision, execution and reconciliation evidence; no forced order. |
| Offline Plane visibility | Future task-board mapping only | `config/plane_sync.json`, `src/forex/plane_sync.py` | `python3 scripts/plane_sync.py` | Offline mapping output only; H5 external Plane acceptance remains blocked. |

The former W1–W3 queue at
`docs/milestones/autonomous-delivery-queue.json` is retained historical/deferred
planning. It is not the active selector and cannot establish a current task,
formal completion, Plane acceptance or trading authority.
