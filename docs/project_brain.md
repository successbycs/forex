# Project brain

Forex is a learning-first EUR/USD research project intended to mature cautiously from education to observable decision support, then potentially to human-approved demo assistance. Automation and live readiness are not assumed outcomes. `NO TRADE`, `WAIT`, `INSUFFICIENT DATA`, and `NO SUFFICIENT EDGE HAS BEEN DEMONSTRATED` are valid results.

The approximately USD 300 monthly figure is an aspiration for research comparison only. It is not a quota, acceptance criterion, sizing input, or profitability claim. Capital preservation, data integrity, safety, reproducibility, and explainability precede return.

Current state is authoritative in `project_state.json`; the milestone registry is the fixed contract. The approved roadmap has three phases: historical foundation and deterministic research (M0–M16), offline decision and safety controls (M17–M26), and real-time Demo operational validation (M27–M32). M1 is a read-only export of closed Demo history; fresh-tick proof is intentionally deferred to M27.

M2 has persisted the retained M1 EUR/USD H1 historical observation in the
private T480 shared PostgreSQL service. Its verified evidence records one
`DEMO_ONLY` source, one raw observation, one immutable snapshot, and 720 bars
with lineage and no-lookahead checks. This is historical research data only:
it neither creates a live feed nor permits orders, and M2 is not complete
until the evidence-bound Triad and human route has completed.

## Architecture knowledge

The maintained visual overview is
[`docs/assets/forex-architecture-overview.png`](assets/forex-architecture-overview.png).
It records the intended three-zone boundary: Forex owns its application
contracts, evidence tooling, and catalog-locked adapter; `cs-ai-lab-infra`
owns shared T480 transport and platform services; Windows T480 hosts the
future read-only MetaTrader 5 surface. It also records the current
self-attested evidence path and four-role Triad-plus-domain review.

The diagram is explanatory rather than an assertion that every shown future or
shared component is deployed. `docs/architecture.md` is the narrative source
of truth for the design, while the milestone registry and project state retain
their respective contract and execution roles.

Final evidence review uses four isolated roles. The `ptr.py` helper can either
generate one reviewer prompt or run a visible sequential request/response
handoff. It validates a role's JSON against its immutable packet before
recording it and stops on failure. It adds no completion state, authority,
trading capability, or substitute for human acceptance.

The design-only prompt for the proposed historical market-intelligence and
Ollama-assisted research capability is retained in
[`docs/prompts/advanced-market-intelligence-milestone-prompt.md`](prompts/advanced-market-intelligence-milestone-prompt.md).

## Inspected sources

Inspected on 2026-08-17:

- `mp4-to-transcript`, local `main` at `85af3a6`: explicit job lifecycle, persistent failures, verification, and human review patterns.
- `options-learning-kb`, local `main` at `dc12e04`: registry/state separation, dependency gates, evidence freshness, hashing, and independent verification.
- `cs-ai-lab-infra`, local `main` at `e11c27d`: real-world checks, `proven_at`, T480 evidence bundles, and shared transport ownership. Pre-existing edits to its milestone registry and documentation were preserved.
- Autonomous Framework, inspected current `main` at `174226df` through its available checkout/repository material: transition contracts, definition of done, proof-value audit, and human sign-off policy. The local reference directory is not currently a Git checkout, so its present local revision cannot be independently re-read with `git`.

No reference repository was modified as part of M0 governance hardening.
