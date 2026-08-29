# Security model

M0 has no trading, database, or model-provider capability. Its T480 adapter exposes catalogued read-only operations through the shared transport core. The sole MT5/data exception is the fixed `m1_mt5_demo_probe`: it is Demo-only and exports exactly 720 closed EUR/USD H1 bars solely to prepare M1. It does not provide generic MT5, generic market-data, arbitrary account, shell, deployment, or order access.

Hard boundaries:

- `GOMarketsMU-Live` is forbidden.
- Live trading and order operations cannot be enabled by configuration.
- The agent has no trading or approval authority.
- Secrets, credentials, account identifiers, private host addresses, and populated `.env` files are excluded from version control and proof summaries.
- PostgreSQL and future MT5 integration must use private/local interfaces and require observed exposure tests.
- Fixed command arrays execute without a shell; arbitrary command strings are not accepted.

Evidence is redacted before retention. A manifest records declared redactions and hashes the retained form.
