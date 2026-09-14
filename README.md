# Forex

Forex is a solo-operator, risk-controlled EUR/USD Demo trading platform. Its
near-term mission is the shortest safe path to protected, explainable and
reconciled Demo trading decisions—not an open-ended research programme or
edge-case hardening exercise. Approximately USD 300 per month remains only a
distant aspiration; it is not a milestone, quota, sizing input, or claim of
expected performance.

The roadmap retains historical research and future validation work, but those
are subordinate to the current critical path. M20 is the active MVP: a fixed,
capped `GOMarketsMU-Demo` EUR/USD loop from fresh data to recorded assessment,
Demo execution, monitoring, and PostgreSQL reconciliation. A decision is
"good" at this stage when it follows the frozen strategy and all required
freshness, account, sizing, protection, cost, audit and reconciliation rules;
profitability is learned from retained Demo outcomes rather than assumed. Live
trading and `GOMarketsMU-Live` remain structurally out of scope throughout.

## Start building and testing

The canonical milestone definitions are in `milestone_registry.json`; mutable status and timestamps are in `project_state.json`; audit events are in `runs/run_history.json`.

```bash
python3 scripts/forex_milestones.py status
python3 scripts/forex_milestones.py show --id M1
python3 scripts/forex_milestones.py validate
bash scripts/verify_project.sh
```

The mutable state records the currently active or blocked milestone. The registry's three-phase contract determines what may be built with historical data and what must wait for real-time Demo market activity. Use `ready` only after dependencies are proven, then `start`.

The normal closeout sequence is:

```text
start -> implement -> record-check -> verify -> capture evidence
-> independently verify and record evidence -> finish-implementation
-> any review gates declared by the active milestone -> prove
```

Only `prove` writes `proven_at`, the actual completion date. An optional registry `target_date` is editable by the human operator and remains a planning forecast only.

See `docs/evidence_and_milestones.md` for commands, proof rules, failure handling, and revalidation.

The final Review Board—Triad plus Financial Domain Expert—is required at the
three phase gates: M16, M27, and M32. M20 also requires a current
Triad-plus-domain `RECOMMEND_COMPLETE` result, but it has no human sign-off
gate. See `docs/triad_review.md`.

Administrators can inspect the T480 PostgreSQL historical price data from the
home LAN using the guide in [`docs/database_access.md`](docs/database_access.md).

Evidence is currently self-attested: a fixed-job local runner signs each captured M0 evidence manifest with a private key kept outside Git, and the repository verifies using the committed public key. See `docs/evidence_and_milestones.md` for its limitations.
