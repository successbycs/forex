# M6 — multi-timeframe historical path

M6 adds one fixed, read-only T480 MT5 operation. It measures closed `EURUSD`
history from `GOMarketsMU-Demo` across `M15`, `H1`, and `D1` using fixed
counts of 720, 720, and 365 respectively. Position one excludes each current,
forming bar. The output retains only timeframe-level counts, time ranges and
SHA-256 hashes; it contains no credentials, orders, balances or live-server
access.

The capability is incomplete until the committed probe is staged on the T480,
the fixed adapter executes it successfully, and the resulting multi-timeframe
dataset is imported and verified on the declared PostgreSQL surface.
