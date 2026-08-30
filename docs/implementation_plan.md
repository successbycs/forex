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

## Three-phase historical-first roadmap

1. **Phase 1 — historical foundation and deterministic research (M0–M16).** M1 proves the bounded MT5 bridge using 720 closed H1 bars. M2 establishes the initial data contracts and persistence; M3 then hardens the bounded historical MT5 CLI result contract and complete local configuration example before M4–M6 add application integration and wider multi-timeframe history. M7 qualifies sources before adoption; M8–M11 add US macro, Euro-area macro, calendar, and experimental sentiment inputs. M12–M14 normalise, align, and create regimes; M15 adds one explainable offline ML baseline beside deterministic hypotheses; M16 evaluates both using chronological walk-forward comparison with no-change and price-only baselines. Historical data cannot establish a fresh tick, current spread, live-market restart behaviour, or execution.

The M15 ML baseline is intentionally a learning tool: one small classifier, one pre-declared historical target, versioned inputs and parameters, and an advisory-score output for research. It cannot place, approve, or recommend orders. Deep learning, reinforcement learning, online learning, automated retraining, and LLM trade decisions are excluded from the MVP.

## Initial intraday strategy shape

The first strategy is intentionally narrow: for a defined EUR/USD session,
make one assessment at a configured UTC decision time and return `BUY`, `SELL`,
or `NO_TRADE`. At most one human-approved Demo position may be open for that
session. It must close at the configured UTC cutoff, or earlier because of a
predefined risk exit. The eventual M15 score is a 0–100 advisory ranking with
its inputs, rationale, calibration status, and invalidating conditions; it is
not an order or approval. Session hours, daylight-saving handling, spread
limits, loss limits, and economic-event blackout rules are versioned inputs to
be proven before any Demo execution.
2. **Phase 2 — offline decision and safety controls (M17–M26).** M17 defines a non-executing agent context; M18 and M20 constrain Ollama to versioned, schema-validated, offline sentiment experiments; M19 preserves decision/model lineage; M21 hardens event quality. M22–M26 add simulated risk, sizing, intent, human approval, and revalidation. A simulated intent is not an order.
3. **Phase 3 — real-time Demo operational validation (M27–M32).** Once markets are active, M27–M29 prove fresh `GOMarketsMU-Demo` data, tick/spread collection, and recovery safety. M30 is the separately gated human-approved Demo execution and reconciliation proof. M31–M32 evaluate the controlled Demo workflow and forward observations. `GOMarketsMU-Live` remains prohibited, and M32 grants no live-trading authority.

M1 is the bounded historical-export proof. The former fresh-tick requirement is deliberately deferred to M27. Source qualification and any paid-provider decision are explicitly deferred to M7; no provider credential is required or permitted before that contract is proven.

## Lean MVP quality checkpoints

Two short reviews prevent accumulated complexity from slowing the MVP without
creating an enterprise assurance programme:

1. **Mid-build review — after M16 and before M17.** Confirm that historical data lineage and no-lookahead controls are truthful, the user path is understandable, safety limits remain intact, and unused complexity is removed. It does not create a new approval board or grant execution authority.
2. **Final review — before M32 closeout.** Confirm that the human-operated Demo workflow is safe, observable, and explainable; remove non-essential components and record any live-readiness gaps. It grants no live-trading authority.
