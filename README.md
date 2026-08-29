# Forex

Forex is a learning-first, risk-controlled EUR/USD research and trading-assistance project. Approximately USD 300 per month is only a distant research aspiration; it is not a milestone, quota, sizing input, or claim of expected performance.

The roadmap has three phases: historical data foundation and deterministic research; offline decision and safety controls; then real-time Demo operational validation. Live trading and `GOMarketsMU-Live` are structurally out of scope throughout.

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
-> human sign-off when required -> prove
```

Only `prove` writes `proven_at`, the actual completion date. An optional registry `target_date` is editable by the human operator and remains a planning forecast only.

See `docs/evidence_and_milestones.md` for commands, proof rules, failure handling, and revalidation.

Every milestone also requires the isolated engineering Triad plus financial-domain review described in `docs/triad_review.md`. Its deterministic recommendation informs—but never replaces—the human completion decision.

Evidence is currently self-attested: a fixed-job local runner signs each captured M0 evidence manifest with a private key kept outside Git, and the repository verifies using the committed public key. See `docs/evidence_and_milestones.md` for its limitations.
