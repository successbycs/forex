# Architecture

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
