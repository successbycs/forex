# Security model

M0 itself had no trading, database, or model-provider capability. The current
M2 boundary adds only a fixed Forex-owned PostgreSQL adapter using the shared
T480 transport core: `preflight`, `inspect`, `vector-probe`, and
`forex-m2-verify` are read-only; the fixed schema/import operations require an
explicit `--approve`. It has no caller-supplied SQL, URL, host, shell, MT5, or
order argument. The sole MT5/data exception remains the fixed
`m1_mt5_demo_probe`: it is Demo-only and exports exactly 720 closed EUR/USD H1
bars solely to prepare M1. It does not provide generic MT5, generic
market-data, arbitrary account, shell, deployment, or order access.

Hard boundaries:

- `GOMarketsMU-Live` is forbidden.
- Live trading and order operations cannot be enabled by configuration.
- The agent has no trading or approval authority.
- Secrets, credentials, account identifiers, private host addresses, and populated `.env` files are excluded from version control and proof summaries.
- PostgreSQL and future MT5 integration must use private/local interfaces and require observed exposure tests.
- Fixed command arrays execute without a shell; arbitrary command strings are not accepted.

Evidence is redacted before retention. A manifest records declared redactions and hashes the retained form.
