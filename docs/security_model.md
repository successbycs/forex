# Security model

M0 itself had no trading, database, or model-provider capability. The current
M2 boundary adds only a fixed Forex-owned PostgreSQL adapter using the shared
T480 transport core: `preflight`, `inspect`, `vector-probe`, and
`forex-m2-verify` are read-only; the fixed schema/import operations require an
explicit `--approve`. It has no caller-supplied SQL, URL, host, shell, MT5, or
order argument. The historical MT5/data exception is the fixed
`m1_mt5_demo_probe`: it is Demo-only and exports exactly 720 closed EUR/USD H1
bars solely to prepare M1. M20 adds its separate, fixed `m20_demo_trading_session`
path, which starts by requiring a bounded local lease and captures only fresh
EUR/USD tick plus closed M1/M5 data until its executor/audit prerequisites are
proven. Neither path provides generic MT5, generic market-data, arbitrary
account, shell, deployment, or order access.

## M20 Demo-only execution boundary

M20 is the sole planned order-capable path. It is a fixed
`GOMarketsMU-Demo` EUR/USD loop, not a generic MT5 or broker capability. A
human operator enables a short session lease before it can act; the initial
lease is capped at ten trades in sixty minutes, one open position, USD 100
notional per trade, and USD 1,000 cumulative notional. A trade assessment must
be persisted before an execution attempt, including the fresh tick/candle
snapshot, reasons, decision timestamp, input hashes, and an idempotency key.
The executor must fail closed on an expired or absent lease, server or symbol
mismatch, stale data, cap breach, duplicate proposal, missing audit record, or
unknown broker state. The operator can pause or stop the session.

PostgreSQL retains the proposal, execution attempt, position events,
reconciliation, and outcome for back-testing. It retains no broker credential.
Raw evidence is redacted before retention and is kept separate from the
verification result.

Hard boundaries:

- `GOMarketsMU-Live` is forbidden; there is no real-money account connection,
  credential, endpoint, server selection, or order route in the project.
- No configuration may turn the fixed M20 Demo adapter into a generic MT5,
  arbitrary-symbol, arbitrary-account, or arbitrary-order interface.
- Demo execution is permitted only through the active M20 bounded-session
  contract; all other broker operations fail closed.
- Secrets, credentials, account identifiers, private host addresses, and
  populated `.env` files are excluded from version control, logs, and proof
  summaries. They are supplied only through ignored, machine-local settings.
- PostgreSQL and MT5 integration must use private/local interfaces and require
  observed exposure tests.
- Fixed command arrays execute without a shell; arbitrary command strings are
  not accepted.

Evidence is redacted before retention. A manifest records declared redactions and hashes the retained form.
