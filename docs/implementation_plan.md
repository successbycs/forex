# Implementation plan

The authoritative sequence and phase membership are in `milestone_registry.json`. Work proceeds one milestone at a time; each milestone declares dependencies, bounded scope, artifacts, verification, real-world surface, evidence freshness, and invalidation triggers.

M0 is divided into controlled work packages:

1. M0.1 — governance traceability.
2. M0.2 — typed configuration and safety invariants.
3. M0.3 — documentation and repository guardrails.
4. M0.4 — isolated verification and durable evidence.
5. M0.5 — isolated Triad plus financial-domain assurance review.
6. M0.6 — human review and closeout.

Work packages help sequence work but do not create alternative completion claims. Only the parent milestone's `proven_at` is completion.

## MVP critical path

M20 is the active MVP milestone. It replaces the former Ollama-evaluation
critical path with a continuous-lease, Demo-only operational loop. Its work packages
are ordered to deliver an inspectable learning loop early without introducing
a generic broker interface:

1. **M20.1 — Demo-only fixed adapter and server checks.** Allow only
   `GOMarketsMU-Demo`, EUR/USD, and fixed operations; fail closed on any other
   server, symbol, or account surface.
2. **M20.2 — Fresh data and decision snapshots.** Retain fresh bid/ask/spread
   plus completed M1 candles in PostgreSQL with decision-time and source
   lineage.
3. **M20.3 — Versioned assessment and proposal audit.** Persist a `BUY`,
   `SELL`, or `NO_TRADE` assessment, its reasons, and hashes of its inputs
   before any execution attempt.
4. **M20.4 — Continuous Demo lease executor.** The approved Demo authority
   lease uses duration `0` (no time expiry) while retaining one open position,
   USD 10,000 notional per trade, USD 100,000 cumulative notional, and AUD 100
   maximum theoretical loss per trade. The fixed executor refuses stale data,
   an absent or disabled lease, cap breaches, server mismatch, duplicate
   proposals, and unknown execution state.
5. **M20.5 — Monitoring, reconciliation, and proof.** Link each proposal to
   its execution attempt or `NO_TRADE`, position events, outcome, and
   PostgreSQL reconciliation; then capture independent evidence and obtain the
   current Triad-plus-domain recommendation. M20 has no human sign-off or
   Review Board gate.
6. **M20.6 — Runner-to-audit remediation.** Ensure the fixed runner emits the
   same complete persisted proposal, PostgreSQL receipt, and reconciliation
   shape that the independent evidence verifier accepts. It proves the
   `NO_TRADE` path first; actionable execution remains a separate M20.4
   dependency and fails closed until deployed.

This is a Demo-only learning loop, not an assertion of profitability. The
human operator has approved autonomous Demo operation and can pause or stop it.
`GOMarketsMU-Live` is excluded; credentials and account identifiers stay in
ignored local files.

## Historical foundation and later hardening

1. **Historical foundation (M0–M19).** M1 proves the bounded MT5 bridge using
   720 closed H1 bars. M2–M16 build the data, research, provenance, and
   walk-forward foundations; M17–M19 add bounded context and lineage.
   Historical data cannot establish a fresh tick, current spread, or order
   result.
2. **M20 — continuous-lease automated Demo MVP.** M20 introduces the fresh-data,
   recorded-assessment, capped-execution, monitoring, and reconciliation loop
   described above. It is constrained to `GOMarketsMU-Demo` and does not
   broaden the broker, account, or order interface.
3. **Later hardening (M21–M32).** M21 improves economic-event quality;
   M22–M26 add richer deterministic risk, sizing, intent, approval, and
   revalidation controls. M27–M29 add fresh-data, tick/spread, and recovery
   hardening; M30–M32 broaden controlled Demo evaluation and forward
   assessment. `GOMarketsMU-Live` remains prohibited and no later milestone
   grants real-money authority.

## Initial M20 assessment shape

The first assessment is intentionally narrow: a permanent listener evaluates
a fresh EUR/USD M1 snapshot every ten seconds and returns a recorded `BUY`,
`SELL`, or `NO_TRADE`. Before
any execution attempt it must retain the decision timestamp, input hashes,
reasons, invalidating conditions, and session-lease identity. The assessment
cannot bypass the fixed executor; only an eligible persisted proposal can be
actioned, and every M20 cap remains in force.

M1 remains the bounded historical-export proof. Its closed history is useful
for back-testing but does not prove current prices, spreads, or M20 execution.
Source qualification and any paid-provider decision remain governed by their
own contracts; credentials are never placed in tracked configuration.

## Lean MVP quality checkpoints

Two short reviews prevent accumulated complexity from slowing the MVP without
creating an enterprise assurance programme:

1. **M20 operational review.** Confirm the fixed Demo server boundary,
   session lease, caps, proposal-before-execution ordering, PostgreSQL audit,
   reconciliation, and pause/stop controls work on the declared surface.
2. **Later final review — before M32 closeout.** Confirm the broader Demo
   workflow is safe, observable, and explainable; remove non-essential
   components and record any real-money-readiness gaps. It grants no live
   authority.
