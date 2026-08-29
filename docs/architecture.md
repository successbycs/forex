# Architecture

## High-level system diagram

![High-level Forex repository architecture](assets/forex-architecture-overview.png)

The diagram is a maintained overview of the intended ownership and trust
boundaries. It distinguishes the Forex repository, shared `cs-ai-lab-infra`,
and the Windows T480 / MetaTrader 5 environment. It also shows the evidence
path: the fixed local evidence runner self-attests a captured bundle; the
repository verifier checks its signature, schema, policy, and reproducibility;
then the four-role Triad-plus-domain review produces a recommendation for a
human decision.

This is an architecture map, not proof that a shared service or future
capability is currently deployed. The current M0 scope is stated below and the
mutable execution record remains `project_state.json`.

The M0 repository contains only governance, typed operator configuration, testing, evidence tooling, and the catalog-locked T480 transport adapter. It intentionally has no strategy, agent, database, market-data, MT5 API, account, position-sizing, or order implementation.

Target ownership boundary:

```text
cs-ai-lab-infra
  shared T480 transport, PostgreSQL, n8n, optional Ollama, internal network

Forex
  application configuration, read-only MT5 adapter, schemas, migrations,
  research logic, workflows, decisions, and evidence

Windows T480
  installed MetaTrader 5 terminal; later, the Forex-owned MT5 adapter
```

Capabilities are introduced vertically, one milestone at a time. Shared infrastructure is referenced rather than copied. Fixed safety invariants remain in schemas and code, even when related operator settings are visible in configuration.

The hard boundary remains: research only; no live trading, no
`GOMarketsMU-Live`, and no order surface before M27. The evidence signature is
self-attested integrity, not independent execution provenance.
