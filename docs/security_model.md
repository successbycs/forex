# Security model

M0 has no trading, market-data, account, database, or model-provider capability. Its T480 adapter exposes only catalogued read-only operational observations through the shared transport core.

Hard boundaries:

- `GOMarketsMU-Live` is forbidden.
- Live trading and order operations cannot be enabled by configuration.
- The agent has no trading or approval authority.
- Secrets, credentials, account identifiers, private host addresses, and populated `.env` files are excluded from version control and proof summaries.
- PostgreSQL and future MT5 integration must use private/local interfaces and require observed exposure tests.
- Fixed command arrays execute without a shell; arbitrary command strings are not accepted.

Evidence is redacted before retention. A manifest records declared redactions and hashes the retained form.
